import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.core import build_report_data, load_config, read_csv_table
from reqtable.html_report import render_report


def large_report(rows: int, **options) -> str:
    config = load_config(None, {"id_column": "ID", "title": "Large", **options})
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "large.csv"
        lines = ["ID,Requirement,Priority"] + [f"REQ-{n:04},The system shall do thing {n}.,Must" for n in range(rows)]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return render_report(build_report_data(read_csv_table(str(path), config), config, "large.html"))


def embedded_data(report: str) -> dict:
    match = re.search(r'<script id="reqtable-data" type="application/json">(.*?)</script>', report, re.S)
    return json.loads(match.group(1))


class LargeReportTests(unittest.TestCase):
    def test_every_row_is_embedded_and_no_row_markup_is_prerendered(self):
        report = large_report(450)
        self.assertEqual(len(embedded_data(report)["source"]["new"]["rows"]), 450)
        self.assertIn('<tbody id="requirements-body"></tbody>', report)

    @unittest.skipUnless(shutil.which("node"), "Node is needed to parse the report's JavaScript")
    def test_report_script_parses(self):
        for options in ({}, {"document_mode": "develop"}, {"document_mode": "develop", "traceability": True}):
            report = large_report(350, **options)
            script = report.rsplit("<script>", 1)[1].rsplit("</script>", 1)[0]
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
                handle.write(script)
                handle.flush()
                subprocess.run(["node", "--check", handle.name], check=True)


if __name__ == "__main__":
    unittest.main()
