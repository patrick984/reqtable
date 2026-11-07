"""Offline requirement quality rules and report controls."""

QUALITY_JS = r"""
const qualityPanel=$("#quality-panel");
const quality={checked:false,only:false,revealId:null,activeCell:null,findings:new Map()};
const qualityHeaders=data.source.new.headers.filter(name=>name!==data.meta.idColumn);
const escapeRegex=text=>text.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
let requirementColumn,qualityColumns,obligation,obligationPattern,disabledQualityRules;
function configureQuality(){
  const options=state.qualityReview.settings;
  requirementColumn=options.requirement_column
    ??qualityHeaders.find(name=>/^(requirement|requirement text)$/i.test(name.trim()));
  qualityColumns=[...new Set([requirementColumn,...(options.required_columns??[])])]
    .filter(name=>qualityHeaders.includes(name));
  obligation=options.obligation===undefined?"shall":options.obligation;
  obligationPattern=obligation&&new RegExp(
    `(?<![\\p{L}\\p{N}_])${escapeRegex(obligation.trim())}(?![\\p{L}\\p{N}_])`,"giu");
  disabledQualityRules=new Set(options.disabled_rules??[]);
}
configureQuality();
const qualityRules={
  "missing-content":["Missing content","Fill in this field so readers can review and verify the requirement."],
  "placeholder":["Unresolved placeholder","Record what is still open and replace the placeholder when the decision is made."],
  "ambiguous-choice":["Ambiguous alternatives","State which alternatives are permitted and whether both can apply."],
  "ambiguous-condition":["Vague condition","Name the condition that triggers the behavior or defines when it applies."],
  "ambiguous-timing":["Vague timing","Specify the maximum elapsed time and the event it is measured from."],
  "open-ended-list":["Open-ended list","State the complete set or reference a controlled list."],
  "missing-obligation":["Missing obligation keyword","Check the configured obligation keyword for a binding statement."],
  "multiple-obligations":["Possible multiple obligations","Check whether the obligations can be verified independently and should be separate requirements."]
};
const qualityPhrases=[
  ["placeholder",/\b(?:TBD|TBR|TODO)\b/gi],
  ["ambiguous-choice",/\band\/or\b/gi],
  ["ambiguous-condition",/\b(?:as appropriate|as needed|when necessary|where applicable)\b/gi],
  ["ambiguous-timing",/\b(?:quickly|promptly|as soon as possible|in a timely manner)\b/gi],
  ["open-ended-list",/\b(?:etc\.|including but not limited to)/gi]
];
function lintRequirementField(value,isStatement){
  if(!value.trim())return disabledQualityRules.has("missing-content")
    ?[]:[{rule:"missing-content",phrase:"",start:0}];
  // Keep source offsets while masking examples and link destinations.
  const prose=value.replace(/```[\s\S]*?```|`[^`\n]*`|\]\([^\n)]*\)|https?:\/\/[^\s<>]+/g,
    match=>match.replace(/[^\r\n]/g," "));
  const findings=[];
  for(const [rule,pattern] of qualityPhrases){
    if(disabledQualityRules.has(rule))continue;
    for(const match of prose.matchAll(pattern)){
      findings.push({rule,phrase:match[0],start:match.index});
    }
  }
  if(isStatement&&obligationPattern){
    const matches=[...prose.matchAll(obligationPattern)];
    if(matches.length===0&&!disabledQualityRules.has("missing-obligation")){
      findings.push({rule:"missing-obligation",phrase:"",start:0});
    }
    if(matches.length>1&&!disabledQualityRules.has("multiple-obligations")){
      findings.push({rule:"multiple-obligations",phrase:matches[1][0],start:matches[1].index});
    }
  }
  return findings;
}
function qualityDismissal(id,column,value,issue){
  const keyword=issue.rule.endsWith("-obligation")||issue.rule==="multiple-obligations"?obligation:null;
  return state.qualityReview.dismissals.find(record=>record.id===id&&record.column===column
    &&record.value===value&&record.rule===issue.rule&&record.start===issue.start
    &&record.obligation===keyword);
}
function scanQuality(){
  if(!quality.checked)return;
  configureQuality();
  const findings=new Map();
  quality.dismissed=[];
  for(const row of state.currentRows){
    const id=rowId(row),fields=new Map();
    for(const column of qualityColumns){
      const value=String(row[column]??"");
      const issues=[];
      for(const issue of lintRequirementField(value,column===requirementColumn)){
        const dismissal=qualityDismissal(id,column,value,issue);
        if(dismissal)quality.dismissed.push(dismissal);
        else issues.push(issue);
      }
      if(issues.length)fields.set(column,issues);
    }
    if(fields.size)findings.set(id,fields);
  }
  quality.findings=findings;
}
function underlineQualityPhrases(wrapper,issues){
  const phrases=[...new Set(issues.map(issue=>issue.phrase).filter(Boolean))];
  if(!phrases.length)return;
  const pattern=new RegExp(`(?<![\\p{L}\\p{N}_])(?:${phrases.map(escapeRegex).join("|")})(?![\\p{L}\\p{N}_])`,"giu");
  const walker=document.createTreeWalker(wrapper,NodeFilter.SHOW_TEXT,{acceptNode(node){
    return node.parentElement.closest("code,pre,button,.quality-phrase")
      ?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT;
  }});
  const nodes=[];
  while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){
    const matches=[...node.data.matchAll(pattern)];
    if(!matches.length)continue;
    const fragment=document.createDocumentFragment();
    let offset=0;
    for(const match of matches){
      fragment.append(node.data.slice(offset,match.index));
      const mark=document.createElement("span");
      mark.className="quality-phrase";
      mark.textContent=match[0];
      fragment.append(mark);
      offset=match.index+match[0].length;
    }
    fragment.append(node.data.slice(offset));
    node.replaceWith(fragment);
  }
}
function paintQualityMarkers(){
  if(!quality.checked)return;
  for(const row of tableBody.rows){
    const fields=quality.findings.get(row.dataset.rowId);
    if(!fields)continue;
    for(const cell of row.querySelectorAll("[data-grid-cell]")){
      const column=cell.dataset.column,issues=fields.get(column);
      const wrapper=cell.querySelector(".cell-wrap");
      if(!issues||!wrapper||wrapper.querySelector(".quality-marker"))continue;
      if(!diffActive()){
        const dismissedPhrases=new Set(quality.dismissed
          .filter(record=>record.id===row.dataset.rowId&&record.column===column)
          .map(record=>record.phrase.toLowerCase()));
        // When identical phrases have different review outcomes, the editor
        // can select the exact occurrence using its source offset.
        underlineQualityPhrases(wrapper,issues.filter(issue=>!dismissedPhrases.has(issue.phrase.toLowerCase())));
      }
      const marker=document.createElement("button");
      marker.type="button";
      marker.className="quality-marker";
      marker.textContent="⚠";
      const label=`${issues.length} quality ${issues.length===1?"finding":"findings"} for ${row.dataset.rowId}, ${column}`;
      marker.setAttribute("aria-label",label);
      marker.title=label;
      marker.addEventListener("click",()=>openQuality(row.dataset.rowId,column));
      wrapper.append(marker);
    }
  }
}
function renderQualityPanel(){
  if(qualityPanel.hidden)return;
  const list=$("#quality-findings"),body=list.parentElement,scroll=body.scrollTop;
  const displayed=new Set([...tableBody.rows].map(row=>row.dataset.rowId));
  let count=0;
  const cards=[];
  for(const [id,fields] of quality.findings){
    for(const [column,issues] of fields){
      const active=quality.activeCell?.id===id&&quality.activeCell.column===column;
      const rowHidden=!displayed.has(id);
      const hidden=rowHidden||state.hidden.has(column);
      const card=document.createElement("article");
      card.className="comment-card quality-card";
      card.classList.toggle("quality-active",active);
      const title=document.createElement("h3");
      const label=data.columns.find(item=>item.name===column)?.label??column;
      title.textContent=`${id} · ${label}`;
      card.append(title);
      if(rowHidden){
        const note=document.createElement("p");
        note.className="meta";
        note.textContent="This row is hidden. Revealing it clears the current row filters.";
        card.append(note);
      }
      for(const issue of issues){
        const {rule,phrase}=issue;
        const [name,suggestion]=qualityRules[rule];
        const section=document.createElement("div");
        section.className="quality-issue";
        const text=document.createElement("p");
        const evidence=document.createElement("strong");
        evidence.textContent=phrase?`${name} · “${phrase}”`:name;
        text.append(evidence,document.createElement("br"),suggestion);
        const actions=document.createElement("div");
        actions.className="comment-actions";
        const edit=document.createElement("button");
        edit.type="button";
        edit.textContent=hidden?"Reveal and edit":phrase?"Edit wording":"Edit field";
        edit.setAttribute("aria-label",`${edit.textContent} for ${id}, ${label}${phrase?` · ${phrase}`:""}`);
        edit.addEventListener("click",()=>jumpToQualityCell(id,column,hidden,issue));
        const dismiss=document.createElement("button");
        dismiss.type="button";
        dismiss.textContent="Dismiss…";
        dismiss.addEventListener("click",()=>openQualityDismissal(id,column,issue,dismiss));
        actions.append(edit,dismiss);
        section.append(text,actions);
        card.append(section);
        count++;
      }
      cards.push(card);
    }
  }
  if($("#quality-show-dismissed").checked){
    for(const record of quality.dismissed??[]){
      const card=document.createElement("article");
      card.className="comment-card quality-dismissed";
      const title=document.createElement("strong");
      const name=qualityRules[record.rule][0];
      const evidence=record.phrase?`${name} · “${record.phrase}”`:name;
      title.textContent=`${record.id} · ${record.column} · ${evidence} (dismissed)`;
      const reason=document.createElement("p");
      reason.textContent=record.reason;
      const restore=document.createElement("button");
      restore.type="button";
      restore.textContent="Restore finding";
      restore.addEventListener("click",()=>{
        if(!qualityCanChange())return;
        state.qualityReview.dismissals=state.qualityReview.dismissals.filter(item=>item!==record);
        updateDirty();
        render();
        $("#quality-show-dismissed").focus();
      });
      card.append(title,reason,restore);
      cards.push(card);
    }
  }
  list.replaceChildren(...cards);
  $("#quality-count").textContent=qualityColumns.length
    ?`${count} ${count===1?"finding":"findings"} across ${quality.findings.size} of ${state.currentRows.length} requirements · ${quality.dismissed?.length??0} dismissed`
    :"Choose a requirement column or required fields in Quality settings.";
  $("#quality-only").checked=quality.only;
  body.scrollTop=scroll;
}
function closeQuality(){
  if(qualityPanel.hidden)return;
  qualityPanel.hidden=true;
  renderLayout();
}
function openQuality(id,column){
  if(!developMode())return;
  if(!quality.checked){
    quality.checked=true;
    scanQuality();
    paintQualityMarkers();
  }
  closeReview();
  quality.activeCell=id===undefined?null:{id,column};
  qualityPanel.hidden=false;
  renderLayout();
  renderQualityPanel();
  const active=qualityPanel.querySelector(".quality-active");
  if(active){
    active.scrollIntoView({block:"nearest"});
    active.querySelector("button").focus({preventScroll:true});
  }else $("#quality-title").focus({preventScroll:true});
}
function jumpToQualityCell(id,column,hidden,issue){
  if(state.editingCell){
    $("#quality-count").textContent="Apply or cancel the current edit before jumping to a finding.";
    return;
  }
  quality.activeCell={id,column};
  if(hidden){
    const rowVisible=[...tableBody.rows].some(row=>row.dataset.rowId===id);
    state.hidden.delete(column);
    if(!rowVisible){
      state.filters.clear();
      state.valueFilters.clear();
      state.commentsOnly=false;
      state.statuses=new Set(["added","removed","changed","unchanged"]);
      quality.revealId=id;
    }
    render();
  }else renderQualityPanel();
  if(matchMedia("(max-width:900px)").matches)closeQuality();
  const cell=focusRequirement(id,column);
  if(issue&&cell&&startCellEdit(cell)){
    const textarea=cell.querySelector("textarea");
    if(issue.phrase)textarea.setSelectionRange(issue.start,issue.start+issue.phrase.length);
    else textarea.select();
  }
}
$("#check-quality").addEventListener("click",()=>openQuality());
$("#close-quality").addEventListener("click",()=>{
  closeQuality();
  if(!state.editingCell)restoreSelectedCell();
  else tableBody.querySelector("[data-cell-editor] textarea")?.focus();
});
$("#quality-only").addEventListener("change",event=>{
  if(state.editingCell){
    event.target.checked=quality.only;
    $("#quality-count").textContent="Apply or cancel the current edit before filtering findings.";
    return;
  }
  quality.only=event.target.checked;
  renderBodyOnly();
});
function qualityCanChange(){
  if(!state.editingCell)return true;
  $("#quality-count").textContent="Apply or cancel the current edit before changing quality settings or dismissals.";
  return false;
}
const qualitySettings=$("#quality-settings-dialog");
function openQualitySettings(){
  if(!qualityCanChange())return;
  configureQuality();
  const select=$("#quality-column");
  select.replaceChildren();
  for(const name of ["",...qualityHeaders]){
    const option=document.createElement("option");
    option.value=name;
    option.textContent=name||"No statement column";
    option.selected=name===(requirementColumn??"");
    select.append(option);
  }
  $("#quality-obligation").value=obligation??"";
  const fillCheckboxes=(container,entries,checked)=>{
    container.replaceChildren(...entries.map(([value,text])=>{
      const label=document.createElement("label"),input=document.createElement("input");
      input.type="checkbox";
      input.value=value;
      input.checked=checked(value);
      label.append(input," "+text);
      return label;
    }));
  };
  const required=new Set(state.qualityReview.settings.required_columns??[]);
  fillCheckboxes($("#quality-required-columns"),qualityHeaders.map(name=>[name,name]),name=>required.has(name));
  fillCheckboxes($("#quality-enabled-rules"),Object.entries(qualityRules).map(([rule,[name]])=>[rule,name]),
    rule=>!disabledQualityRules.has(rule));
  qualitySettings.showModal();
}
$("#quality-settings").addEventListener("click",openQualitySettings);
$("#quality-settings-cancel").addEventListener("click",()=>qualitySettings.close());
qualitySettings.addEventListener("close",()=>$("#quality-settings").focus());
$("#quality-settings-form").addEventListener("submit",event=>{
  event.preventDefault();
  const checkedValues=selector=>[...document.querySelectorAll(selector)].map(input=>input.value);
  const previous=state.qualityReview.settings;
  const column=$("#quality-column").value;
  const disabled=checkedValues("#quality-enabled-rules input:not(:checked)");
  state.qualityReview.settings={
    ...previous,
    requirement_column:column===(requirementColumn??"")?previous.requirement_column:column,
    obligation:$("#quality-obligation").value.trim()||null,
    required_columns:checkedValues("#quality-required-columns input:checked"),
    ...(disabled.length||previous.disabled_rules?{disabled_rules:disabled}:{})
  };
  quality.checked=true;
  updateDirty();
  render();
  qualitySettings.close();
});
const qualityDismissDialog=$("#quality-dismiss-dialog");
for(const dialog of [qualitySettings,qualityDismissDialog]){
  dialog.addEventListener("keydown",event=>{
    if(event.key==="Escape")event.stopPropagation();
  });
}
let pendingQualityDismissal=null,dismissalOpener=null;
function openQualityDismissal(id,column,issue,opener){
  if(!qualityCanChange())return;
  const row=findCurrentRow(id);
  if(!row)return;
  const keyword=issue.rule.endsWith("-obligation")||issue.rule==="multiple-obligations"?obligation:null;
  pendingQualityDismissal={id,column,value:String(row[column]??""),rule:issue.rule,
    phrase:issue.phrase,start:issue.start,obligation:keyword};
  dismissalOpener=opener;
  $("#quality-dismiss-description").textContent=
    `${id} · ${column} · ${qualityRules[issue.rule][0]}${issue.phrase?` · “${issue.phrase}”`:""}`;
  const reason=$("#quality-dismiss-reason");
  reason.value="";
  reason.setCustomValidity("");
  qualityDismissDialog.showModal();
  reason.focus();
}
$("#quality-dismiss-cancel").addEventListener("click",()=>qualityDismissDialog.close());
qualityDismissDialog.addEventListener("close",()=>{
  pendingQualityDismissal=null;
  (dismissalOpener?.isConnected?dismissalOpener:$("#quality-show-dismissed")).focus();
});
$("#quality-dismiss-reason").addEventListener("input",event=>event.target.setCustomValidity(""));
$("#quality-dismiss-form").addEventListener("submit",event=>{
  event.preventDefault();
  const input=$("#quality-dismiss-reason"),reason=input.value.trim();
  if(!reason){
    input.setCustomValidity("Enter a reason for dismissing this finding.");
    input.reportValidity();
    return;
  }
  if(!pendingQualityDismissal)return;
  state.qualityReview.dismissals.push({...pendingQualityDismissal,reason});
  updateDirty();
  render();
  qualityDismissDialog.close();
});
$("#quality-show-dismissed").addEventListener("change",renderQualityPanel);

"""
