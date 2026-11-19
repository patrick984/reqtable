from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from reqtable.cli import main
from reqtable.traceability import TRACE_MODEL_JS
from reqtable.values import VALUE_RENAME_JS
from reqtable.xlsx import _slug

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
    match = re.search(
        r'<script[^>]*id="reqtable-data"[^>]*>(.*?)</script>',
        path.read_text(encoding="utf-8"),
        re.S,
    )
    return json.loads(match.group(1))


def _cell(ref: str, text: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _sheet_xml(grid: list[list[str]], first_row: int = 1) -> str:
    rows = []
    for offset, values in enumerate(grid):
        number = first_row + offset
        cells = "".join(
            _cell(f"{chr(65 + i)}{number}", v) for i, v in enumerate(values) if v
        )
        rows.append(f'<row r="{number}">{cells}</row>')
    return f'<worksheet xmlns="{MAIN_NS}"><sheetData>{"".join(rows)}</sheetData></worksheet>'


def requirements_workbook(path: Path, glossary: list[list[str]] | None = None) -> None:
    """Hand-built workbook (synthetic, not Excel output): a plain sheet and a glossary sheet with other headers."""
    glossary = (
        glossary
        if glossary is not None
        else [
            ["Term", "Meaning", "Abbreviation", "Notes"],
            ["Identifier", "A unique label.", "ID", "internal"],
            ["Comma separated values", "A text table format.", "CSV;TSV", ""],
        ]
    )
    parts = {
        "xl/workbook.xml": (
            f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>'
            '<sheet name="Reqs" sheetId="1" r:id="rId1"/><sheet name="Terms" sheetId="2" r:id="rId2"/>'
            "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": _sheet_xml(
            [
                ["Req ID", "Text", "Owner"],
                ["R-1", "The tool shall export CSV.", "Ann"],
                ["R-2", "The tool shall list tables.", "Bo"],
            ]
        ),
        "xl/worksheets/sheet2.xml": _sheet_xml(glossary),
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)


def lookup_workbook(
    path: Path, tests_cell: str = "T-1, T-2", method: str = "Manual verification"
) -> None:
    """Hand-built workbook (synthetic, not Excel output) with real tables, lookup sheets and a tests table."""
    sheets = {
        "Reqs": (
            "Reqs",
            [
                ["Req ID", "Text", "Priority", "Tests"],
                ["R-1", "Export CSV.", "Must", tests_cell],
                ["R-2", "List tables.", "Should", "T-3"],
            ],
        ),
        "Priorities": (
            None,
            [
                ["Value", "Meaning"],
                ["Must", "Needed for release."],
                ["Should", "Wanted for release."],
            ],
        ),
        "Lists": (
            None,
            [
                ["Field", "Value", "Meaning", "Old spellings"],
                [
                    "Verification Method",
                    "Manual browser test",
                    "A person drives the report.",
                    "Manual verification, Browser check",
                ],
                ["Verification Method", "Automated test", "A script checks it.", ""],
            ],
        ),
        "TestCases": (
            "TestCases",
            [
                ["Test ID", "Title", "Plan", "Method"],
                ["T-1", "Export check", "P-1", "Automated test"],
                ["T-2", "Export UI", "P-1", method],
                ["T-3", "List check", "P-1", "Automated test"],
            ],
        ),
        "Plans": ("Plans", [["Plan ID", "Title"], ["P-1", "UAT plan"]]),
        "Systems": (None, [["System"], ["Reqtable"]]),
        "Fields": (
            None,
            [
                ["Column", "Meaning"],
                ["Verification Method", "How a test checks a requirement."],
            ],
        ),
    }
    names = list(sheets)
    workbook = "".join(
        f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>'
        for i, n in enumerate(names, 1)
    )
    parts = {
        "xl/workbook.xml": f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>{workbook}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)
        )
        + "</Relationships>",
    }
    for i, name in enumerate(names, 1):
        table, grid = sheets[name]
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(grid)
        if table:
            end = f"{chr(64 + len(grid[0]))}{len(grid)}"
            parts[f"xl/worksheets/_rels/sheet{i}.xml.rels"] = (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f'<Relationship Id="rId1" Type="table" Target="../tables/table{i}.xml"/></Relationships>'
            )
            parts[f"xl/tables/table{i}.xml"] = (
                f'<table xmlns="{MAIN_NS}" name="{table}" displayName="{table}" ref="A1:{end}"/>'
            )
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)


