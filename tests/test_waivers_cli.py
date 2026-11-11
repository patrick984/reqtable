from __future__ import annotations

import json
import re
import shutil
import unittest

from reqtable.baselines import current_user
from signoff_support import git
from test_baselines_cli import CSV_TEXT, CliTestCase, report_data

GATES = [{"id": "SRR", "name": "System Requirements Review", "signoff": [{"role": "Reviewer", "min": 1}], "checks": [
    {"id": "has-name", "description": "Every requirement has a name", "filled": "Name", "enforcement": "strict"},
    {"id": "has-verifier", "description": "Every requirement has a verifier", "filled": "Verified by"},
    {"id": "has-compliance", "description": "Every requirement has compliance", "filled": "Compliance", "enforcement": "strict"},
]}]
UNNAMED = CSV_TEXT.replace("R2,,Two", "R2,,")
DATE = r"\d{4}-\d\d-\d\dT[\d:]+[+-]\d\d:\d\d"
BLOCKED = [
    "blocked: has-name fails (1 of 2): Every requirement has a name",
]


class WaiverFlow:
    def setUp(self) -> None:
        super().setUp()
        self.config = self.write_config({"gates": GATES})
        self.csv.write_text(UNNAMED, encoding="utf-8")
        self.commit()

    def commit(self) -> None:
        pass

    def baseline_names(self) -> list[str]:
        return [line.split("\t")[0] for line in self.run_main(str(self.csv), "--list-baselines")[1].splitlines()]

    def create(self, *extra: str) -> tuple[int, str, str]:
        return self.run_main(str(self.csv), "--create-baseline", "SRR", *extra)

    def test_a_failing_strict_check_blocks_creation(self) -> None:
        code, out, err = self.create()
        self.assertEqual((code, out), (1, ""))
        lines = err.splitlines()
        self.assertEqual(lines[0], "warning: has-verifier fails (2 of 2): Every requirement has a verifier")
        self.assertEqual(lines[1:-1], BLOCKED)
        self.assertEqual(lines[-1], 'Fix the data, or record a waiver: --waive has-name --reason "..."')
        self.assertEqual(self.baseline_names(), ["No baselines."])

    def test_advisory_failures_warn_and_still_create(self) -> None:
        self.csv.write_text(CSV_TEXT, encoding="utf-8")
        self.commit()
        code, out, err = self.create()
        self.assertEqual(code, 0)
        self.assertEqual(err, "warning: has-verifier fails (2 of 2): Every requirement has a verifier\n")
        self.assertTrue(out.startswith("Created baseline SRR "))
        self.assertEqual(self.manifest_waivers(), [])

    def test_waiver_validation_errors_exit_two_and_create_nothing(self) -> None:
        for args, message in (
            (("--waive", "has-name"), "--reason"),
            (("--waive", "has-name", "--reason", "  "), "--reason"),
            (("--waive", "nope", "--reason", "x"), "no such check"),
            (("--waive", "has-verifier", "--reason", "x"), "advisory"),
            (("--waive", "has-compliance", "--reason", "x"), "not failing"),
            (("--waive", "has-name,has-compliance", "--reason", "x"), "not failing"),
            (("--reason", "x"), "--waive"),
        ):
            with self.subTest(args):
                code, _, err = self.create(*args)
                self.assertEqual(code, 2)
                self.assertIn(message, err)
        self.assertEqual(self.baseline_names(), ["No baselines."])

    def test_waive_applies_only_to_create_baseline(self) -> None:
        for args in (("--check-gate", "SRR", "--waive", "has-name", "--reason", "x"), ("--list-baselines", "--user", "ann")):
            with self.subTest(args):
                self.assertEqual(self.run_main(str(self.csv), *args)[0], 2)

    def test_waived_creation_records_and_prints_the_waiver(self) -> None:
        code, out, err = self.create("--waive", "has-name", "--reason", "Names arrive with the vendor data", "--user", "ann")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Waived has-name (1 record): Names arrive with the vendor data")
        self.assertTrue(lines[1].startswith("Created baseline SRR "))
        (waiver,) = self.manifest_waivers()
        self.assertEqual(
            {key: waiver[key] for key in ("check", "reason", "user", "failing")},
            {"check": "has-name", "reason": "Names arrive with the vendor data", "user": "ann", "failing": ["R2"]},
        )
        self.assertRegex(waiver["date"], DATE)

    def test_waivers_default_to_the_configured_user_and_accept_lists(self) -> None:
        self.csv.write_text(UNNAMED.replace("Not verified", ""), encoding="utf-8")
        self.commit()
        code, out, err = self.create("--waive", "has-name,has-compliance", "--waive", "has-name", "--reason", "r")
        self.assertEqual(code, 0, err)
        self.assertEqual(
            out.splitlines()[:2], ["Waived has-name (1 record): r", "Waived has-compliance (2 records): r"],
        )
        self.assertEqual({w["user"] for w in self.manifest_waivers()}, {current_user(self.root)})

    def test_reasons_pair_with_waived_checks_in_order(self) -> None:
        self.csv.write_text(UNNAMED.replace("Not verified", ""), encoding="utf-8")
        self.commit()
        code, out, err = self.create("--waive", "has-name", "--reason", "names later", "--waive", "has-compliance", "--reason", "not verified yet")
        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines()[:2], ["Waived has-name (1 record): names later", "Waived has-compliance (2 records): not verified yet"])
        code, _, err = self.create("--waive", "has-name,has-compliance", "--reason", "a", "--reason", "b", "--reason", "c")
        self.assertEqual(code, 2)
        self.assertIn("one per check", err)

    def test_verify_lists_waivers_and_they_do_not_change_approval(self) -> None:
        self.create("--waive", "has-name", "--reason", "vendor data", "--user", "ann")
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        lines = out.splitlines()
        self.assertEqual(code, 1)
        self.assertRegex(lines[0], r"^SRR sha256:[0-9a-f]{64} content hash matches$")
        self.assertRegex(lines[1], rf"^waived has-name by ann on {DATE}: vendor data \(1 record\)$")
        self.assertEqual(lines[-1], "not approved")

    def test_embedded_baselines_and_packages_carry_waivers(self) -> None:
        self.create("--waive", "has-name", "--reason", "vendor data", "--user", "ann")
        code, data, err = self.embed("SRR")
        self.assertEqual((code, err), (0, ""))
        (waiver,) = data["baselines"][0]["waivers"]
        self.assertEqual((waiver["check"], waiver["reason"], waiver["user"], waiver["failing"]), ("has-name", "vendor data", "ann", ["R2"]))
        code, _, err = self.run_main(str(self.csv), "--gate-package", "SRR", "-o", str(self.output))
        self.assertEqual((code, err), (0, ""))
        (packaged,) = report_data(self.output)["package"]["waivers"]
        self.assertEqual((packaged["check"], packaged["description"]), ("has-name", "Every requirement has a name"))
        self.assertEqual((packaged["reason"], packaged["user"], packaged["failing"]), ("vendor data", "ann", ["R2"]))

    def test_package_description_is_missing_when_the_gate_dropped_the_check(self) -> None:
        self.create("--waive", "has-name", "--reason", "vendor data")
        self.config = self.write_config({"gates": [{**GATES[0], "checks": []}]})
        self.run_main(str(self.csv), "--gate-package", "SRR", "-o", str(self.output))
        self.assertIsNone(report_data(self.output)["package"]["waivers"][0]["description"])


