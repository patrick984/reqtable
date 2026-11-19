from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from reqtable.core import ConfigError, validate_xlsx_sources
from test_xlsx_mapping import MAIN_NS, REL_NS, _sheet_xml, report_data, run_cli

PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
THREADED_NS = "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments"
HEADERS = ["Req ID", "Req Type", "Requirement", "Owner", "Category"]
SYSTEM = "System Requirement"

GRID = [
    HEADERS,
    ["", "Heading", "Safety", "", ""],
    ["R-1", SYSTEM, "Shall A.", "Ann", ""],
    ["R-2", SYSTEM, "Shall B.", "Bo", "Custom"],
    ["", "heading ", "Comms", "", ""],
    ["", SYSTEM, "Shall C.", "Cy", ""],
    ["", "", "", "", ""],
    ["R-1", SYSTEM, "Shall D.", "Di", ""],
    ["R-1", SYSTEM, "Shall E.", "Ed", ""],
]

SOURCES = [
    {
        "sheet": "Reqs",
        "columns": {"Req ID": "ID", "Requirement": "Text"},
        "exclude": ["Req Type"],
        "headings": {
            "column": "Req Type",
            "values": ["Heading"],
            "text": "Requirement",
            "into": "Category",
        },
    }
]


def comments_xml(authors: list[str], notes: list[tuple[str, int, str]]) -> str:
    people = "".join(f"<author>{a}</author>" for a in authors)
    items = "".join(
        f'<comment ref="{ref}" authorId="{who}"><text>{body}</text></comment>'
        for ref, who, body in notes
    )
    return f'<comments xmlns="{MAIN_NS}"><authors>{people}</authors><commentList>{items}</commentList></comments>'


def threaded_xml(items: list[tuple[str, str, str, str, str]]) -> str:
    body = "".join(
        f'<threadedComment ref="{ref}" dT="{when}" personId="{person}" id="{{{i}}}"'
        + (f' parentId="{{{parent}}}"' if parent else "")
        + f"><text>{text}</text></threadedComment>"
        for i, (ref, when, person, parent, text) in enumerate(items)
    )
    return f'<ThreadedComments xmlns="{THREADED_NS}">{body}</ThreadedComments>'


def write_workbook(
    path: Path,
    grid: list[list[str]] = GRID,
    notes: str | None = None,
    threaded: str | None = None,
    people: dict[str, str] | None = None,
    modified: str | None = None,
) -> Path:
    """Hand-built workbook (synthetic, not Excel output): one sheet 'Reqs' plus optional comment parts."""
    sheet_rels = []
    workbook_rels = [
        '<Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>'
    ]
    parts = {
        "xl/workbook.xml": f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets><sheet name="Reqs" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/worksheets/sheet1.xml": _sheet_xml(grid),
    }
    if notes:
        parts["xl/comments1.xml"] = notes
        sheet_rels.append(
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments1.xml"/>'
        )
    if threaded:
        parts["xl/threadedComments/threadedComment1.xml"] = threaded
        sheet_rels.append(
            '<Relationship Id="rId2" Type="http://schemas.microsoft.com/office/2017/10/relationships/threadedComment" Target="../threadedComments/threadedComment1.xml"/>'
        )
    if people:
        listed = "".join(
            f'<person displayName="{name}" id="{pid}" userId="u" providerId="None"/>'
            for pid, name in people.items()
        )
        parts["xl/persons/person.xml"] = (
            f'<personList xmlns="{THREADED_NS}">{listed}</personList>'
        )
        workbook_rels.append(
            '<Relationship Id="rId9" Type="http://schemas.microsoft.com/office/2017/10/relationships/person" Target="persons/person.xml"/>'
        )
    if sheet_rels:
        parts["xl/worksheets/_rels/sheet1.xml.rels"] = (
            f'<Relationships xmlns="{PACKAGE_REL}">{"".join(sheet_rels)}</Relationships>'
        )
    parts["xl/_rels/workbook.xml.rels"] = (
        f'<Relationships xmlns="{PACKAGE_REL}">{"".join(workbook_rels)}</Relationships>'
    )
    if modified:
        parts["docProps/core.xml"] = (
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dcterms="http://purl.org/dc/terms/"><dcterms:modified>'
            + modified
            + "</dcterms:modified></cp:coreProperties>"
        )
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    return path


