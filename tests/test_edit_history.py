from __future__ import annotations

import shutil
import subprocess
import unittest

from reqtable.html_report import JS

HISTORY_JS = JS[JS.index("function cloneRecords(") :]
HISTORY_JS = HISTORY_JS[
    : HISTORY_JS.index("\n", HISTORY_JS.index("function redoEdit("))
]

PRELUDE = r"""
const assert=require("node:assert/strict");
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{textContent:"",hidden:true,open:false});return elements.get(selector);};
const window={addEventListener(){}};
let renders=0,rendered=[];
const render=()=>{renders++;},scheduleAutosave=()=>{},draftChanged=()=>{};
const renderChanges=changes=>{renders++;rendered.push(changes);};
const rowId=row=>row.ID;
const cloneValue=value=>JSON.parse(JSON.stringify(value));
const rows=()=>[{ID:"R1",Text:"One"},{ID:"R2",Text:"Two"}];
const state={currentRows:rows(),savedRows:rows(),comments:[],savedComments:[],
  qualityReview:{settings:{},dismissals:[]},savedQualityReview:{settings:{},dismissals:[]},
  decisions:[],savedDecisions:[],undo:[],redo:[],editingCell:null};
"""


@unittest.skipUnless(
    shutil.which("node"), "Node is needed to exercise the report's JavaScript"
)
class EditHistoryTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(
            ["node"],
            input=PRELUDE + HISTORY_JS + "\n" + assertions,
            text=True,
            check=True,
        )

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

    def test_changed_records_lists_each_changed_record_and_column(self):
        self.run_js(r"""
const after=rows();after[1].Text="Two!";after[1].Note="new";
assert.deepEqual(changedRecords(rows(),after,rowId),[{index:1,id:"R2",columns:new Set(["Text","Note"])}]);
const dropped=rows();delete dropped[0].Text;
assert.deepEqual(changedRecords(rows(),dropped,rowId),[{index:0,id:"R1",columns:new Set(["Text"])}]);
assert.deepEqual(changedRecords(rows(),rows(),rowId),[]);
""")

    def test_changed_records_refuses_inserts_removals_reorders_and_id_changes(self):
        self.run_js(r"""
assert.equal(changedRecords(rows(),[...rows(),{ID:"R3"}],rowId),null);
assert.equal(changedRecords(rows(),rows().slice(1),rowId),null);
assert.equal(changedRecords(rows(),rows().reverse(),rowId),null);
const renamed=rows();renamed[0].ID="R7";
assert.equal(changedRecords(rows(),renamed,rowId),null);
""")

    def test_rows_redraw_alone_only_when_nothing_else_reads_the_changed_columns(self):
        self.run_js(r"""
const plain={comparing:false,qualityOnly:false,ranged:false,idColumn:"ID",sortColumn:null,filtered:()=>false,traceColumns:new Set()};
const edit=column=>[{index:0,id:"R1",columns:new Set([column])}];
assert.equal(confinedToRows(edit("Text"),plain),true);
assert.equal(confinedToRows([],plain),true);
assert.equal(confinedToRows(edit("ID"),plain),false);
assert.equal(confinedToRows(edit("Text"),{...plain,sortColumn:"Text"}),false);
assert.equal(confinedToRows(edit("Text"),{...plain,sortColumn:"Priority"}),true);
assert.equal(confinedToRows(edit("Text"),{...plain,filtered:column=>column==="Text"}),false);
assert.equal(confinedToRows(edit("Text"),{...plain,filtered:column=>column==="Priority"}),true);
assert.equal(confinedToRows(edit("Text"),{...plain,comparing:true}),false);
assert.equal(confinedToRows(edit("Text"),{...plain,qualityOnly:true}),false);
assert.equal(confinedToRows(edit("Text"),{...plain,ranged:true}),false);
assert.equal(confinedToRows(edit("Verified by"),{...plain,traceColumns:new Set(["Verified by"])}),false);
assert.equal(confinedToRows(edit("Text"),{...plain,traceColumns:new Set(["Verified by"])}),true);
assert.equal(confinedToRows(edit("Text"),{...plain,traceColumns:null}),false);
""")

    def test_undo_of_a_value_edit_restores_into_the_same_records(self):
        self.run_js(r"""
const live=state.currentRows.slice();
remember();state.currentRows[1].Text="Two!";updateDirty();
undoEdit();
assert.ok(state.currentRows.every((row,i)=>row===live[i]));
assert.deepEqual(state.currentRows,rows());
assert.deepEqual(rendered.at(-1),[{index:1,id:"R2",columns:new Set(["Text"])}]);
redoEdit();
assert.ok(state.currentRows.every((row,i)=>row===live[i]));
assert.equal(state.currentRows[1].Text,"Two!");
remember();state.currentRows.push({ID:"R3"});updateDirty();
undoEdit();
assert.equal(rendered.at(-1),null);
assert.deepEqual(state.currentRows,[{ID:"R1",Text:"One"},{ID:"R2",Text:"Two!"}]);
""")


if __name__ == "__main__":
    unittest.main()
