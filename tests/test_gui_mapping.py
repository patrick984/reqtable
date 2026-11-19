from __future__ import annotations

import json
import re
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from reqtable.core import RECORD_TYPES
from reqtable.gui import BadRequest, GuiError
from reqtable.gui_mapping import (
    FIELD_CHOICES,
    ROLES,
    HeadingRows,
    build_mapping,
    form_from_mapping,
    load_mapping,
    preview_mapping,
    role_named,
    save_mapping,
    suggest_columns,
)
from reqtable.xlsx import Workbook, XlsxSelection, import_workbook
from test_xlsx_import import GRID, HEADERS, SOURCES, write_workbook
from test_xlsx_merge import merge_workbook
from test_xlsx_mapping import lookup_workbook, report_data, run_cli

EXCEL_DOC = Path(__file__).resolve().parent.parent / "docs" / "excel.md"


def documented_mappings() -> list[dict[str, object]]:
    blocks = re.findall(
        r"```json\n(.*?)\n```", EXCEL_DOC.read_text(encoding="utf-8"), re.S
    )
    return [
        json.loads(block)
        for block in blocks
        if '"xlsx"' in block and '"sources"' in block
    ]


def source(
    kind: str,
    name: str,
    role: str,
    columns: list[tuple[str, str, str, str]],
    **extra: object,
) -> dict[str, object]:
    return {
        "kind": kind,
        "name": name,
        "role": role,
        "columns": [
            {"header": header, "action": action, "to": to, "separator": sep}
            for header, action, to, sep in columns
        ],
        **extra,
    }


class RoleTests(unittest.TestCase):
    def test_every_role_type_is_a_record_type(self) -> None:
        for role in ROLES:
            self.assertTrue(role.type is None or role.type in RECORD_TYPES, role.id)
        self.assertEqual(
            [r.id for r in ROLES if r.type is None], ["requirements", "merge"]
        )
        self.assertEqual([r.id for r in ROLES if r.merge], ["merge"])

    def test_roles_are_distinct_and_every_role_can_carry_an_id_and_a_name(self) -> None:
        self.assertEqual(len({r.id for r in ROLES}), len(ROLES))
        self.assertEqual(len({r.type for r in ROLES}), len(ROLES) - 1)
        for role in ROLES:
            columns = [t.column for t in role.targets]
            self.assertEqual(len(columns), len(set(columns)), role.id)
            self.assertIn("ID", columns, role.id)
            self.assertTrue(role.help.endswith("."), role.id)
            self.assertTrue(all(t.label for t in role.targets), role.id)
            self.assertEqual(bool(role.id_prefix), role.type is not None, role.id)
        self.assertEqual([r.id for r in ROLES if r.needs_field], ["values"])
        for role in ROLES:
            if role.id not in ("values", "requirements", "merge"):
                self.assertIn("Name", [t.column for t in role.targets], role.id)

    def test_tests_describe_into_requirement_and_plans_and_terms_use_their_own_columns(
        self,
    ) -> None:
        def label(role: str, column: str) -> str:
            return next(t.label for t in role_named(role).targets if t.column == column)

        self.assertEqual(label("tests", "Requirement"), "Description")
        self.assertEqual(label("plans", "Requirement"), "Description")
        self.assertEqual(label("glossary", "Definition"), "Meaning")
        self.assertIn("Test plan", [t.column for t in role_named("tests").targets])

    def test_verification_levels_are_offered_as_stages_and_as_an_allowed_value_field(
        self,
    ) -> None:
        requirement = next(
            t
            for t in role_named("requirements").targets
            if t.column == "Verification Level"
        )
        self.assertIn("verification stages", requirement.label)
        self.assertTrue(requirement.list_separator)
        self.assertIn(
            ("Verification Level", "Verification Level (verification stages)"),
            FIELD_CHOICES,
        )

    def test_unknown_roles_are_bad_requests(self) -> None:
        with self.assertRaises(BadRequest):
            role_named("nope")


