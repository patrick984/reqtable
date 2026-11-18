import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.core import build_report_data, load_config, read_csv_table
from reqtable.html_report import WINDOW_JS, render_report


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


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class WindowRangeTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n' + WINDOW_JS + assertions,
                       text=True, check=True)

    def test_small_tables_draw_every_row(self):
        self.run_js("""
const offsets=rowOffsets(Array.from({length:300},(_,i)=>i),new Map());
assert.deepEqual(windowRange(offsets,5000,600),{start:0,end:300,top:0,bottom:0});
assert.deepEqual(windowRange(rowOffsets([],new Map()),0,600),{start:0,end:0,top:0,bottom:0});
""")

    def test_large_tables_draw_the_viewport_plus_overscan(self):
        self.run_js("""
const ids=Array.from({length:5000},(_,i)=>i),offsets=rowOffsets(ids,new Map(),50);
assert.deepEqual(windowRange(offsets,10000,500,15),{start:185,end:226,top:9250,bottom:(5000-226)*50});
assert.deepEqual(windowRange(offsets,10000,500,0),{start:200,end:211,top:10000,bottom:(5000-211)*50});
""")

    def test_range_clamps_at_both_ends(self):
        self.run_js("""
const offsets=rowOffsets(Array.from({length:1000},(_,i)=>i),new Map(),20);
assert.deepEqual(windowRange(offsets,-300,400,15),{start:0,end:21,top:0,bottom:(1000-21)*20});
const last=windowRange(offsets,10**7,400,15);
assert.equal(last.end,1000);
assert.equal(last.bottom,0);
assert.equal(last.start,1000-1-15);
""")

    def test_unmeasured_rows_use_the_average_of_measured_rows(self):
        self.run_js("""
const heights=new Map([["a",40],["b",80]]);
assert.deepEqual([...rowOffsets(["a","x","b","y"],heights)],[0,40,100,180,240]);
assert.deepEqual([...rowOffsets(["x","y"],new Map())],[0,ROW_HEIGHT_GUESS,2*ROW_HEIGHT_GUESS]);
""")

    def test_measured_heights_place_the_window(self):
        self.run_js("""
const ids=Array.from({length:400},(_,i)=>i),heights=new Map(ids.map(id=>[id,id<200?10:100]));
const range=windowRange(rowOffsets(ids,heights),2000+250,300,0);
assert.deepEqual([range.start,range.end],[202,206]);
assert.equal(range.top,2000+2*100);
""")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class EdgeScrollTests(unittest.TestCase):
    def test_scroll_speed_follows_the_pointer_toward_the_edge(self):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n' + WINDOW_JS + """
assert.equal(edgeScrollSpeed(300,100,500),0);
assert.equal(edgeScrollSpeed(100,100,500),-28);
assert.equal(edgeScrollSpeed(20,100,500),-28);
assert.equal(edgeScrollSpeed(500,100,500),28);
assert.equal(edgeScrollSpeed(900,100,500),28);
assert.ok(edgeScrollSpeed(120,100,500)<0&&edgeScrollSpeed(120,100,500)>-28);
assert.ok(edgeScrollSpeed(480,100,500)>0&&edgeScrollSpeed(480,100,500)<28);
""", text=True, check=True)
