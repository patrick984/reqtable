import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.comparison import COMPARISON_JS
from reqtable.gate_checks import GATE_CHECKS_JS
from reqtable.traceability import TRACE_MODEL_JS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "change_control.json"
CHANGE = "(?:Changed|Added|Removed) since"


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class ChangeControlTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n' + COMPARISON_JS + GATE_CHECKS_JS
                       + TRACE_MODEL_JS + f"const fixture={FIXTURE.read_text()};\n"
                       + 'const identify=row=>row.ID,schema={headers:fixture.headers,idColumn:"ID"};\n'
                       + f"const isChange=issue=>/^{CHANGE}/.test(issue.message);\n" + assertions,
                       text=True, check=True)

    def test_shared_fixture_cases(self):
        self.run_js("""
const {issues}=buildTraceIndex(fixture.rows,identify,{...schema,controls:fixture.controls});
assert.deepEqual(issues.filter(isChange).map(({id,field,message})=>[id,field,message]),fixture.expected);
""")

    def test_change_findings_come_last_and_need_controls(self):
        self.run_js("""
const rows=[...fixture.rows,{ID:"X1",Type:"Mystery"}];
const withControls=buildTraceIndex(rows,identify,{...schema,controls:fixture.controls}).issues;
const without=buildTraceIndex(rows,identify,schema).issues;
assert.deepEqual(without.filter(isChange),[]);
const firstChange=withControls.findIndex(isChange);
assert.ok(firstChange>0&&withControls.slice(firstChange).every(isChange));
""")

    def test_affects_may_name_a_removed_record_only(self):
        self.run_js("""
const missing=issues=>issues.filter(issue=>issue.message.includes("is missing")).map(issue=>issue.message);
const rows=[...fixture.rows,{ID:"CR4",Type:"Change request",Affects:"R3; GONE","Change status":"Proposed"}];
assert.deepEqual(missing(buildTraceIndex(rows,identify,{...schema,controls:fixture.controls}).issues),["Target GONE is missing."]);
assert.deepEqual(missing(buildTraceIndex(rows,identify,schema).issues),["Target R3 is missing.","Target R3 is missing.","Target GONE is missing."]);
""")

    def test_change_status_applies_to_change_requests(self):
        self.run_js("""
const rows=[...fixture.rows,{ID:"R9",Type:"Requirement","Change status":"Approved"},
  {ID:"CR5",Type:"Change request",Affects:"R9","Change status":"Approved"}];
const {issues}=buildTraceIndex(rows,identify,schema);
assert.deepEqual(issues.filter(issue=>issue.id==="R9").map(issue=>issue.message),["Change status applies to change requests."]);
assert.deepEqual(issues.filter(issue=>issue.id==="CR5"),[]);
""")

    def test_rejected_and_proposed_requests_do_not_authorise(self):
        self.run_js("""
const rows=fixture.rows.map(row=>row.ID==="CR1"?{...row,"Change status":"Rejected"}:row);
const messages=buildTraceIndex(rows,identify,{...schema,controls:fixture.controls}).issues.filter(isChange).map(issue=>issue.id);
assert.deepEqual(messages,["R1","R2","R5","R6","R7"]);
""")

    def test_unchanged_since_gate_check(self):
        self.run_js("""
const run=(system,extra={},controls=fixture.controls)=>{
  const {issues}=buildTraceIndex(fixture.rows,identify,{...schema,controls});
  return evaluateGateCheck({id:"c",description:"d",unchanged_since:true,...extra},fixture.rows,"ID",fixture.headers,system,issues,controls);
};
const all=run(null);
assert.deepEqual([all.error,all.total,all.failing],[null,fixture.rows.length+2,["R2","R5","R6","R7"]]);
assert.equal(gateCheckFailed(all),true);
const sysB=run("SYS-B");
assert.deepEqual([sysB.failing.includes("R2"),sysB.failing.includes("R5"),sysB.failing.includes("R7")],[false,true,false]);
assert.deepEqual(run(null,{applies_to:{type:"System"}}).failing,["R7"]);
const clean=evaluateGateCheck({id:"c",description:"d",unchanged_since:true},fixture.rows,"ID",fixture.headers,null,[],null);
assert.deepEqual([clean.total,clean.failing,gateCheckFailed(clean)],[fixture.rows.length,[],false]);
const dup=evaluateGateCheck({id:"c",description:"d",unchanged_since:true},fixture.rows,"ID",fixture.headers,null,
  [{id:"R2",field:"a",message:"Changed since X (a) without an approved change request."},{id:"R2",field:"b",message:"Added since X without an approved change request."},{id:"R2",field:"b",message:"other"}],null);
assert.deepEqual(dup.failing,["R2"]);
""")