class SuggestTests(unittest.TestCase):
    def pairs(self, role: str, headers: list[str]) -> dict[str, str]:
        found = suggest_columns(role_named(role), headers)["columns"]
        return {c["header"]: c["to"] or "-" for c in found}  # type: ignore[index]

    def test_headers_named_after_a_target_or_its_label_are_matched_case_insensitively(
        self,
    ) -> None:
        self.assertEqual(
            self.pairs("glossary", ["Term", "meaning", "Abbreviation", "Notes"]),
            {
                "Term": "Name",
                "meaning": "Definition",
                "Abbreviation": "Aliases",
                "Notes": "-",
            },
        )
        self.assertEqual(
            self.pairs("tests", ["Test ID", "Title", "Plan", "Method", "Owner"]),
            {
                "Test ID": "ID",
                "Title": "Name",
                "Plan": "Test plan",
                "Method": "Verification Method",
                "Owner": "-",
            },
        )
        self.assertEqual(
            self.pairs("requirements", ["verification level", "ID"]),
            {"verification level": "Verification Level", "ID": "ID"},
        )

    def test_a_target_is_used_once_and_list_targets_get_a_separator(self) -> None:
        found = suggest_columns(role_named("requirements"), ["Tests", "Verified by"])[
            "columns"
        ]
        self.assertEqual([c["to"] for c in found], ["Verified by", ""])  # type: ignore[index]
        self.assertEqual([c["separator"] for c in found], [",", ""])  # type: ignore[index]

    def test_the_id_prefix_is_offered_only_when_no_column_is_the_id(self) -> None:
        self.assertEqual(
            suggest_columns(role_named("glossary"), ["Term", "Meaning"])["id_prefix"],
            "TERM-",
        )
        self.assertEqual(
            suggest_columns(role_named("glossary"), ["Term ID", "Term"])["id_prefix"],
            "",
        )
        self.assertEqual(
            suggest_columns(role_named("requirements"), ["Text"])["id_prefix"], ""
        )


