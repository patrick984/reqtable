from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reqtable.baselines import current_user
from signoff_support import TOOLS_PRESENT, git, init_signing_repo
from test_baselines_cli import CliTestCase

SIGN = ("--sign-off", "SRR")


def sign(who: str, role: str, decision: str, *extra: str) -> tuple[str, ...]:
    return (
        "--sign-off",
        "SRR",
        "--role",
        role,
        "--decision",
        decision,
        "--user",
        who,
        *extra,
    )


class SignoffFlow:
    def approve_fully(self) -> None:
        for who, role, decision in (
            ("ann", "Reviewer", "Reviewed"),
            ("bob", "Reviewer", "Reviewed"),
            ("cy", "Approver", "Approved"),
        ):
            self.assertEqual(
                self.run_main(str(self.csv), *sign(who, role, decision))[0], 0
            )

    def test_verify_before_and_after_approval(self) -> None:
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual(code, 1)
        self.assertIn("  no sign-offs", out)
        self.assertIn("Reviewer: 0 of 2 needed, incomplete", out)
        self.assertEqual(out.splitlines()[-1], "not approved")
        self.run_main(str(self.csv), *sign("ann", "Reviewer", "Reviewed"))
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual(code, 1)
        self.assertIn("Reviewer: 1 of 2 needed, incomplete (ann)", out)
        self.approve_fully()
        code, out, err = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertRegex(lines[0], r"^SRR sha256:[0-9a-f]{64} content hash matches$")
        self.assertIn("Reviewer: 2 of 2 needed, complete (ann, bob)", out)
        self.assertIn("Approver: 1 of 1 needed, complete (cy)", out)
        self.assertEqual(lines[-1], "approved")

    def test_later_negative_decision_withdraws_approval(self) -> None:
        self.approve_fully()
        self.run_main(
            str(self.csv), *sign("cy", "Approver", "Rejected", "--note", "scope gap")
        )
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual(code, 1)
        self.assertIn("Approver: 0 of 1 needed, incomplete; against: cy", out)

    def test_tampered_content_fails_verification_and_refuses_new_sign_offs(
        self,
    ) -> None:
        self.approve_fully()
        self.tamper()
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual(code, 1)
        self.assertIn("content hash DOES NOT MATCH", out)
        self.assertEqual(out.splitlines()[-1], "not approved")
        code, _, err = self.run_main(
            str(self.csv), *sign("dee", "Reviewer", "Reviewed")
        )
        self.assertEqual(code, 3)
        self.assertIn("does not match its recorded hash", err)

    def test_usage_errors(self) -> None:
        for args, code in (
            ((*SIGN,), 2),
            ((*SIGN, "--role", "Reviewer"), 2),
            ((*SIGN, "--role", "Nobody", "--decision", "Reviewed"), 2),
            ((*SIGN, "--role", "Reviewer", "--decision", "Maybe"), 2),
            (("--sign-off", "PDR", "--role", "Reviewer", "--decision", "Reviewed"), 3),
            (("--verify-baseline", "PDR"), 3),
            (("--role", "Reviewer"), 2),
            (
                (
                    *SIGN,
                    "--role",
                    "Reviewer",
                    "--decision",
                    "Reviewed",
                    "--verify-baseline",
                    "SRR",
                ),
                2,
            ),
            (("--verify-baseline", "SRR", "--check-gate", "SRR"), 2),
            (("--verify-baseline", "SRR", "--list-baselines"), 2),
            (("--verify-baseline", "SRR", "--create-baseline", "SRR"), 2),
            (("--verify-baseline", "SRR", "--baselines", "SRR"), 2),
            (("--verify-baseline", "SRR", "--extract-comments", "x.html"), 2),
        ):
            with self.subTest(args):
                self.assertEqual(self.run_main(str(self.csv), *args)[0], code)
        self.assertEqual(self.run_main("--verify-baseline", "SRR")[0], 2)
        self.assertEqual(
            self.run_main(
                str(self.csv), "--old", str(self.csv), "--verify-baseline", "SRR"
            )[0],
            2,
        )

    def test_default_user_and_case_insensitive_role_and_decision(self) -> None:
        code, out, _ = self.run_main(
            str(self.csv),
            *SIGN,
            "--role",
            "reviewer",
            "--decision",
            "changes requested",
        )
        self.assertEqual(code, 0)
        self.assertTrue(
            out.startswith(
                f"Recorded Changes requested by {current_user(self.root)} as Reviewer for SRR "
            ),
            out,
        )


