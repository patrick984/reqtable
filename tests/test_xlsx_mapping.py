from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from reqtable.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "excel-sample.xlsx"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

FIXTURE_SOURCES = [
    {"table": "Requirements"},
    {"sheet": "Glossary", "header_row": 2, "type": "Term", "id_prefix": "TERM-"},
]


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def report_data(path: Path) -> dict:
    match = re.search(r'<script[^>]*id="reqtable-data"[^>]*>(.*?)</script>', path.read_text(encoding="utf-8"), re.S)
    return json.loads(match.group(1))


def _cell(ref: str, text: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _sheet_xml(grid: list[list[str]], first_row: int = 1) -> str:
    rows = []
    for offset, values in enumerate(grid):
        number = first_row + offset
        cells = "".join(_cell(f"{chr(65 + i)}{number}", v) for i, v in enumerate(values) if v)
        rows.append(f'<row r="{number}">{cells}</row>')
    return f'<worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(rows)}</sheetData></worksheet>'


def requirements_workbook(path: Path, glossary: list[list[str]] | None = None) -> None:
    """Hand-built workbook (synthetic, not Excel output): a plain sheet and a glossary sheet with other headers."""
    glossary = glossary if glossary is not None else [
        ["Term", "Meaning", "Abbreviation", "Notes"],
        ["Identifier", "A unique label.", "ID", "internal"],
        ["Comma separated values", "A text table format.", "CSV;TSV", ""],
    ]
    parts = {
        "xl/workbook.xml": (
            f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>'
            '<sheet name="Reqs" sheetId="1" r:id="rId1"/><sheet name="Terms" sheetId="2" r:id="rId2"/>'
            '</sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": _sheet_xml(
            [["Req ID", "Text", "Owner"], ["R-1", "The tool shall export CSV.", "Ann"], ["R-2", "The tool shall list tables.", "Bo"]]
        ),
        "xl/worksheets/sheet2.xml": _sheet_xml(glossary),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)


class MappingCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def config(self, sources: list[dict], **extra: object) -> str:
        path = self.root / f"config{len(list(self.root.glob('config*.json')))}.json"
        path.write_text(json.dumps({"id_column": "ID", **extra, "xlsx": {"sources": sources}}), encoding="utf-8")
        return str(path)

    def report(self, workbook: Path, sources: list[dict], *flags: str, **extra: object) -> tuple[int, str, dict]:
        out = self.root / "report.html"
        out.unlink(missing_ok=True)
        code, _, err = run_cli(str(workbook), "-c", self.config(sources, **extra), *flags, "-o", str(out))
        return code, err, report_data(out) if out.exists() else {}


class FixtureMappingTests(MappingCase):
    def test_requirements_and_glossary_combine_into_term_rows(self) -> None:
        code, err, data = self.report(FIXTURE, FIXTURE_SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        rows = {row["ID"]: row for row in data["source"]["new"]["rows"]}
        self.assertEqual(list(rows), ["REQ-1", "REQ-2", "REQ-3", "REQ-4", "TERM-CSV", "TERM-ID"])
        self.assertEqual(rows["TERM-ID"]["Type"], "Term")
        self.assertEqual(rows["TERM-ID"]["Name"], "Identifier")
        self.assertTrue(rows["TERM-ID"]["Definition"])
        self.assertTrue(rows["TERM-CSV"]["Aliases"])
        for requirement in ("REQ-1", "REQ-4"):
            self.assertEqual(rows[requirement]["Type"], "")
            self.assertEqual(rows[requirement]["Name"], "")
        self.assertEqual(rows["REQ-1"]["Due"], "2026-12-01")
        self.assertIn("[Requirements + Glossary]", data["meta"]["newFilename"])

    def test_csv_input_ignores_xlsx_sources(self) -> None:
        source = self.root / "in.csv"
        source.write_text("ID,Requirement\nR1,text\n", encoding="utf-8")
        out = self.root / "r.html"
        code, _, err = run_cli(str(source), "-c", self.config(FIXTURE_SOURCES), "-o", str(out))
        self.assertEqual(code, 0, err)
        self.assertEqual([r["ID"] for r in report_data(out)["source"]["new"]["rows"]], ["R1"])

    def test_sources_conflict_with_selection_flags(self) -> None:
        code, _, err = run_cli(
            str(FIXTURE), "--table", "Requirements", "-c", self.config(FIXTURE_SOURCES), "-o", str(self.root / "r.html")
        )
        self.assertEqual(code, 2)
        self.assertIn("xlsx.sources", err)

    def test_template_lists_every_table_and_sheet_and_runs_once_edited(self) -> None:
        code, out, err = run_cli("--xlsx-mapping-template", str(FIXTURE))
        self.assertEqual(code, 0, err)
        template = json.loads(out)
        sources = template["xlsx"]["sources"]
        self.assertEqual(template["id_column"], "ID")
        self.assertEqual([s.get("table") or s["sheet"] for s in sources], ["Table2", "Requirements", "Glossary"])
        glossary = sources[2]
        self.assertEqual(glossary["header_row"], 2)
        self.assertEqual(glossary["columns"], {"Name": "Name", "Definition": "Definition", "Aliases": "Aliases"})

        unedited = self.root / "template.json"
        unedited.write_text(out, encoding="utf-8")
        code, _, err = run_cli(str(FIXTURE), "-c", str(unedited), "-o", str(self.root / "a.html"))
        self.assertEqual(code, 2)
        self.assertIn("xlsx source 'Table2' has no 'ID' column", err)
        self.assertIn("id_prefix", err)

        edited = copy.deepcopy(template)
        edited["xlsx"]["sources"] = [sources[1], {**glossary, "type": "Term", "id_prefix": "TERM-"}]
        edited_path = self.root / "edited.json"
        edited_path.write_text(json.dumps(edited), encoding="utf-8")
        for output in ("b.html", "b.csv"):
            code, _, err = run_cli(str(FIXTURE), "-c", str(edited_path), "--traceability", "-o", str(self.root / output))
            self.assertEqual(code, 0, err)


class SyntheticMappingTests(MappingCase):
    SOURCES = [
        {"sheet": "Reqs", "columns": {"Req ID": "ID", "Text": "Requirement"}, "exclude": ["Owner"]},
        {
            "sheet": "Terms", "columns": {"Term": "Name", "Meaning": "Definition", "Abbreviation": "Aliases"},
            "exclude": ["Notes"], "type": "Term", "id_prefix": "T-",
        },
    ]

    def setUp(self) -> None:
        super().setUp()
        self.workbook = self.root / "team.xlsx"
        requirements_workbook(self.workbook)

    def test_columns_exclude_and_generated_ids(self) -> None:
        code, err, data = self.report(self.workbook, self.SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        rows = {row["ID"]: row for row in data["source"]["new"]["rows"]}
        self.assertEqual(list(rows), ["R-1", "R-2", "T-ID", "T-CSV"])
        self.assertEqual(rows["R-1"]["Requirement"], "The tool shall export CSV.")
        self.assertEqual(rows["T-CSV"]["Name"], "Comma separated values")
        self.assertEqual(rows["T-CSV"]["Aliases"], "CSV;TSV")
        for row in rows.values():
            self.assertNotIn("Ann", row.values())
            self.assertNotIn("Notes", row)
            self.assertNotIn("Req ID", row)

    def test_slug_falls_back_to_name_when_there_is_no_alias(self) -> None:
        requirements_workbook(self.workbook, [["Term", "Meaning"], ["Test case", "A check."]])
        sources = [self.SOURCES[0], {**self.SOURCES[1], "columns": {"Term": "Name", "Meaning": "Definition"}, "exclude": []}]
        code, err, data = self.report(self.workbook, sources, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertEqual([r["ID"] for r in data["source"]["new"]["rows"]], ["R-1", "R-2", "T-TEST-CASE"])

    def test_export_to_csv_round_trips(self) -> None:
        exported = self.root / "combined.csv"
        code, _, err = run_cli(
            str(self.workbook), "-c", self.config(self.SOURCES), "--traceability", "-o", str(exported)
        )
        self.assertEqual(code, 0, err)
        raw = exported.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        records = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
        self.assertEqual([r["ID"] for r in records], ["R-1", "R-2", "T-ID", "T-CSV"])
        direct = self.root / "direct.html"
        again = self.root / "again.html"
        self.assertEqual(run_cli(str(self.workbook), "-c", self.config(self.SOURCES), "--traceability", "-o", str(direct))[0], 0)
        self.assertEqual(run_cli(str(exported), "--id-column", "ID", "--traceability", "-o", str(again))[0], 0)
        self.assertEqual(report_data(direct)["source"]["new"]["rows"], report_data(again)["source"]["new"]["rows"])

    def test_unknown_column_names_the_actual_headers(self) -> None:
        bad = [{"sheet": "Reqs", "columns": {"Requirement ID": "ID"}}]
        code, err, _ = self.report(self.workbook, bad)
        self.assertEqual(code, 2)
        self.assertIn("Requirement ID", err)
        self.assertIn("Reqs", err)
        self.assertIn("Req ID, Text, Owner", err)
        code, err, _ = self.report(self.workbook, [{"sheet": "Reqs", "exclude": ["Nope"]}])
        self.assertEqual(code, 2)
        self.assertIn("Req ID, Text, Owner", err)

    def test_type_needs_traceability(self) -> None:
        code, err, _ = self.report(self.workbook, self.SOURCES)
        self.assertEqual(code, 2)
        self.assertIn("traceability", err)
        code, err, _ = self.report(self.workbook, self.SOURCES, traceability=True)
        self.assertEqual(code, 0, err)

    def test_shape_errors(self) -> None:
        cases = [
            [{"table": "A", "sheet": "B"}],
            [{}],
            [{"table": "A", "header_row": 2}],
            [{"sheet": "Reqs", "header_row": 0}],
            [{"sheet": "Reqs", "columns": {"Text": 3}}],
            [{"sheet": "Reqs", "exclude": "Owner"}],
            [{"sheet": "Reqs", "colums": {}}],
        ]
        for sources in cases:
            with self.subTest(sources=sources):
                code, err, _ = self.report(self.workbook, sources)
                self.assertEqual(code, 2)
                self.assertIn("xlsx.sources[0]", err)

    def test_impossible_slug(self) -> None:
        requirements_workbook(self.workbook, [["Term", "Meaning", "Abbreviation", "Notes"], ["***", "Symbols only.", "", ""]])
        code, err, _ = self.report(self.workbook, self.SOURCES, "--traceability")
        self.assertEqual(code, 3)
        self.assertIn("Terms", err)
        self.assertIn("row 2", err)

    def test_duplicate_generated_ids_use_the_existing_error(self) -> None:
        requirements_workbook(
            self.workbook,
            [["Term", "Meaning", "Abbreviation", "Notes"], ["Alpha", "One.", "A-1", ""], ["Beta", "Two.", "A 1", ""]],
        )
        code, err, _ = self.report(self.workbook, self.SOURCES, "--traceability")
        self.assertEqual(code, 3)
        self.assertIn("duplicate ID 'T-A-1'", err)


if __name__ == "__main__":
    unittest.main()