def commented_workbook(path: Path) -> Path:
    notes = comments_xml(
        ["Patrick Norman", "Prince", ""],
        [
            (
                "C3",
                0,
                '<r><rPr><b/></rPr><t>Patrick Norman:</t></r><r><t xml:space="preserve">\nCheck </t></r><r><t>this</t></r>',
            ),
            ("A3", 1, "<t>On the ID.</t>"),
            ("B3", 1, "<t>Excluded column.</t>"),
            ("C2", 1, "<t>On a heading row.</t>"),
            ("H3", 1, "<t>Outside the table.</t>"),
            ("C6", 2, "<t>No ID here.</t>"),
            ("C8", 1, "<t>Second R-1.</t>"),
            ("D4", 0, "<t>[Threaded comment] placeholder</t>"),
        ],
    )
    threaded = threaded_xml(
        [
            ("D4", "2026-03-02T09:30:00.00", "p2", "", "Reply comes later."),
            ("D4", "2026-03-01T08:00:00.00", "p1", "", "Is Bo the owner?"),
        ]
    )
    return write_workbook(
        path,
        notes=notes,
        threaded=threaded,
        people={"p1": "Ann Lee", "p2": "Bo"},
        modified="2026-02-01T12:00:00Z",
    )


class ImportCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def config(self, sources: list[dict] | None = SOURCES, **extra: object) -> str:
        path = self.root / f"config{len(list(self.root.glob('config*.json')))}.json"
        body = {"id_column": "ID", **extra}
        if sources is not None:
            body["xlsx"] = {"sources": sources}
        path.write_text(json.dumps(body), encoding="utf-8")
        return str(path)

    def report(
        self,
        workbook: Path,
        *flags: str,
        sources: list[dict] | None = SOURCES,
        **extra: object,
    ) -> tuple[int, str, dict]:
        out = self.root / "report.html"
        out.unlink(missing_ok=True)
        code, _, err = run_cli(
            str(workbook), "-c", self.config(sources, **extra), *flags, "-o", str(out)
        )
        return code, err, report_data(out) if out.exists() else {}


