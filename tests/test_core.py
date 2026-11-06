from __future__ import annotations

import csv
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from reqtable.core import (
    ConfigError,
    InputError,
    build_report_data,
    extract_comments_csv,
    extract_report_json,
    load_config,
    read_csv_table,
    render_diff,
)
from reqtable.html_report import render_report
from reqtable.markdown import render_markdown


class TempFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, value: str) -> Path:
        path = self.root / name
        path.write_text(value, encoding="utf-8", newline="")
        return path


class ConfigTests(TempFiles):
    def test_cli_override_wins(self) -> None:
        path = self.write("config.json", json.dumps({"id_column": "Old", "title": "Configured"}))
        config = load_config(str(path), {"id_column": "ID", "title": "CLI"})
        self.assertEqual(config["id_column"], "ID")
        self.assertEqual(config["title"], "CLI")

    def test_unknown_key_fails(self) -> None:
        path = self.write("config.json", '{"titel":"bad"}')
        with self.assertRaisesRegex(ConfigError, "unknown configuration key"):
            load_config(str(path))

    def test_unsafe_width_fails(self) -> None:
        path = self.write("config.json", '{"columns":{"widths":{"ID":"1rem; color:red"}}}')
        with self.assertRaisesRegex(ConfigError, "unsafe"):
            load_config(str(path))

    def test_document_mode_validation(self) -> None:
        self.assertEqual(load_config(None, {"document_mode": "develop"})["document_mode"], "develop")
        with self.assertRaisesRegex(ConfigError, "document_mode"):
            load_config(None, {"document_mode": "edit"})


class CsvTests(TempFiles):
    def config(self):
        return load_config(None, {"id_column": "ID"})

    def test_multiline_and_bom(self) -> None:
        path = self.write("input.csv", '\ufeffID,Text\nR1,"first\nsecond"\n')
        table = read_csv_table(str(path), self.config())
        self.assertEqual(table.rows[0]["Text"], "first\nsecond")

    def test_duplicate_header(self) -> None:
        path = self.write("input.csv", "ID,ID\nR1,x\n")
        with self.assertRaisesRegex(InputError, "duplicate column"):
            read_csv_table(str(path), self.config())

    def test_duplicate_id_reports_records(self) -> None:
        path = self.write("input.csv", "ID,Text\n R1 ,a\nR1,b\n")
        with self.assertRaisesRegex(InputError, "records 2 and 3"):
            read_csv_table(str(path), self.config())

    def test_wrong_field_count(self) -> None:
        path = self.write("input.csv", "ID,Text\nR1,a,extra\n")
        with self.assertRaisesRegex(InputError, "3 fields; expected 2"):
            read_csv_table(str(path), self.config())

    def test_blank_physical_line_is_ignored(self) -> None:
        path = self.write("input.csv", "ID,Text\n\nR1,a\n")
        table = read_csv_table(str(path), self.config())
        self.assertEqual(table.ids, ["R1"])


