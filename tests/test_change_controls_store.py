from __future__ import annotations

import copy
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from reqtable.baselines import build_controls, create_baseline, open_store
from reqtable.core import DEFAULT_CONFIG, ConfigError, read_csv_table, validate_config
from test_baselines_cli import CliTestCase, report_data

HEADERS = "ID,Type,Name,Part of,Allocated to,Requirement,Priority,Verification Level,Compliance,Affects,Change status\n"
SYSTEMS = "SYS-A,System,Product,,,,,,,,\nSYS-B,System,Sub B,SYS-A,,,,,,,\n"


def table(r1: str, r2: str) -> str:
    return HEADERS + SYSTEMS + f"R1,,,,SYS-B,{r1},Must,Unit,Not verified,,\nR2,,,,SYS-A,{r2},Must,Unit,Not verified,,\n"


class ControlsFlow:
    store_kind = "files"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.input = self.root / "requirements.csv"
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.config.update(id_column="ID", traceability=True)
        self.config["baselines"]["store"] = self.store_kind
        self.warnings: list[str] = []
        self.store = open_store(self.input, self.config, lambda p: read_csv_table(str(p), self.config), self.warnings.append)
        self.input.write_text(table("One", "Two"), encoding="utf-8")
        self.prepare()

    def prepare(self) -> None:
        pass

    def save(self, text: str) -> None:
        self.input.write_text(text, encoding="utf-8")

    def freeze(self, gate: str, system: str | None, epoch: int) -> None:
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": str(epoch)}):
            create_baseline(self.store, self.config, gate, system)

    def controlling(self) -> dict[str, tuple[str, str]]:
        controls = build_controls(self.store, self.config)
        return {rid: (entry["baseline"], entry["row"]["Requirement"]) for rid, entry in controls["records"].items()}

    def test_newest_containing_baseline_controls_each_record(self) -> None:
        self.assertIsNone(build_controls(self.store, self.config))
        self.freeze("PDR", None, 1_000_000)
        self.save(table("One reworded", "Two reworded"))
        self.freeze("DDR", "SYS-B", 2_000_000)
        self.assertEqual(self.controlling(), {
            "SYS-A": ("PDR", ""), "SYS-B": ("DDR/SYS-B", ""), "R1": ("DDR/SYS-B", "One reworded"), "R2": ("PDR", "Two"),
        })
        controls = build_controls(self.store, self.config)
        self.assertEqual([b["name"] for b in controls["baselines"]], ["PDR", "DDR/SYS-B"])
        self.assertEqual(controls["baselines"][1], {
            "name": "DDR/SYS-B", "created": controls["baselines"][1]["created"], "system": "SYS-B",
            "includes": ["Requirement", "System"], "capturesStatus": False, "statusColumns": ["Compliance", "Result"],
        })
        self.save(table("One third", "Two third"))
        self.freeze("PDR", None, 3_000_000)
        self.assertEqual(self.controlling(), {
            "SYS-A": ("PDR-2", ""), "SYS-B": ("PDR-2", ""), "R1": ("PDR-2", "One third"), "R2": ("PDR-2", "Two third"),
        })
        self.assertEqual(self.warnings, [])

    def test_equal_creation_times_go_to_the_later_gate_listed_first(self) -> None:
        self.freeze("PDR", None, 1_000_000)
        self.save(table("One reworded", "Two"))
        self.freeze("DDR", "SYS-B", 1_000_000)
        self.assertEqual(self.controlling()["R1"], ("DDR/SYS-B", "One reworded"))
        names = [b["name"] for b in build_controls(self.store, self.config)["baselines"]]
        self.assertEqual(names, ["DDR/SYS-B", "PDR"])

    def test_switched_off(self) -> None:
        self.freeze("PDR", None, 1_000_000)
        self.config["baselines"]["change_control"] = False
        self.assertIsNone(build_controls(self.store, self.config))


