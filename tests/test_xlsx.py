from __future__ import annotations

import contextlib
import csv
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from reqtable.cli import main
from reqtable.core import ConfigError, InputError
from reqtable.xlsx import XlsxSelection, block_to_csv, read_selection

FIXTURE = Path(__file__).parent / "fixtures" / "excel-sample.xlsx"
HEADERS = ["ID", "Requirement", "Priority", "Due", "Version", "Length"]


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def report_data(path: Path) -> dict:
    match = re.search(
        r'<script[^>]*id="reqtable-data"[^>]*>(.*?)</script>',
        path.read_text(encoding="utf-8"),
        re.S,
    )
    return json.loads(match.group(1))


class ExcelFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_table_values(self) -> None:
        rows = read_selection(FIXTURE, XlsxSelection(table="Requirements")).rows
        self.assertEqual(rows[0], HEADERS)
        self.assertEqual(len(rows), 5)
        by_id = {row[0]: dict(zip(HEADERS, row)) for row in rows[1:]}
        self.assertEqual(by_id["REQ-1"]["Due"], "2026-12-01")
        self.assertEqual(by_id["REQ-3"]["Due"], "2027-01-15")
        self.assertEqual(by_id["REQ-2"]["Due"], "")
        self.assertEqual(
            [by_id[i]["Version"] for i in ("REQ-1", "REQ-2", "REQ-3", "REQ-4")],
            ["1.1", "1.10", "2", "TRUE"],
        )
        self.assertEqual(
            [by_id[i]["Length"] for i in ("REQ-1", "REQ-2", "REQ-3", "REQ-4")],
            ["41", "41", "45", "0"],
        )
        self.assertEqual(by_id["REQ-2"]["Requirement"].count("\n"), 2)
        self.assertEqual(
            by_id["REQ-3"]["Requirement"],
            "Café names shall keep accents — “quotes” too.",
        )
        self.assertEqual(by_id["REQ-4"]["Requirement"], "")

    def test_sheet_with_default_header_detection(self) -> None:
        rows = read_selection(FIXTURE, XlsxSelection(sheet="Glossary")).rows
        self.assertEqual(rows[0], ["Name", "Definition", "Aliases"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2][0], "Identifier")

    def test_sheet_with_header_row_matches_table(self) -> None:
        table = read_selection(FIXTURE, XlsxSelection(table="Requirements")).rows
        sheet = read_selection(
            FIXTURE, XlsxSelection(sheet="Requirements", header_row=3)
        ).rows
        self.assertEqual(sheet, table)

    def test_selection_errors(self) -> None:
        code, _, err = run_cli(
            str(FIXTURE), "--id-column", "ID", "-o", str(self.root / "r.html")
        )
        self.assertEqual(code, 3)
        self.assertIn("Table2", err)
        self.assertIn("Requirements", err)
        self.assertIn("Glossary", err)

        code, _, err = run_cli(
            str(FIXTURE),
            "--table",
            "Nope",
            "--id-column",
            "ID",
            "-o",
            str(self.root / "r.html"),
        )
        self.assertEqual(code, 3)
        self.assertIn("Table2", err)

        code, _, err = run_cli(
            str(FIXTURE),
            "--sheet",
            "Nope",
            "--id-column",
            "ID",
            "-o",
            str(self.root / "r.html"),
        )
        self.assertEqual(code, 3)
        self.assertIn("Glossary", err)

        code, _, err = run_cli(
            str(FIXTURE),
            "--table",
            "Requirements",
            "--sheet",
            "Glossary",
            "--id-column",
            "ID",
            "-o",
            str(self.root / "r.html"),
        )
        self.assertEqual(code, 2)
        self.assertFalse((self.root / "r.html").exists())

    def test_selection_flag_rules(self) -> None:
        with self.assertRaises(ConfigError):
            XlsxSelection(header_row=3)
        with self.assertRaises(ConfigError):
            XlsxSelection(sheet="A", header_row=0)
        csv_path = self.root / "in.csv"
        csv_path.write_text("ID\nR1\n", encoding="utf-8")
        code, _, err = run_cli(
            str(csv_path),
            "--table",
            "T",
            "--id-column",
            "ID",
            "-o",
            str(self.root / "r.html"),
        )
        self.assertEqual(code, 2)
        self.assertIn(".xlsx", err)

    def test_csv_export_round_trips_into_a_report(self) -> None:
        exported = self.root / "requirements.csv"
        code, _, err = run_cli(
            str(FIXTURE),
            "--table",
            "Requirements",
            "--id-column",
            "ID",
            "-o",
            str(exported),
        )
        self.assertEqual(code, 0, err)
        raw = exported.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(raw.endswith(b"\r\n"))
        self.assertNotIn(b"\r\n\r\n", raw)
        self.assertEqual(
            raw.count(b"\r\n"), 5
        )  # the multi-line cell keeps bare LFs inside its quotes

        direct, via_csv = self.root / "direct.html", self.root / "via.html"
        self.assertEqual(
            run_cli(
                str(FIXTURE),
                "--table",
                "Requirements",
                "--id-column",
                "ID",
                "-o",
                str(direct),
            )[0],
            0,
        )
        self.assertEqual(
            run_cli(str(exported), "--id-column", "ID", "-o", str(via_csv))[0], 0
        )
        self.assertEqual(
            report_data(direct)["source"]["new"], report_data(via_csv)["source"]["new"]
        )
        self.assertIn("[Requirements]", report_data(direct)["meta"]["newFilename"])
        self.assertNotIn(
            str(FIXTURE.parent), report_data(direct)["meta"]["newFilename"]
        )

    def test_csv_export_rejects_what_reqtable_would_reject(self) -> None:
        exported = self.root / "glossary.csv"
        code, _, err = run_cli(
            str(FIXTURE),
            "--sheet",
            "Glossary",
            "--id-column",
            "ID",
            "-o",
            str(exported),
        )
        self.assertEqual(code, 3)
        self.assertIn("ID column", err)
        self.assertFalse(exported.exists())

    def test_diff_against_csv(self) -> None:
        old = self.root / "old.csv"
        old.write_text("ID,Requirement\nREQ-1,Old text\nREQ-9,Gone\n", encoding="utf-8")
        out = self.root / "diff.html"
        code, _, err = run_cli(
            "--old",
            str(old),
            "--new",
            str(FIXTURE),
            "--table",
            "Requirements",
            "--id-column",
            "ID",
            "-o",
            str(out),
        )
        self.assertEqual(code, 0, err)
        data = report_data(out)
        self.assertEqual(data["meta"]["mode"], "diff")
        self.assertIn("[Requirements]", data["meta"]["newFilename"])
        code, _, err = run_cli(
            "--old",
            str(FIXTURE),
            "--new",
            str(old),
            "--table",
            "Requirements",
            "--id-column",
            "ID",
            "-o",
            str(out),
        )
        self.assertEqual(code, 0, err)

    def test_git_baseline_with_xlsx_is_refused(self) -> None:
        code, _, err = run_cli(
            "--old",
            "git:HEAD",
            "--new",
            str(FIXTURE),
            "--table",
            "Requirements",
            "--id-column",
            "ID",
            "-o",
            str(self.root / "d.html"),
        )
        self.assertEqual(code, 3)
        self.assertIn("git baselines need CSV", err)

    def test_list_tables(self) -> None:
        code, out, _ = run_cli("--list-tables", str(FIXTURE))
        self.assertEqual(code, 0)
        for name in ("Table2", "Requirements", "Glossary", "A3:F7"):
            self.assertIn(name, out)
        self.assertIn("ID, Requirement, Priority, Due, Version, Length", out)

    def test_not_a_workbook(self) -> None:
        bogus = self.root / "bogus.xlsx"
        bogus.write_text("not a zip", encoding="utf-8")
        code, _, err = run_cli(
            str(bogus), "--id-column", "ID", "-o", str(self.root / "r.html")
        )
        self.assertEqual(code, 3)
        self.assertIn("bogus.xlsx", err)


