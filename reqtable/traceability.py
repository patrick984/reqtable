"""Offline traceability model and report controls for opted-in CSVs."""

TRACE_COLUMNS = (
    "Type", "Name", "Requirement", "Part of", "Allocated to", "Owner",
    "Derived from", "Source refs", "Reference", "Origin", "Rationale",
)

TRACE_MODEL_JS = r"""
const traceFields={
  "Part of": {from:["System"],to:["System"],single:true},
  "Allocated to": {from:["Requirement"],to:["System"]},
  "Owner": {from:["Requirement"],to:["System"],single:true},
  "Derived from": {from:["Requirement"],to:["Requirement"]},
  "Source refs": {from:["Requirement","Need"],to:["Need","Source"]}
};
function traceType(row){
  const value=String(row.Type??"").trim();
  return value||"Requirement";
}
function traceIds(value){
  return String(value??"").split(";").map(id=>id.trim()).filter(Boolean);
}
function traceTargetTypes(field,type){
  return field==="Source refs"&&type==="Need"?["Source"]:traceFields[field].to;
}
function buildTraceIndex(rows,identify){
  const records=new Map(rows.map(row=>{
    const id=identify(row);
    return [id,{id,row,type:traceType(row),outgoing:new Map(),incoming:[]}];
  }));
  const issues=[];
  const issue=(id,field,message)=>issues.push({id,field,message});
  const systems=[];
  for(const record of records.values()){
    const {id,row,type}=record;
    if(id.includes(";"))issue(id,"ID","A traceable ID cannot contain a semicolon.");
    if(type==="System")systems.push(record);
    if(!["System","Requirement","Need","Source"].includes(type))issue(id,"Type",`Unknown record type “${type}”.`);
    if(type==="Requirement"&&row.Origin?.trim()==="Self-derived"&&!row.Rationale?.trim()){
      issue(id,"Rationale","Explain why this self-derived requirement is needed.");
    }
    for(const [field,rule] of Object.entries(traceFields)){
      const ids=traceIds(row[field]);
      if(!ids.length)continue;
      if(!rule.from.includes(type)){
        issue(id,field,`${field} does not apply to ${type} records.`);
        continue;
      }
      if(rule.single&&ids.length>1)issue(id,field,"Select at most one target.");
      const seen=new Set(),targets=[];
      for(const targetId of ids){
        if(seen.has(targetId)){
          issue(id,field,`Duplicate reference to ${targetId}.`);
          continue;
        }
        seen.add(targetId);
        const target=records.get(targetId);
        if(targetId===id)issue(id,field,"A record cannot link to itself.");
        else if(!target)issue(id,field,`Target ${targetId} is missing.`);
        else if(!traceTargetTypes(field,type).includes(target.type)){
          issue(id,field,`Target ${targetId} has type ${target.type}. Expected ${traceTargetTypes(field,type).join(" or ")}.`);
        }else{
          targets.push(target);
          if(!rule.single||ids.length===1)target.incoming.push({field,record});
        }
      }
      record.outgoing.set(field,targets);
    }
  }
  const roots=systems.filter(({row})=>!traceIds(row["Part of"]).length);
  if(roots.length!==1)issue(null,"Part of",`Expected one top-level system. Found ${roots.length}.`);

  for(const field of ["Part of","Derived from"]){
    const done=new Set(),active=new Set();
    for(const start of records.values()){
      if(done.has(start))continue;
      const stack=[{record:start,targets:(start.outgoing.get(field)??[]).values()}];
      active.add(start.id);
      while(stack.length){
        const frame=stack.at(-1),{value:target,done:exhausted}=frame.targets.next();
        if(exhausted){
          active.delete(frame.record.id);
          done.add(frame.record.id);
          stack.pop();
        }else if(active.has(target.id)){
          const cycle=stack.slice(stack.findIndex(item=>item.record===target)).map(item=>item.record.id);
          issue(frame.record.id,field,`Cycle: ${[...cycle,target.id].join(" → ")}.`);
        }else if(!done.has(target.id)){
          active.add(target.id);
          stack.push({record:target,targets:(target.outgoing.get(field)??[]).values()});
        }
      }
    }
  }
  return {records,systems,roots,issues};
}
function traceCanLink(record,field,target){
  const rule=traceFields[field];
  if(record===target||record.id.includes(";")||target.id.includes(";")||!rule.from.includes(record.type)
      ||!traceTargetTypes(field,record.type).includes(target.type)
      ||traceIds(record.row[field]).includes(target.id))return false;
  if(field!=="Part of"&&field!=="Derived from")return true;
  const seen=new Set(),pending=[target];
  while(pending.length){
    const next=pending.pop();
    if(next===record)return false;
    if(seen.has(next))continue;
    seen.add(next);
    // Inspect all typed references, including a malformed single-parent field.
    pending.push(...(next.outgoing.get(field)??[]));
  }
  return true;
}
function traceIncomingChanges(rows,oldId,newId){
  const changes=[];
  for(const row of rows){
    for(const field of Object.keys(traceFields)){
      const value=row[field]??"";
      const parts=value.split(";");
      if(!parts.some(part=>part.trim()===oldId))continue;
      const updated=newId
        ?parts.map(part=>part.trim()===oldId?part.replace(oldId,()=>newId):part)
        :parts.filter(part=>part.trim()!==oldId);
      const first=newId?updated.findIndex(part=>part.trim()===newId):-1;
      const valueAfter=updated.filter((part,i)=>part.trim()!==newId||i===first).join(";").trim();
      changes.push({row,field,value:valueAfter});
    }
  }
  return changes;
}
"""

