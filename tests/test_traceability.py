from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import unittest

from reqtable.core import build_report_data, extract_comments_csv, load_config, read_csv_table
from reqtable.html_report import render_report
from reqtable.traceability import TRACE_MODEL_JS
from tests.test_core import TempFiles


class TraceCsvTests(TempFiles):
    def test_opt_in_and_csv_round_trip(self):
        note = {"column": "Requirement", "text": "Still works offline.", "initials": "PN",
                "created": "2026-11-07T10:00:00+11:00", "modified": None}
        csv_file = io.StringIO(newline="")
        writer = csv.writer(csv_file, delimiter=";")
        writer.writerows([
            ["Key", "Type", "Requirement", "Allocated to", "Comments"],
            ["A", "System", "", "", "[]"],
            ["B", "System", "", "", "[]"],
            ["R", "", "Open and review.", "A; B", json.dumps([note])],
        ])
        path = self.write("source.csv", csv_file.getvalue())
        config = load_config(None, {"id_column": "Key", "csv.delimiter": ";"})
        table = read_csv_table(str(path), config)
        flat = build_report_data(table, config, "flat.html")
        self.assertEqual(flat["source"]["new"]["headers"], table.headers)
        self.assertFalse(flat["options"]["traceability"])
        self.assertNotIn('id="open-trace"', render_report(flat))

        config = load_config(None, {"id_column": "Key", "csv.delimiter": ";", "traceability": True})
        pilot = build_report_data(table, config, "pilot.html")
        self.assertTrue(pilot["options"]["traceability"])
        self.assertIn("Derived from", pilot["source"]["new"]["headers"])
        self.assertNotIn("Comments", pilot["source"]["new"]["headers"])
        self.assertEqual(pilot["comments"], [{"id": "imported-0", "requirementId": "R", **note}])
        report = render_report(pilot)
        self.assertIn('id="open-trace"', report)

        report_path = self.write("pilot.html", report)
        output_path = self.root / "saved.csv"
        extract_comments_csv(str(report_path), str(output_path), "Comments", "json", "new", False, ";")
        reopened = build_report_data(read_csv_table(str(output_path), config), config, "pilot.html")
        self.assertEqual(pilot["source"], reopened["source"])
        self.assertEqual(pilot["comments"], reopened["comments"])


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class TraceModelTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + TRACE_MODEL_JS + assertions, text=True, check=True)

    def test_canonical_records_and_picker_constraints(self):
        self.run_js(r"""
const rows=[
  {ID:"SYS",Type:"System"},
  {ID:"A",Type:"System","Part of":"SYS"},
  {ID:"B",Type:"System","Part of":"SYS"},
  {ID:"N",Type:"Need","Source refs":"S"},
  {ID:"S",Type:"Source"},
  {ID:"P","Allocated to":" A; B ","Owner":"SYS","Source refs":"N"},
  {ID:"C","Derived from":"P"}
];
const {records,issues}=buildTraceIndex(rows,row=>row.ID);
const get=id=>records.get(id);
const shared=get("P");
assert.deepEqual(issues,[]);
assert.deepEqual(shared.outgoing.get("Allocated to").map(record=>record.id),["A","B"]);
assert.equal(get("A").incoming.find(edge=>edge.field==="Allocated to").record,shared);
assert.equal(get("B").incoming.find(edge=>edge.field==="Allocated to").record,shared);
assert.equal(shared.incoming.find(edge=>edge.field==="Derived from").record,get("C"));
assert.equal(shared.outgoing.get("Source refs")[0],get("N"));
assert.equal(traceCanLink(get("SYS"),"Part of",get("A")),false);
assert.equal(traceCanLink(shared,"Derived from",get("C")),false);
assert.equal(traceCanLink(shared,"Allocated to",get("A")),false);
assert.equal(traceCanLink(shared,"Allocated to",get("N")),false);
assert.equal(traceCanLink(shared,"Source refs",get("S")),true);
""")

    def test_invalid_imports_and_reference_updates(self):
        self.run_js(r"""
const rows=[
  {ID:"SYS",Type:"System","Part of":"SUB"},
  {ID:"SUB",Type:"System","Part of":"SYS"},
  {ID:"P","Allocated to":"SYS; absent; SYS; N","Derived from":"C; P",Origin:"Self-derived"},
  {ID:"C","Derived from":"P; NEW"},
  {ID:"N",Type:"Need"},
  {ID:"X; Y",Type:"Unknown"}
];
const before=JSON.stringify(rows);
const {issues}=buildTraceIndex(rows,row=>row.ID);
assert.equal(JSON.stringify(rows),before);
const messages=issues.map(issue=>issue.message).join("\n");
for(const expected of [/semicolon/, /Unknown record type/, /missing/, /has type Need/, /Duplicate/,
    /link to itself/, /Cycle: SYS → SUB → SYS/, /Cycle: P → C → P/, /self-derived/]){
  assert.match(messages,expected);
}
const rename=traceIncomingChanges(rows,"P","NEW");
assert.deepEqual(rename.map(({row,field,value})=>[row.ID,field,value]),
  [["P","Derived from","C; NEW"],["C","Derived from","NEW"]]);
const remove=traceIncomingChanges(rows,"SYS",null);
assert.deepEqual(remove.map(({row,field,value})=>[row.ID,field,value]),
  [["SUB","Part of",""],["P","Allocated to","absent; N"]]);
""")
