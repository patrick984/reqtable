from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reqtable.baselines import classify_verification, create_baseline, open_store
from reqtable.core import DEFAULT_CONFIG, CsvSource, InputError, read_csv_source
from reqtable.signoff import CheckedSignOff, SignOff, approval_status, slug

from signoff_support import CSV_TEXT, TOOLS_PRESENT, git, init_signing_repo

ROLES = [{"role": "Reviewer", "min": 2}, {"role": "Approver", "min": 1}]


def record(
    role: str,
    user: str,
    decision: str,
    date: str,
    baseline: str = "SRR",
    digest: str = "sha256:x",
) -> SignOff:
    return SignOff(baseline, role, user, decision, date, digest, recorded_by="Tester")


def counted(*records: SignOff) -> list[CheckedSignOff]:
    return [CheckedSignOff(r, "recorded", "", True) for r in records]


class ApprovalStatusTests(unittest.TestCase):
    def test_min_distinct_positive_users_complete_a_role(self) -> None:
        status = approval_status(
            ROLES,
            counted(
                record("Reviewer", "ann", "Reviewed", "2026-01-01T10:00:00+00:00"),
                record("Reviewer", "ann", "Reviewed", "2026-01-01T11:00:00+00:00"),
                record("Approver", "cy", "Approved", "2026-01-02T10:00:00+00:00"),
            ),
        )
        self.assertFalse(status["approved"])
        self.assertEqual(
            status["roles"][0],
            {"role": "Reviewer", "min": 2, "positive": ["ann"], "negative": []},
        )
        status = approval_status(
            ROLES,
            counted(
                record("Reviewer", "ann", "Reviewed", "2026-01-01T10:00:00+00:00"),
                record("Reviewer", "bob", "Reviewed", "2026-01-01T10:30:00+00:00"),
                record("Approver", "cy", "Approved", "2026-01-02T10:00:00+00:00"),
            ),
        )
        self.assertTrue(status["approved"])

    def test_latest_decision_wins_across_time_zones(self) -> None:
        status = approval_status(
            ROLES[1:],
            counted(
                record("Approver", "cy", "Approved", "2026-01-02T10:00:00+00:00"),
                record("Approver", "cy", "Rejected", "2026-01-02T12:00:00+01:00"),
            ),
        )
        self.assertEqual(status["roles"][0]["negative"], ["cy"])
        self.assertEqual(status["roles"][0]["positive"], [])
        self.assertFalse(status["approved"])
        status = approval_status(
            ROLES[1:],
            counted(
                record("Approver", "cy", "Rejected", "2026-01-02T10:30:00+00:00"),
                record("Approver", "cy", "Approved", "2026-01-02T12:00:00+01:00"),
            ),
        )
        self.assertTrue(status["approved"])

    def test_equal_dates_fall_back_to_record_order(self) -> None:
        status = approval_status(
            ROLES[1:],
            counted(
                record("Approver", "cy", "Approved", "2026-01-02T10:00:00+00:00"),
                record(
                    "Approver", "cy", "Changes requested", "2026-01-02T10:00:00+00:00"
                ),
            ),
        )
        self.assertEqual(status["roles"][0]["negative"], ["cy"])

    def test_sign_offs_that_do_not_count_are_ignored(self) -> None:
        bad = CheckedSignOff(
            record("Approver", "cy", "Approved", "2026-01-02T10:00:00+00:00"),
            "bad",
            "",
            False,
        )
        status = approval_status(ROLES[1:], [bad])
        self.assertEqual(
            (status["approved"], status["roles"][0]["positive"]), (False, [])
        )

    def test_unknown_roles_are_ignored_and_no_roles_is_never_approved(self) -> None:
        extra = counted(
            record("Stakeholder", "dee", "Approved", "2026-01-02T10:00:00+00:00")
        )
        self.assertEqual(approval_status(ROLES[1:], extra)["roles"][0]["positive"], [])
        self.assertEqual(approval_status([], extra), {"approved": False, "roles": []})

    def test_user_names_compare_without_case(self) -> None:
        status = approval_status(
            ROLES[:1],
            counted(
                record("Reviewer", "Ann", "Reviewed", "2026-01-01T10:00:00+00:00"),
                record("Reviewer", "ann", "Reviewed", "2026-01-01T11:00:00+00:00"),
            ),
        )
        self.assertEqual(len(status["roles"][0]["positive"]), 1)