class BuildMappingTests(unittest.TestCase):
    def test_a_glossary_sheet_becomes_a_term_source(self) -> None:
        form = {
            "sources": [
                source(
                    "sheet",
                    "Glossary",
                    "glossary",
                    [
                        ("Term", "map", "Name", ""),
                        ("Meaning", "map", "Definition", ""),
                        ("Abbreviation", "map", "Aliases", ";"),
                        ("Notes", "exclude", "", ""),
                    ],
                    header_row=2,
                    id_prefix="TERM-",
                ),
            ]
        }
        self.assertEqual(
            build_mapping(form),
            {
                "id_column": "ID",
                "traceability": True,
                "xlsx": {
                    "sources": [
                        {
                            "sheet": "Glossary",
                            "header_row": 2,
                            "type": "Term",
                            "id_prefix": "TERM-",
                            "columns": {
                                "Term": "Name",
                                "Meaning": "Definition",
                                "Abbreviation": "Aliases",
                            },
                            "exclude": ["Notes"],
                            "lists": {"Aliases": ";"},
                        }
                    ]
                },
            },
        )

    def test_requirements_keep_their_own_type_and_the_id_column_follows_the_form(
        self,
    ) -> None:
        form = {
            "id_column": "Req ID",
            "sources": [
                source(
                    "table",
                    "Reqs",
                    "requirements",
                    [
                        ("Req ID", "map", "ID", ""),
                        ("Text", "map", "Requirement", ""),
                        ("Tests", "map", "Verified by", "newline"),
                    ],
                ),
            ],
        }
        built = build_mapping(form)["xlsx"]["sources"][0]  # type: ignore[index]
        self.assertEqual(
            built,
            {
                "table": "Reqs",
                "columns": {"Text": "Requirement", "Tests": "Verified by"},
                "lists": {"Verified by": "newline"},
            },
        )
        self.assertNotIn("type", built)
        self.assertEqual(build_mapping(form)["id_column"], "Req ID")

    def test_allowed_values_need_a_field_unless_a_column_supplies_it(self) -> None:
        columns = [("Value", "map", "Name", ""), ("Meaning", "map", "Definition", "")]
        with self.assertRaisesRegex(GuiError, "which column these values are for"):
            build_mapping(
                {
                    "sources": [
                        source(
                            "sheet", "Priorities", "values", columns, id_prefix="VAL-"
                        )
                    ]
                }
            )
        built = build_mapping(
            {
                "sources": [
                    source(
                        "sheet",
                        "Priorities",
                        "values",
                        columns,
                        field="Priority",
                        id_prefix="VAL-",
                    )
                ]
            }
        )
        self.assertEqual(built["xlsx"]["sources"][0]["set"], {"Field": "Priority"})  # type: ignore[index]
        with_column = [*columns, ("Column", "map", "Field", "")]
        for field in ("Priority", ""):
            built = build_mapping(
                {
                    "sources": [
                        source("sheet", "Lists", "values", with_column, field=field)
                    ]
                }
            )
            self.assertNotIn("set", built["xlsx"]["sources"][0])  # type: ignore[index]

    def test_sources_without_a_role_are_left_out_and_at_least_one_is_needed(
        self,
    ) -> None:
        skipped = source("table", "Other", "", [])
        with self.assertRaisesRegex(GuiError, "at least one"):
            build_mapping({"sources": [skipped]})
        built = build_mapping(
            {"sources": [skipped, source("table", "Reqs", "requirements", [])]}
        )
        self.assertEqual([s["table"] for s in built["xlsx"]["sources"]], ["Reqs"])  # type: ignore[index]

    def test_two_columns_to_one_target_and_an_unchosen_target_are_explained(
        self,
    ) -> None:
        clash = [("A", "map", "Name", ""), ("B", "map", "Name", "")]
        with self.assertRaisesRegex(GuiError, "more than one column goes to 'Name'"):
            build_mapping({"sources": [source("table", "T", "systems", clash)]})
        with self.assertRaisesRegex(GuiError, "choose where 'A' goes"):
            build_mapping(
                {"sources": [source("table", "T", "systems", [("A", "map", "", "")])]}
            )

    def test_a_malformed_form_is_a_bad_request(self) -> None:
        for form in (
            {},
            {"sources": "x"},
            {"sources": [{"kind": "cell", "name": "x"}]},
            {"sources": [{"kind": "table"}]},
            {"sources": [{"kind": "table", "name": "T", "role": "nope"}]},
            {"sources": [source("table", "T", "systems", [])], "extra": 3},
        ):
            with self.subTest(form=form), self.assertRaises(BadRequest):
                build_mapping(form)  # type: ignore[arg-type]

    def test_the_result_is_checked_the_way_the_importer_checks_it(self) -> None:
        with self.assertRaisesRegex(GuiError, "header_row"):
            build_mapping(
                {"sources": [source("sheet", "S", "systems", [], header_row=0)]}
            )


