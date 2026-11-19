from __future__ import annotations

import subprocess
import unittest

from reqtable.drafts import DRAFTS_JS


class DraftTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(
            ["node"],
            input='const assert=require("node:assert/strict");\n'
            + DRAFTS_JS.split("const draftStore=")[0]
            + assertions,
            text=True,
            check=True,
        )

    PRELUDE = r"""
const table=()=>({headers:["ID","Text"],rows:[{ID:"R1",Text:"One"},{ID:"R2",Text:"Two"}]});
const idOf=row=>row.ID;
const NOW=new Date("2026-11-08T10:00:00Z");
const draft=(extra={})=>buildDraft({path:"/r.html",fingerprint:"fp",title:"T",headers:["ID","Text"],
  rows:[{ID:"R1",Text:"One!"},{ID:"R2",Text:"Two"},{ID:"R3",Text:"New"}],baseRows:table().rows,
  comments:[],savedComments:[],rowsDirty:true,commentsDirty:false,idOf,now:NOW,...extra});
"""

    def test_fingerprint_is_stable_and_tracks_content(self):
        self.run_js(
            self.PRELUDE
            + r"""
assert.equal(reportFingerprint(table()),reportFingerprint(table()));
const cell=table();cell.rows[1].Text="Too";
assert.notEqual(reportFingerprint(cell),reportFingerprint(table()));
const header=table();header.headers=["ID","Body"];
assert.notEqual(reportFingerprint(header),reportFingerprint(table()));
const fewer=table();fewer.rows.pop();
assert.notEqual(reportFingerprint(fewer),reportFingerprint(table()));
"""
        )

    def test_record_carries_rows_that_round_trip_through_the_csv_serializer(self):
        self.run_js(
            self.PRELUDE
            + r"""
const record=draft(),rows=[{ID:"R1",Text:"a, \"b\"\nc"},{ID:"R2",Text:""}];
const written=draft({rows});
assert.equal(csvText(written.headers,written.rows,","),
  '﻿ID,Text\r\nR1,"a, ""b""\nc"\r\nR2,\r\n');
assert.equal(csvText(["A","B"],[{A:"x;y",B:"1"}],";"),'﻿A;B\r\n"x;y";1\r\n');
assert.deepEqual([record.key,record.fingerprint,record.title,record.savedAt,record.changedCount],
  ["/r.html","fp","T","2026-11-08T10:00:00.000Z",2]);
assert.equal(record.comments,null);
const commentsOnly=draft({rowsDirty:false,commentsDirty:true,comments:[{text:"a"},{text:"b"}],savedComments:[{text:"a"}]});
assert.equal(commentsOnly.rows,null);
assert.equal(commentsOnly.changedCount,0);
assert.equal(commentsOnly.changedComments,1);
"""
        )

    def test_stale_drafts_are_older_than_thirty_days_or_undated(self):
        self.run_js(
            self.PRELUDE
            + r"""
const at=days=>({savedAt:new Date(NOW-days*86400000).toISOString()});
assert.equal(draftIsStale(at(29),NOW),false);
assert.equal(draftIsStale(at(31),NOW),true);
assert.equal(draftIsStale({savedAt:"nonsense"},NOW),true);
assert.equal(draftIsStale({},NOW),true);
"""
        )

    def test_offer_depends_on_fingerprint_mode_and_difference(self):
        self.run_js(
            self.PRELUDE
            + r"""
const saved=table().rows,record=draft(),offer=(over={})=>draftOffer({record,fingerprint:"fp",developMode:true,
  savedRows:saved,savedComments:[],...over});
assert.equal(offer(),"restore");
assert.equal(offer({savedRows:record.rows}),null);
assert.equal(offer({fingerprint:"other"}),"download");
assert.equal(offer({developMode:false}),null);
assert.equal(offer({developMode:false,fingerprint:"other"}),null);
assert.equal(offer({record:null}),null);
const comments=draft({rowsDirty:false,commentsDirty:true,comments:[{text:"a"}]});
assert.equal(offer({record:comments,developMode:false}),"restore");
assert.equal(offer({record:comments,developMode:false,savedComments:[{text:"a"}]}),null);
const decisions=draft({rowsDirty:false,decisions:[{role:"reviewer"}],decisionsDirty:true});
assert.equal(offer({record:decisions,developMode:false}),"restore");
assert.equal(offer({record:decisions,developMode:false,savedDecisions:[{role:"reviewer"}]}),null);
assert.equal(draft().decisions,null);
assert.equal(draftMessage(decisions,"restore",()=>"then"),"Unsaved edits from then (decisions changed).");
"""
        )

    def test_banner_message(self):
        self.run_js(
            self.PRELUDE
            + r"""
const when=iso=>"on "+iso.slice(0,10);
assert.equal(draftMessage(draft(),"restore",when),"Unsaved edits from on 2026-11-08 (2 rows changed).");
assert.equal(draftMessage(draft({rows:[{ID:"R1",Text:"x"},{ID:"R2",Text:"Two"}]}),"restore",when),
  "Unsaved edits from on 2026-11-08 (1 row changed).");
assert.equal(draftMessage(draft(),"download",when),
  "Unsaved edits from an earlier version of this report (on 2026-11-08).");
const both=draft({commentsDirty:true,comments:[{text:"a"}]});
assert.equal(draftMessage(both,"restore",when),"Unsaved edits from on 2026-11-08 (2 rows changed, 1 comment changed).");
"""
        )


if __name__ == "__main__":
    unittest.main()