class RecordTests(unittest.TestCase):
    def test_round_trip_and_validation(self) -> None:
        original = record("Reviewer", "ann", "Reviewed", "2026-01-01T10:00:00+00:00")
        self.assertEqual(SignOff.from_dict(original.to_dict()), original)
        self.assertEqual(original.to_dict()["format"], "reqtable-signoff/1")
        for change in (
            {"decision": "Maybe"},
            {"via": "email"},
            {"date": "yesterday"},
            {"evidence": 3},
            {"user": " "},
        ):
            with self.assertRaises(ValueError, msg=change):
                SignOff.from_dict({**original.to_dict(), **change})
        with self.assertRaises(ValueError):
            SignOff.from_dict(
                {k: v for k, v in original.to_dict().items() if k != "note"}
            )

    def test_slug(self) -> None:
        self.assertEqual(slug("  J. Smith / QA  "), "j-smith-qa")

    def test_classification(self) -> None:
        self.assertEqual(classify_verification(0, "Good signature"), "good")
        self.assertEqual(
            classify_verification(1, "error: no signature found"), "unsigned"
        )
        self.assertEqual(classify_verification(1, "gpg: BAD signature from x"), "bad")
        self.assertEqual(
            classify_verification(
                1, "Signature verification failed: incorrect signature"
            ),
            "bad",
        )
        self.assertEqual(
            classify_verification(
                1, "error: gpg.ssh.allowedSignersFile needs to be configured"
            ),
            "unverifiable",
        )
        self.assertEqual(classify_verification(1, ""), "unverifiable")


class StoreCase(unittest.TestCase):
    store = "files"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "work"
        self.root.mkdir()
        self.keys = Path(tmp.name) / "keys"
        self.csv = self.root / "requirements.csv"
        self.csv.write_text(CSV_TEXT, encoding="utf-8")
        baselines = {**DEFAULT_CONFIG["baselines"], "store": self.store}
        self.config = {
            **DEFAULT_CONFIG,
            "id_column": "ID",
            "traceability": True,
            "baselines": baselines,
        }
        self.warnings: list[str] = []
        self.prepare()
        self.store_ = open_store(
            self.csv,
            self.config,
            lambda p: read_csv_source(CsvSource(str(p), None, p), self.config),
            self.warnings.append,
        )
        self.manifest = create_baseline(self.store_, self.config, "SRR", None)

    def prepare(self) -> None:
        pass

    def make(
        self,
        role: str = "Reviewer",
        user: str = "ann",
        decision: str = "Reviewed",
        **extra: str,
    ) -> SignOff:
        fields = dict(
            baseline="SRR",
            role=role,
            user=user,
            decision=decision,
            date="2026-01-01T10:00:00+00:00",
            content_hash=self.manifest.content_hash,
            recorded_by="Tester",
        )
        return SignOff(**{**fields, **extra})


class FileStoreSignoffTests(StoreCase):
    def test_sign_offs_append_to_the_manifest_and_leave_it_otherwise_alone(
        self,
    ) -> None:
        path = self.root / "baselines" / "SRR" / "manifest.json"
        before = json.loads(path.read_text(encoding="utf-8"))
        where = self.store_.add_signoff(self.manifest, self.make())
        self.store_.add_signoff(
            self.manifest, self.make(user="bob", evidence="minutes.pdf")
        )
        self.assertEqual(where, f"in {path}")
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({k: v for k, v in after.items() if k != "signoffs"}, before)
        self.assertEqual([s["user"] for s in after["signoffs"]], ["ann", "bob"])
        self.assertEqual(self.store_.list(), [self.manifest])

    def test_verification_is_recorded_and_reports_evidence_presence(self) -> None:
        (self.root / "baselines" / "SRR" / "minutes.pdf").write_bytes(b"x")
        self.store_.add_signoff(self.manifest, self.make(evidence="minutes.pdf"))
        self.store_.add_signoff(
            self.manifest, self.make(user="bob", evidence="missing.pdf")
        )
        self.store_.add_signoff(
            self.manifest, self.make(user="cy", evidence="https://example.com/x")
        )
        found = self.store_.signoffs(self.manifest)
        self.assertEqual([c.verification for c in found], ["recorded"] * 3)
        self.assertTrue(all(c.counts for c in found))
        self.assertIn("minutes.pdf found", found[0].detail)
        self.assertIn("missing.pdf not found", found[1].detail)
        self.assertEqual(found[2].detail, "")

    def test_invalid_entries_are_skipped_with_a_warning(self) -> None:
        self.store_.add_signoff(self.manifest, self.make())
        path = self.root / "baselines" / "SRR" / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["signoffs"].append({"role": "x"})
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(len(self.store_.signoffs(self.manifest)), 1)
        self.assertIn("ignoring sign-off 2", self.warnings[0])


