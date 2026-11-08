from __future__ import annotations

DRAFTS_CSS = r"""
.draft-banner{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin:0 0 6px;padding:5px 9px;background:var(--panel);color:var(--text);border:1px solid var(--accent);border-radius:6px}
.draft-banner[hidden]{display:none}
"""

DRAFTS_HTML = """<div id="draft-banner" class="draft-banner" role="region" aria-label="Unsaved draft" hidden><span id="draft-message" role="status"></span><button id="draft-restore" type="button">Restore</button><button id="draft-download" type="button">Download CSV</button><button id="draft-discard" type="button">Discard</button></div>"""

DRAFTS_JS = r"""
const DRAFT_MAX_AGE_MS=30*24*60*60*1000,DRAFT_DELAY_MS=1000;
function csvField(value,delimiter){const text=String(value??"");return(/["\r\n]/.test(text)||text.includes(delimiter))?'"'+text.replace(/"/g,'""')+'"':text;}
function csvText(headers,rows,delimiter){
  const lines=[headers.map(x=>csvField(x,delimiter)).join(delimiter)];
  for(const row of rows)lines.push(headers.map(h=>csvField(row[h]??"",delimiter)).join(delimiter));
  return"﻿"+lines.join("\r\n")+"\r\n";
}
function reportFingerprint(table){
  const text=JSON.stringify([table.headers,table.rows]);
  let hash=2166136261;
  for(let i=0;i<text.length;i++)hash=Math.imul(hash^text.charCodeAt(i),16777619);
  return (hash>>>0).toString(16)+"-"+text.length;
}
function changedRowCount(baseRows,rows,idOf){
  const before=new Map(baseRows.map(row=>[idOf(row),JSON.stringify(row)])),after=new Map(rows.map(row=>[idOf(row),JSON.stringify(row)]));
  let count=0;
  for(const [id,json] of after)if(before.get(id)!==json)count++;
  for(const id of before.keys())if(!after.has(id))count++;
  return count;
}
function changedCommentCount(saved,comments){
  const before=new Set(saved.map(c=>JSON.stringify(c))),after=new Set(comments.map(c=>JSON.stringify(c)));
  return Math.max([...after].filter(json=>!before.has(json)).length,[...before].filter(json=>!after.has(json)).length);
}
function buildDraft({path,fingerprint,title,headers,rows,baseRows,comments,savedComments,rowsDirty,commentsDirty,idOf,now,decisions=[],decisionsDirty=false}){
  return {key:path,fingerprint,savedAt:now.toISOString(),title,headers:[...headers],
    rows:rowsDirty?JSON.parse(JSON.stringify(rows)):null,
    comments:commentsDirty?JSON.parse(JSON.stringify(comments)):null,
    changedCount:rowsDirty?changedRowCount(baseRows,rows,idOf):0,
    changedComments:commentsDirty?changedCommentCount(savedComments,comments):0,
    decisions:decisionsDirty?JSON.parse(JSON.stringify(decisions)):null};
}
function draftIsStale(record,now){
  const age=now-Date.parse(record.savedAt);
  return !(age<=DRAFT_MAX_AGE_MS);
}
function draftOffer({record,fingerprint,developMode,savedRows,savedComments,savedDecisions=[]}){
  if(!record)return null;
  if(record.fingerprint!==fingerprint)return developMode&&record.rows?"download":null;
  const rows=developMode&&record.rows&&JSON.stringify(record.rows)!==JSON.stringify(savedRows),
    comments=record.comments&&JSON.stringify(record.comments)!==JSON.stringify(savedComments),
    decisions=record.decisions&&JSON.stringify(record.decisions)!==JSON.stringify(savedDecisions);
  return rows||comments||decisions?"restore":null;
}
function draftMessage(record,offer,formatDate){
  const when=formatDate(record.savedAt),count=(n,noun)=>`${n} ${noun}${n===1?"":"s"} changed`;
  if(offer==="download")return`Unsaved edits from an earlier version of this report (${when}).`;
  const parts=[];
  if(record.rows)parts.push(count(record.changedCount,"row"));
  if(record.comments)parts.push(count(record.changedComments,"comment"));
  if(record.decisions)parts.push("decisions changed");
  return`Unsaved edits from ${when}`+(parts.length?` (${parts.join(", ")}).`:".");
}

const draftStore={
  run(mode,work){
    return new Promise(resolve=>{
      try{
        const opening=indexedDB.open("reqtable-drafts",1);
        opening.onupgradeneeded=()=>opening.result.createObjectStore("drafts",{keyPath:"key"});
        opening.onerror=opening.onblocked=()=>resolve(undefined);
        opening.onsuccess=()=>{
          const db=opening.result;
          try{
            const tx=db.transaction("drafts",mode),request=work(tx.objectStore("drafts"));
            tx.oncomplete=()=>{db.close();resolve(request?.result);};
            tx.onerror=tx.onabort=()=>{db.close();resolve(undefined);};
          }catch{db.close();resolve(undefined);}
        };
      }catch{resolve(undefined);}
    });
  },
  get:key=>draftStore.run("readonly",store=>store.get(key)),
  put:record=>draftStore.run("readwrite",store=>store.put(record)),
  remove:key=>draftStore.run("readwrite",store=>store.delete(key)),
  prune:now=>draftStore.run("readwrite",store=>{
    store.openCursor().onsuccess=event=>{
      const cursor=event.target.result;
      if(!cursor)return;
      if(draftIsStale(cursor.value,now))cursor.delete();
      cursor.continue();
    };
  })
};

const drafts={phase:"none",timer:0,record:null,enabled:false,fingerprint:""};
function draftWanted(){return $("#autosave").checked&&(state.commentsDirty||(developMode()&&state.requirementsDirty)||state.decisionsDirty);}
function draftChanged(){
  if(!drafts.enabled||drafts.phase==="offered")return;
  clearTimeout(drafts.timer);
  if(draftWanted()){
    drafts.phase="pending";
    drafts.timer=setTimeout(draftFlush,DRAFT_DELAY_MS);
  }else if(drafts.phase!=="none"){
    drafts.phase="none";
    draftStore.remove(location.pathname);
  }
}
function draftFlush(){
  clearTimeout(drafts.timer);
  if(drafts.phase!=="pending")return;
  drafts.phase="written";
  draftStore.put(buildDraft({path:location.pathname,fingerprint:drafts.fingerprint,title:data.meta.title,
    headers:data.source.new.headers,rows:state.currentRows,baseRows:data.source.new.rows,comments:state.comments,
    savedComments:state.savedComments,rowsDirty:developMode()&&state.requirementsDirty,commentsDirty:state.commentsDirty,
    idOf:rowId,now:new Date(),decisions:state.decisions,decisionsDirty:state.decisionsDirty}));
}
function closeDraftBanner(){
  $("#draft-banner").hidden=true;
  drafts.record=null;
  drafts.phase="none";
}
async function draftsStart(){
  if(!window.indexedDB||!(developMode()||data.options.commentsEnabled))return;
  drafts.fingerprint=reportFingerprint(data.source.new);
  await draftStore.prune(Date.now());
  const record=await draftStore.get(location.pathname),
    offer=draftOffer({record,fingerprint:drafts.fingerprint,developMode:developMode(),savedRows:state.savedRows,savedComments:state.savedComments,savedDecisions:state.savedDecisions});
  drafts.enabled=true;
  if(offer&&!state.dirty){
    drafts.record=record;
    drafts.phase="offered";
    $("#draft-message").textContent=draftMessage(record,offer,iso=>new Date(iso).toLocaleString());
    $("#draft-restore").hidden=offer!=="restore";
    $("#draft-download").hidden=offer!=="download";
    $("#draft-banner").hidden=false;
  }else{
    if(record&&!offer&&record.fingerprint===drafts.fingerprint)draftStore.remove(location.pathname);
    draftChanged();
  }
}
$("#draft-restore").addEventListener("click",()=>{
  const record=drafts.record;
  if(!record||(state.dirty&&!confirm("Replace the current changes with the unsaved draft?")))return;
  closeDraftBanner();
  remember();
  if(record.decisions)state.decisions=cloneValue(record.decisions);
  restoreHistory({rows:developMode()&&record.rows?record.rows:state.currentRows,comments:record.comments??state.comments});
  $("#save-status").textContent="Unsaved edits restored";
  restoreSelectedCell();
});
$("#draft-download").addEventListener("click",()=>{
  const record=drafts.record;
  if(!record?.rows)return;
  downloadBlob(new Blob([csvText(record.headers,record.rows,data.options.csvDelimiter||",")],{type:"text/csv;charset=utf-8"}),`${data.meta.baseFilename}-draft.csv`);
  $("#save-status").textContent="Draft CSV download initiated";
});
$("#draft-discard").addEventListener("click",()=>{
  draftStore.remove(location.pathname);
  closeDraftBanner();
  draftChanged();
  $("#save-status").textContent="Unsaved draft discarded";
});
window.addEventListener("pagehide",draftFlush);
document.addEventListener("visibilitychange",()=>{if(document.hidden)draftFlush();});
"""
