from __future__ import annotations

import shutil
import subprocess
import unittest

from reqtable.html_report import JS

HISTORY_JS = JS[JS.index("function cloneRecords("):]
HISTORY_JS = HISTORY_JS[:HISTORY_JS.index("\n", HISTORY_JS.index("function redoEdit("))]

PRELUDE = r"""
const assert=require("node:assert/strict");
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{textContent:"",hidden:true,open:false});return elements.get(selector);};
const window={addEventListener(){}};
let renders=0;
const render=()=>{renders++;},scheduleAutosave=()=>{},draftChanged=()=>{};
const cloneValue=value=>JSON.parse(JSON.stringify(value));
const rows=()=>[{ID:"R1",Text:"One"},{ID:"R2",Text:"Two"}];
const state={currentRows:rows(),savedRows:rows(),comments:[],savedComments:[],
  qualityReview:{settings:{},dismissals:[]},savedQualityReview:{settings:{},dismissals:[]},
  decisions:[],savedDecisions:[],undo:[],redo:[],editingCell:null};
"""


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class EditHistoryTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input=PRELUDE + HISTORY_JS + "\n" + assertions, text=True, check=True)

    def test_same_records_compares_record_contents(self):
        self.run_js(r"""
assert.equal(sameRecords(rows(),rows()),true);
assert.equal(sameRecords([{ID:"R1",Text:"One"}],[{Text:"One",ID:"R1"}]),true);
assert.equal(sameRecords([{ID:"R1",Text:"One"}],[{ID:"R1",Text:"One!"}]),false);
assert.equal(sameRecords([{ID:"R1"}],[{ID:"R1",Text:""}]),false);
assert.equal(sameRecords([{ID:"R1",Text:undefined}],[{ID:"R1",Note:undefined}]),false);
assert.equal(sameRecords(rows(),rows().slice(1)),false);
assert.equal(sameRecords(rows(),rows().reverse()),false);
""")

    def test_clone_records_detaches_the_copy(self):
        self.run_js(r"""
const original=rows(),copy=cloneRecords(original);
copy[0].Text="Changed";copy.push({ID:"R3"});
assert.deepEqual(original,rows());
""")

    def test_undo_to_the_saved_state_clears_the_unsaved_indicator(self):
        self.run_js(r"""
updateDirty();
assert.equal(state.dirty,false);
remember();state.currentRows[1].Text="Two!";updateDirty();
assert.equal(state.requirementsDirty,true);
assert.equal($("#dirty-indicator").hidden,false);
assert.equal($("#dirty-details").textContent,"Unsaved requirements");
undoEdit();
assert.deepEqual(state.currentRows,rows());
assert.equal(state.dirty,false);
assert.equal($("#dirty-indicator").hidden,true);
assert.equal($("#dirty-details").textContent,"");
redoEdit();
assert.equal(state.currentRows[1].Text,"Two!");
assert.equal(state.dirty,true);
undoEdit();
assert.equal(state.dirty,false);
""")

    def test_undo_and_redo_restore_row_and_comment_changes_exactly(self):
        self.run_js(r"""
remember();state.currentRows.splice(1,0,{ID:"R9",Text:"New"});updateDirty();
remember();state.currentRows.reverse();updateDirty();
remember();state.currentRows.splice(0,1);state.comments.push({id:"c1",requirementId:"R1",column:"Text",text:"Hi",modified:null});updateDirty();
remember();state.comments[0].text="Edited";updateDirty();
const steps=[];
while(state.undo.length){steps.push(cloneValue({rows:state.currentRows,comments:state.comments}));undoEdit();}
assert.deepEqual(state.currentRows,rows());
assert.deepEqual(state.comments,[]);
assert.equal(state.dirty,false);
while(state.redo.length){redoEdit();assert.deepEqual({rows:state.currentRows,comments:state.comments},steps[state.redo.length]);}
assert.equal(state.comments[0].text,"Edited");
assert.equal(state.dirty,true);
""")


if __name__ == "__main__":
    unittest.main()
