from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from reqtable.cli import main
from reqtable.core import DEFAULT_CONFIG, CsvTable, build_report_data

CSV_TEXT = (
    "ID,Type,Name,Part of,Allocated to,Verified by,Requirement,Verification Method,Priority\n"
    "SYS-A,System,Product,,,,,,\n"
    "SYS-B,System,Other,,,,,,\n"
    + "".join(f"R{n},,,,SYS-A,,Text {n},,Must\n" for n in range(1, 13))
    + "R13,,,,SYS-B,,Text,Test,Must\n"
)
BASE = ("--id-column", "ID", "--traceability")


def run_cli(*argv: str, findings=()):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch("reqtable.cli.table_findings", return_value=list(findings)), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CheckGateCliTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "req.csv")
        Path(self.path).write_text(CSV_TEXT, encoding="utf-8")

    def test_not_ready_lists_failures_and_truncates(self) -> None:
        code, out, _ = run_cli(self.path, *BASE, "--check-gate", "SRR")
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(lines[0], "SRR System Requirements Review: not ready")
        self.assertEqual(lines[1], "  pass srr-text  Every requirement has its requirement text")
        self.assertEqual(
            lines[2],
            "  FAIL srr-method  Every requirement has a verification method: 12 of 13 records: "
            "R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, …",
        )
        self.assertEqual(lines[-1], "  pass srr-no-findings  There are no trace findings")

    def test_ready_exit_zero_and_findings_fail(self) -> None:
        code, out, _ = run_cli(self.path, *BASE, "--check-gate", "SFR")
        self.assertEqual((code, out.splitlines()[0]), (0, "SFR System Functional Review: ready"))
        code, out, _ = run_cli(self.path, *BASE, "--check-gate", "SFR", findings=[("R2", "Allocated to", "m"), (None, "", "g")])
        self.assertEqual(code, 1)
        self.assertIn("  FAIL sfr-no-findings  There are no trace findings: 2 of 16 records: R2, (table)", out)

    def test_system_scoped_gate(self) -> None:
        code, out, _ = run_cli(self.path, *BASE, "--check-gate", "DDR", "--system", "SYS-B")
        self.assertEqual(out.splitlines()[0], "DDR Detailed Design Review for SYS-B: not ready")
        self.assertIn("FAIL ddr-verified", out)
        self.assertIn("1 of 1 records: R13", out)

    def test_config_errors_exit_two(self) -> None:
        for argv in (
            ("--check-gate", "DDR"),
            ("--check-gate", "SRR", "--system", "SYS-A"),
            ("--check-gate", "NOPE"),
            ("--check-gate", "SRR", "--create-baseline", "SRR"),
            ("--check-gate", "SRR", "--list-baselines"),
            ("--check-gate", "SRR", "--baselines", "SRR"),
            ("--check-gate", "SRR", "--old", self.path),
            ("--check-gate", "SRR", "--extract-comments", "r.html"),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(self.path, *BASE, *argv)[0], 2)

    def test_input_errors_exit_three(self) -> None:
        self.assertEqual(run_cli(self.path, *BASE, "--check-gate", "DDR", "--system", "R1")[0], 3)

    def test_real_findings_fail_the_no_findings_check(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([self.path, *BASE, "--check-gate", "SFR"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL sfr-no-findings", out.getvalue())
        self.assertIn("(table)", out.getvalue())


class EmbeddedGatesTests(unittest.TestCase):
    def table(self) -> CsvTable:
        return CsvTable("t", "t.csv", ["ID"], [{"ID": "R1"}], ["R1"], {"R1": {"ID": "R1"}})

    def test_gates_are_embedded_with_checks(self) -> None:
        data = build_report_data(self.table(), {**DEFAULT_CONFIG, "id_column": "ID"}, "r.html")
        self.assertEqual([gate["id"] for gate in data["gates"]][:2], ["SRR", "SFR"])
        self.assertEqual(data["gates"][0]["checks"][0]["id"], "srr-text")
        self.assertEqual(set(data["gates"][0]), {"id", "name", "produces", "scope", "includes", "captures_status", "checks"})

    def test_no_gates_gives_empty_list(self) -> None:
        data = build_report_data(self.table(), {**DEFAULT_CONFIG, "id_column": "ID", "gates": []}, "r.html")
        self.assertEqual(data["gates"], [])


if __name__ == "__main__":
    unittest.main()
