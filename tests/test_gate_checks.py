import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.comparison import COMPARISON_JS
from reqtable.gate_checks import GATE_CHECKS_JS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gate_checks.json"


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class GateCheckTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + COMPARISON_JS + GATE_CHECKS_JS + f"const fixture={FIXTURE.read_text()};\n" + assertions,
                       text=True, check=True)

    def test_shared_fixture_cases(self):
        self.run_js("""
for(const [index,item] of fixture.cases.entries()){
  const result=evaluateGateCheck({id:"c",description:"d",...item.check},fixture.rows,fixture.id_column,fixture.headers,item.system??null,[]);
  if(item.error!==undefined)assert.equal(result.error,item.error,`case ${index}`);
  else assert.deepEqual([result.error,result.total,result.failing],[null,item.total,item.failing],`case ${index}`);
}
""")

    def test_no_findings_fails_records_with_findings(self):
        self.run_js("""
const run=(findings,system=null,extra={})=>evaluateGateCheck({id:"c",description:"d",no_findings:true,...extra},
  fixture.rows,fixture.id_column,fixture.headers,system,findings);
const clean=run([]);
assert.deepEqual([clean.total,clean.failing,clean.global,gateCheckFailed(clean)],[8,[],[],false]);
const flagged=run([{id:"R2",field:"Allocated to",message:"x"},{id:"R2",field:"Verified by",message:"y"},{id:"T1",field:"Test plan",message:"z"}]);
assert.deepEqual([flagged.failing,gateCheckFailed(flagged)],[["R2","T1"],true]);
assert.deepEqual(run([{id:"R2",field:"f",message:"x"}],null,{applies_to:{type:"Test"}}).failing,[]);
assert.deepEqual(run([{id:"NOPE",field:"f",message:"x"}]).failing,[]);
assert.deepEqual(run([{id:"R2",field:"f",message:"x"}],"SYS-B").failing,[]);
assert.deepEqual(run([{id:"T1",field:"f",message:"x"}],null,{applies_to:{type:"Test"}}).failing,["T1"]);
const table=run([{id:null,field:"Part of",message:"Expected one top-level system. Found 0."}]);
assert.deepEqual([table.failing,table.global,table.total],[[""],["Expected one top-level system. Found 0."],9]);
""")

    def test_labels_separate_blocking_from_advisory_failures(self):
        self.run_js("""
const fail=enforcement=>({id:"c",enforcement,failing:["R1"],total:2,error:null});
const pass={id:"p",enforcement:"strict",failing:[],total:2,error:null};
assert.deepEqual(gateCheckLabel(fail("strict")),{tone:"gate-fail",mark:"✗ Fail · blocking"});
assert.deepEqual(gateCheckLabel(fail("advisory")),{tone:"gate-advisory",mark:"✗ Fail · advisory"});
assert.deepEqual(gateCheckLabel(fail(undefined)),{tone:"gate-advisory",mark:"✗ Fail · advisory"});
assert.deepEqual(gateCheckLabel(pass),{tone:"gate-pass",mark:"✓ Pass"});
assert.equal(gateCheckLabel({id:"e",enforcement:"strict",error:"x",failing:[]}).mark,"! Error · blocking");
assert.equal(gateCheckLabel({id:"e",enforcement:"advisory",error:"x",failing:[]}).mark,"! Error");
assert.deepEqual(gateBadgeLabel([pass,fail("advisory")]),{tone:"gate-advisory",mark:"✗ Not ready"});
assert.deepEqual(gateBadgeLabel([pass,fail("advisory"),fail("strict")]),{tone:"gate-fail",mark:"✗ Blocked"});
assert.deepEqual(gateBadgeLabel([pass]),{tone:"gate-pass",mark:"✓ Ready"});
assert.deepEqual(gateBadgeLabel([]),{tone:"gate-pass",mark:"✓ Ready"});
""")

    def test_linked_looks_up_every_row_not_only_the_scope(self):
        self.run_js("""
const run=(spec,system)=>evaluateGateCheck({id:"c",description:"d",applies_to:{type:"Requirement"},...spec},
  fixture.rows,fixture.id_column,fixture.headers,system,[]);
assert.deepEqual(run({linked:"Allocated to",leaf:true},"SYS-B").failing,[]);
assert.deepEqual(run({linked:"Allocated to",leaf:true},"SYS-A").failing,["R2"]);
assert.deepEqual(run({linked:"Verified by"},"SYS-B").failing,[]);
""")

    def test_applies_to_filters(self):
        self.run_js("""
const run=applies_to=>evaluateGateCheck({id:"c",description:"d",applies_to,filled:"Name"},
  fixture.rows,fixture.id_column,fixture.headers,null,[]);
assert.equal(run(undefined).total,3);
assert.equal(run({type:"System"}).total,2);
assert.equal(run({type:["System","Test"]}).total,4);
assert.equal(run({type:"Requirement",Priority:"Must"}).total,1);
assert.equal(run({type:"Requirement",Priority:["Must","Should"]}).total,2);
assert.equal(run({type:"Test",Owner:"x"}).error,"The table has no \\u201cOwner\\u201d column.");
assert.match(run({type:"Requirement",Owner:"x"}).error,/no \\u201cOwner\\u201d column/);
assert.equal(evaluateGateCheck({id:"c",description:"d"},fixture.rows,"ID",fixture.headers,null,[]).error,"The check has no condition.");
""")


if __name__ == "__main__":
    unittest.main()