class FileStoreWaiverTests(WaiverFlow, CliTestCase):
    def manifest_waivers(self) -> list[dict]:
        path = self.root / "baselines" / "SRR" / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8"))["waivers"]

    def test_manifest_without_waivers_reads_as_empty(self) -> None:
        self.create("--waive", "has-name", "--reason", "x")
        path = self.root / "baselines" / "SRR" / "manifest.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        del stored["waivers"]
        path.write_text(json.dumps(stored), encoding="utf-8")
        code, data, err = self.embed("SRR")
        self.assertEqual((code, err, data["baselines"][0]["waivers"]), (0, "", []))

    def test_a_waived_baseline_can_still_be_approved(self) -> None:
        self.create("--waive", "has-name", "--reason", "x")
        self.run_main(str(self.csv), "--sign-off", "SRR", "--role", "Reviewer", "--decision", "Reviewed")
        self.assertEqual(len(self.manifest_waivers()), 1)
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SRR")
        self.assertEqual((code, out.splitlines()[-1]), (0, "approved"))

    def test_a_malformed_waiver_makes_the_baseline_unreadable(self) -> None:
        self.create("--waive", "has-name", "--reason", "x")
        path = self.root / "baselines" / "SRR" / "manifest.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored["waivers"][0]["reason"] = " "
        path.write_text(json.dumps(stored), encoding="utf-8")
        code, out, err = self.run_main(str(self.csv), "--list-baselines")
        self.assertEqual(out, "No baselines.\n")
        self.assertIn("waiver reason is empty", err)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class GitStoreWaiverTests(WaiverFlow, CliTestCase):
    store = "git"

    def commit(self) -> None:
        if not (self.root / ".git").exists():
            git(self.root, "init", "-q")
            git(self.root, "config", "user.name", "Tester")
            git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "add", "requirements.csv")
        git(self.root, "commit", "-q", "-m", "edit", "--allow-empty")

    def manifest_waivers(self) -> list[dict]:
        tags = git(self.root, "tag", "-l").split()
        if not tags:
            return []
        message = git(self.root, "for-each-ref", "--format=%(contents)", f"refs/tags/{tags[0]}")
        return json.JSONDecoder().raw_decode(message.partition("\n\n")[2].lstrip())[0]["waivers"]

    def test_the_tag_message_holds_the_waivers(self) -> None:
        self.create("--waive", "has-name", "--reason", "x", "--user", "ann")
        message = git(self.root, "for-each-ref", "--format=%(contents)", "refs/tags/baseline/SRR")
        self.assertRegex(message, r'"waivers": \[\s*\{\s*"check": "has-name"')
        self.assertTrue(re.search(r'"user": "ann"', message))


if __name__ == "__main__":
    unittest.main()
