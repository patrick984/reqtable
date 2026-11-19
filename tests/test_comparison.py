from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.comparison import COMPARISON_JS

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "baseline_scope.json"


@unittest.skipUnless(
    shutil.which("node"), "Node is needed to exercise the report's JavaScript"
)
class ComparisonModelTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(
            ["node"],
            input='const assert=require("node:assert/strict");\n'
            + COMPARISON_JS
            + assertions,
            text=True,
            check=True,
        )

    def test_scope_matches_shared_fixture(self):
        self.run_js(f"""
const fixture={FIXTURE.read_text()};
for(const [index,{{system,includes,expected}}] of fixture.cases.entries()){{
  assert.deepEqual([...baselineScopeIds(fixture.rows,fixture.id_column,system,includes)],expected,`case ${{index}}`);
}}
""")

    def test_comparison_statuses_against_a_baseline(self):
        self.run_js(r"""
const columns=["ID","Type","Name","Allocated to","Status"],normalize=value=>value;
const row=(ID,Type,Name,alloc="",Status="")=>({ID,Type,Name,"Allocated to":alloc,Status});
const baseline=(extra={})=>({name:"SRR-1",system:"SYS-A",includes:["Requirement","System"],capturesStatus:false,
  statusColumns:["Status"],rows:[row("SYS-A","System","Product"),row("GONE","","Dropped","SYS-A"),
  row("SAME","","Same","SYS-A"),row("EDIT","","Old name","SYS-A"),row("STAT","","Same","SYS-A","Open")],...extra});
const current=[row("SYS-A","System","Product"),row("NEW","","Added","SYS-A"),row("SAME","","Same","SYS-A"),
  row("EDIT","","New name","SYS-A"),row("STAT","","Same","SYS-A","Closed"),row("ELSEWHERE","","Edited outside","SYS-Z")];
const statuses=extra=>comparisonStatuses(current,baselineSource(baseline(extra),current,"ID",[]),"ID",columns,normalize);
assert.deepEqual(statuses(),{"SYS-A":"unchanged",NEW:"added",GONE:"removed",SAME:"unchanged",EDIT:"changed",
  STAT:"unchanged",ELSEWHERE:"unchanged"});
assert.equal(statuses({capturesStatus:true}).STAT,"changed");
const pairs=comparisonPairs(current,baselineSource(baseline(),current,"ID",[]),"ID");
assert.deepEqual(pairs.map(pair=>pair.id),["SYS-A","NEW","GONE","SAME","EDIT","STAT","ELSEWHERE"]);
assert.equal(pairs.at(-1).oldRow,pairs.at(-1).newRow);
assert.deepEqual(comparisonStatuses(current,null,"ID",columns,normalize).EDIT,"unchanged");
""")