def synthetic_workbook(path: Path, date1904: bool) -> None:
    """Hand-built workbook (not Excel output) for what Excel did not produce here: inline strings and date1904."""
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts = {
        "xl/workbook.xml": (
            f'<workbook xmlns="{main_ns}" xmlns:r="{rel_ns}"><workbookPr date1904="{int(date1904)}"/>'
            '<sheets><sheet name="Data" sheetId="1" state="hidden" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/styles.xml": (
            f'<styleSheet xmlns="{main_ns}"><numFmts><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>'
            '<cellXfs><xf numFmtId="0"/><xf numFmtId="164"/><xf numFmtId="22"/></cellXfs></styleSheet>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{main_ns}"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>ID</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>Text</t></is></c><c r="C1" t="inlineStr"><is><t>When</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>R1</t></is></c>'
            '<c r="B2" t="inlineStr"><is><r><t>Rich </t></r><r><t>text</t></r><rPh><t>phonetic</t></rPh></is></c>'
            '<c r="C2" s="1"><v>1</v></c></row>'
            '<row r="3"><c r="A3" t="inlineStr"><is><t>R2</t></is></c><c r="C3" s="2"><v>45000.75</v></c></row>'
            "</sheetData></worksheet>"
        ),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)


class SyntheticWorkbookTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_inline_strings_rich_text_and_hidden_sheet(self) -> None:
        path = self.root / "s.xlsx"
        synthetic_workbook(path, date1904=False)
        rows = read_selection(path, XlsxSelection(sheet="Data")).rows
        self.assertEqual(rows[0], ["ID", "Text", "When"])
        self.assertEqual(rows[1][:2], ["R1", "Rich text"])
        self.assertEqual(rows[1][2], "1900-01-01")
        self.assertEqual(rows[2], ["R2", "", "2023-03-15T18:00:00"])
        code, out, _ = run_cli("--list-tables", str(path))
        self.assertEqual(code, 0)
        self.assertIn("Data (hidden)", out)

    def test_date1904_shifts_the_epoch(self) -> None:
        path = self.root / "s.xlsx"
        synthetic_workbook(path, date1904=True)
        rows = read_selection(path, XlsxSelection(sheet="Data")).rows
        self.assertEqual(rows[1][2], "1904-01-02")
        self.assertEqual(rows[2][2], "2027-03-16T18:00:00")

    def test_csv_text_uses_delimiter_and_quotes(self) -> None:
        text = block_to_csv([["a", "b;c"], ["x\ny", 'q"']], ";")
        self.assertEqual(
            list(csv.reader(io.StringIO(text, newline=""), delimiter=";")),
            [["a", "b;c"], ["x\ny", 'q"']],
        )
        self.assertTrue(text.endswith("\r\n"))


if __name__ == "__main__":
    unittest.main()
