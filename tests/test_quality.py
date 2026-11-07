import shutil
import subprocess
import unittest

from reqtable.quality import QUALITY_JS


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class QualityTests(unittest.TestCase):
    def test_source_offsets_and_content_bound_dismissals(self):
        script = """
const assert=require("node:assert/strict");
const $=()=>null;
const data={meta:{idColumn:"ID"},source:{new:{headers:["ID","Requirement","Verification"]}}};
const rowId=row=>row.ID;
const row={ID:"R1",Requirement:"The system shall ignore `quickly` and respond quickly, then retry quickly."};
const state={currentRows:[row],qualityReview:{settings:{},dismissals:[]}};
"""
        script += QUALITY_JS.split("function underlineQualityPhrases", 1)[0]
        script += """
quality.checked=true;
scanQuality();
const findings=()=>quality.findings.get("R1")?.get("Requirement")??[];
const [first,second]=findings();
assert.equal(findings().length,2);
assert.equal(first.start,row.Requirement.indexOf("quickly,"));
assert.equal(second.start,row.Requirement.lastIndexOf("quickly"));
state.qualityReview.dismissals.push({id:"R1",column:"Requirement",value:row.Requirement,
    ...first,obligation:null,reason:"Accepted"});
scanQuality();
assert.deepEqual(findings(),[second]);
assert.equal(quality.dismissed[0].reason,"Accepted");
row.Requirement+=" After startup.";
scanQuality();
assert.equal(findings().length,2);
assert.equal(quality.dismissed.length,0);
state.qualityReview.settings={required_columns:["Verification"],obligation:null,
    disabled_rules:["ambiguous-timing"]};
scanQuality();
assert.deepEqual(findings(),[]);
assert.equal(quality.findings.get("R1").get("Verification")[0].rule,"missing-content");
"""
        subprocess.run(["node"], input=script, text=True, check=True)
