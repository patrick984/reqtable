from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from reqtable.findings import trace_findings
from test_xlsx_import import PACKAGE_REL, comments_xml
from test_xlsx_mapping import MAIN_NS, REL_NS, MappingCase, _sheet_xml, run_cli

REQS = [
    ["Req ID", "Text"],
    ["R-1", "Export CSV."],
    ["R-2", "List tables."],
    ["R-3", "Show tests."],
]
MATRIX = [
    ["Requirement", "Level", "Test"],
    ["R-1", "System", "T-1"],
    ["R-1", "System", "T-2"],
    ["R-2", "Unit", "T-3"],
    ["R-9", "Unit", "T-1"],
    ["R-2", "Subsystem", "T-3"],
    ["", "", ""],
    ["R-3", "", ""],
]
TESTS = [
    ["Test ID", "Title", "Verifies"],
    ["T-1", "Export check", "R-1, R-3"],
    ["T-2", "Export UI", "R-1"],
    ["T-3", "List check", "R-2"],
]
SYSTEMS = [
    ["ID", "Type", "Name", "Requirements"],
    ["SYS-1", "System", "Reqtable", "R-1, R-2, R-3"],
]
MATRIX_NOTES = comments_xml(
    ["Pat Norman"],
    [("B2", 0, "<t>Confirm the level.</t>"), ("B5", 0, "<t>Unknown row.</t>")],
)

REQ_SOURCE = {"table": "Reqs", "columns": {"Req ID": "ID", "Text": "Requirement"}}
MATRIX_SOURCE = {
    "sheet": "Matrix",
    "merge": True,
    "columns": {
        "Requirement": "ID",
        "Level": "Verification Level",
        "Test": "Verified by",
    },
}
TEST_RECORDS = {
    "table": "Tests",
    "type": "Test",
    "columns": {"Test ID": "ID", "Title": "Name"},
    "exclude": ["Verifies"],
}
TEST_LINKS = {
    "table": "Tests",
    "merge": True,
    "columns": {"Verifies": "ID", "Test ID": "Verified by"},
    "exclude": ["Title"],
    "lists": {"ID": ","},
}
SYSTEM_SOURCE = {"sheet": "Systems", "exclude": ["Requirements"]}
ALLOCATIONS = {
    "sheet": "Systems",
    "merge": True,
    "columns": {"Requirements": "ID", "ID": "Allocated to"},
    "exclude": ["Type", "Name"],
    "lists": {"ID": ","},
}


def merge_workbook(path: Path) -> Path:
    """Hand-built workbook (synthetic, not Excel output): requirements, a verification matrix, tests and systems."""
    sheets = {
        "Reqs": ("Reqs", REQS, None),
        "Matrix": (None, MATRIX, MATRIX_NOTES),
        "Tests": ("Tests", TESTS, None),
        "Systems": (None, SYSTEMS, None),
    }
    workbook = "".join(
        f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>'
        for i, n in enumerate(sheets, 1)
    )
    parts = {
        "xl/workbook.xml": f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets>{workbook}</sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PACKAGE_REL}">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        + "</Relationships>",
    }
    for i, (name, (table, grid, notes)) in enumerate(sheets.items(), 1):
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(grid)
        rels = []
        if table:
            end = f"{chr(64 + len(grid[0]))}{len(grid)}"
            parts[f"xl/tables/table{i}.xml"] = (
                f'<table xmlns="{MAIN_NS}" name="{table}" displayName="{table}" ref="A1:{end}"/>'
            )
            rels.append(
                f'<Relationship Id="rId1" Type="table" Target="../tables/table{i}.xml"/>'
            )
        if notes:
            parts[f"xl/comments{i}.xml"] = notes
            rels.append(
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
                f'Target="../comments{i}.xml"/>'
            )
        if rels:
            parts[f"xl/worksheets/_rels/sheet{i}.xml.rels"] = (
                f'<Relationships xmlns="{PACKAGE_REL}">{"".join(rels)}</Relationships>'
            )
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    return path