@unittest.skipUnless(TOOLS_PRESENT, "git or ssh-keygen is not on PATH")
class GitStoreSignoffTests(StoreCase):
    store = "git"

    def prepare(self) -> None:
        self.allowed = init_signing_repo(self.root, self.keys)
        git(self.root, "add", "requirements.csv")
        git(self.root, "commit", "-q", "-m", "first")

    def test_signed_tag_is_good_and_counts(self) -> None:
        where = self.store_.add_signoff(self.manifest, self.make(user="Ann Lee"))
        self.assertEqual(where, "as tag signoff/SRR/reviewer/ann-lee")
        message = git(
            self.root,
            "for-each-ref",
            "--format=%(contents)",
            "refs/tags/signoff/SRR/reviewer/ann-lee",
        )
        self.assertTrue(
            message.startswith("ReqTable sign-off SRR Reviewer Reviewed\n\n{")
        )
        self.assertIn("BEGIN SSH SIGNATURE", message)
        tagged = git(self.root, "rev-parse", "signoff/SRR/reviewer/ann-lee^{commit}")
        self.assertEqual(tagged, git(self.root, "rev-parse", "baseline/SRR^{commit}"))
        (found,) = self.store_.signoffs(self.manifest)
        self.assertEqual((found.verification, found.counts), ("good", True))
        self.assertEqual(found.record.user, "Ann Lee")

    def test_repeat_decisions_are_numbered_and_never_overwrite(self) -> None:
        names = [
            self.store_.add_signoff(
                self.manifest, self.make(date=f"2026-01-0{day}T10:00:00+00:00")
            )
            for day in (1, 2, 3)
        ]
        self.assertEqual(
            names,
            [f"as tag signoff/SRR/reviewer/ann{suffix}" for suffix in ("", "-2", "-3")],
        )
        self.assertEqual(len(self.store_.signoffs(self.manifest)), 3)

    def test_tenth_decision_sorts_after_the_ninth(self) -> None:
        for number in range(1, 11):
            self.store_.add_signoff(
                self.manifest, self.make(decision="Changes requested", note=str(number))
            )
        self.assertEqual(
            [c.record.note for c in self.store_.signoffs(self.manifest)],
            [str(n) for n in range(1, 11)],
        )

    def test_unsigned_tag_does_not_count(self) -> None:
        body = json.dumps(self.make().to_dict(), indent=2)
        git(
            self.root,
            "tag",
            "-a",
            "signoff/SRR/reviewer/ann",
            "-m",
            f"ReqTable sign-off\n\n{body}",
            "baseline/SRR^{commit}",
        )
        (found,) = self.store_.signoffs(self.manifest)
        self.assertEqual((found.verification, found.counts), ("unsigned", False))
        self.assertIn("no signature", found.detail)

    def test_missing_allowed_signers_is_unverifiable(self) -> None:
        self.store_.add_signoff(self.manifest, self.make())
        self.allowed.write_text("", encoding="utf-8")
        (found,) = self.store_.signoffs(self.manifest)
        self.assertEqual((found.verification, found.counts), ("unverifiable", False))
        self.assertTrue(found.detail)

    def test_content_hash_mismatch_does_not_count(self) -> None:
        self.store_.add_signoff(self.manifest, self.make(content_hash="sha256:other"))
        (found,) = self.store_.signoffs(self.manifest)
        self.assertEqual((found.verification, found.counts), ("good", False))
        self.assertIn("content hash differs", found.detail)

    def test_tag_on_another_commit_does_not_count(self) -> None:
        self.csv.write_text(CSV_TEXT + "R3,,Three,,SYS-A,,\n", encoding="utf-8")
        git(self.root, "commit", "-q", "-am", "second")
        body = json.dumps(self.make().to_dict(), indent=2)
        git(
            self.root,
            "tag",
            "-s",
            "signoff/SRR/reviewer/ann",
            "-m",
            f"ReqTable sign-off\n\n{body}",
            "HEAD",
        )
        (found,) = self.store_.signoffs(self.manifest)
        self.assertEqual((found.verification, found.counts), ("good", False))
        self.assertIn("does not point at the baseline commit", found.detail)

    def test_other_baselines_tags_are_not_mixed_in(self) -> None:
        second = create_baseline(self.store_, self.config, "SRR", None)
        self.store_.add_signoff(
            second, self.make(baseline="SRR-2", content_hash=second.content_hash)
        )
        self.assertEqual(self.store_.signoffs(self.manifest), [])
        self.assertEqual(len(self.store_.signoffs(second)), 1)

    def test_signing_failure_names_the_fix_and_creates_nothing(self) -> None:
        git(self.root, "config", "user.signingkey", str(self.keys / "missing"))
        with self.assertRaises(InputError) as caught:
            self.store_.add_signoff(self.manifest, self.make())
        self.assertIn("signing key", str(caught.exception))
        self.assertEqual(git(self.root, "tag", "-l", "signoff/*"), "")

    def test_approval_status_from_real_tags(self) -> None:
        for user, role, decision in (
            ("ann", "Reviewer", "Reviewed"),
            ("bob", "Reviewer", "Reviewed"),
            ("cy", "Approver", "Approved"),
        ):
            self.store_.add_signoff(
                self.manifest, self.make(role=role, user=user, decision=decision)
            )
        self.assertTrue(
            approval_status(ROLES, self.store_.signoffs(self.manifest))["approved"]
        )
        later = self.make(
            role="Reviewer",
            user="bob",
            decision="Changes requested",
            date="2026-01-03T10:00:00+00:00",
        )
        self.store_.add_signoff(self.manifest, later)
        status = approval_status(ROLES, self.store_.signoffs(self.manifest))
        self.assertEqual(
            (status["approved"], status["roles"][0]["negative"]), (False, ["bob"])
        )


if __name__ == "__main__":
    unittest.main()