class SwitchTests(unittest.TestCase):
    def test_change_control_must_be_a_boolean(self) -> None:
        config = copy.deepcopy(DEFAULT_CONFIG)
        self.assertIs(config["baselines"]["change_control"], True)
        config["baselines"]["change_control"] = "yes"
        with self.assertRaisesRegex(ConfigError, "baselines.change_control must be true or false"):
            validate_config(config)


class FileStoreControlsTests(ControlsFlow, unittest.TestCase):
    pass


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class GitStoreControlsTests(ControlsFlow, unittest.TestCase):
    store_kind = "git"

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def prepare(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.name", "Tester")
        self.git("config", "user.email", "t@example.com")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "first")

    def save(self, text: str) -> None:
        super().save(text)
        self.git("commit", "-q", "-am", "edit")

    def test_outside_a_repository_there_are_no_controls(self) -> None:
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        path = Path(elsewhere.name) / "requirements.csv"
        path.write_text(table("One", "Two"), encoding="utf-8")
        store = open_store(path, self.config, lambda p: read_csv_table(str(p), self.config), self.warnings.append)
        self.assertIsNone(build_controls(store, self.config))
        self.assertEqual(self.warnings, [])


class ReportEmbeddingTests(CliTestCase):
    def test_reports_embed_the_controls(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SRR")[0], 0)
        self.csv.write_text(self.csv.read_text(encoding="utf-8").replace("One", "Uno"), encoding="utf-8")
        for mode in ("review", "develop"):
            with self.subTest(mode=mode):
                code, _, err = self.run_main(str(self.csv), "--document-mode", mode, "-o", str(self.output))
                self.assertEqual((code, err), (0, ""))
                controls = report_data(self.output)["controls"]
                self.assertEqual([b["name"] for b in controls["baselines"]], ["SRR"])
                self.assertEqual(controls["records"]["R1"]["row"]["Name"], "One")

    def test_report_without_baselines_has_null_controls(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "-o", str(self.output))[0], 0)
        self.assertIsNone(report_data(self.output)["controls"])

    def test_report_outside_git_still_generates(self) -> None:
        self.store = "git"
        self.config = self.write_config({})
        code, _, err = self.run_main(str(self.csv), "-o", str(self.output))
        self.assertEqual((code, err), (0, ""))
        self.assertIsNone(report_data(self.output)["controls"])

    def test_check_gate_counts_unapproved_changes_as_findings(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "SRR")[0], 0)
        self.csv.write_text(self.csv.read_text(encoding="utf-8").replace("One", "Uno"), encoding="utf-8")
        code, out, _ = self.run_main(str(self.csv), "--check-gate", "SFR")
        self.assertIn("  FAIL (advisory) sfr-no-findings  There are no trace findings: 2 of 5 records: R1, (table)", out)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class CheckGateChangeControlTests(CliTestCase):
    store = "git"

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def test_edit_after_a_baseline_needs_an_approved_change_request(self) -> None:
        self.csv.write_text(table("One", "Two").replace(",SYS-A,Two", ",SYS-B,Two"), encoding="utf-8")
        for args in (("init", "-q"), ("config", "user.name", "T"), ("config", "user.email", "t@example.com"),
                     ("add", "requirements.csv"), ("commit", "-q", "-m", "first")):
            self.git(*args)
        self.assertEqual(self.run_main(str(self.csv), "--create-baseline", "PDR")[0], 0)
        self.assertEqual(self.run_main(str(self.csv), "--check-gate", "PDR")[0], 0)
        edited = self.csv.read_text(encoding="utf-8").replace("One", "Uno")
        self.csv.write_text(edited, encoding="utf-8")
        code, out, _ = self.run_main(str(self.csv), "--check-gate", "PDR")
        self.assertEqual(code, 1)
        self.assertIn(
            "  FAIL (advisory) pdr-change-control  Every change since the last baseline has an approved change request: "
            "1 of 4 records: R1", out,
        )
        self.csv.write_text(edited + "CR1,Change request,Reword R1,,,,,,,R1,Approved\n", encoding="utf-8")
        code, out, _ = self.run_main(str(self.csv), "--check-gate", "PDR")
        self.assertEqual(code, 0, out)
        self.assertIn("  pass pdr-change-control", out)