class MergeSourceTests(MappingCase):
    def setUp(self) -> None:
        super().setUp()
        self.workbook = merge_workbook(self.root / "merge.xlsx")

    def rows(self, data: dict) -> dict[str, dict[str, str]]:
        return {row["ID"]: row for row in data["source"]["new"]["rows"]}

    def test_matrix_fills_in_requirements_without_adding_rows(self) -> None:
        code, err, data = self.report(self.workbook, [REQ_SOURCE, MATRIX_SOURCE])
        self.assertEqual(code, 0, err)
        rows = self.rows(data)
        self.assertEqual(list(rows), ["R-1", "R-2", "R-3"])
        self.assertEqual(
            data["source"]["new"]["headers"],
            ["ID", "Requirement", "Verification Level", "Verified by"],
        )
        self.assertEqual(
            (rows["R-1"]["Verification Level"], rows["R-1"]["Verified by"]),
            ("System", "T-1; T-2"),
        )
        self.assertEqual(
            (rows["R-2"]["Verification Level"], rows["R-2"]["Verified by"]),
            ("Unit", "T-3"),
        )
        self.assertEqual(
            (rows["R-3"]["Verification Level"], rows["R-3"]["Verified by"]), ("", "")
        )
        self.assertNotIn("duplicate ID", err)
        self.assertNotIn("ROW-", err)

    def test_unknown_ids_and_conflicts_warn_once_per_source(self) -> None:
        code, err, data = self.report(self.workbook, [REQ_SOURCE, MATRIX_SOURCE])
        self.assertEqual(code, 0, err)
        unknown = "merge.xlsx [Matrix]: 1 ID matches no record in 'ID'; ignored R-9"
        conflict = "merge.xlsx [Matrix]: 1 value differs from the record; R-2 Verification Level: kept 'Unit', ignored 'Subsystem'"
        dropped = "merge.xlsx [Reqs + Matrix]: dropped 1 Excel comment on heading rows, excluded columns or cells outside the imported block"
        self.assertEqual(data["meta"]["warnings"], [unknown, conflict, dropped])
        self.assertIn(f"warning: {unknown}", err)
        self.assertIn(f"warning: {conflict}", err)

    def test_matrix_comments_land_on_the_matched_requirement(self) -> None:
        code, err, data = self.report(self.workbook, [REQ_SOURCE, MATRIX_SOURCE])
        self.assertEqual(code, 0, err)
        self.assertEqual(
            [(c["requirementId"], c["column"], c["text"]) for c in data["comments"]],
            [("R-1", "Verification Level", "Confirm the level.")],
        )
        self.assertIn("merge.xlsx [Reqs + Matrix]: dropped 1 Excel comment", err)

    def test_tests_table_both_adds_tests_and_links_requirements(self) -> None:
        code, err, data = self.report(
            self.workbook, [REQ_SOURCE, TEST_RECORDS, TEST_LINKS], "--traceability"
        )
        self.assertEqual(code, 0, err)
        rows = self.rows(data)
        self.assertEqual(list(rows), ["R-1", "R-2", "R-3", "T-1", "T-2", "T-3"])
        self.assertEqual(
            [rows[r]["Verified by"] for r in ("R-1", "R-2", "R-3")],
            ["T-1; T-2", "T-3", "T-1"],
        )
        self.assertEqual(
            (rows["T-1"]["Type"], rows["T-1"]["Name"], rows["T-1"]["Verified by"]),
            ("Test", "Export check", ""),
        )
        self.assertEqual(data["meta"]["warnings"], [])

    def test_linked_workbook_has_no_trace_findings(self) -> None:
        sources = [REQ_SOURCE, TEST_RECORDS, SYSTEM_SOURCE, TEST_LINKS, ALLOCATIONS]
        code, err, data = self.report(self.workbook, sources, "--traceability")
        self.assertEqual(code, 0, err)
        source = data["source"]["new"]
        self.assertEqual(self.rows(data)["R-2"]["Allocated to"], "SYS-1")
        self.assertEqual(trace_findings(source["rows"], source["headers"], "ID"), [])
        _, _, untested = self.report(
            self.workbook,
            [REQ_SOURCE, SYSTEM_SOURCE, TEST_LINKS, ALLOCATIONS],
            "--traceability",
        )
        source = untested["source"]["new"]
        self.assertIn(
            "R-1|Verified by",
            {
                f"{f.id}|{f.field}"
                for f in trace_findings(source["rows"], source["headers"], "ID")
            },
        )

    def test_merged_import_exports_csv(self) -> None:
        exported = self.root / "out.csv"
        code, _, err = run_cli(
            str(self.workbook),
            "-c",
            self.config([REQ_SOURCE, MATRIX_SOURCE]),
            "-o",
            str(exported),
        )
        self.assertEqual(code, 0, err)
        with exported.open(encoding="utf-8-sig", newline="") as handle:
            table = list(csv.reader(handle))
        self.assertEqual(
            table[0], ["ID", "Requirement", "Verification Level", "Verified by"]
        )
        self.assertEqual(table[1], ["R-1", "Export CSV.", "System", "T-1; T-2"])
        self.assertEqual(len(table), 4)

    def test_list_columns_append_after_existing_values(self) -> None:
        reqs = {**REQ_SOURCE, "set": {"Verified by": "T-0; T-1"}}
        code, err, data = self.report(self.workbook, [reqs, MATRIX_SOURCE])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.rows(data)["R-1"]["Verified by"], "T-0; T-1; T-2")

    def test_a_comma_separated_record_cell_is_not_given_a_value_it_already_lists(
        self,
    ) -> None:
        reqs = {**REQ_SOURCE, "set": {"Verified by": "T-0, T-1"}}
        code, err, data = self.report(self.workbook, [reqs, MATRIX_SOURCE])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.rows(data)["R-1"]["Verified by"], "T-0, T-1; T-2")
        self.assertEqual(self.rows(data)["R-3"]["Verified by"], "T-0, T-1")

    def test_validation_errors_name_the_source(self) -> None:
        cases = [
            (
                {**MATRIX_SOURCE, "merge": "yes"},
                "xlsx.sources[1].merge must be true or false",
            ),
            (
                {**MATRIX_SOURCE, "type": "Test"},
                "xlsx.sources[1] is a merge source, which adds no records, so it cannot give type",
            ),
            ({**MATRIX_SOURCE, "id_prefix": "X-"}, "cannot give id_prefix"),
            (
                {**MATRIX_SOURCE, "id_prefix": "X-", "id_from": ["Level"]},
                "cannot give id_prefix, id_from",
            ),
            (
                {
                    **MATRIX_SOURCE,
                    "headings": {
                        "column": "Level",
                        "values": ["H"],
                        "into": "Category",
                    },
                },
                "cannot give headings",
            ),
            ({**MATRIX_SOURCE, "set": {"Type": "Test"}}, "cannot give set.Type"),
            (
                {**MATRIX_SOURCE, "columns": {"Level": "Verification Level"}},
                "xlsx source 'Matrix' is a merge source with no 'ID' column to match records by; "
                "columns: Requirement, Verification Level, Test",
            ),
        ]
        for source, message in cases:
            with self.subTest(message=message):
                code, err, _ = self.report(
                    self.workbook, [REQ_SOURCE, source], "--traceability"
                )
                self.assertEqual(code, 2)
                self.assertIn(message, err)
        code, err, _ = self.report(self.workbook, [MATRIX_SOURCE, TEST_LINKS])
        self.assertEqual(code, 2)
        self.assertIn("xlsx.sources: every source is a merge source", err)

    def test_merge_false_is_an_ordinary_source(self) -> None:
        code, err, data = self.report(self.workbook, [{**REQ_SOURCE, "merge": False}])
        self.assertEqual(code, 0, err)
        self.assertEqual(list(self.rows(data)), ["R-1", "R-2", "R-3"])