class MergeRoleTests(unittest.TestCase):
    def test_prefill_keys_on_the_requirement_a_row_points_to(self) -> None:
        def targets(headers: list[str]) -> dict[str, str]:
            return {
                c["header"]: c["to"]
                for c in suggest_columns(role_named("merge"), headers)["columns"]
            }

        self.assertEqual(
            targets(["Requirement", "Level", "Test"]),
            {"Requirement": "ID", "Level": "Verification Level", "Test": "Verified by"},
        )
        self.assertEqual(
            targets(["Test ID", "Title", "Verifies"]),
            {"Test ID": "Verified by", "Title": "", "Verifies": "ID"},
        )
        self.assertEqual(
            targets(["Req ID", "Stage"]),
            {"Req ID": "ID", "Stage": "Verification Level"},
        )
        self.assertEqual(targets(["ID", "Stage"])["ID"], "ID")

    def test_a_merge_prefill_leaves_out_columns_that_match_nothing(self) -> None:
        found = suggest_columns(role_named("merge"), ["Test ID", "Title", "Verifies"])[
            "columns"
        ]
        self.assertEqual(
            {c["header"]: c["action"] for c in found},
            {"Test ID": "map", "Title": "exclude", "Verifies": "map"},
        )
        with tempfile.TemporaryDirectory() as directory:
            book = merge_workbook(Path(directory) / "merge.xlsx")
            form = {
                "sources": [
                    source(
                        "table",
                        "Reqs",
                        "requirements",
                        [
                            ("Req ID", "map", "ID", ""),
                            ("Text", "map", "Requirement", ""),
                        ],
                    ),
                    {
                        "kind": "table",
                        "name": "Tests",
                        "role": "merge",
                        "columns": found,
                    },
                ]
            }
            mapping = build_mapping(form)
            imported = import_workbook(
                book, XlsxSelection(), mapping["xlsx"]["sources"], "ID", True, False
            )  # type: ignore[index]
        self.assertEqual(imported.block.rows[0], ["ID", "Requirement", "Verified by"])

    def test_a_merge_source_emits_merge_and_a_list_of_ids(self) -> None:
        form = {
            "sources": [
                source(
                    "table",
                    "TestCases",
                    "tests",
                    [("Test ID", "map", "ID", ""), ("Title", "map", "Name", "")],
                ),
                source(
                    "table",
                    "TestCases",
                    "merge",
                    [
                        ("Verifies", "map", "ID", ","),
                        ("Test ID", "map", "Verified by", ""),
                        ("Level", "map", "Verification Level", ";"),
                        ("Notes", "keep", "", ""),
                    ],
                    id_prefix="IGNORED-",
                ),
            ]
        }
        built = build_mapping(form)["xlsx"]["sources"]  # type: ignore[index]
        self.assertEqual(
            built[1],
            {
                "table": "TestCases",
                "merge": True,
                "columns": {
                    "Verifies": "ID",
                    "Test ID": "Verified by",
                    "Level": "Verification Level",
                },
                "lists": {"ID": ",", "Verification Level": ";"},
            },
        )
        self.assertNotIn("merge", built[0])

    def test_the_id_column_name_is_used_for_the_merge_key(self) -> None:
        form = {
            "id_column": "Req ID",
            "sources": [
                source("table", "Reqs", "requirements", [("Req ID", "map", "ID", "")]),
                source(
                    "sheet",
                    "Matrix",
                    "merge",
                    [
                        ("Requirement", "map", "ID", ""),
                        ("Level", "map", "Verification Level", ""),
                    ],
                ),
            ],
        }
        built = build_mapping(form)["xlsx"]["sources"][1]  # type: ignore[index]
        self.assertEqual(
            built["columns"], {"Requirement": "Req ID", "Level": "Verification Level"}
        )

    def test_a_merge_source_must_say_which_column_holds_the_id(self) -> None:
        with self.assertRaisesRegex(GuiError, "which column holds the requirement ID"):
            build_mapping(
                {
                    "sources": [
                        source(
                            "sheet",
                            "Matrix",
                            "merge",
                            [("Level", "map", "Verification Level", "")],
                        )
                    ]
                }
            )

    def test_a_merge_source_round_trips_through_the_form(self) -> None:
        mapping = {
            "id_column": "ID",
            "traceability": True,
            "xlsx": {
                "sources": [
                    {"table": "Reqs", "columns": {"Req ID": "ID"}},
                    {
                        "sheet": "Matrix",
                        "merge": True,
                        "columns": {"Reqs": "ID", "Stage": "Verification Level"},
                        "lists": {"ID": ","},
                    },
                ]
            },
        }
        form, notes = form_from_mapping(mapping)
        self.assertEqual((notes, form["sources"][1]["role"]), ([], "merge"))
        self.assertEqual(build_mapping(form), mapping)

    def test_the_same_table_can_be_added_twice_with_different_roles(self) -> None:
        both = {
            "sources": [
                source("table", "T", "tests", [("ID", "keep", "", "")]),
                source("table", "T", "merge", [("Verifies", "map", "ID", ",")]),
            ]
        }
        self.assertEqual(len(build_mapping(both)["xlsx"]["sources"]), 2)  # type: ignore[index]


