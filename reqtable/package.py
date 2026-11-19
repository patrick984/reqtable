"""Gate package cover, sign-off table and decision recording for Review-mode reports."""

PACKAGE_HTML = '<section id="package-cover" class="package-cover" aria-labelledby="package-title" hidden></section>\n<div id="package-footer" class="package-footer" aria-hidden="true"></div>'

PACKAGE_CSS = r"""
.package-cover{margin:0 0 10px;padding:12px 14px;border:1px solid var(--line);border-radius:7px;background:var(--panel)}
.package-cover[hidden]{display:none}
.package-cover h2{margin:0 0 8px;font-size:1.25rem}
.package-cover h3{margin:14px 0 6px;font-size:1rem}
.package-facts{display:grid;grid-template-columns:max-content 1fr;gap:3px 14px;margin:0}
.package-facts dt{color:var(--muted)}
.package-facts dd{margin:0;overflow-wrap:anywhere}
.package-hash{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;user-select:all}
.package-warning{margin:8px 0 0;padding:6px 9px;border-radius:5px;background:var(--remove)}
.package-warning[hidden]{display:none}
.package-approval{display:flex;align-items:center;gap:8px;margin:14px 0 6px}
.package-approval h3{margin:0}
.badge.approved{background:var(--add)}
.badge.not-approved{background:var(--remove)}
.signoff-table{width:100%;min-width:0;table-layout:auto;border:1px solid var(--line);border-bottom:0}
.signoff-table th,.signoff-table td{font-size:.92rem;border-left:0}
.signoff-table th:nth-child(-n+2),.signoff-table td:nth-child(-n+2){white-space:nowrap;overflow-wrap:normal;width:1%}
.waiver-table th:nth-child(2),.waiver-table td:nth-child(2){white-space:normal;overflow-wrap:anywhere;width:auto}
.signoff-table thead th{position:static;height:auto}
.signoff-table ul{margin:0;padding:0;list-style:none}
.signoff-table li+li{margin-top:4px}
.signoff-none{color:var(--muted)}
.signoff-excluded{color:var(--muted);font-style:italic}
.decision-remove{margin-inline-start:6px;padding:0 6px;font-size:.8rem}
.decision-form{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:flex-end;margin-top:6px}
.decision-form label{display:flex;flex-direction:column;gap:2px;font-size:.88rem;color:var(--muted)}
.decision-form input,.decision-form select{min-width:9rem}
.decision-form .decision-note{min-width:16rem;flex:1}
.package-footer{display:none}
@media print{
  .package-cover{border:0;padding:0;background:none;break-after:page;page-break-after:always}
  .decision-form,.decision-remove{display:none!important}
  body:has(#package-cover:not([hidden])),body:has(#package-cover:not([hidden])) .page{background:#fff}
  body:has(#package-cover:not([hidden])) #filter-row,body:has(#package-cover:not([hidden])) .comment-button:not(.has-comments){display:none}
  body:has(#package-cover:not([hidden])) .selected-cell{background:none!important;box-shadow:none}
  body:has(#package-cover:not([hidden])) .status-cell .badge.unchanged{visibility:hidden}
  .badge.approved,.badge.not-approved{border-color:#000;background:none;color:#000}
  .package-warning{border:1px solid #000;background:none}
  .signoff-table{border-color:#000}
  .signoff-table th,.signoff-table td{border-color:#000}
  .signoff-table tr{break-inside:avoid}
  .package-cover,.package-cover .package-facts dt,.signoff-none,.signoff-excluded{color:#000}
}
"""