class FileStoreSignoffCliTests(SignoffFlow, CliTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SRR")[0], 0)
        self.manifest = self.root / "baselines" / "SRR" / "manifest.json"

    def tamper(self) -> None:
        frozen = self.root / "baselines" / "SRR" / "requirements.csv"
        frozen.write_bytes(frozen.read_bytes().replace(b"One", b"Won"))

    def test_sign_off_message_and_manifest_entry(self) -> None:
        (self.root / "baselines" / "SRR" / "minutes.pdf").write_bytes(b"x")
        code, out, _ = self.run_main(
            str(self.csv),
            *sign(
                "ann",
                "Reviewer",
                "Reviewed",
                "--note",
                "ok",
                "--evidence",
                "minutes.pdf",
            ),
        )
        self.assertEqual(
            out, f"Recorded Reviewed by ann as Reviewer for SRR in {self.manifest}\n"
        )
        (entry,) = json.loads(self.manifest.read_text(encoding="utf-8"))["signoffs"]
        self.assertEqual(
            {
                k: entry[k]
                for k in (
                    "baseline",
                    "role",
                    "user",
                    "decision",
                    "note",
                    "evidence",
                    "via",
                    "format",
                )
            },
            {
                "baseline": "SRR",
                "role": "Reviewer",
                "user": "ann",
                "decision": "Reviewed",
                "note": "ok",
                "evidence": "minutes.pdf",
                "via": "cli",
                "format": "reqtable-signoff/1",
            },
        )
        self.assertRegex(entry["date"], r"^\d{4}-\d\d-\d\dT[\d:]+[+-]\d\d:\d\d$")
        _, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertRegex(
            out,
            r"  Reviewer  ann  Reviewed  \S+  recorded  counts \(evidence minutes.pdf found",
        )


@unittest.skipUnless(TOOLS_PRESENT, "git or ssh-keygen is not on PATH")
class GitStoreSignoffCliTests(SignoffFlow, CliTestCase):
    store = "git"

    def setUp(self) -> None:
        super().setUp()
        keys = tempfile.TemporaryDirectory()
        self.addCleanup(keys.cleanup)
        self.allowed = init_signing_repo(self.root, Path(keys.name))
        git(self.root, "add", "requirements.csv")
        git(self.root, "commit", "-q", "-m", "first")
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SRR")[0], 0)

    def tamper(self) -> None:
        message = git(
            self.root, "for-each-ref", "--format=%(contents)", "refs/tags/baseline/SRR"
        )
        git(self.root, "tag", "-d", "baseline/SRR")
        self.csv.write_text(
            self.csv.read_text(encoding="utf-8").replace("One", "Won"), encoding="utf-8"
        )
        git(self.root, "commit", "-q", "-am", "edit")
        git(self.root, "tag", "-a", "baseline/SRR", "-m", message, "HEAD")

    def test_sign_off_creates_signed_tags_and_never_pushes(self) -> None:
        code, out, _ = self.run_main(
            str(self.csv), *sign("Ann Lee", "Reviewer", "Reviewed")
        )
        self.assertEqual(
            out,
            "Recorded Reviewed by Ann Lee as Reviewer for SRR as tag signoff/SRR/reviewer/ann-lee\n",
        )
        _, out, _ = self.run_main(
            str(self.csv), *sign("Ann Lee", "Reviewer", "Reviewed")
        )
        self.assertTrue(out.endswith("as tag signoff/SRR/reviewer/ann-lee-2\n"))
        self.assertEqual(git(self.root, "remote"), "")
        _, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertRegex(out, r"  Reviewer  Ann Lee  Reviewed  \S+  good  counts\n")

    def test_unverifiable_signatures_do_not_count(self) -> None:
        self.approve_fully()
        self.allowed.write_text("", encoding="utf-8")
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual(code, 1)
        self.assertEqual(out.count("unverifiable  does not count"), 3)
        self.assertEqual(out.splitlines()[-1], "not approved")

    def test_signing_failure_exits_3_with_a_hint(self) -> None:
        git(self.root, "config", "user.signingkey", str(self.root / "missing"))
        code, _, err = self.run_main(
            str(self.csv), *sign("ann", "Reviewer", "Reviewed")
        )
        self.assertEqual(code, 3)
        self.assertIn("Configure a signing key", err)


if __name__ == "__main__":
    unittest.main()