HEADING_FORM = {
    "column": "Req Type",
    "values": ["Heading"],
    "text": "Requirement",
    "into": "Category",
}


def heading_source(
    headings: object = HEADING_FORM, **extra: object
) -> dict[str, object]:
    return source(
        "sheet",
        "Reqs",
        "requirements",
        [
            ("Req ID", "map", "ID", ""),
            ("Req Type", "exclude", "", ""),
            ("Requirement", "map", "Text", ""),
        ],
        headings=headings,
        **extra,
    )


class HeadingRowsTests(unittest.TestCase):
    def test_only_the_requirements_role_offers_heading_rows(self) -> None:
        self.assertEqual([r.id for r in ROLES if r.headings], ["requirements"])

    def test_the_form_builds_the_documented_headings_key(self) -> None:
        built = build_mapping({"sources": [heading_source()]})["xlsx"]["sources"][0]  # type: ignore[index]
        self.assertEqual(
            built, SOURCES[0] | {"columns": {"Req ID": "ID", "Requirement": "Text"}}
        )
        self.assertEqual(built["headings"], HEADING_FORM)

    def test_text_is_left_out_when_empty_and_values_are_trimmed(self) -> None:
        form = {
            "column": "Req Type",
            "values": [" Heading ", "", "Section"],
            "text": "",
            "into": "Category",
        }
        built = build_mapping({"sources": [heading_source(headings=form)]})["xlsx"][
            "sources"
        ][0]  # type: ignore[index]
        self.assertEqual(
            built["headings"],
            {
                "column": "Req Type",
                "values": ["Heading", "Section"],
                "into": "Category",
            },
        )

    def test_missing_pieces_are_explained(self) -> None:
        for change, message in (
            ({"column": ""}, "which column marks a heading row"),
            ({"values": [" "]}, "which value in 'Req Type'"),
            ({"into": ""}, "which column receives the category"),
        ):
            with self.subTest(change=change), self.assertRaisesRegex(GuiError, message):
                build_mapping(
                    {"sources": [heading_source(headings={**HEADING_FORM, **change})]}
                )

    def test_a_role_without_heading_rows_rejects_them(self) -> None:
        for role in ("glossary", "tests", "merge", "values"):
            with self.subTest(role=role), self.assertRaises(BadRequest):
                build_mapping(
                    {
                        "sources": [
                            source(
                                "sheet",
                                "S",
                                role,
                                [("ID", "keep", "", "")],
                                headings=HEADING_FORM,
                            )
                        ]
                    }
                )

    def test_a_malformed_headings_shape_is_a_bad_request(self) -> None:
        for bad in (
            "Heading",
            {**HEADING_FORM, "values": "Heading"},
            {**HEADING_FORM, "column": 5},
        ):
            with self.subTest(bad=bad), self.assertRaises(BadRequest):
                build_mapping({"sources": [heading_source(headings=bad)]})

    def test_the_readme_example_round_trips_through_the_typed_form(self) -> None:
        mapping = {
            "id_column": "ID",
            "traceability": True,
            "xlsx": {"sources": SOURCES},
        }
        form, notes = form_from_mapping(mapping)
        self.assertEqual(notes, [])
        self.assertEqual(form["sources"][0]["headings"], HEADING_FORM)
        self.assertEqual(form["sources"][0]["extra"], {})
        self.assertEqual(build_mapping(form), mapping)

    def test_malformed_headings_stay_as_they_are_with_a_note(self) -> None:
        for bad in (
            {"column": "T"},
            {"column": "T", "values": [], "into": "C"},
            "Heading",
        ):
            mapping = {"xlsx": {"sources": [{"sheet": "S", "headings": bad}]}}
            with self.subTest(bad=bad):
                form, notes = form_from_mapping(mapping)
                self.assertIsNone(form["sources"][0]["headings"])
                self.assertEqual(form["sources"][0]["extra"], {"headings": bad})
                self.assertTrue(any("headings" in n for n in notes))

    def test_heading_rows_on_another_role_stay_untouched(self) -> None:
        mapping = {
            "xlsx": {
                "sources": [{"sheet": "S", "type": "Term", "headings": HEADING_FORM}]
            }
        }
        form, notes = form_from_mapping(mapping)
        self.assertEqual(form["sources"][0]["extra"], {"headings": HEADING_FORM})
        self.assertTrue(any("headings" in n for n in notes))

    def test_the_dataclass_matches_the_json_shape(self) -> None:
        self.assertEqual(HeadingRows.from_json(HEADING_FORM).to_json(), HEADING_FORM)


class HeadingPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.book = write_workbook(Path(directory.name) / "w.xlsx")

    def preview(
        self, headings: dict[str, object] | None = HEADING_FORM
    ) -> dict[str, object]:
        form = {"sources": [heading_source(headings=headings)]}
        return preview_mapping(self.book, build_mapping(form))

    def test_categories_come_in_order_with_their_counts_and_the_removed_heading_rows(
        self,
    ) -> None:
        found = self.preview()["sources"][0]  # type: ignore[index]
        self.assertEqual(found["rows"], 5)
        self.assertEqual(
            found["headings"],
            {
                "removed": 2,
                "categories": [
                    {"name": "Safety", "count": 1},
                    {"name": "Custom", "count": 1},
                    {"name": "Comms", "count": 3},
                ],
                "uncategorised": 0,
                "warning": None,
            },
        )

    def test_rows_above_the_first_heading_are_counted_apart(self) -> None:
        grid = [HEADERS, ["R-0", "System Requirement", "Shall Z.", "", ""], *GRID[1:3]]
        book = write_workbook(self.book.parent / "x.xlsx", grid)
        found = preview_mapping(book, build_mapping({"sources": [heading_source()]}))[
            "sources"
        ][0]["headings"]  # type: ignore[index]
        self.assertEqual(
            (found["uncategorised"], found["categories"], found["removed"]),
            (1, [{"name": "Safety", "count": 1}], 1),
        )

    def test_a_marker_no_row_uses_warns_in_plain_words(self) -> None:
        found = self.preview({**HEADING_FORM, "values": ["Section"]})["sources"][0][
            "headings"
        ]  # type: ignore[index]
        self.assertEqual(found["removed"], 0)
        self.assertEqual(found["warning"], "No row in 'Req Type' says Section.")

    def test_counts_and_categories_come_from_one_import(self) -> None:
        opened = []
        real = Workbook.open.__func__  # type: ignore[attr-defined]

        def counting(cls: type[Workbook], path: object) -> Workbook:
            opened.append(path)
            return real(cls, path)

        form = {
            "sources": [
                heading_source(),
                heading_source(None),
                source("sheet", "Reqs", "merge", [("Req ID", "map", "ID", "")]),
            ]
        }
        with mock.patch.object(Workbook, "open", classmethod(counting)):
            found = preview_mapping(self.book, build_mapping(form))
        self.assertEqual(len(opened), 1)
        self.assertEqual([s["rows"] for s in found["sources"]], [5, 7, None])  # type: ignore[index]
        self.assertEqual(found["sources"][0]["headings"]["removed"], 2)  # type: ignore[index]

    def test_sources_without_headings_have_none(self) -> None:
        self.assertNotIn("headings", self.preview(None)["sources"][0])  # type: ignore[index]


