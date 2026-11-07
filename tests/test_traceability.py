from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import unittest

from reqtable.core import build_report_data, extract_comments_csv, load_config, read_csv_table
from reqtable.html_report import JS, render_report
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
            ["T", "Term", "", "", "[]"],
        ])
        path = self.write("source.csv", csv_file.getvalue())
        config = load_config(None, {"id_column": "Key", "csv.delimiter": ";"})
        table = read_csv_table(str(path), config)
        flat = build_report_data(table, config, "flat.html")
        self.assertEqual(flat["source"]["new"]["headers"], table.headers)
        self.assertFalse(flat["options"]["traceability"])
        self.assertNotIn('id="trace-workspace"', render_report(flat))

        config = load_config(None, {"id_column": "Key", "csv.delimiter": ";", "traceability": True})
        pilot = build_report_data(table, config, "pilot.html")
        self.assertTrue(pilot["options"]["traceability"])
        self.assertIn("Derived from", pilot["source"]["new"]["headers"])
        self.assertIn("Definition", pilot["source"]["new"]["headers"])
        self.assertNotIn("Comments", pilot["source"]["new"]["headers"])
        self.assertEqual(pilot["comments"], [{"id": "imported-0", "requirementId": "R", **note}])
        report = render_report(pilot)
        self.assertIn('data-trace-view="requirements" aria-pressed="true"', report)
        self.assertIn('data-trace-view="systems"', report)
        self.assertIn('data-trace-view="sources"', report)
        self.assertIn('data-trace-view="glossary"', report)
        self.assertIn('id="glossary-definition"', report)
        self.assertIn('data-trace-view="all"', report)

        report_path = self.write("pilot.html", report)
        output_path = self.root / "saved.csv"
        extract_comments_csv(str(report_path), str(output_path), "Comments", "json", "new", False, ";")
        reopened = build_report_data(read_csv_table(str(output_path), config), config, "pilot.html")
        self.assertEqual(pilot["source"], reopened["source"])
        self.assertEqual(pilot["comments"], reopened["comments"])

    def test_glossary_values_survive_csv_round_trip(self):
        path = self.write("glossary.csv",
                          "ID,Type,Name,Definition,Aliases,Auto Link,Source refs\n"
                          "S,Source,Reference,,,,\n"
                          'T,Term,Example Term,"A definition,\non two lines.",ET; Term,Yes,S\n')
        config = load_config(None, {"id_column": "ID", "traceability": True})
        pilot = build_report_data(read_csv_table(str(path), config), config, "glossary.html")
        report_path = self.write("glossary.html", render_report(pilot))
        output = self.root / "saved.csv"
        extract_comments_csv(str(report_path), str(output), "Comments", "json", "new", False)
        reopened = build_report_data(read_csv_table(str(output), config), config, "glossary.html")
        self.assertEqual(pilot["source"], reopened["source"])


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class TraceModelTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + TRACE_MODEL_JS + assertions, text=True, check=True)

    def test_glossary_matching_and_validation(self):
        self.run_js(r"""
const term=(ID,Name,Aliases="",extra={})=>({ID,Type:"Term",Name,Aliases,Definition:"Definition",...extra});
const rows=[
  {ID:"SYS",Type:"System"}, {ID:"SOURCE",Type:"Source"}, {ID:"NEED",Type:"Need"},
  term("CSV","Comma-Separated Values","CSV; CSV",{"Source refs":"SOURCE"}),
  term("CACHE","Data Cache"),term("SHARED","Shared Data Cache"),
  term("SINGLE","Baseline","",{"Auto Link":"Yes"}),
  term("SKIP","Report"),term("UTF","Unicode Transformation Format","UTF-8"),
  term("JOIN","Proof of Concept"),
  term("CLASH1","First Term","CLASH; Shared Data Cache Format"),
  term("CLASH2","Second Term","CLASH; Shared Data Cache Format"),
  term("DUP1","Duplicate Name"),term("DUP2","duplicate name"),
  term("BLANK","Blank Definition","BD",{Definition:"  "}),
  term("NAMELESS","","NM",{"Source refs":"NEED"})
];
const {records,glossary,issues}=buildTraceIndex(rows,row=>row.ID);
const matches=text=>glossary.matches(text).map(({record,start,text:spelling})=>{
  assert.equal(text.slice(start,start+spelling.length),spelling);
  return [record.id,spelling];
});
assert.deepEqual(matches("Comma-Separated Values (CSV), csv, xCSV, CSV_file and CSV2."),[
  ["CSV","Comma-Separated Values"],["CSV","CSV"]
]);
assert.deepEqual(matches("Shared Data Cache; Data Cache. Baseline Report UTF-8 Proof of Concept."),[
  ["SHARED","Shared Data Cache"],["CACHE","Data Cache"],["SINGLE","Baseline"],
  ["UTF","UTF-8"],["JOIN","Proof of Concept"]
]);
assert.deepEqual(matches("CLASH Shared Data Cache Format Duplicate Name Blank Definition BD NM"),[]);
assert.deepEqual(matches("https://site.test/CSV www.site.test/CSV CSV@example.test then CSV"),[["CSV","CSV"]]);
assert.deepEqual(records.get("CSV").outgoing.get("Source refs").map(record=>record.id),["SOURCE"]);
assert.equal(traceCanLink(records.get("CSV"),"Source refs",records.get("NEED")),false);
assert(issues.some(({id,field})=>id==="NAMELESS"&&field==="Name"));
assert(issues.some(({id,field})=>id==="BLANK"&&field==="Definition"));
assert(issues.some(({id,field})=>id==="DUP1"&&field==="Name"));
assert(issues.some(({id,field})=>id==="CLASH2"&&field==="Aliases"));
""")

    def test_reordering_requirements_keeps_systems_and_sources_in_place(self):
        movement = "function moveRowsInOrder(" + JS.split("function moveRowsInOrder(", 1)[1]
        self.run_js(movement.split("function moveRenderedRows(", 1)[0] + r"""
const records=["SYS","R1","R2","NEED","R3","SOURCE","R4"];
const requirements=new Set(["R1","R2","R3","R4"]);
moveRowsInOrder(records,id=>id,requirements,0,2,2);
assert.deepEqual(records,["SYS","R3","R4","NEED","R1","SOURCE","R2"]);
moveRowsInOrder(records,id=>id,requirements,2,0,2);
assert.deepEqual(records,["SYS","R1","R2","NEED","R3","SOURCE","R4"]);
""")

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
