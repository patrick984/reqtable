from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.core import build_report_data, extract_comments_csv, load_config, read_csv_table
from reqtable.html_report import JS, render_report
from reqtable.traceability import TRACE_COLUMNS, TRACE_MODEL_JS
from tests.test_core import TempFiles

UAT_CSV = Path(__file__).resolve().parent.parent / "requirements-uat.csv"


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
        self.assertIn('data-trace-view="tests"', report)
        self.assertIn('data-trace-view="changes" aria-pressed="false">Change requests</button>', report)
        self.assertIn('<label>System <select id="trace-gates-system">', report)
        order = ["sources", "requirements", "systems", "tests", "verification", "glossary", "all"]
        positions = [report.index(f'data-trace-view="{view}"') for view in order]
        self.assertEqual(positions, sorted(positions))
        for label in ("Define", "Verify", "Reference"):
            self.assertIn(f'role="group" aria-label="{label}"', report)
        for name in ("Verified by", "Test plan"):
            self.assertIn(name, pilot["source"]["new"]["headers"])

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


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class TestRecordModelTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + TRACE_MODEL_JS + assertions, text=True, check=True)

    def test_location_hash_omits_defaults(self):
        self.run_js(r"""
const home={view:"requirements",kind:"terms",mode:"",system:"",unallocated:false,descendants:true,record:""};
assert.equal(traceLocationHash(home),"");
assert.equal(traceLocationHash({...home,kind:"values"}),"");
assert.equal(traceLocationHash({...home,view:"glossary",kind:"values"}),"#view=glossary&kind=values");
assert.equal(traceLocationHash({...home,view:"glossary"}),"#view=glossary");
assert.equal(traceLocationHash({...home,descendants:false}),"#descendants=0");
assert.equal(traceLocationHash({...home,view:"verification",mode:"matrix",system:"SYS-REPORT",record:"REQ-003"}),
  "#view=verification&mode=matrix&system=SYS-REPORT&record=REQ-003");
""")

    def test_location_round_trips_and_encodes_ids(self):
        self.run_js(r"""
const full={view:"verification",kind:"terms",mode:"matrix",system:"SYS A&B",unallocated:true,descendants:false,record:"REQ #1&x=2"};
const hash=traceLocationHash(full);
assert.ok(!hash.slice(1).includes("#")&&!/ |&x=2/.test(hash));
assert.deepEqual(parseTraceLocation(hash),full);
const glossary={view:"glossary",kind:"values",mode:"",system:"",unallocated:false,descendants:true,record:"VAL 1"};
assert.deepEqual(parseTraceLocation(traceLocationHash(glossary)),glossary);
""")

    def test_location_parse_ignores_invalid_and_foreign_input(self):
        self.run_js(r"""
const home={view:"requirements",kind:"terms",mode:"",system:"",unallocated:false,descendants:true,record:""};
for(const hash of ["","#","#top","#trace-matrix","trace-matrix",undefined,null,"#=&&=","#%E0%A4%A"]){
  assert.deepEqual(parseTraceLocation(hash),home,String(hash));
}
assert.deepEqual(parseTraceLocation("#unallocated=yes&descendants=maybe&kind=other&bogus=1&view=tests"),{...home,view:"tests"});
assert.equal(parseTraceLocation("#view=tests&view=all").view,"tests");
assert.equal(traceLocationHash(parseTraceLocation("#view=tests&bogus=1")),"#view=tests");
""")

    def test_trace_columns_include_test_links(self):
        self.assertIn("Verified by", TRACE_COLUMNS)
        self.assertIn("Test plan", TRACE_COLUMNS)

    def test_links_resolve_in_both_directions(self):
        self.run_js(r"""
const rows=[
  {ID:"SYS",Type:"System"},
  {ID:"R1",Type:"Requirement","Verified by":"T1; T2"},
  {ID:"T1",Type:"Test","Test plan":"TP"},
  {ID:"T2",Type:"Test"},
  {ID:"TP",Type:"Test plan"}
];
const {records,issues}=buildTraceIndex(rows,row=>row.ID);
assert.deepEqual(issues,[]);
assert.deepEqual(records.get("T1").incoming.map(({field,record})=>[field,record.id]),[["Verified by","R1"]]);
assert.deepEqual(records.get("TP").incoming.map(({field,record})=>[field,record.id]),[["Test plan","T1"]]);
assert.equal(traceCanLink(records.get("R1"),"Verified by",records.get("TP")),false);
assert.equal(traceCanLink(records.get("T2"),"Test plan",records.get("TP")),true);
assert.equal(traceCanLink(records.get("R1"),"Test plan",records.get("TP")),false);
""")

    def test_invalid_test_links_are_flagged(self):
        self.run_js(r"""
const rows=[
  {ID:"SYS",Type:"System"},
  {ID:"R1",Type:"Requirement","Verified by":"TP; MISSING; R1; T1; T1"},
  {ID:"T1",Type:"Test","Test plan":"TP; TP2","Verified by":"T1"},
  {ID:"TP",Type:"Test plan"},
  {ID:"TP2",Type:"Test plan"},
  {ID:"T2",Type:"Test","Test plan":"T1"},
  {ID:"N",Type:"Need","Test plan":"TP"}
];
const messages=buildTraceIndex(rows,row=>row.ID).issues.map(({id,field,message})=>`${id}|${field}|${message}`);
for(const expected of [
  "R1|Verified by|Target TP has type Test plan. Expected Test.",
  "R1|Verified by|Target MISSING is missing.",
  "R1|Verified by|A record cannot link to itself.",
  "R1|Verified by|Duplicate reference to T1.",
  "T1|Test plan|Select at most one target.",
  "T1|Verified by|Verified by does not apply to Test records.",
  "T2|Test plan|Target T1 has type Test. Expected Test plan.",
  "N|Test plan|Test plan does not apply to Need records."
])assert.ok(messages.includes(expected),expected+"\n"+messages.join("\n"));
""")

    def test_test_plan_links_do_not_build_the_system_tree(self):
        self.run_js(r"""
const rows=[{ID:"SYS",Type:"System"},{ID:"T",Type:"Test","Test plan":"TP"},{ID:"TP",Type:"Test plan"}];
const index=buildTraceIndex(rows,row=>row.ID);
assert.deepEqual(index.issues,[]);
assert.equal(index.roots.length,1);
assert.deepEqual(index.records.get("TP").incoming.filter(edge=>edge.field==="Part of"),[]);
""")

    def test_deleting_a_test_removes_requirement_links(self):
        self.run_js(r"""
const rows=[
  {ID:"R1",Type:"Requirement","Verified by":"T1; T2"},
  {ID:"T1",Type:"Test","Test plan":"TP"},
  {ID:"TP",Type:"Test plan"}
];
const gone=traceIncomingChanges(rows,"T1",null).map(({row,field,value})=>[row.ID,field,value]);
assert.deepEqual(gone,[["R1","Verified by","T2"]]);
const plan=traceIncomingChanges(rows,"TP",null).map(({row,field,value})=>[row.ID,field,value]);
assert.deepEqual(plan,[["T1","Test plan",""]]);
""")

    def test_verification_method_on_tests_is_checked_against_values(self):
        self.run_js(r"""
const HEADERS=["ID","Type","Name","Definition","Verification Method","Field","Multiple","Test plan","Verified by"];
const rows=[
  {ID:"V1",Type:"Value",Field:"Verification Method",Name:"Automated test",Definition:"Runs unattended."},
  {ID:"T1",Type:"Test","Verification Method":"Automated test"},
  {ID:"T2",Type:"Test","Verification Method":"Eyeball it"}
];
const {issues}=buildTraceIndex(rows,row=>row.ID,{headers:HEADERS,idColumn:"ID"});
assert.deepEqual(issues.filter(({id})=>id==="T1"),[]);
const flagged=issues.filter(({id})=>id==="T2");
assert.equal(flagged.length,1);
assert.equal(flagged[0].field,"Verification Method");
""")

    def test_requirement_values_must_be_covered_by_its_linked_tests(self):
        self.run_js(r"""
const HEADERS=["ID","Type","Name","Field","Multiple","Aliases","Definition","Level","Priority","Verified by"];
const value=(ID,Name,Aliases="")=>({ID,Type:"Value",Field:"Level",Name,Aliases,Definition:"A level."});
const rows=[
  {ID:"F1",Type:"Field",Name:"Level",Multiple:"Yes",Definition:"V-model level."},
  value("L-UNIT","Unit","Unit test"),value("L-SYS","System"),value("L-ACC","Acceptance","UAT"),
  {ID:"P1",Type:"Value",Field:"Priority",Name:"Must",Definition:"Required."},
  {ID:"T-UNIT",Type:"Test",Level:"Unit test"},{ID:"T-SYS",Type:"Test",Level:"System"},{ID:"T-NONE",Type:"Test"},
  {ID:"R-GAP",Level:"Unit; System; UAT",Priority:"Must","Verified by":"T-UNIT"},
  {ID:"R-OK",Level:"Unit; System","Verified by":"T-UNIT; T-SYS"},
  {ID:"R-UNPLANNED","Verified by":"T-UNIT"},
  {ID:"R-UNLEVELLED-TEST",Level:"System","Verified by":"T-NONE"},
  {ID:"R-UNLINKED",Level:"System"}
];
const {issues}=buildTraceIndex(rows,row=>row.ID,{headers:HEADERS,idColumn:"ID"});
assert.deepEqual(issues.filter(({message})=>message.startsWith("No test")).map(({id,field,message})=>`${id}|${field}|${message}`),[
  "R-GAP|Level|No test in Verified by covers “System”, “Acceptance”. Its tests have “Unit”."
]);
""")

    VERIFICATION_PRELUDE = r"""
const HEADERS=["ID","Type","Name","Field","Aliases","Definition","Compliance","Result","Verified by"];
const value=(Field,Name,Aliases="")=>({ID:`V-${Field}-${Name}`,Type:"Value",Field,Name,Aliases,Definition:"Defined."});
const defined=[
  value("Compliance","Compliant"),value("Compliance","Non-compliant"),value("Result","Passed","Pass"),value("Result","Failed")
];
const test=(ID,Result)=>({ID,Type:"Test",Result});
const findings=(rows,withValues=true)=>buildTraceIndex(withValues?[...defined,...rows]:rows,row=>row.ID,{headers:HEADERS,idColumn:"ID"})
  .issues.filter(({field})=>field==="Compliance"||field==="Result").map(({id,field,message})=>`${id}|${field}|${message}`);
"""

    def test_compliant_requirement_needs_every_linked_test_to_have_passed(self):
        self.run_js(self.VERIFICATION_PRELUDE + r"""
const rows=[
  test("T-PASS","Passed"),test("T-ALIAS","Pass"),test("T-FAIL","Failed"),test("T-BLANK",""),test("T-BLANK2",""),
  {ID:"R-OK",Compliance:"Compliant","Verified by":"T-PASS; T-ALIAS"},
  {ID:"R-FAILED",Compliance:"Compliant","Verified by":"T-PASS; T-FAIL"},
  {ID:"R-TWO",Compliance:"Compliant","Verified by":"T-FAIL; T-BLANK"},
  {ID:"R-THREE",Compliance:"Compliant","Verified by":"T-FAIL; T-BLANK; T-PASS; T-BLANK2"},
  {ID:"R-NO-TESTS",Compliance:"Compliant"},
  {ID:"R-NON",Compliance:"Non-compliant","Verified by":"T-FAIL"},
  {ID:"R-BLANK-COMPLIANCE","Verified by":"T-FAIL"}
];
assert.deepEqual(findings(rows).filter(line=>!line.includes("replaced spelling")),[
  "R-FAILED|Compliance|Compliant, but T-FAIL is “Failed”.",
  "R-TWO|Compliance|Compliant, but T-FAIL is “Failed” and T-BLANK has no result.",
  "R-THREE|Compliance|Compliant, but T-FAIL is “Failed”, T-BLANK has no result and T-BLANK2 has no result."
]);
assert.deepEqual(findings([test("T","Failed"),{ID:"R",Compliance:"Compliant","Verified by":"T"}],false),
  ["R|Compliance|Compliant, but T is “Failed”."]);
""")

    def test_compliance_and_result_apply_only_to_their_record_types(self):
        self.run_js(self.VERIFICATION_PRELUDE + r"""
const rows=[
  {ID:"R",Compliance:"Compliant",Result:"Passed"},
  {ID:"T",Type:"Test",Compliance:"Compliant",Result:"Passed"},
  {ID:"N",Type:"Need",Result:"Failed"},
  {ID:"S",Type:"System",Compliance:" "}
];
assert.deepEqual(findings(rows).sort(),[
  "N|Result|Result applies to tests.",
  "R|Result|Result applies to tests.",
  "T|Compliance|Compliance applies to requirements."
]);
""")

    def test_verification_method_marks_fill_slots_in_value_order(self):
        self.run_js(r"""
const value=(Name,Aliases="")=>({row:{Name,Aliases}});
const rule={multiple:true,values:new Map(["Inspection","Analysis","Demonstration","Test"].map(name=>[name,value(name)])),
  aliases:new Map([["Try it",value("Demonstration")]])};
const marks=cell=>verificationMethodMarks(rule,cell).map(({letter,filled})=>letter+(filled?"+":"-")).join(" ");
assert.equal(marks("Test; Try it"),"I- A- D+ T+");
assert.equal(marks(""),"I- A- D- T-");
assert.equal(marks("Unknown"),"I- A- D- T-");
""")

    MATRIX_PRELUDE = r"""
const HEADERS=["ID","Type","Name","Field","Aliases","Multiple","Definition","Requirement","Verification Method","Verification Level","Compliance","Result","Verified by"];
const value=(Field,Name,Aliases="")=>({ID:`V-${Field}-${Name}`,Type:"Value",Field,Name,Aliases,Definition:"Defined."});
const field=Name=>({ID:`F-${Name}`,Type:"Field",Name,Multiple:"Yes",Definition:"Field."});
const defined=[
  field("Verification Method"),field("Verification Level"),
  value("Verification Method","Inspection"),value("Verification Method","Test","Try it"),
  value("Verification Level","Unit"),value("Verification Level","Acceptance","UAT"),
  value("Compliance","Not verified"),value("Compliance","Compliant"),value("Result","Passed","Pass")
];
const build=(rows,withValues=true)=>{
  const index=buildTraceIndex(withValues?[...defined,...rows]:rows,row=>row.ID,{headers:HEADERS,idColumn:"ID"});
  const picked=rows.filter(row=>(row.Type??"Requirement")==="Requirement").map(row=>index.records.get(row.ID));
  return buildVerificationMatrix(picked,index.values,"ID");
};
"""

    def test_matrix_orders_columns_by_value_records_and_resolves_aliases(self):
        self.run_js(self.MATRIX_PRELUDE + r"""
const m=build([
  {ID:"R1",Requirement:"Text","Verification Method":"Try it; Inspection","Verification Level":"UAT; Unit"},
  {ID:"R2",Name:"Named",Requirement:"Text"}
]);
assert.deepEqual(m.methods,["Inspection","Test"]);
assert.deepEqual(m.levels,["Unit","Acceptance"]);
assert.deepEqual(m.rows[0].methods.slice().sort(),["Inspection","Test"]);
assert.deepEqual(m.rows[0].levels.slice().sort(),["Acceptance","Unit"]);
assert.equal(m.rows[0].requirement,"Text");
assert.equal(m.rows[1].requirement,"Named");
assert.deepEqual(m.totals.methods,{Inspection:1,Test:1});
assert.deepEqual(m.totals.levels,{Unit:1,Acceptance:1});
""")

    def test_matrix_lists_undefined_values_as_extras(self):
        self.run_js(self.MATRIX_PRELUDE + r"""
const m=build([{ID:"R1","Verification Method":"Test; Telepathy","Verification Level":"Beta"}]);
assert.deepEqual(m.rows[0].methods,["Test"]);
assert.deepEqual(m.rows[0].extraMethods,["Telepathy"]);
assert.deepEqual(m.rows[0].levels,[]);
assert.deepEqual(m.rows[0].extraLevels,["Beta"]);
assert.deepEqual(m.totals.methods,{Inspection:0,Test:1});
""")

    def test_matrix_carries_tests_results_compliance_and_totals(self):
        self.run_js(self.MATRIX_PRELUDE + r"""
const m=build([
  {ID:"T1",Type:"Test",Name:"Core test",Result:"Pass"},{ID:"T2",Type:"Test"},
  {ID:"R1",Compliance:"Compliant","Verified by":"T1; T2"},
  {ID:"R2",Compliance:"Not verified"},{ID:"R3",Compliance:"Not verified"},{ID:"R4"}
]);
assert.deepEqual(m.rows.map(row=>row.id),["R1","R2","R3","R4"]);
assert.deepEqual(m.rows[0].tests,[{id:"T1",name:"Core test",result:"Passed"},{id:"T2",name:"T2",result:""}]);
assert.deepEqual(m.rows[1].tests,[]);
assert.deepEqual(m.totals.compliance,{Compliant:1,"Not verified":2,"No compliance":1});
""")

    def test_matrix_without_method_values_has_no_method_columns(self):
        self.run_js(self.MATRIX_PRELUDE + r"""
const m=build([{ID:"R1","Verification Method":"Test"}],false);
assert.deepEqual(m.methods,[]);
assert.deepEqual(m.levels,[]);
assert.deepEqual(m.rows[0].methods,[]);
assert.deepEqual(m.rows[0].extraMethods,["Test"]);
""")

    def test_matrix_headers_use_the_shortest_unique_prefix(self):
        self.run_js(r"""
assert.deepEqual(verificationMatrixLabels(["Inspection","Analysis","Demonstration","Test"]),["I","A","D","T"]);
assert.deepEqual(verificationMatrixLabels(["Unit","Integration","System","Acceptance"]),["U","I","S","A"]);
assert.deepEqual(verificationMatrixLabels(["System","Safety","Sim"]),["SY","SA","SI"]);
assert.deepEqual(verificationMatrixLabels(["Test","Test run"]),["TEST","TEST R"]);
""")

    def test_matrix_csv_rows_mark_methods_levels_tests_and_extras(self):
        self.run_js(self.MATRIX_PRELUDE + r"""
const m=build([
  {ID:"T1",Type:"Test",Result:"Passed"},{ID:"T2",Type:"Test"},
  {ID:"R1",Requirement:"Shall work","Verification Method":"Test; Telepathy","Verification Level":"Unit",Compliance:"Compliant","Verified by":"T1; T2"}
]);
assert.deepEqual(verificationMatrixCsvRows(m),[
  ["ID","Requirement","Inspection","Test","Unit","Acceptance","Tests","Compliance"],
  ["R1","Shall work","","X; Telepathy","X","","T1 (Passed); T2 (No result)","Compliant"]
]);
""")

    def test_shipped_uat_csv_links_tests_without_findings(self):
        config = load_config(None, {"id_column": "ID", "traceability": True})
        source = build_report_data(read_csv_table(str(UAT_CSV), config), config, "uat.html")["source"]["new"]
        script = (
            'const rows=' + json.dumps(source["rows"]) + ';\n' + TRACE_MODEL_JS
            + 'const index=buildTraceIndex(rows,row=>row.ID,{headers:' + json.dumps(source["headers"])
            + ',idColumn:"ID"});const types=type=>[...index.records.values()].filter(r=>r.type===type);'
            + 'console.log(JSON.stringify({issues:index.issues,tests:types("Test").length,plans:types("Test plan").length,'
            + 'verified:types("Test").filter(r=>r.incoming.some(e=>e.field==="Verified by")).length}));'
        )
        result = json.loads(subprocess.run(["node"], input=script, text=True, check=True,
                                           capture_output=True).stdout)
        self.assertEqual(result["issues"], [])
        self.assertEqual((result["plans"], result["tests"]), (2, 7))
        self.assertGreaterEqual(result["verified"], 1)