class RepairTests(ImportCase):
    def test_headings_fill_category_and_leave_the_report_clean(self) -> None:
        workbook = write_workbook(self.root / "w.xlsx")
        code, err, data = self.report(workbook)
        self.assertEqual(code, 0, err)
        rows = data["source"]["new"]["rows"]
        self.assertEqual(
            [r["ID"] for r in rows], ["R-1", "R-2", "ROW-6", "R-1~2", "R-1~3"]
        )
        self.assertEqual(
            [r["Category"] for r in rows],
            ["Safety", "Custom", "Comms", "Comms", "Comms"],
        )
        self.assertNotIn("Req Type", data["source"]["new"]["headers"])
        self.assertEqual(rows[0]["Text"], "Shall A.")

    def test_missing_and_duplicate_ids_warn_in_stderr_and_the_report(self) -> None:
        workbook = write_workbook(self.root / "w.xlsx")
        code, err, data = self.report(workbook)
        self.assertEqual(code, 0, err)
        missing = "w.xlsx [Reqs]: 1 row has no ID in 'ID'; named it ROW-6"
        duplicate = "w.xlsx [Reqs]: duplicate ID 'R-1' at rows 3, 8, 9; renamed the later ones R-1~2, R-1~3"
        for message in (missing, duplicate):
            self.assertIn(f"warning: {message}", err)
            self.assertIn(message, data["meta"]["warnings"])

    def test_plain_sheet_import_repairs_ids_too(self) -> None:
        workbook = write_workbook(self.root / "w.xlsx")
        code, err, data = self.report(
            workbook, "--sheet", "Reqs", sources=None, id_column="Req ID"
        )
        self.assertEqual(code, 0, err)
        ids = [r["Req ID"] for r in data["source"]["new"]["rows"]]
        self.assertEqual(
            ids, ["ROW-2", "R-1", "R-2", "ROW-5", "ROW-6", "R-1~2", "R-1~3"]
        )
        self.assertIn(
            "3 rows have no ID in 'Req ID'; named them ROW-2, ROW-5, ROW-6", err
        )

    def test_suffix_skips_a_value_already_taken(self) -> None:
        grid = [["ID", "Text"], ["A", "1"], ["A", "2"], ["A~2", "3"]]
        code, err, data = self.report(
            write_workbook(self.root / "w.xlsx", grid), "--sheet", "Reqs", sources=None
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            [r["ID"] for r in data["source"]["new"]["rows"]], ["A", "A~3", "A~2"]
        )

    def test_csv_input_stays_strict(self) -> None:
        source = self.root / "in.csv"
        source.write_text("ID,Text\nR1,a\nR1,b\n", encoding="utf-8")
        code, _, err = run_cli(
            str(source), "--id-column", "ID", "-o", str(self.root / "r.html")
        )
        self.assertEqual(code, 3)
        self.assertIn("duplicate ID", err)
        source.write_text("ID,Text\n,a\n", encoding="utf-8")
        self.assertEqual(
            run_cli(str(source), "--id-column", "ID", "-o", str(self.root / "r.html"))[
                0
            ],
            3,
        )

    def test_two_workbooks_with_repaired_ids_diff_line_up(self) -> None:
        old = write_workbook(self.root / "old.xlsx")
        edited = [list(row) for row in GRID]
        edited[7][2] = "Shall D, revised."
        new = write_workbook(self.root / "new.xlsx", edited)
        out = self.root / "diff.html"
        code, _, err = run_cli(
            "--old", str(old), "--new", str(new), "-c", self.config(), "-o", str(out)
        )
        self.assertEqual(code, 0, err)
        data = report_data(out)
        self.assertEqual(
            data["meta"]["counts"],
            {"added": 0, "removed": 0, "changed": 1, "unchanged": 4},
        )
        self.assertEqual(sum("duplicate ID" in w for w in data["meta"]["warnings"]), 2)

    def test_csv_export_prints_the_warnings(self) -> None:
        exported = self.root / "out.csv"
        code, _, err = run_cli(
            str(write_workbook(self.root / "w.xlsx")),
            "-c",
            self.config(),
            "-o",
            str(exported),
        )
        self.assertEqual(code, 0, err)
        self.assertIn("warning: w.xlsx [Reqs]: duplicate ID 'R-1'", err)
        self.assertIn("R-1~3", exported.read_text(encoding="utf-8-sig"))

    def test_heading_text_defaults_to_the_first_other_cell(self) -> None:
        sources = [
            {
                **SOURCES[0],
                "headings": {
                    "column": "Req Type",
                    "values": ["Heading"],
                    "into": "Category",
                },
            }
        ]
        grid = [
            HEADERS,
            ["", "Heading", "", "Zed", ""],
            ["R-1", SYSTEM, "Shall A.", "Ann", ""],
        ]
        code, err, data = self.report(
            write_workbook(self.root / "w.xlsx", grid), sources=sources
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(data["source"]["new"]["rows"][0]["Category"], "Zed")

    def test_headings_config_errors(self) -> None:
        bad = [
            "x",
            {},
            {"column": "Req Type", "values": ["Heading"]},
            {"column": "Req Type", "values": [], "into": "C"},
            {"column": "Req Type", "values": "Heading", "into": "C"},
            {
                "column": "Req Type",
                "values": ["H"],
                "into": "C",
                "texts": "Requirement",
            },
        ]
        for headings in bad:
            with (
                self.subTest(headings=headings),
                self.assertRaises(ConfigError) as caught,
            ):
                validate_xlsx_sources([{"sheet": "Reqs", "headings": headings}])
            self.assertIn("xlsx.sources[0].headings", str(caught.exception))
        workbook = write_workbook(self.root / "w.xlsx")
        for key in ("column", "text"):
            sources = [
                {**SOURCES[0], "headings": {**SOURCES[0]["headings"], key: "Nope"}}
            ]
            code, err, _ = self.report(workbook, sources=sources)
            self.assertEqual(code, 2)
            self.assertIn("no column 'Nope'", err)
            self.assertIn("Req Type", err)


class CommentTests(ImportCase):
    def imported(self, **extra: object) -> tuple[str, dict, list[dict]]:
        code, err, data = self.report(commented_workbook(self.root / "c.xlsx"), **extra)
        self.assertEqual(code, 0, err)
        return err, data, data["comments"]

    def test_notes_and_threaded_comments_land_on_the_repaired_id_and_column(
        self,
    ) -> None:
        _, _, comments = self.imported()
        by_cell = {(c["requirementId"], c["column"]): [] for c in comments}
        for c in comments:
            by_cell[(c["requirementId"], c["column"])].append(c)
        self.assertEqual(
            set(by_cell),
            {("R-1", "Text"), ("R-2", "Owner"), ("ROW-6", "Text"), ("R-1~2", "Text")},
        )
        note = [
            c for c in by_cell[("R-1", "Text")] if not c["text"].startswith("[on ID]")
        ]
        self.assertEqual(
            [(c["initials"], c["text"], c["created"], c["modified"]) for c in note],
            [("PN", "Check this", "2026-02-01T12:00:00Z", None)],
        )
        self.assertEqual(
            [
                (c["initials"], c["text"], c["created"])
                for c in by_cell[("R-2", "Owner")]
            ],
            [
                ("AL", "Is Bo the owner?", "2026-03-01T08:00:00.00"),
                ("BO", "Reply comes later.", "2026-03-02T09:30:00.00"),
            ],
        )
        self.assertEqual(by_cell[("ROW-6", "Text")][0]["initials"], "XL")
        self.assertEqual(
            sorted(c["id"] for c in comments),
            [f"xlsx-{n}" for n in range(1, len(comments) + 1)],
        )

    def test_id_column_comments_move_and_dropped_ones_are_counted(self) -> None:
        err, data, comments = self.imported()
        moved = [c for c in comments if c["text"].startswith("[on ID]")]
        self.assertEqual(
            [
                (c["requirementId"], c["column"], c["initials"], c["text"])
                for c in moved
            ],
            [("R-1", "Text", "PR", "[on ID] On the ID.")],
        )
        self.assertEqual(len(comments), 6)
        self.assertNotIn("Excluded column", json.dumps(comments))
        self.assertNotIn("On a heading row", json.dumps(comments))
        self.assertNotIn("placeholder", json.dumps(comments))
        warning = "c.xlsx [Reqs]: dropped 3 Excel comments on heading rows, excluded columns or cells outside the imported block"
        self.assertIn(f"warning: {warning}", err)
        self.assertIn(warning, data["meta"]["warnings"])

    def test_comments_disabled_imports_none(self) -> None:
        err, data, comments = self.imported(comments={"enabled": False})
        self.assertEqual(comments, [])
        self.assertNotIn("Excel comment", err)

    def test_traceability_report_gets_them_too(self) -> None:
        code, err, data = self.report(
            commented_workbook(self.root / "c.xlsx"), "--traceability"
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(len(data["comments"]), 6)

    def test_diff_keeps_old_side_comments_only_for_ids_not_in_new(self) -> None:
        old = commented_workbook(self.root / "old.xlsx")
        grid = [row for row in GRID if row[0] != "R-2"]
        new = write_workbook(
            self.root / "new.xlsx",
            grid,
            notes=comments_xml(["Zoe Q"], [("C3", 0, "<t>New side.</t>")]),
        )
        out = self.root / "diff.html"
        code, _, err = run_cli(
            "--old", str(old), "--new", str(new), "-c", self.config(), "-o", str(out)
        )
        self.assertEqual(code, 0, err)
        comments = report_data(out)["comments"]
        new_side = [c for c in comments if not c["id"].startswith("old-")]
        self.assertEqual(
            [(c["requirementId"], c["initials"]) for c in new_side], [("R-1", "ZQ")]
        )
        old_ids = {c["requirementId"] for c in comments if c["id"].startswith("old-")}
        self.assertEqual(old_ids, {"R-2", "ROW-6"})

    def test_plain_sheet_import_keeps_every_column_and_drops_cells_outside(
        self,
    ) -> None:
        # No mapping excludes columns or headings, so only the cell outside the block is dropped.
        workbook = commented_workbook(self.root / "c.xlsx")
        code, err, data = self.report(
            workbook, "--sheet", "Reqs", sources=None, id_column="Req ID"
        )
        self.assertEqual(code, 0, err)
        cells = {(c["requirementId"], c["column"]) for c in data["comments"]}
        self.assertIn(("R-1", "Req Type"), cells)
        self.assertIn(("ROW-2", "Requirement"), cells)
        self.assertIn("dropped 1 Excel comment ", err)


if __name__ == "__main__":
    unittest.main()
