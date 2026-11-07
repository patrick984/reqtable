from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.core import build_report_data, load_config, read_csv_table
from reqtable.traceability import TRACE_COLUMNS, TRACE_MODEL_JS
from reqtable.values import VALUE_EDIT_JS
from tests.test_core import TempFiles

UAT_CSV = Path(__file__).resolve().parent.parent / "requirements-uat.csv"


class ValueColumnTests(TempFiles):
    def test_traceability_adds_field_and_multiple_columns(self):
        path = self.write("rows.csv", "ID,Priority\nR,Must\n")
        config = load_config(None, {"id_column": "ID", "traceability": True})
        data = build_report_data(read_csv_table(str(path), config), config, "rows.html")
        headers = data["source"]["new"]["headers"]
        for name in ("Field", "Multiple"):
            self.assertIn(name, TRACE_COLUMNS)
            self.assertIn(name, headers)


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class ValueModelTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + TRACE_MODEL_JS + assertions, text=True, check=True)

    PRELUDE = r"""
const HEADERS=["ID","Type","Name","Definition","Aliases","Priority","Method","Field","Multiple","Part of","Source refs"];
const value=(ID,Field,Name,extra={})=>({ID,Type:"Value",Field,Name,Definition:"Defined.",...extra});
const field=(ID,Name,Multiple="",extra={})=>({ID,Type:"Field",Name,Definition:"Describes.",Multiple,...extra});
const req=(ID,extra)=>({ID,Type:"Requirement",...extra});
const index=rows=>buildTraceIndex([{ID:"SYS",Type:"System"},...rows],row=>row.ID,{headers:HEADERS,idColumn:"ID"});
const findings=rows=>index(rows).issues.map(({id,field,message})=>`${id}|${field}|${message}`);
const base=[
  value("V1","Priority","Must"),value("V2","Priority","Should"),
  value("M1","Method","Manual browser test",{Aliases:"Manual verification; Browser check"}),
  value("M2","Method","Automated test"),field("F2","Method","yes")
];
"""

    def test_clean_table_and_unconstrained_column_have_no_findings(self):
        self.run_js(self.PRELUDE + r"""
assert.deepEqual(findings([...base,req("R1",{Priority:"Must",Method:"Manual browser test; Automated test"}),
  req("R2",{Priority:" Should "}),req("R3",{})]),[]);
const loose=[value("V1","Priority","Must"),req("R1",{Method:"Anything goes"})];
assert.deepEqual(findings(loose),[]);
const rules=index(base).values;
assert.deepEqual([...rules.keys()].sort(),["Method","Priority"]);
assert.equal(rules.get("Priority").field,null);
assert.equal(rules.get("Priority").multiple,false);
assert.equal(rules.get("Method").multiple,true);
assert.equal(rules.get("Method").aliases.get("Browser check").row.Name,"Manual browser test");
assert.deepEqual([...rules.get("Method").values.keys()],["Manual browser test","Automated test"]);
""")

    def test_undefined_alias_and_case_spellings(self):
        self.run_js(self.PRELUDE + r"""
const found=findings([...base,req("R1",{Priority:"Shoud"}),req("R2",{Priority:"must"}),
  req("R3",{Method:"Manual verification"}),req("R4",{Priority:"Must; Should"}),
  req("R5",{Method:"automated TEST"}),{ID:"N",Type:"Need",Priority:"Urgent"}]);
assert.deepEqual(found,[
  "R1|Priority|“Shoud” is not a defined Priority value.",
  "R2|Priority|“must” is spelled differently from the defined value; use “Must”.",
  "R3|Method|“Manual verification” is a replaced spelling; use “Manual browser test”.",
  "R4|Priority|“Must; Should” is not a defined Priority value. Priority allows one value.",
  "R5|Method|“automated TEST” is spelled differently from the defined value; use “Automated test”.",
  "N|Priority|“Urgent” is not a defined Priority value."
]);
""")

    def test_multiple_values_split_and_flag_duplicates(self):
        self.run_js(self.PRELUDE + r"""
const found=findings([...base,
  req("R1",{Method:"Automated test; Browser check; Bogus;; "}),
  req("R2",{Method:"Automated test; automated test"})]);
assert.deepEqual(found,[
  "R1|Method|“Browser check” is a replaced spelling; use “Manual browser test”.",
  "R1|Method|“Bogus” is not a defined Method value.",
  "R2|Method|“automated test” is listed more than once.",
  "R2|Method|“automated test” is spelled differently from the defined value; use “Automated test”."
]);
""")

    def test_invalid_value_records(self):
        self.run_js(self.PRELUDE + r"""
const found=findings([
  value("V1","Priority","Must"),value("DUP","Priority","must"),
  value("A1","Method","One",{Aliases:"Uno"}),value("A2","Method","Two",{Aliases:"uno; One"}),
  {ID:"NOFIELD",Type:"Value",Name:"Orphan",Definition:"Defined."},
  value("GHOST","Colour","Red"),value("RES1","Type","System"),value("RES2","ID","X"),
  value("RES3","Part of","SYS"),value("RES4","Multiple","Yes"),
  value("NONAME","Priority",""),value("NODEF","Priority","Could",{Definition:" "}),
  value("LINK","Priority","Won't",{"Source refs":"SYS"})
]);
const has=text=>assert(found.some(line=>line===text),`${text}\n${found.join("\n")}`);
has("DUP|Name|Another Priority value is named “must”.");
has("A2|Aliases|“uno” is already a Method value name or alias.");
has("A2|Aliases|“One” is already a Method value name or alias.");
has("NOFIELD|Field|Enter the column this value belongs to.");
has("GHOST|Field|There is no “Colour” column.");
for(const id of ["RES1","RES2","RES3","RES4"]){
  assert(found.some(line=>line.startsWith(`${id}|Field|`)&&line.includes("reserved column")),id);
}
has("NONAME|Name|Enter the allowed value.");
has("NODEF|Definition|Explain what this value means.");
has("LINK|Source refs|Source refs does not apply to Value records.");
assert.equal(index([value("GHOST","Colour","Red")]).values.size,0);
""")

    def test_invalid_field_records(self):
        self.run_js(self.PRELUDE + r"""
const found=findings([
  value("V1","Priority","Must"),field("F1","Priority"),field("F2","Priority","Yes"),
  field("NONAME",""),field("GHOST","Colour"),field("RES","Type"),
  field("BAD","Method","Maybe"),field("NODEF","Source refs","",{Definition:""}),
  field("DOC","Part of"),
  field("UNUSED","Definition","No"),field("LINK","Aliases","",{"Part of":"SYS"})
]);
const has=text=>assert(found.includes(text),`${text}\n${found.join("\n")}`);
has("F1|Name|Another Field record describes Priority.");
has("F2|Name|Another Field record describes Priority.");
has("NONAME|Name|Enter the column this record describes.");
has("GHOST|Name|There is no “Colour” column.");
has("RES|Name|“Type” is a reserved column and cannot have defined values.");
has("BAD|Multiple|Enter Yes or No.");
has("NODEF|Definition|Describe this column.");
has("LINK|Part of|Part of does not apply to Field records.");
assert(!found.some(line=>line.startsWith("UNUSED|")));
const rules=index([value("V1","Priority","Must"),field("F1","Priority","Yes")]).values;
assert.equal(rules.get("Priority").field.id,"F1");
assert.equal(rules.get("Priority").multiple,true);
""")

    def test_shipped_uat_csv_has_no_value_findings(self):
        config = load_config(None, {"id_column": "ID", "traceability": True})
        source = build_report_data(read_csv_table(str(UAT_CSV), config), config, "uat.html")["source"]["new"]
        script = (
            'const rows=' + json.dumps(source["rows"]) + ';\n' + TRACE_MODEL_JS
            + 'const index=buildTraceIndex(rows,row=>row.ID,{headers:' + json.dumps(source["headers"])
            + ',idColumn:"ID"});console.log(JSON.stringify({issues:index.issues,'
            + 'columns:[...index.values.keys()]}));'
        )
        result = json.loads(subprocess.run(["node"], input=script, text=True, check=True,
                                           capture_output=True).stdout)
        self.assertEqual(result["issues"], [])
        self.assertEqual(sorted(result["columns"]), ["Priority", "Verification Method"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class ValueEditorTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + TRACE_MODEL_JS + VALUE_EDIT_JS + assertions, text=True, check=True)

    PRELUDE = ValueModelTests.PRELUDE + r"""
const names=source=>source.items.map(item=>item.value);
const rule=column=>index(base).values.get(column);
const pick=(source,text,caret=text.length)=>matchSuggestions(source,text,caret).map(item=>item.value);
"""

    def test_defined_values_carry_definitions_and_skip_aliases(self):
        self.run_js(self.PRELUDE + r"""
const source=suggestionSource(rule("Priority"),[],"Priority");
assert.deepEqual(source.items,[{value:"Must",detail:"Defined."},{value:"Should",detail:"Defined."}]);
assert.equal(source.defined,true);
assert.equal(source.multiple,false);
const method=suggestionSource(rule("Method"),[],"Method");
assert.deepEqual(names(method),["Manual browser test","Automated test"]);
assert.equal(method.multiple,true);
""")

    def test_observed_values_keep_prefix_matching_and_limits(self):
        self.run_js(self.PRELUDE + r"""
const rows=[{Cat:"Zed"},{Cat:"Alpha"},{Cat:"Alpine "},{Cat:""}];
const source=suggestionSource(undefined,rows,"Cat");
assert.deepEqual(source.items,[{value:"Alpha",detail:""},{value:"Alpine",detail:""},{value:"Zed",detail:""}]);
assert.deepEqual(pick(source,"Al"),["Alpha","Alpine"]);
assert.deepEqual(pick(source,"pha"),[]);
assert.deepEqual(pick(source,"Alpha"),[]);
assert.deepEqual(suggestionSource(undefined,[{Cat:"a\nb"}],"Cat").items,[]);
assert.deepEqual(suggestionSource(undefined,[{Cat:"x".repeat(61)}],"Cat").items,[]);
assert.deepEqual(suggestionSource(undefined,Array.from({length:51},(_,i)=>({Cat:"v"+i})),"Cat").items,[]);
""")

    def test_defined_values_match_prefix_before_contained_text(self):
        self.run_js(self.PRELUDE + r"""
const source=suggestionSource(rule("Method"),[],"Method");
assert.deepEqual(pick(source,"browser"),["Manual browser test"]);
assert.deepEqual(pick(source,"A"),["Automated test","Manual browser test"]);
assert.deepEqual(pick(source,"TEST"),["Manual browser test","Automated test"]);
assert.deepEqual(pick(source,"auto"),["Automated test"]);
assert.deepEqual(pick(source,"zzz"),[]);
""")

    def test_multiple_columns_work_on_the_segment_under_the_caret(self):
        self.run_js(self.PRELUDE + r"""
const source=suggestionSource(rule("Method"),[],"Method");
const text="Manual browser test; au; ";
assert.deepEqual(pick(source,text,text.indexOf("au")+1),["Automated test"]);
assert.deepEqual(pick(source,"Automated test; ",16),["Manual browser test"]);
assert.deepEqual(pick(source,"Automated test; Manual browser test",5),[]);
assert.deepEqual(pick(source,"Manual browser test; ",3),[]);
""")

    def test_choosing_replaces_only_the_segment(self):
        self.run_js(self.PRELUDE + r"""
const multi=suggestionSource(rule("Method"),[],"Method");
const middle="Manual browser test;au;Documentation review";
const joined="Manual browser test; Automated test; Documentation review";
assert.deepEqual(chooseSuggestion(multi,middle,middle.indexOf("au")+1,"Automated test"),
  {text:joined,caret:joined.length,commit:false});
assert.deepEqual(chooseSuggestion(multi,"Manual browser test; ",21,"Automated test"),
  {text:"Manual browser test; Automated test",caret:35,commit:false});
assert.deepEqual(chooseSuggestion(multi,"",0,"Automated test"),{text:"Automated test",caret:14,commit:false});
const single=suggestionSource(rule("Priority"),[],"Priority");
assert.deepEqual(chooseSuggestion(single,"Mu",2,"Must"),{text:"Must",caret:4,commit:true});
""")

    def test_findings_group_by_record_and_column(self):
        self.run_js(self.PRELUDE + r"""
const found=index([...base,req("R1",{Priority:"Shoud",Method:"Nope; Automated test"}),req("R2",{Priority:"Must"})]).issues;
const cells=groupFindingsByCell(found);
assert.deepEqual([...cells.keys()],["R1"]);
assert.deepEqual([...cells.get("R1").keys()].sort(),["Method","Priority"]);
assert.equal(cells.get("R1").get("Priority").length,1);
const two=groupFindingsByCell([{id:null,field:"Part of",message:"x"},{id:"A",field:"ID",message:"y"},{id:"A",field:"ID",message:"z"}]);
assert.equal(two.get("A").get("ID").length,2);
assert.equal(two.size,1);
""")


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class ValueRenameTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + VALUE_EDIT_JS + assertions, text=True, check=True)

    def test_single_value_columns_match_the_whole_cell(self):
        self.run_js(r"""
const rows=[{ID:"A",Priority:"Must"},{ID:"B",Priority:" Must "},{ID:"C",Priority:"Must have"},
  {ID:"D",Priority:"must"},{ID:"E",Priority:"Should"},{ID:"F"}];
const changes=renameValueUses(rows,"Priority",false,"Must","Required");
assert.deepEqual(changes.map(({row,value})=>[row.ID,value]),[["A","Required"],["B","Required"]]);
""")

    def test_multiple_columns_match_exact_segments_and_normalize(self):
        self.run_js(r"""
const rows=[{ID:"A",Method:"Manual;Automated test"},{ID:"B",Method:"Manual test; Automated test"},
  {ID:"C",Method:"manual"},{ID:"D",Method:"Documentation;  Manual ; "}];
const changes=renameValueUses(rows,"Method",true,"Manual","Manual UAT");
assert.deepEqual(changes.map(({row,value})=>[row.ID,value]),
  [["A","Manual UAT; Automated test"],["D","Documentation; Manual UAT"]]);
""")

    def test_value_and_field_records_are_left_alone(self):
        self.run_js(r"""
const rows=[{ID:"V",Type:"Value",Priority:"Must"},{ID:"F",Type:"Field",Priority:"Must"},
  {ID:"R",Type:"Requirement",Priority:"Must"},{ID:"N",Type:"Need",Priority:"Must"}];
assert.deepEqual(renameValueUses(rows,"Priority",false,"Must","Shall").map(change=>change.row.ID),["R","N"]);
assert.deepEqual(renameValueUses(rows,"Priority",false,"Shall","Must"),[]);
""")

    def test_value_ids_use_the_field_and_name_and_stay_unique(self):
        self.run_js(r"""
assert.equal(valueSlug("  Won't / Will not "),"WON-T-WILL-NOT");
assert.equal(valueRecordId("Priority","Won't",new Set()),"VAL-PRIORITY-WON-T");
assert.equal(valueRecordId("Verification Method","Manual browser test",new Set()),"VAL-VERIFICATION-METHOD-MANUAL-BROWSER-TEST");
const taken=new Set(["VAL-PRIORITY-MUST","VAL-PRIORITY-MUST-2"]);
assert.equal(valueRecordId("Priority","must",taken),"VAL-PRIORITY-MUST-3");
assert.equal(valueRecordId("Priority","???",new Set()),"VAL-PRIORITY-VALUE");
""")