class LoadMappingTests(unittest.TestCase):
    def test_every_documented_mapping_round_trips_through_the_form(self) -> None:
        mappings = documented_mappings()
        self.assertGreaterEqual(len(mappings), 2)
        for mapping in mappings:
            form, notes = form_from_mapping(mapping)
            self.assertEqual(notes, [])
            self.assertEqual(build_mapping(form), {**mapping, "traceability": True})

    def test_what_the_form_cannot_show_is_kept_and_reported(self) -> None:
        mapping = {
            "id_column": "ID",
            "title": "Mine",
            "xlsx": {
                "note": 1,
                "sources": [
                    {
                        "sheet": "Heads",
                        "headings": {"column": "T", "values": ["H"], "into": "Cat"},
                        "id_from": ["Name"],
                        "id_prefix": "X-",
                        "set": {"Origin": "Excel"},
                        "type": "Term",
                    },
                    {"table": "Fields", "type": "Field", "set": {"Multiple": "Yes"}},
                ],
            },
        }
        form, notes = form_from_mapping(mapping)
        self.assertIn("Kept as it is, not editable here: title", notes)
        self.assertIn("Kept as it is, not editable here: xlsx.note", notes)
        self.assertTrue(any("headings" in n for n in notes))
        self.assertTrue(any("'Fields'" in n and "kept exactly" in n for n in notes))
        rebuilt = build_mapping(form)
        self.assertEqual(rebuilt["title"], "Mine")
        self.assertEqual(rebuilt["xlsx"]["note"], 1)  # type: ignore[index]
        self.assertEqual(rebuilt["xlsx"]["sources"][1], mapping["xlsx"]["sources"][1])  # type: ignore[index]
        edited = rebuilt["xlsx"]["sources"][0]  # type: ignore[index]
        self.assertEqual(
            (edited["headings"], edited["id_from"], edited["set"]),
            (mapping["xlsx"]["sources"][0]["headings"], ["Name"], {"Origin": "Excel"}),
        )  # type: ignore[index]

    def test_files_that_are_not_a_workbook_mapping_are_explained(self) -> None:
        for bad in (
            [],
            {"xlsx": {"sources": []}},
            {"xlsx": {"sources": [{"table": "a", "sheet": "b"}]}},
            {},
        ):
            with self.subTest(bad=bad), self.assertRaises(GuiError):
                form_from_mapping(bad)


class WorkbookRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.book = self.root / "book.xlsx"
        lookup_workbook(self.book)

    def headers(self, kind: str, name: str) -> list[str]:
        with Workbook.open(self.book) as wb:
            if kind == "table":
                table = wb.table_named(name)
                from reqtable.xlsx import _table_block

                return _table_block(wb, table).rows[0]
            from reqtable.xlsx import _sheet_block

            return _sheet_block(wb, wb.sheet_named(name), None).rows[0]

    def prefilled(
        self, kind: str, name: str, role: str, **extra: object
    ) -> dict[str, object]:
        found = suggest_columns(role_named(role), self.headers(kind, name))
        return {
            "kind": kind,
            "name": name,
            "role": role,
            "columns": found["columns"],
            "id_prefix": found["id_prefix"],
            **extra,
        }

    def form(self) -> dict[str, object]:
        systems = self.prefilled("sheet", "Systems", "systems")
        systems["columns"] = [
            {"header": "System", "action": "map", "to": "Name", "separator": ""}
        ]
        return {
            "sources": [
                self.prefilled("table", "Reqs", "requirements"),
                self.prefilled("sheet", "Priorities", "values", field="Priority"),
                self.prefilled("sheet", "Lists", "values"),
                self.prefilled("table", "TestCases", "tests"),
                self.prefilled("table", "Plans", "plans"),
                systems,
            ]
        }

    def test_the_prefilled_form_builds_the_documented_mapping(self) -> None:
        sources = build_mapping(self.form())["xlsx"]["sources"]  # type: ignore[index]
        self.assertEqual(
            sources[0],
            {
                "table": "Reqs",
                "columns": {
                    "Req ID": "ID",
                    "Text": "Requirement",
                    "Tests": "Verified by",
                },
                "lists": {"Verified by": ","},
            },
        )
        self.assertEqual(
            sources[1],
            {
                "sheet": "Priorities",
                "type": "Value",
                "columns": {"Value": "Name", "Meaning": "Definition"},
                "set": {"Field": "Priority"},
                "id_prefix": "VAL-",
            },
        )
        self.assertEqual(
            sources[3],
            {
                "table": "TestCases",
                "type": "Test",
                "columns": {
                    "Test ID": "ID",
                    "Title": "Name",
                    "Plan": "Test plan",
                    "Method": "Verification Method",
                },
                "lists": {"Verification Method": ","},
            },
        )

    def test_preview_counts_rows_and_record_types(self) -> None:
        found = preview_mapping(self.book, build_mapping(self.form()))
        self.assertNotIn("error", found)
        self.assertEqual(
            {s["name"]: s["rows"] for s in found["sources"]},
            {
                "Reqs": 2,
                "Priorities": 2,
                "Lists": 2,
                "TestCases": 3,
                "Plans": 1,
                "Systems": 1,
            },
        )
        self.assertEqual(
            found["types"],
            {"Requirement": 2, "Value": 4, "Test": 3, "Test plan": 1, "System": 1},
        )
        self.assertEqual(found["total"], 11)

    def test_preview_reports_the_importer_error_text(self) -> None:
        form = self.form()
        form["sources"][0]["columns"][0]["to"] = "Name"  # type: ignore[index]
        self.assertIn(
            "no 'ID' column",
            str(preview_mapping(self.book, build_mapping(form))["error"]),
        )
        form = self.form()
        form["sources"][1]["name"] = "Missing"  # type: ignore[index]
        self.assertIn(
            "Missing", str(preview_mapping(self.book, build_mapping(form))["error"])
        )

    def test_the_saved_mapping_builds_a_report_with_terms_tests_and_values(
        self,
    ) -> None:
        form = self.form()
        form["sources"].append(self.prefilled("sheet", "Fields", "glossary"))  # type: ignore[attr-defined]
        outcome = save_mapping(self.root, "mapping.json", build_mapping(form), False)
        self.assertEqual(outcome, {"saved": str(self.root / "mapping.json")})
        code, _, err = run_cli(
            str(self.book),
            "-c",
            str(self.root / "mapping.json"),
            "--traceability",
            "-o",
            str(self.root / "report.html"),
        )
        self.assertEqual(code, 0, err)
        rows = report_data(self.root / "report.html")["source"]["new"]["rows"]
        types = {row.get("Type") for row in rows}
        self.assertTrue(
            {"Test", "Test plan", "Value", "System", "Term"} <= types, types
        )
        names = {row["ID"]: row.get("Name") for row in rows}
        self.assertEqual(names["VAL-PRIORITY-MUST"], "Must")

    def test_saving_never_replaces_a_file_unless_told_to(self) -> None:
        mapping = build_mapping(self.form())
        save_mapping(self.root, "mapping.json", mapping, False)
        (self.root / "mapping.json").write_text("mine", encoding="utf-8")
        self.assertEqual(
            save_mapping(self.root, "mapping.json", mapping, False),
            {"exists": True, "path": str(self.root / "mapping.json")},
        )
        self.assertEqual(
            (self.root / "mapping.json").read_text(encoding="utf-8"), "mine"
        )
        save_mapping(self.root, "mapping.json", mapping, True)
        self.assertEqual(
            json.loads((self.root / "mapping.json").read_text(encoding="utf-8")),
            mapping,
        )
        with self.assertRaises(GuiError):
            save_mapping(self.root, "mapping.txt", mapping, False)
        with self.assertRaises(GuiError):
            save_mapping(self.root, "", mapping, False)

    def test_a_saved_mapping_loads_back_into_an_equal_form(self) -> None:
        mapping = build_mapping(self.form())
        save_mapping(self.root, "m.json", mapping, False)
        loaded = load_mapping(self.root, "m.json")
        self.assertEqual(loaded["notes"], [])
        self.assertEqual(build_mapping(loaded["form"]), mapping)
        (self.root / "bad.json").write_text("{", encoding="utf-8")
        for name in ("bad.json", "none.json"):
            with self.subTest(name), self.assertRaises(GuiError):
                load_mapping(self.root, name)


if __name__ == "__main__":
    unittest.main()