PACKAGE_MODEL_JS = r"""
const VERIFICATION_LABELS={good:"Signature good",signaturegood:"Signature good",unsigned:"Unsigned",bad:"Bad signature",badsignature:"Bad signature",unverifiable:"Cannot verify",cannotverify:"Cannot verify"};
function verificationLabel(verification){return VERIFICATION_LABELS[String(verification??"").toLowerCase().replace(/[\s_-]+/g,"")]??"Recorded";}
function signoffTable(pkg,decisions){
  const roles=pkg.roles.map(({role,min})=>({role,min}));
  for(const {role} of [...pkg.signoffs,...decisions])if(!roles.some(r=>r.role===role))roles.push({role,min:null});
  return roles.map(({role,min})=>({role,min,
    signoffs:pkg.signoffs.filter(s=>s.role===role).map(s=>({user:s.user,decision:s.decision,date:s.date,note:s.note??"",
      verification:verificationLabel(s.verification),counts:s.counts!==false})),
    pending:decisions.filter(d=>d.role===role)}));
}
function waiverRows(waivers){
  return (waivers??[]).map(w=>({check:w.check,description:w.description??"",reason:w.reason,user:w.user,date:w.date,records:(w.failing??[]).length}));
}
function isoWithOffset(d){
  const off=-d.getTimezoneOffset(),pad=n=>String(Math.abs(n)).padStart(2,"0");
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${off>=0?"+":"-"}${pad(Math.trunc(Math.abs(off)/60))}:${pad(Math.abs(off)%60)}`;
}
function createDecision({role,user,decision,note},now){
  const record={role:String(role??"").trim(),user:String(user??"").trim(),decision:String(decision??"").trim(),date:isoWithOffset(now),note:String(note??"").trim()};
  const missing=["user","role","decision"].find(field=>!record[field]);
  return missing?{error:`Enter a ${missing}.`}:{record};
}
const sameDecision=(a,b)=>a.role===b.role&&a.user===b.user&&a.date===b.date;
function removeDecision(decisions,record){return decisions.filter(d=>!sameDecision(d,record));}
function packageFooterText(pkg){return `${pkg.baseline.name} · ${pkg.baseline.hash}`;}
"""