TRACE_UI_JS = r"""
const trace=(()=>{
  const panel=$("#trace-panel"),tree=$("#trace-tree"),detail=$("#trace-record");
  const editor=$("#trace-editor"),picker=$("#trace-picker"),status=$("#trace-status");
  let index, system="", descendants=true, selected=null, pending=null, revealed=null;
  let scope=new Set(), editedRecord=null, linkEdit=null;
  const label=record=>record.row.Name?.trim()||record.id;
  const caption=record=>label(record)===record.id?record.id:`${label(record)} (${record.id})`;
  const writable=()=>developMode()&&!state.editingCell;
  const visible=id=>[...tableBody.rows].some(row=>row.dataset.rowId===id);
  const link=(id,label)=>`<button type="button" class="trace-link" data-trace-jump="${escapeHtml(id)}">${escapeHtml(label)}</button>`;
  const focusControl=(container,attribute,value)=>{
    [...container.querySelectorAll(`[${attribute}]`)].find(button=>button.getAttribute(attribute)===value)?.focus();
  };

  function matches(row){
    if(!system)return true;
    const record=index.records.get(row.id);
    const allocated=record?(record.outgoing.get("Allocated to")??[]).map(target=>target.id)
      :traceIds(row.cells["Allocated to"]?.old);
    const type=record?.type||(row.cells.Type?.old?.trim()||"Requirement");
    return type==="Requirement"&&allocated.some(id=>scope.has(id));
  }
  function refresh(){
    index=buildTraceIndex(state.currentRows,rowId);
    if(index.records.get(system)?.type!=="System")system="";
    if(revealed&&!index.records.has(revealed)&&!data.rows.some(row=>row.id===revealed))revealed=null;
    scope=new Set();
    const root=index.records.get(system);
    const queue=root?[root]:[];
    for(let i=0;i<queue.length;i++){
      const record=queue[i];
      if(scope.has(record.id))continue;
      scope.add(record.id);
      if(descendants)for(const edge of record.incoming)if(edge.field==="Part of")queue.push(edge.record);
    }
    if(!panel.hidden)renderTree();
  }
  function filters(){
    const result=[];
    if(system)result.push([`System: ${caption(index.records.get(system))}${descendants?" and subsystems":""}`,
      ()=>{system="";}]);
    if(revealed)result.push([`Revealed record: ${revealed}`,()=>{revealed=null;}]);
    return result;
  }
  function reset(){system="";revealed=null;pending=null;}
  function renderTree(){
    const visit=new Set();
    const children=record=>record.incoming.filter(edge=>edge.field==="Part of").map(edge=>edge.record);
    const options=[`<li><button type="button" data-trace-system="" aria-pressed="${!system}">All records</button></li>`];
    const addBranch=root=>{
      const stack=[[root,0]];
      while(stack.length){
        const [record,depth]=stack.pop();
        if(visit.has(record.id))continue;
        visit.add(record.id);
        options.push(`<li style="--trace-depth:${Math.min(depth,8)}">
          <button type="button" data-trace-system="${escapeHtml(record.id)}" aria-pressed="${system===record.id}">${escapeHtml(caption(record))}</button>
          <button type="button" data-trace-inspect="${escapeHtml(record.id)}" aria-label="Inspect ${escapeHtml(caption(record))}">↗</button>
        </li>`);
        for(const child of children(record).reverse())stack.push([child,depth+1]);
      }
    };
    for(const root of [...index.roots,...index.systems])addBranch(root);
    tree.innerHTML=options.join("");
    $("#trace-descendants").checked=descendants;
    $("#trace-descendants").disabled=!system;
    $("#trace-findings").querySelector("summary").textContent=`Trace findings (${index.issues.length})`;
    $("#trace-issues").innerHTML=index.issues.length?index.issues.map(({id,field,message})=>
      `<li>${id?link(id,id)+" · ":""}<strong>${escapeHtml(field)}</strong><br>${escapeHtml(message)}</li>`
    ).join(""):"<li>No trace findings.</li>";
  }
  function renderDetail(){
    if(panel.hidden)return;
    const record=index.records.get(selected);
    const reveal=pending?`<div class="trace-reveal">${escapeHtml(pending)} is outside the current view.
      <button type="button" id="trace-reveal">Reveal in grid</button></div>`:"";
    if(!record){
      detail.innerHTML=reveal+"<p>Select a current record in the grid to inspect its links.</p>";
      return;
    }
    const {id,row,type}=record;
    const incomingLabels={"Part of":"Subsystems","Allocated to":"Allocated requirements","Owner":"Owned requirements",
      "Derived from":"Downstream requirements","Source refs":"Cited by"};
    const sections=[];
    for(const [field,rule] of Object.entries(traceFields)){
      const ids=[...new Set(traceIds(row[field]))];
      if(!rule.from.includes(type)&&!ids.length)continue;
      const targets=ids.map(targetId=>{
        const target=index.records.get(targetId);
        const remove=writable()?` <button type="button" class="trace-remove" data-trace-remove="${escapeHtml(field)}"
          data-trace-target="${escapeHtml(targetId)}" aria-label="Remove ${escapeHtml(field)} link to ${escapeHtml(targetId)}">×</button>`:"";
        return `<li>${target?link(targetId,caption(target)):escapeHtml(targetId)+" (missing)"}${remove}</li>`;
      });
      const edit=writable()&&rule.from.includes(type)?` <button type="button" data-trace-pick="${escapeHtml(field)}"
        aria-label="Choose ${escapeHtml(field)} target">${rule.single&&ids.length?"Change":"Add"}…</button>`:"";
      sections.push(`<section><h4>${escapeHtml(field)}${edit}</h4>${targets.length?`<ul>${targets.join("")}</ul>`:'<p class="meta">None</p>'}</section>`);
    }
    for(const [field,heading] of Object.entries(incomingLabels)){
      const links=record.incoming.filter(edge=>edge.field===field);
      if(links.length)sections.push(`<section><h4>${heading}</h4><ul>${links.map(({record:source})=>
        `<li>${link(source.id,caption(source))}</li>`).join("")}</ul></section>`);
      else if(field==="Derived from"&&type==="Requirement")sections.push('<section><h4>Downstream requirements</h4><p class="meta">None</p></section>');
    }
    const origin=row.Origin?.trim()||(traceIds(row["Source refs"]).length||traceIds(row["Derived from"]).length?"":"No origin recorded");
    const notes=[row.Requirement,row.Reference,type==="Requirement"?origin:"",row.Rationale].filter(Boolean);
    detail.innerHTML=reveal+`<h3 tabindex="-1">${escapeHtml(caption(record))}</h3><p class="meta">${escapeHtml(type)}</p>`
      +notes.map(note=>`<p class="trace-note">${escapeHtml(note)}</p>`).join("")
      +(type==="System"&&writable()?'<button type="button" id="trace-edit-system">Edit system…</button>':"")
      +(visible(id)?"":link(id,"Locate in grid"))+sections.join("");
  }
  function syncSelection(id,force=false){
    if(id===selected&&!force)return;
    selected=id;
    pending=null;
    renderDetail();
  }
  function navigate(id){
    if(state.editingCell){
      status.textContent="Apply or cancel the cell edit before navigating.";
      return;
    }
    if(!visible(id)){
      pending=id;
      renderDetail();
      $("#trace-reveal").focus();
      return;
    }
    pending=null;
    if(matchMedia("(max-width:900px)").matches)close();
    focusRequirement(id,data.meta.idColumn);
    syncSelection(id,true);
  }
  function close(){
    if(panel.hidden)return;
    panel.hidden=true;
    $("#open-trace").setAttribute("aria-expanded","false");
    renderLayout();
  }
  function open(){
    if(state.editingCell)return;
    if(!panel.hidden){close();restoreSelectedCell();return;}
    closeReview();
    closeQuality();
    panel.hidden=false;
    $("#open-trace").setAttribute("aria-expanded","true");
    refresh();
    syncSelection(selectedRequirementId(),true);
    renderLayout();
    $("#trace-title").focus();
  }
  function changeScope(id){
    if(state.editingCell){
      status.textContent="Apply or cancel the cell edit before switching systems.";
      return;
    }
    status.textContent="";
    const current=selectedRequirementId(),column=visibleColumns()[state.focus.column]?.name;
    system=id;
    revealed=null;
    render();
    // Preserve the current record across subsystem views when it belongs to both.
    const row=current&&[...tableBody.rows].find(row=>row.dataset.rowId===current);
    const cell=[...row?.cells??[]].find(cell=>cell.dataset.column===column);
    if(cell)state.focus.row=+cell.dataset.rowIndex;
    else state.focus.row=0;
    setRovingFocus();
  }
  function updateLink(field,value){
    const record=index.records.get(selected);
    if(!writable()||!record||record.row[field]===value)return;
    const id=record.id;
    remember();
    record.row[field]=value;
    updateDirty();
    render();
    syncSelection(id,true);
    focusControl(detail,"data-trace-pick",field);
  }
  function showCandidates(){
    const {id,field}=linkEdit,record=index.records.get(id);
    const query=$("#trace-query").value.trim().toLocaleLowerCase();
    const results=[...index.records.values()].filter(target=>caption(target).toLocaleLowerCase().includes(query)
      &&traceCanLink(record,field,target));
    $("#trace-candidates").innerHTML=results.length?results.map(target=>
      `<li><button type="button" data-trace-target="${escapeHtml(target.id)}">${escapeHtml(caption(target))}</button></li>`
    ).join(""):"<li>No eligible targets match.</li>";
  }
  function editLink(field){
    if(!writable()||!index.records.has(selected))return;
    linkEdit={id:selected,field};
    $("#trace-picker-title").textContent=field;
    $("#trace-query").value="";
    showCandidates();
    picker.showModal();
  }
  function editRecord(record=null){
    if(!writable())return;
    editedRecord=record;
    $("#trace-editor-title").textContent=record?"Edit system":"Add trace record";
    $("#trace-record-id").value=record?.id??"";
    $("#trace-record-id").readOnly=!!record;
    $("#trace-record-type").value=record?.type??"System";
    $("#trace-record-type").disabled=!!record;
    $("#trace-record-name").value=record?.row.Name??"";
    editor.showModal();
  }
  function clearCopy(clone){
    clone.querySelector("#trace-panel").hidden=true;
    clone.querySelector("#open-trace").setAttribute("aria-expanded","false");
    for(const id of ["trace-tree","trace-record","trace-issues","trace-candidates","trace-status"]){
      clone.querySelector("#"+id).replaceChildren();
    }
    for(const id of ["trace-editor","trace-picker","trace-findings"]){
      clone.querySelector("#"+id).removeAttribute("open");
    }
  }

  $("#open-trace").addEventListener("click",open);
  for(const dialog of [editor,picker]){
    dialog.addEventListener("keydown",event=>event.stopPropagation());
  }
  $("#close-trace").addEventListener("click",()=>{close();restoreSelectedCell();});
  $("#trace-add-record").addEventListener("click",()=>editRecord());
  $("#trace-descendants").addEventListener("change",event=>{
    if(state.editingCell){event.target.checked=descendants;return;}
    descendants=event.target.checked;
    changeScope(system);
  });
  panel.addEventListener("click",event=>{
    const button=event.target.closest("button");
    if(!button)return;
    const {traceSystem,traceJump,traceInspect,tracePick,traceRemove,traceTarget}=button.dataset;
    if(traceSystem!==undefined){
      changeScope(traceSystem);
      focusControl(tree,"data-trace-system",traceSystem);
    }else if(traceInspect!==undefined){
      if(!state.editingCell){
        syncSelection(traceInspect,true);
        $("#trace-record h3")?.focus();
      }
    }else if(traceJump!==undefined)navigate(traceJump);
    else if(tracePick)editLink(tracePick);
    else if(traceRemove)updateLink(traceRemove,traceIds(index.records.get(selected).row[traceRemove])
      .filter(id=>id!==traceTarget).join("; "));
    else if(button.id==="trace-edit-system")editRecord(index.records.get(selected));
    else if(button.id==="trace-reveal"&&pending){
      if(state.editingCell)return;
      const id=pending;
      revealed=id;
      render();
      navigate(id);
    }
  });
  $("#trace-query").addEventListener("input",showCandidates);
  $("#trace-picker-cancel").addEventListener("click",()=>picker.close());
  $("#trace-candidates").addEventListener("click",event=>{
    const targetId=event.target.closest("[data-trace-target]")?.dataset.traceTarget;
    if(!targetId||!linkEdit)return;
    const {id,field}=linkEdit,record=index.records.get(id),target=index.records.get(targetId);
    if(!writable()||!record||!target||!traceCanLink(record,field,target))return;
    picker.close();
    selected=id;
    const value=traceFields[field].single?targetId:[...traceIds(record.row[field]),targetId].join("; ");
    updateLink(field,value);
  });
  $("#trace-editor-cancel").addEventListener("click",()=>editor.close());
  $("#trace-record-form").addEventListener("submit",event=>{
    event.preventDefault();
    if(!writable())return;
    const name=$("#trace-record-name").value.trim();
    if(!name){$("#trace-record-name").focus();return;}
    const id=editedRecord?.id??validateNewId($("#trace-record-id").value);
    if(!id)return;
    if(editedRecord?.row.Name===name){editor.close();return;}
    remember();
    if(editedRecord)editedRecord.row.Name=name;
    else state.currentRows.push({...newRequirement(id),Type:$("#trace-record-type").value,Name:name});
    editor.close();
    updateDirty();
    render();
    syncSelection(id,true);
    (detail.querySelector("h3")??$("#trace-title")).focus();
  });
  return {refresh,matches,filters,reset,syncSelection,close,clearCopy,
    revealed:id=>id===revealed, scoped:()=>!!system||!!revealed,
    rename:(oldId,newId)=>{if(system===oldId)system=newId;if(revealed===oldId)revealed=newId;},
    incomingChanges:(oldId,newId)=>traceIncomingChanges(state.currentRows,oldId,newId),
    isRequirement:row=>traceType(row)==="Requirement",
    allocate:row=>{if(system)row["Allocated to"]=system;},
    reveal:id=>{if(system)revealed=id;},
    panel};
})();
"""