LOOKUP_SOURCES = [
    {
        "table": "Reqs",
        "columns": {"Req ID": "ID", "Text": "Requirement", "Tests": "Verified by"},
        "lists": {"Verified by": ","},
    },
    {
        "sheet": "Priorities",
        "type": "Value",
        "set": {"Field": "Priority"},
        "columns": {"Value": "Name", "Meaning": "Definition"},
        "id_prefix": "VAL-",
    },
    {
        "sheet": "Lists",
        "type": "Value",
        "columns": {
            "Value": "Name",
            "Meaning": "Definition",
            "Old spellings": "Aliases",
        },
        "lists": {"Aliases": ","},
        "id_prefix": "VAL-",
    },
    {
        "sheet": "Fields",
        "type": "Field",
        "set": {"Multiple": "Yes"},
        "columns": {"Column": "Name", "Meaning": "Definition"},
        "id_prefix": "FIELD-",
    },
    {
        "table": "TestCases",
        "type": "Test",
        "columns": {
            "Test ID": "ID",
            "Title": "Name",
            "Plan": "Test plan",
            "Method": "Verification Method",
        },
    },
    {
        "sheet": "Systems",
        "type": "System",
        "columns": {"System": "Name"},
        "id_prefix": "SYS-",
    },
    {
        "table": "Plans",
        "type": "Test plan",
        "columns": {"Plan ID": "ID", "Title": "Name"},
    },
]


class MappingCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def config(self, sources: list[dict], **extra: object) -> str:
        path = self.root / f"config{len(list(self.root.glob('config*.json')))}.json"
        path.write_text(
            json.dumps({"id_column": "ID", **extra, "xlsx": {"sources": sources}}),
            encoding="utf-8",
        )
        return str(path)

    def report(
        self, workbook: Path, sources: list[dict], *flags: str, **extra: object
    ) -> tuple[int, str, dict]:
        out = self.root / "report.html"
        out.unlink(missing_ok=True)
        code, _, err = run_cli(
            str(workbook), "-c", self.config(sources, **extra), *flags, "-o", str(out)
        )
        return code, err, report_data(out) if out.exists() else {}