class MarkdownAndDiffTests(unittest.TestCase):
    def test_safe_markdown(self) -> None:
        rendered = render_markdown('**bold** <script>alert(1)</script> [bad](javascript:alert(1))')
        self.assertIn("<strong>bold</strong>", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn('href="javascript:', rendered)

    def test_word_diff(self) -> None:
        rendered = render_diff("shall be fast", "shall be very fast")
        self.assertIn("added-word", rendered["newHtml"])
        self.assertIn("very", rendered["newHtml"])

    def test_one_sided_diff_has_no_highlighted_blank_counterpart(self) -> None:
        added = render_diff("", "new content")
        removed = render_diff("old content", "")
        self.assertEqual(added["oldHtml"], "")
        self.assertNotIn("removed-line", added["unifiedHtml"])
        self.assertEqual(removed["newHtml"], "")
        self.assertNotIn("added-line", removed["unifiedHtml"])


class ReportTests(TempFiles):
    def config(self):
        return load_config(None, {"id_column": "ID", "title": "Test report"})

    def tables(self):
        old = self.write("old.csv", "ID,Requirement,Status\nR1,Old wording,Draft\nR2,Removed item,Draft\nR4,Same,Final\n")
        new = self.write("new.csv", "ID,Requirement,Status,Owner\nR1,New wording,Final,PN\nR3,Added item,Draft,AB\nR4,Same,Final,PN\n")
        return read_csv_table(str(old), self.config()), read_csv_table(str(new), self.config())

    def test_diff_status_and_schema_union(self) -> None:
        old, new = self.tables()
        data = build_report_data(new, self.config(), "report.html", old)
        statuses = {row["id"]: row["status"] for row in data["rows"]}
        self.assertEqual(statuses, {"R1": "changed", "R2": "removed", "R3": "added", "R4": "changed"})
        self.assertEqual([c["name"] for c in data["columns"]], ["ID", "Requirement", "Status", "Owner"])

    def test_absent_empty_column_does_not_create_cell_diff(self) -> None:
        old_path = self.write("old-empty.csv", "ID,Text\nR1,Same\n")
        new_path = self.write("new-empty.csv", "ID,Text,New Column\nR1,Same,\n")
        old = read_csv_table(str(old_path), self.config())
        new = read_csv_table(str(new_path), self.config())
        data = build_report_data(new, self.config(), "report.html", old)
        self.assertEqual(data["rows"][0]["status"], "unchanged")
        self.assertFalse(data["rows"][0]["cells"]["New Column"]["changed"])

    def test_report_is_self_contained_and_escaped(self) -> None:
        path = self.write("input.csv", 'ID,Text\nR1,"</script><script>alert(1)</script>"\n')
        table = read_csv_table(str(path), self.config())
        report = render_report(build_report_data(table, self.config(), "report.html"))
        self.assertIn('id="reqtable-data"', report)
        self.assertNotIn('</script><script>alert(1)</script>', report)
        self.assertNotRegex(report, r'<(?:link|script)[^>]+src=')
        self.assertNotIn("https://cdn", report)

    def test_report_includes_interactive_uat_controls(self) -> None:
        path = self.write("input.csv", "ID,Text\nR1,Hello world\n")
        table = read_csv_table(str(path), self.config())
        data = build_report_data(table, self.config(), "report.html")
        report = render_report(data)
        self.assertGreaterEqual(data["columns"][0]["estimatedWidth"], 82)
        self.assertIn('class="resize-handle"', report)
        self.assertIn('id="quick-comment"', report)
        self.assertIn('id="keyboard-help"', report)
        self.assertIn('class="clear-filter"', report)
        self.assertIn("selected-cell", report)
        self.assertIn("Show sidebar", report)
        self.assertIn('key==="h"', report)
        self.assertIn("ensureCellVisible", report)
        self.assertIn("Previous comment", report)
        self.assertIn("caret-color:var(--text)", report)
        self.assertIn('id="comments-only-rows"', report)
        self.assertIn('id="value-filter-popover"', report)
        self.assertIn('id="back-comments"', report)
        self.assertIn("reqtable-reviewer-initials", report)
        self.assertIn("displayTimestamp", report)
        self.assertIn("filenameTimestamp", report)
        self.assertIn("data-sidebar-resize", report)
        self.assertIn("column.name!==data.meta.idColumn", report)
        self.assertIn("--comment:#cf222e", report)
        self.assertIn("wrap.clientHeight", report)
        self.assertIn("safeLeft=wr.left+statusWidth", report)
        self.assertIn('"#dirty-indicator"', report)
        self.assertIn('data-inline-comment-id=', report)
        self.assertIn("saveInlineComment", report)
        self.assertIn("restoreSidebarFocus", report)
        self.assertIn(">Comments only</button>", report)
        self.assertIn("values.length>50", report)
        self.assertIn("renderHead();renderBodyOnly()", report)
        self.assertNotIn("Edit my comment", report)
        self.assertNotIn("Requirements: 1", report)

    def test_develop_report_includes_editing_and_csv_controls(self) -> None:
        path = self.write("input.csv", "ID,Text\nR1,Hello\n")
        config = load_config(None, {"id_column": "ID", "document_mode": "develop"})
        data = build_report_data(read_csv_table(str(path), config), config, "report.html")
        report = render_report(data)
        self.assertEqual(data["meta"]["documentMode"], "develop")
        self.assertIn(">Develop mode<", report)
        self.assertIn('id="add-end"', report)
        self.assertIn('id="rename-requirement"', report)
        self.assertIn('id="delete-requirement"', report)
        self.assertIn('id="unsaved-diff"', report)
        self.assertIn('id="save-csv"', report)
        self.assertIn("showSaveFilePicker", report)
        self.assertIn("data-cell-editor", report)
        self.assertIn("commentsColumn", report)

    def test_source_date_epoch(self) -> None:
        path = self.write("input.csv", "ID,Text\nR1,Hello\n")
        prior = os.environ.get("SOURCE_DATE_EPOCH")
        os.environ["SOURCE_DATE_EPOCH"] = "0"
        try:
            table = read_csv_table(str(path), self.config())
            data = build_report_data(table, self.config(), "report.html")
        finally:
            if prior is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)
            else:
                os.environ["SOURCE_DATE_EPOCH"] = prior
        self.assertTrue(data["meta"]["generated"].startswith("1970-01-01T"))

    def test_comment_round_trip(self) -> None:
        path = self.write("input.csv", "ID,Text\nR1,Hello\nR2,World\n")
        table = read_csv_table(str(path), self.config())
        data = build_report_data(table, self.config(), "report.html")
        data["comments"] = [{
            "id": "c1", "requirementId": "R1", "column": "Text", "initials": "PN",
            "created": "2026-09-13T15:42:18+10:00", "modified": None, "text": "Clarify this."
        }]
        report_path = self.write("reviewed.html", render_report(data))
        csv_path = self.root / "reviewed.csv"
        extract_comments_csv(str(report_path), str(csv_path), "Comments", "json", "new", False)
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        comments = json.loads(rows[0]["Comments"])
        self.assertEqual(comments[0]["column"], "Text")
        self.assertEqual(comments[0]["text"], "Clarify this.")
        self.assertEqual(rows[1]["Comments"], "[]")

    def test_diff_export_refuses_comment_loss(self) -> None:
        old, new = self.tables()
        data = build_report_data(new, self.config(), "report.html", old)
        data["comments"] = [{
            "id": "c1", "requirementId": "R2", "column": "Requirement", "initials": "PN",
            "created": "2026-09-13T15:42:18+10:00", "modified": None, "text": "Why removed?"
        }]
        report_path = self.write("diff-reviewed.html", render_report(data))
        embedded = extract_report_json(report_path)
        self.assertEqual(embedded["formatVersion"], 2)
        self.assertNotIn("rows", embedded)
        with self.assertRaisesRegex(InputError, "would omit comments"):
            extract_comments_csv(str(report_path), str(self.root / "out.csv"), "Comments", "json", "new", False)
        extract_comments_csv(str(report_path), str(self.root / "union.csv"), "Comments", "json", "union", False)
        with (self.root / "union.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        removed = next(row for row in rows if row["ID"] == "R2")
        self.assertEqual(removed["_Diff Status"], "removed")

        legacy = self.write(
            "legacy.html",
            '<script id="reqtable-data" type="application/json">'
            + json.dumps(data)
            + "</script>",
        )
        legacy_csv = self.root / "legacy.csv"
        extract_comments_csv(str(legacy), str(legacy_csv), "Comments", "json", "union", False)
        self.assertEqual(legacy_csv.read_bytes(), (self.root / "union.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