TRACE_MENU = '<button id="open-trace" aria-expanded="false" aria-controls="trace-panel">Systems and traceability</button>'

TRACE_HTML = """
<aside id="trace-panel" class="review-panel" hidden aria-labelledby="trace-title">
  <div class="review-head"><h2 id="trace-title" tabindex="-1">Systems and traceability</h2><button id="close-trace">Close</button></div>
  <div class="review-body">
    <h3>Systems</h3>
    <ul id="trace-tree" aria-label="System views"></ul>
    <label><input type="checkbox" id="trace-descendants" checked> Include subsystems</label>
    <button type="button" id="trace-add-record" class="develop-only">Add trace record…</button>
    <p class="meta" id="trace-status" role="status"></p>
    <details id="trace-findings"><summary>Trace findings</summary><ul id="trace-issues"></ul></details>
    <div id="trace-record"></div>
  </div>
</aside>
<dialog id="trace-picker" class="help-dialog" aria-labelledby="trace-picker-title">
  <div class="help-head"><h2 id="trace-picker-title">Choose target</h2><button type="button" id="trace-picker-cancel">Cancel</button></div>
  <div class="help-body"><label for="trace-query">Search by ID or name</label>
    <input type="search" id="trace-query" autofocus><ul id="trace-candidates" aria-label="Eligible targets"></ul>
  </div>
</dialog>
<dialog id="trace-editor" class="help-dialog" aria-labelledby="trace-editor-title">
  <form id="trace-record-form">
    <div class="help-head"><h2 id="trace-editor-title">Add trace record</h2><button type="button" id="trace-editor-cancel">Cancel</button></div>
    <div class="help-body">
      <label>Type <select id="trace-record-type"><option>System</option><option>Need</option><option>Source</option></select></label>
      <label>ID <input id="trace-record-id" required></label>
      <label>Name <input id="trace-record-name" required></label>
      <button type="submit" class="primary">Apply</button>
    </div>
  </form>
</dialog>
"""

