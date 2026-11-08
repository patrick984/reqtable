from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.core import build_report_data, extract_report_json, load_config, read_csv_table
from reqtable.html_report import render_report
from reqtable.package import PACKAGE_MODEL_JS

PACKAGE = {
    "gate": {"id": "SRR", "name": "System Requirements Review", "produces": "SRR", "scope": "table"},
    "baseline": {"name": "SRR", "gate": "SRR", "system": None, "created": "2026-11-01", "createdBy": "pn",
                 "hash": "sha256:" + "ab" * 32, "hashOk": True, "source": "git"},
    "previous": None,
    "roles": [{"role": "reviewer", "min": 2}, {"role": "approver", "min": 1}],
    "signoffs": [],
    "approval": {"approved": False, "roles": []},
    "decisionOptions": ["Reviewed", "Changes requested", "Approved", "Rejected"],
}
DECISION = {"role": "reviewer", "user": "jsmith", "decision": "Reviewed", "date": "2026-11-08T10:00:00+01:00", "note": ""}


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class PackageModelTests(unittest.TestCase):
    def run_js(self, assertions, tz="UTC"):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n' + PACKAGE_MODEL_JS + assertions,
                       text=True, check=True, env={"TZ": tz, "PATH": shutil.which("node").rsplit("/", 1)[0]})

    def test_verification_labels(self):
        self.run_js(r"""
const labels=["good","unsigned","bad","unverifiable","cannot verify","Signature Good","recorded","",null,"surprise"].map(verificationLabel);
assert.deepEqual(labels,["Signature good","Unsigned","Bad signature","Cannot verify","Cannot verify","Signature good","Recorded","Recorded","Recorded","Recorded"]);
""")

    def test_signoff_table_groups_signoffs_and_decisions_by_role(self):
        self.run_js(r"""
const pkg={roles:[{role:"reviewer",min:2},{role:"approver",min:1}],signoffs:[
  {role:"reviewer",user:"a",decision:"Reviewed",date:"2026-11-02",verification:"good",counts:true},
  {role:"reviewer",user:"b",decision:"Reviewed",date:"2026-11-03",verification:"bad",counts:false,note:"hash"},
  {role:"observer",user:"o",decision:"Reviewed",date:"2026-11-03",verification:"unsigned"}]};
const decisions=[{role:"approver",user:"c",decision:"Approved",date:"d",note:""}];
const table=signoffTable(pkg,decisions);
assert.deepEqual(table.map(r=>[r.role,r.min,r.signoffs.length,r.pending.length]),
  [["reviewer",2,2,0],["approver",1,0,1],["observer",null,1,0]]);
assert.deepEqual(table[0].signoffs.map(s=>[s.user,s.verification,s.counts]),[["a","Signature good",true],["b","Bad signature",false]]);
assert.equal(table[2].signoffs[0].counts,true);
assert.equal(table[1].pending[0].user,"c");
""")

    def test_create_decision_trims_and_requires_fields(self):
        self.run_js(r"""
const now=new Date("2026-11-08T10:05:07Z");
const ok=createDecision({role:" approver ",user:"  pn ",decision:"Approved",note:"  fine\n"},now);
assert.deepEqual(ok.record,{role:"approver",user:"pn",decision:"Approved",date:"2026-11-08T05:05:07-05:00",note:"fine"});
assert.match(createDecision({role:"r",user:"  ",decision:"d"},now).error,/user/);
assert.match(createDecision({role:"",user:"u",decision:"d"},now).error,/role/);
assert.match(createDecision({role:"r",user:"u"},now).error,/decision/);
assert.equal(createDecision({role:"r",user:"u",decision:"d"},now).record.note,"");
""", tz="America/New_York")

    def test_date_has_local_offset_with_minutes(self):
        self.run_js(r"""
assert.equal(isoWithOffset(new Date("2026-11-08T10:05:07Z")),"2026-11-08T15:35:07+05:30");
""", tz="Asia/Kolkata")

    def test_remove_decision_matches_role_user_and_date(self):
        self.run_js(r"""
const a={role:"reviewer",user:"pn",decision:"Reviewed",date:"1",note:""},
  b={...a,date:"2"},c={...a,user:"other"},d={...a,role:"approver"};
assert.deepEqual(removeDecision([a,b,c,d],b),[a,c,d]);
assert.deepEqual(removeDecision([a,b],{...a,user:"PN"}),[a,b]);
""")


class PackageReportTests(unittest.TestCase):
    def build(self, **extra):
        config = load_config(None, {"id_column": "ID", "title": "Pkg"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "in.csv"
            path.write_text("ID,Text\nR1,One\n", encoding="utf-8")
            data = build_report_data(read_csv_table(str(path), config), config, "report.html")
        data.update(extra)
        return render_report(data)

    def test_package_report_has_cover_and_round_trips_decisions(self):
        report = self.build(package=PACKAGE, decisions=[DECISION])
        self.assertIn('id="package-cover"', report)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.html"
            path.write_text(report, encoding="utf-8")
            data = extract_report_json(str(path))
        self.assertEqual(data["decisions"], [DECISION])
        self.assertEqual(data["package"]["baseline"]["hash"], PACKAGE["baseline"]["hash"])

    def test_normal_report_has_no_cover(self):
        report = self.build()
        self.assertNotIn('id="package-cover"', report)
        self.assertNotIn("buildPackageCover", report)