PACKAGE_JS = (
    PACKAGE_MODEL_JS
    + r"""
const packageCover=data.package?$("#package-cover"):null;
function packageFacts(pkg){
  const {baseline,gate}=pkg,scope=baseline.system?`System ${baseline.system}`:"Whole table";
  return [["Baseline",baseline.name],["Produces",gate.produces],["Scope",scope],
    ["Created",`${baseline.created}${baseline.createdBy?` by ${baseline.createdBy}`:""}`],
    ["Content hash",`<span class="package-hash">${escapeHtml(baseline.hash)}</span>`,true],
    ["Compared with",pkg.previous??"No earlier baseline"]]
    .map(([term,value,raw])=>`<dt>${term}</dt><dd>${raw?value:escapeHtml(value??"")}</dd>`).join("");
}
function packageWaivers(pkg){
  const rows=waiverRows(pkg.waivers);
  if(!rows.length)return "";
  const body=rows.map(w=>`<tr><th scope="row">${escapeHtml(w.check)}</th><td>${escapeHtml(w.description)}</td><td>${escapeHtml(w.reason)}</td><td>${escapeHtml(w.user)}</td><td>${escapeHtml(displayTimestamp(w.date))}</td><td>${w.records}</td></tr>`).join("");
  return `<h3>Waivers</h3>
<table class="signoff-table waiver-table" id="package-waiver-table"><thead><tr><th scope="col">Check</th><th scope="col">Description</th><th scope="col">Reason</th><th scope="col">Waived by</th><th scope="col">Date</th><th scope="col">Records</th></tr></thead><tbody>${body}</tbody></table>`;
}
function signoffItem(s){
  return `<li class="signoff${s.counts?"":" signoff-excluded"}">${escapeHtml(s.user)}: ${escapeHtml(s.decision)}, ${escapeHtml(s.date)}, ${escapeHtml(s.verification)}${s.counts?"":" (does not count)"}${s.note?` <span class="meta">${escapeHtml(s.note)}</span>`:""}</li>`;
}
function pendingItem(d){
  const index=state.decisions.findIndex(x=>sameDecision(x,d));
  return `<li class="decision-recorded">${escapeHtml(d.user)}: ${escapeHtml(d.decision)}, ${escapeHtml(displayTimestamp(d.date))}${d.note?` <span class="meta">${escapeHtml(d.note)}</span>`:""}<button type="button" class="decision-remove" data-remove-decision="${index}" aria-label="Remove ${escapeHtml(d.decision)} by ${escapeHtml(d.user)} as ${escapeHtml(d.role)}">Remove</button></li>`;
}
function renderPackage(){
  if(!packageCover)return;
  const list=(items,render)=>items.length?`<ul>${items.map(render).join("")}</ul>`:'<span class="signoff-none">None</span>',
    approved=data.package.approval.approved;
  $("#package-approval").innerHTML=`<h3>Sign-offs</h3><span class="badge ${approved?"approved":"not-approved"}">${approved?"Approved":"Not approved"}</span>`;
  $("#package-signoffs").innerHTML=signoffTable(data.package,state.decisions).map(r=>`<tr data-role="${escapeHtml(r.role)}"><th scope="row">${escapeHtml(r.role)}</th><td>${r.min??""}</td><td>${list(r.signoffs,signoffItem)}</td><td>${list(r.pending,pendingItem)}</td></tr>`).join("");
}
function buildPackageCover(){
  if(!packageCover)return;
  const pkg=data.package;
  packageCover.innerHTML=`<h2 id="package-title">${escapeHtml(pkg.gate.name)} (${escapeHtml(pkg.gate.id)}) gate package</h2>
<dl class="package-facts" id="package-facts">${packageFacts(pkg)}</dl>
<p id="package-hash-warning" class="package-warning" role="alert" ${pkg.baseline.hashOk?"hidden":""}>The baseline content does not match its recorded hash.</p>
${packageWaivers(pkg)}
<div id="package-approval" class="package-approval"></div>
<table class="signoff-table" id="package-signoff-table"><thead><tr><th scope="col">Role</th><th scope="col">Required</th><th scope="col">Recorded sign-offs</th><th scope="col">Recorded in this package, not yet imported</th></tr></thead><tbody id="package-signoffs"></tbody></table>
<form id="package-decision-form" class="decision-form" aria-label="Record decision">
<label>Name<input id="package-decision-user" maxlength="80" autocomplete="off" value="${escapeHtml(reviewerInitials())}"></label>
<label>Role<select id="package-decision-role">${pkg.roles.map(r=>`<option>${escapeHtml(r.role)}</option>`).join("")}</select></label>
<label>Decision<select id="package-decision-decision">${pkg.decisionOptions.map(o=>`<option>${escapeHtml(o)}</option>`).join("")}</select></label>
<label class="decision-note">Note (optional)<input id="package-decision-note" maxlength="500" autocomplete="off"></label>
<button type="submit" id="package-decision-submit" class="primary">Record decision</button>
<span id="package-decision-status" class="meta" role="status"></span></form>`;
  packageCover.hidden=false;
  $("#package-footer").textContent=packageFooterText(pkg);
  const pageFooter=document.getElementById("package-page-footer")??document.head.appendChild(Object.assign(document.createElement("style"),{id:"package-page-footer"}));
  pageFooter.textContent=`@media print{@page{size:landscape;margin:12mm 12mm 20mm;@bottom-center{content:${JSON.stringify(packageFooterText(pkg))};font:8pt ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#000}}}`;
  renderPackage();
  $("#package-decision-user").addEventListener("focus",e=>{if(!e.target.value)e.target.value=reviewerInitials();});
  $("#package-decision-form").addEventListener("submit",e=>{
    e.preventDefault();
    const field=id=>$("#package-decision-"+id),result=createDecision({role:field("role").value,user:field("user").value,decision:field("decision").value,note:field("note").value},new Date());
    if(result.error){field("status").textContent=result.error;return;}
    state.decisions.push(result.record);
    field("note").value="";
    field("status").textContent=`Recorded ${result.record.decision} for ${result.record.role}. Save a report copy to keep it.`;
    updateDirty();
    renderPackage();
  });
  packageCover.addEventListener("click",e=>{
    const button=e.target.closest("[data-remove-decision]");
    if(!button)return;
    const record=state.decisions[Number(button.dataset.removeDecision)];
    if(!record)return;
    state.decisions=removeDecision(state.decisions,record);
    $("#package-decision-status").textContent=`Removed ${record.decision} for ${record.role}.`;
    updateDirty();
    renderPackage();
  });
}
function packageClearCopy(clone){
  clone.querySelector("#package-cover")?.replaceChildren();
  clone.querySelector("#package-cover")?.setAttribute("hidden","");
  clone.querySelector("#package-footer")?.replaceChildren();
  clone.querySelector("#package-page-footer")?.remove();
}
buildPackageCover();
"""
)