TRACE_CSS = """
#trace-panel {width:min(380px,100vw)}
#trace-panel h3 {font-size:1em;margin:8px 0 4px}
#trace-tree, #trace-record ul, #trace-candidates {list-style:none;padding:0;margin:4px 0 8px}
#trace-tree li {display:flex;gap:4px;padding-inline-start:calc(var(--trace-depth,0) * .8rem);margin-bottom:4px}
#trace-tree button:first-child {flex:1;text-align:start;overflow-wrap:anywhere}
#trace-tree button[aria-pressed="true"] {background:var(--selected);border-color:var(--accent)}
#trace-status:empty {display:none}
#trace-add-record {display:block;margin:8px 0}
#trace-add-record[hidden] {display:none}
#trace-record {border-top:1px solid var(--line);margin-top:10px;padding-top:4px;overflow-wrap:anywhere}
#trace-record h4 {font-size:inherit;margin:0;display:flex;align-items:center;justify-content:space-between;gap:6px}
#trace-record section {border-top:1px solid var(--line);padding:6px 0}
#trace-record p {margin:4px 0}
.trace-link {text-align:start;color:var(--accent);overflow-wrap:anywhere}
.trace-note {white-space:pre-wrap}
.trace-remove {min-width:24px}
.trace-reveal {background:var(--selected);padding:6px;border-radius:4px}
#trace-findings summary {cursor:pointer}
#trace-issues {padding-inline-start:20px;overflow-wrap:anywhere}
#trace-issues li {margin-bottom:6px}
#trace-query {display:block;width:100%}
#trace-candidates button {width:100%;text-align:start;margin-top:4px;overflow-wrap:anywhere}
#trace-record-form label {display:grid;gap:3px;margin-bottom:10px}
@media screen and (min-width:901px) {body:has(#trace-panel:not([hidden])) .page {margin-right:380px}}
@media print {#trace-panel {display:none}}
"""