class FixtureMappingTests(MappingCase):
    def test_requirements_and_glossary_combine_into_term_rows(self) -> None:
        code, err, data = self.report(FIXTURE, FIXTURE_SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        rows = {row["ID"]: row for row in data["source"]["new"]["rows"]}
        self.assertEqual(
            list(rows), ["REQ-1", "REQ-2", "REQ-3", "REQ-4", "TERM-CSV", "TERM-ID"]
        )
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
        code, _, err = run_cli(
            str(source), "-c", self.config(FIXTURE_SOURCES), "-o", str(out)
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            [r["ID"] for r in report_data(out)["source"]["new"]["rows"]], ["R1"]
        )

    def test_sources_conflict_with_selection_flags(self) -> None:
        code, _, err = run_cli(
            str(FIXTURE),
            "--table",
            "Requirements",
            "-c",
            self.config(FIXTURE_SOURCES),
            "-o",
            str(self.root / "r.html"),
        )
        self.assertEqual(code, 2)
        self.assertIn("xlsx.sources", err)

    def test_template_lists_every_table_and_sheet_and_runs_once_edited(self) -> None:
        code, out, err = run_cli("--xlsx-mapping-template", str(FIXTURE))
        self.assertEqual(code, 0, err)
        template = json.loads(out)
        sources = template["xlsx"]["sources"]
        self.assertEqual(template["id_column"], "ID")
        self.assertEqual(
            [s.get("table") or s["sheet"] for s in sources],
            ["Table2", "Requirements", "Glossary"],
        )
        glossary = sources[2]
        self.assertEqual(glossary["header_row"], 2)
        self.assertEqual(
            glossary["columns"],
            {"Name": "Name", "Definition": "Definition", "Aliases": "Aliases"},
        )

        unedited = self.root / "template.json"
        unedited.write_text(out, encoding="utf-8")
        code, _, err = run_cli(
            str(FIXTURE), "-c", str(unedited), "-o", str(self.root / "a.html")
        )
        self.assertEqual(code, 2)
        self.assertIn("xlsx source 'Table2' has no 'ID' column", err)
        self.assertIn("id_prefix", err)

        edited = copy.deepcopy(template)
        edited["xlsx"]["sources"] = [
            sources[1],
            {**glossary, "type": "Term", "id_prefix": "TERM-"},
        ]
        edited_path = self.root / "edited.json"
        edited_path.write_text(json.dumps(edited), encoding="utf-8")
        for output in ("b.html", "b.csv"):
            code, _, err = run_cli(
                str(FIXTURE),
                "-c",
                str(edited_path),
                "--traceability",
                "-o",
                str(self.root / output),
            )
            self.assertEqual(code, 0, err)


class SyntheticMappingTests(MappingCase):
    SOURCES = [
        {
            "sheet": "Reqs",
            "columns": {"Req ID": "ID", "Text": "Requirement"},
            "exclude": ["Owner"],
        },
        {
            "sheet": "Terms",
            "columns": {
                "Term": "Name",
                "Meaning": "Definition",
                "Abbreviation": "Aliases",
            },
            "exclude": ["Notes"],
            "type": "Term",
            "id_prefix": "T-",
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
        requirements_workbook(
            self.workbook, [["Term", "Meaning"], ["Test case", "A check."]]
        )
        sources = [
            self.SOURCES[0],
            {
                **self.SOURCES[1],
                "columns": {"Term": "Name", "Meaning": "Definition"},
                "exclude": [],
            },
        ]
        code, err, data = self.report(self.workbook, sources, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertEqual(
            [r["ID"] for r in data["source"]["new"]["rows"]],
            ["R-1", "R-2", "T-TEST-CASE"],
        )

    def test_export_to_csv_round_trips(self) -> None:
        exported = self.root / "combined.csv"
        code, _, err = run_cli(
            str(self.workbook),
            "-c",
            self.config(self.SOURCES),
            "--traceability",
            "-o",
            str(exported),
        )
        self.assertEqual(code, 0, err)
        raw = exported.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        records = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
        self.assertEqual([r["ID"] for r in records], ["R-1", "R-2", "T-ID", "T-CSV"])
        direct = self.root / "direct.html"
        again = self.root / "again.html"
        self.assertEqual(
            run_cli(
                str(self.workbook),
                "-c",
                self.config(self.SOURCES),
                "--traceability",
                "-o",
                str(direct),
            )[0],
            0,
        )
        self.assertEqual(
            run_cli(
                str(exported), "--id-column", "ID", "--traceability", "-o", str(again)
            )[0],
            0,
        )
        self.assertEqual(
            report_data(direct)["source"]["new"]["rows"],
            report_data(again)["source"]["new"]["rows"],
        )

    def test_unknown_column_names_the_actual_headers(self) -> None:
        bad = [{"sheet": "Reqs", "columns": {"Requirement ID": "ID"}}]
        code, err, _ = self.report(self.workbook, bad)
        self.assertEqual(code, 2)
        self.assertIn("Requirement ID", err)
        self.assertIn("Reqs", err)
        self.assertIn("Req ID, Text, Owner", err)
        code, err, _ = self.report(
            self.workbook, [{"sheet": "Reqs", "exclude": ["Nope"]}]
        )
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

    def test_impossible_slug_becomes_a_numbered_row(self) -> None:
        requirements_workbook(
            self.workbook,
            [
                ["Term", "Meaning", "Abbreviation", "Notes"],
                ["***", "Symbols only.", "", ""],
            ],
        )
        code, err, data = self.report(self.workbook, self.SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertIn("ROW-2", [row["ID"] for row in data["source"]["new"]["rows"]])
        self.assertIn("[Terms]: 1 row has no ID", err)

    def test_duplicate_generated_ids_are_suffixed(self) -> None:
        requirements_workbook(
            self.workbook,
            [
                ["Term", "Meaning", "Abbreviation", "Notes"],
                ["Alpha", "One.", "A-1", ""],
                ["Beta", "Two.", "A 1", ""],
            ],
        )
        code, err, data = self.report(self.workbook, self.SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertIn("T-A-1~2", [row["ID"] for row in data["source"]["new"]["rows"]])
        self.assertIn("duplicate ID 'T-A-1' at rows 2, 3", err)


@unittest.skipUnless(
    shutil.which("node"), "Node is needed to exercise the report's JavaScript"
)
class LookupListTests(MappingCase):
    def setUp(self) -> None:
        super().setUp()
        self.workbook = self.root / "lookups.xlsx"
        lookup_workbook(self.workbook)

    def findings(self, data: dict) -> list[str]:
        source = data["source"]["new"]
        script = (
            "const rows="
            + json.dumps(source["rows"])
            + ";\n"
            + TRACE_MODEL_JS
            + "const index=buildTraceIndex(rows,row=>row.ID,{headers:"
            + json.dumps(source["headers"])
            + ',idColumn:"ID"});console.log(JSON.stringify(index.issues.map(i=>`${i.id}|${i.field}|${i.message}`)));'
        )
        return json.loads(
            subprocess.run(
                ["node"], input=script, text=True, check=True, capture_output=True
            ).stdout
        )

    def rows(self, data: dict) -> dict:
        return {row["ID"]: row for row in data["source"]["new"]["rows"]}

    def test_lookup_lists_and_tests_import_cleanly(self) -> None:
        code, err, data = self.report(self.workbook, LOOKUP_SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        rows = self.rows(data)
        self.assertEqual(
            list(rows),
            [
                "R-1",
                "R-2",
                "VAL-PRIORITY-MUST",
                "VAL-PRIORITY-SHOULD",
                "VAL-VERIFICATION-METHOD-MANUAL-BROWSER-TEST",
                "VAL-VERIFICATION-METHOD-AUTOMATED-TEST",
                "FIELD-VERIFICATION-METHOD",
                "T-1",
                "T-2",
                "T-3",
                "SYS-REQTABLE",
                "P-1",
            ],
        )
        self.assertEqual(rows["R-1"]["Verified by"], "T-1; T-2")
        self.assertEqual(rows["R-2"]["Verified by"], "T-3")
        must = rows["VAL-PRIORITY-MUST"]
        self.assertEqual(
            (must["Type"], must["Field"], must["Name"]), ("Value", "Priority", "Must")
        )
        self.assertEqual(
            rows["VAL-VERIFICATION-METHOD-MANUAL-BROWSER-TEST"]["Aliases"],
            "Manual verification; Browser check",
        )
        self.assertEqual(
            (
                rows["FIELD-VERIFICATION-METHOD"]["Type"],
                rows["FIELD-VERIFICATION-METHOD"]["Multiple"],
            ),
            ("Field", "Yes"),
        )
        self.assertEqual(
            (rows["T-1"]["Type"], rows["T-1"]["Test plan"]), ("Test", "P-1")
        )
        self.assertEqual(rows["P-1"]["Type"], "Test plan")

    def test_only_the_alias_spelling_is_flagged_and_rerun_is_identical(self) -> None:
        code, err, first = self.report(self.workbook, LOOKUP_SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertEqual(
            self.findings(first),
            [
                "T-2|Verification Method|“Manual verification” is a replaced spelling; use “Manual browser test”."
            ],
        )
        _, _, again = self.report(self.workbook, LOOKUP_SOURCES, "--traceability")
        self.assertEqual(first["source"]["new"]["rows"], again["source"]["new"]["rows"])
        lookup_workbook(self.workbook, method="Manual browser test")
        code, err, fixed = self.report(self.workbook, LOOKUP_SOURCES, "--traceability")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.findings(fixed), [])

    def test_generated_value_ids_match_the_browser_add_value_rule(self) -> None:
        samples = [
            ("Priority", "Must"),
            ("Verification Method", "Manual browser test"),
            ("Due date", "A/B (v2)!"),
        ]
        script = (
            VALUE_RENAME_JS
            + "console.log(JSON.stringify(%s.map(([f,n])=>valueRecordId(f,n,new Set()))));"
            % json.dumps(samples)
        )
        browser = json.loads(
            subprocess.run(
                ["node"], input=script, text=True, check=True, capture_output=True
            ).stdout
        )
        self.assertEqual(browser, [f"VAL-{_slug(f)}-{_slug(n)}" for f, n in samples])

    def test_combined_import_exports_csv_that_reports_the_same_rows(self) -> None:
        exported = self.root / "combined.csv"
        code, _, err = run_cli(
            str(self.workbook),
            "-c",
            self.config(LOOKUP_SOURCES),
            "--traceability",
            "-o",
            str(exported),
        )
        self.assertEqual(code, 0, err)
        direct = self.root / "direct.html"
        again = self.root / "again.html"
        run_cli(
            str(self.workbook),
            "-c",
            self.config(LOOKUP_SOURCES),
            "--traceability",
            "-o",
            str(direct),
        )
        code, _, err = run_cli(
            str(exported), "--id-column", "ID", "--traceability", "-o", str(again)
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            report_data(direct)["source"]["new"]["rows"],
            report_data(again)["source"]["new"]["rows"],
        )

    def test_lists_split_on_newlines_and_leave_other_columns_alone(self) -> None:
        requirements_workbook(
            self.workbook, [["Term", "Meaning"], ["Alpha", "One, two"], ["Beta", "x"]]
        )
        grid = {
            "sheet": "Terms",
            "columns": {"Term": "Name", "Meaning": "Definition"},
            "id_prefix": "T-",
        }
        sources = [
            {
                "sheet": "Reqs",
                "columns": {"Req ID": "ID", "Owner": "Aliases"},
                "lists": {"Aliases": "newline"},
            },
            grid,
        ]
        code, err, data = self.report(self.workbook, sources)
        self.assertEqual(code, 0, err)
        rows = self.rows(data)
        self.assertEqual(rows["T-ALPHA"]["Definition"], "One, two")
        self.assertEqual(rows["R-1"]["Aliases"], "Ann")

    def test_set_and_list_errors_name_the_columns(self) -> None:
        cases = {
            "id_from": [
                {
                    "sheet": "Priorities",
                    "type": "Value",
                    "id_prefix": "V-",
                    "id_from": ["Nope"],
                    "columns": {"Value": "Name"},
                }
            ],
            "lists": [
                {
                    "sheet": "Priorities",
                    "lists": {"Nope": ","},
                    "columns": {"Value": "ID"},
                }
            ],
        }
        for key, sources in cases.items():
            with self.subTest(key=key):
                code, err, _ = self.report(self.workbook, sources, "--traceability")
                self.assertEqual(code, 2)
                self.assertIn("'Nope'", err)
                self.assertIn("columns:", err)
                self.assertIn("Meaning", err)
        bad = [
            [{"sheet": "Reqs", "type": "Term", "set": {"Type": "Term"}}],
            [{"sheet": "Reqs", "lists": {"Tests": 1}}],
            [{"sheet": "Reqs", "lists": {"Tests": ""}}],
            [{"sheet": "Reqs", "set": {"Owner": 1}}],
            [{"sheet": "Reqs", "id_from": "Name", "id_prefix": "X-"}],
            [{"sheet": "Reqs", "id_from": ["Name"]}],
        ]
        for sources in bad:
            with self.subTest(sources=sources):
                code, err, _ = self.report(self.workbook, sources, "--traceability")
                self.assertEqual(code, 2)
                self.assertIn("xlsx.sources[0]", err)

    def test_value_with_no_field_or_name_cannot_build_an_id(self) -> None:
        lookup_workbook(self.workbook)
        sources = [{"sheet": "Priorities", "type": "Value", "id_prefix": "VAL-"}]
        code, err, _ = self.report(self.workbook, sources, "--traceability")
        self.assertEqual(code, 2, err)
        self.assertIn("'Field'", err)

    def test_template_never_emits_the_new_keys(self) -> None:
        code, out, err = run_cli("--xlsx-mapping-template", str(self.workbook))
        self.assertEqual(code, 0, err)
        for source in json.loads(out)["xlsx"]["sources"]:
            self.assertFalse({"set", "id_from", "lists"} & set(source))


if __name__ == "__main__":
    unittest.main()
