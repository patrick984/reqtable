from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from signoff_support import TOOLS_PRESENT, git, init_signing_repo
from test_baselines_cli import CSV_TEXT, CliTestCase, report_data

PACKAGE_KEYS = {"gate", "baseline", "previous", "roles", "signoffs", "approval", "waivers", "decisionOptions"}
BASELINE_KEYS = {"name", "gate", "system", "created", "createdBy", "hash", "hashOk", "source"}
EDITED = CSV_TEXT.replace("One", "Uno")


def save_copy(path: Path, mutate) -> None:
    data = report_data(path)
    mutate(data)
    text = path.read_text(encoding="utf-8")
    block = re.compile(r'(<script[^>]*id="reqtable-data"[^>]*>).*?(</script>)', re.S)
    replacement = json.dumps(data).replace("<", "\\u003c")
    path.write_text(block.sub(lambda m: m.group(1) + replacement + m.group(2), text, count=1), encoding="utf-8")


def decision(role: str, user: str, kind: str, date: str, note: str = "") -> dict:
    return {"role": role, "user": user, "decision": kind, "date": date, "note": note}


class PackageFlow:
    def commit_edit(self) -> None:
        pass

    def make_baselines(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SRR")[0], 0)
        self.csv.write_text(EDITED, encoding="utf-8")
        self.commit_edit()
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SFR")[0], 0)
        self.csv.write_text(EDITED.replace("Two", "Dos"), encoding="utf-8")
        self.commit_edit()

    def package(self, name: str = "SFR") -> dict:
        code, out, err = self.run_main(str(self.csv), "--gate-package", name, "-o", str(self.output))
        self.assertEqual((code, err), (0, ""), out)
        return report_data(self.output)

    def test_package_follows_the_contract(self) -> None:
        self.make_baselines()
        data = self.package()
        package = data["package"]
        self.assertEqual(set(package), PACKAGE_KEYS)
        self.assertEqual(set(package["baseline"]), BASELINE_KEYS)
        self.assertEqual(package["gate"], {"id": "SFR", "name": "System Functional Review", "produces": "Functional baseline", "scope": "table"})
        self.assertEqual((package["baseline"]["name"], package["baseline"]["hashOk"], package["previous"]), ("SFR", True, "SRR"))
        self.assertEqual(package["roles"], [{"role": "Reviewer", "min": 2}, {"role": "Approver", "min": 1}])
        self.assertEqual(package["signoffs"], [])
        self.assertEqual(package["approval"]["approved"], False)
        self.assertEqual(package["decisionOptions"], ["Reviewed", "Changes requested", "Approved", "Rejected"])
        self.assertEqual(data["decisions"], [])
        self.assertIsNone(data["controls"])
        self.assertEqual([g["id"] for g in data["gates"]], ["SFR"])
        self.assertEqual(data["options"]["initialCompareWith"], "baseline:SRR")
        self.assertEqual([b["name"] for b in data["baselines"]], ["SRR"])
        self.assertEqual(data["meta"]["title"], "System Functional Review gate package: SFR")
        self.assertEqual(data["meta"]["documentMode"], "review")
        names = {row["ID"]: row["Name"] for row in data["source"]["new"]["rows"]}
        self.assertEqual(names, {"SYS-A": "Product", "SYS-B": "Other", "R1": "Uno", "R2": "Two"})
        self.assertEqual(data["baselines"][0]["rows"][2]["Name"], "One")

    def test_first_gate_has_no_previous_baseline(self) -> None:
        self.make_baselines()
        data = self.package("SRR")
        self.assertIsNone(data["package"]["previous"])
        self.assertNotIn("initialCompareWith", data["options"])
        self.assertEqual(data["baselines"], [])

    def test_system_scoped_package_holds_only_the_scoped_rows(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "DDR", "--system", "SYS-A")[0], 0)
        data = self.package("DDR/SYS-A")
        self.assertEqual([row["ID"] for row in data["source"]["new"]["rows"]], ["SYS-A", "R1"])
        self.assertEqual(data["package"]["baseline"]["system"], "SYS-A")
        self.assertEqual(data["package"]["roles"], [{"role": "Reviewer", "min": 1}, {"role": "Approver", "min": 1}])

    def test_package_includes_existing_sign_offs(self) -> None:
        self.make_baselines()
        self.run_main(str(self.csv), "--sign-off", "SFR", "--role", "Reviewer", "--decision", "Reviewed", "--user", "ann")
        package = self.package()["package"]
        (entry,) = package["signoffs"]
        self.assertEqual((entry["user"], entry["counts"]), ("ann", True))
        self.assertEqual(package["approval"]["roles"][0]["positive"], ["ann"])

    def test_embedded_baselines_carry_sign_offs_and_approval(self) -> None:
        self.make_baselines()
        self.run_main(str(self.csv), "--sign-off", "SRR", "--role", "Approver", "--decision", "Approved", "--user", "cy")
        code, data, _ = self.embed("SRR,SFR")
        srr, sfr = data["baselines"]
        self.assertEqual(code, 0)
        self.assertEqual([(s["user"], s["verification"], s["counts"]) for s in srr["signoffs"]][0][0], "cy")
        self.assertEqual(srr["approval"]["roles"][1], {"role": "Approver", "min": 1, "positive": ["cy"], "negative": []})
        self.assertFalse(srr["approval"]["approved"])
        self.assertEqual(sfr["signoffs"], [])

    def test_import_records_decisions_once(self) -> None:
        self.make_baselines()
        self.package()
        stamp = "2026-03-01T09:00:00+00:00"
        save_copy(self.output, lambda d: d["decisions"].extend([
            decision("Reviewer", "ann", "Reviewed", stamp, "looks <good>"),
            decision("reviewer", "bob", "Reviewed", "2026-03-01T10:00:00Z"),
            decision("Approver", "cy", "Approved", "2026-03-02T10:00:00+11:00"),
        ]))
        code, out, err = self.run_main(str(self.csv), "--import-decisions", str(self.output))
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("imported Reviewed by ann as Reviewer on 2026-03-01T09:00:00+00:00 "), lines[0])
        code, out, _ = self.run_main(str(self.csv), "--verify-baseline", "SFR")
        self.assertEqual((code, out.splitlines()[-1]), (0, "approved"))
        recorded = self.package()["package"]["signoffs"]
        self.assertEqual({(s["user"], s["via"], s["evidence"]) for s in recorded}, {(u, "package", self.output.name) for u in ("ann", "bob", "cy")})
        self.assertEqual(recorded[0]["note"], "looks <good>")
        self.assertEqual(recorded[0]["recorded_by"], recorded[1]["recorded_by"])
        self.assertTrue(recorded[0]["recorded_by"])

    def test_reimport_skips_what_is_recorded_and_adds_the_rest(self) -> None:
        self.make_baselines()
        self.package()
        first = decision("Reviewer", "ann", "Reviewed", "2026-03-01T09:00:00+00:00")
        save_copy(self.output, lambda d: d["decisions"].append(first))
        self.run_main(str(self.csv), "--import-decisions", str(self.output))
        save_copy(self.output, lambda d: d["decisions"].append(decision("Reviewer", "ann", "Reviewed", "2026-03-01T21:00:00+11:00")))
        _, out, _ = self.run_main(str(self.csv), "--import-decisions", str(self.output))
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("skipped Reviewed by ann as Reviewer on 2026-03-01T09:00:00+00:00: already recorded"), lines[0])
        self.assertTrue(lines[1].startswith("imported "), lines[1])
        _, out, _ = self.run_main(str(self.csv), "--import-decisions", str(self.output))
        self.assertEqual([line.split()[0] for line in out.splitlines()], ["skipped", "skipped"])

    def test_import_rejects_unusable_packages(self) -> None:
        self.make_baselines()
        self.package()
        cases = {
            "unknown role": lambda d: d["decisions"].append(decision("Janitor", "ann", "Reviewed", "2026-03-01T09:00:00+00:00")),
            "unknown decision": lambda d: d["decisions"].append(decision("Reviewer", "ann", "Shrug", "2026-03-01T09:00:00+00:00")),
            "bad date": lambda d: d["decisions"].append(decision("Reviewer", "ann", "Reviewed", "soon")),
            "different content": lambda d: d["package"]["baseline"].update(hash="sha256:other"),
            "unknown baseline": lambda d: d["package"]["baseline"].update(name="CDR"),
            "not a package": lambda d: d.pop("package"),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                self.package()
                save_copy(self.output, mutate)
                code, _, err = self.run_main(str(self.csv), "--import-decisions", str(self.output))
                self.assertEqual(code, 3, err)
        self.assertEqual(self.package()["package"]["signoffs"], [])

    def test_one_bad_decision_imports_nothing(self) -> None:
        self.make_baselines()
        self.package()
        save_copy(self.output, lambda d: d["decisions"].extend([
            decision("Reviewer", "ann", "Reviewed", "2026-03-01T09:00:00+00:00"),
            decision("Janitor", "bob", "Reviewed", "2026-03-01T09:00:00+00:00"),
        ]))
        self.assertEqual(self.run_main(str(self.csv), "--import-decisions", str(self.output))[0], 3)
        self.assertEqual(self.package()["package"]["signoffs"], [])

    def test_flags_are_exclusive(self) -> None:
        for args in (
            ("--gate-package", "SRR", "--sign-off", "SRR"),
            ("--import-decisions", "x.html", "--gate-package", "SRR"),
            ("--gate-package", "SRR", "--create-baseline", "SRR"),
            ("--gate-package", "SRR", "--check-gate", "SRR"),
            ("--import-decisions", "x.html", "--list-baselines"),
            ("--import-decisions", "x.html", "--baselines", "SRR"),
        ):
            with self.subTest(args):
                self.assertEqual(self.run_main(str(self.csv), *args, "-o", str(self.output))[0], 2)
        self.assertEqual(self.run_main(str(self.csv), "--gate-package", "SRR")[0], 2)
        self.assertEqual(self.run_main("--gate-package", "SRR", "-o", str(self.output))[0], 2)


class FilePackageTests(PackageFlow, CliTestCase):
    pass


@unittest.skipUnless(TOOLS_PRESENT, "git or ssh-keygen is not on PATH")
class GitPackageTests(PackageFlow, CliTestCase):
    store = "git"

    def setUp(self) -> None:
        super().setUp()
        keys = tempfile.TemporaryDirectory()
        self.addCleanup(keys.cleanup)
        init_signing_repo(self.root, Path(keys.name))
        git(self.root, "add", "requirements.csv")
        git(self.root, "commit", "-q", "-m", "first")

    def commit_edit(self) -> None:
        git(self.root, "commit", "-q", "-am", "edit")

    def test_import_creates_signed_tags_for_the_reviewers(self) -> None:
        self.make_baselines()
        self.package()
        save_copy(self.output, lambda d: d["decisions"].append(decision("Reviewer", "Ann Lee", "Reviewed", "2026-03-01T09:00:00+00:00")))
        _, out, _ = self.run_main(str(self.csv), "--import-decisions", str(self.output))
        self.assertTrue(out.strip().endswith("as tag signoff/SFR/reviewer/ann-lee"), out)
        (entry,) = self.package()["package"]["signoffs"]
        self.assertEqual((entry["verification"], entry["counts"], entry["user"]), ("good", True, "Ann Lee"))
        self.assertEqual(entry["recorded_by"], "Tester")


if __name__ == "__main__":
    unittest.main()
