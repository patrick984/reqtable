"""Offline traceability model and report controls for opted-in CSVs."""

from .glossary import GLOSSARY_COLUMNS, GLOSSARY_MODEL_JS, GLOSSARY_UI_JS
from .values import VALUE_COLUMNS, VALUE_MODEL_JS

TRACE_COLUMNS = (
    "Type", "Name", "Requirement", "Part of", "Allocated to", "Owner",
    "Derived from", "Source refs", "Verified by", "Test plan", "Affects", "Change status", "Reference", "Origin", "Rationale", *GLOSSARY_COLUMNS, *VALUE_COLUMNS,
)

TRACE_MODEL_JS = GLOSSARY_MODEL_JS + VALUE_MODEL_JS + r"""
const traceFields={
  "Part of": {from:["System"],to:["System"],single:true},
  "Allocated to": {from:["Requirement"],to:["System"]},
  "Owner": {from:["Requirement"],to:["System"],single:true},
  "Derived from": {from:["Requirement"],to:["Requirement"]},
  "Source refs": {from:["Requirement","Need","Term"],to:["Need","Source"]},
  "Verified by": {from:["Requirement"],to:["Test"]},
  "Test plan": {from:["Test"],to:["Test plan"],single:true},
  "Affects": {from:["Change request"],to:["Requirement","System","Need","Source","Term","Value","Field","Test","Test plan"]}
};
function traceType(row){
  const value=String(row.Type??"").trim();
  return value||"Requirement";
}
function traceIds(value){
  return String(value??"").split(";").map(id=>id.trim()).filter(Boolean);
}
function traceTargetTypes(field,type){
  return field==="Source refs"&&type!=="Requirement"?["Source"]:traceFields[field].to;
}
function definedValues(rule,cell){
  const text=String(cell??"").trim();
  return [...new Set((rule.multiple?traceIds(text):text?[text]:[])
    .map(part=>rule.values.has(part)?part:rule.aliases.get(part)?.row.Name.trim()??part))];
}
const verificationStates={
  Compliance: {appliesTo:"Requirement",plural:"requirements",states:["Not verified","Compliant","Partially compliant","Non-compliant","Waived"]},
  Result: {appliesTo:"Test",plural:"tests",states:["Not run","Passed","Failed","Blocked"]},
  "Change status": {appliesTo:"Change request",plural:"change requests",states:["Proposed","Approved","Rejected","Implemented"]}
};
const approvedChangeStates=["Approved","Implemented"];
function verificationState(values,column,cell){
  const rule=values.get(column),text=String(cell??"").trim();
  return rule?definedValues(rule,text)[0]??"":text;
}
function verificationMethodMarks(rule,cell){
  const present=new Set(definedValues(rule,cell));
  return [...rule.values.keys()].map(name=>({name,letter:name.trim().charAt(0).toUpperCase(),filled:present.has(name)}));
}
function buildVerificationMatrix(records,values,idColumn){
  const names=column=>[...(values.get(column)?.values.keys()??[])];
  const methods=names("Verification Method"),levels=names("Verification Level");
  const split=(record,column,known)=>{
    const rule=values.get(column),cell=record.row[column];
    const parts=rule?definedValues(rule,cell):traceIds(cell);
    return [parts.filter(part=>known.includes(part)),parts.filter(part=>!known.includes(part))];
  };
  const totals={methods:Object.fromEntries(methods.map(name=>[name,0])),levels:Object.fromEntries(levels.map(name=>[name,0])),compliance:{}};
  const rows=[...records].map(record=>{
    const [rowMethods,extraMethods]=split(record,"Verification Method",methods);
    const [rowLevels,extraLevels]=split(record,"Verification Level",levels);
    const compliance=verificationState(values,"Compliance",record.row.Compliance);
    const tests=(record.outgoing.get("Verified by")??[]).filter(test=>test.type==="Test")
      .map(test=>({id:test.id,name:test.row.Name?.trim()||test.id,result:verificationState(values,"Result",test.row.Result)}));
    for(const name of rowMethods)totals.methods[name]++;
    for(const name of rowLevels)totals.levels[name]++;
    const key=compliance||"No compliance";
    totals.compliance[key]=(totals.compliance[key]??0)+1;
    return {id:record.id??record.row[idColumn],requirement:record.row.Name?.trim()||record.row.Requirement?.trim()||"",
      methods:rowMethods,levels:rowLevels,tests,compliance,extraMethods,extraLevels};
  });
  return {methods,levels,rows,totals};
}
function verificationMatrixMarks(row,kind,names){
  const extra=kind==="methods"?row.extraMethods:row.extraLevels;
  return names.map((name,i)=>[row[kind].includes(name)?"X":"",i===names.length-1?extra.join("; "):""]);
}
function verificationMatrixLabels(names){
  const upper=names.map(name=>name.trim().toUpperCase());
  return upper.map(name=>{
    for(let length=1;length<name.length;length++){
      const label=name.slice(0,length);
      if(!label.endsWith(" ")&&upper.every(other=>other===name||!other.startsWith(label)))return label;
    }
    return name;
  });
}
function verificationMatrixTest(test){return `${test.id} (${test.result||"No result"})`;}
function verificationMatrixCsvRows(matrix){
  const marks=(row,kind,names)=>verificationMatrixMarks(row,kind,names).map(parts=>parts.filter(Boolean).join("; "));
  return [["ID","Requirement",...matrix.methods,...matrix.levels,"Tests","Compliance"],
    ...matrix.rows.map(row=>[row.id,row.requirement,...marks(row,"methods",matrix.methods),...marks(row,"levels",matrix.levels),
      row.tests.map(verificationMatrixTest).join("; "),row.compliance])];
}
function checkVerification(records,values,issue){
  const state=(record,column)=>verificationState(values,column,record.row[column]);
  const sentence=parts=>parts.length>1?`${parts.slice(0,-1).join(", ")} and ${parts.at(-1)}`:parts[0];
  for(const record of records.values()){
    for(const [column,{appliesTo,plural}] of Object.entries(verificationStates)){
      if(record.type!==appliesTo&&String(record.row[column]??"").trim())issue(record.id,column,`${column} applies to ${plural}.`);
    }
    if(record.type!=="Requirement"||state(record,"Compliance")!=="Compliant")continue;
    const unmet=(record.outgoing.get("Verified by")??[]).map(test=>[test.id,state(test,"Result")]).filter(([,result])=>result!=="Passed");
    if(unmet.length){
      issue(record.id,"Compliance",`Compliant, but ${sentence(unmet.map(([id,result])=>result?`${id} is “${result}”`:`${id} has no result`))}.`);
    }
  }
}
function checkTestCoverage(records,values,issue){
  const quote=names=>names.map(name=>`“${name}”`).join(", ");
  for(const record of records.values()){
    const tests=record.outgoing.get("Verified by")??[];
    for(const [field,rule] of tests.length?values:[]){
      const planned=definedValues(rule,record.row[field]);
      const covered=new Set(tests.flatMap(test=>definedValues(rule,test.row[field])));
      const missing=planned.filter(name=>!covered.has(name));
      if(covered.size&&missing.length){
        issue(record.id,field,`No test in Verified by covers ${quote(missing)}. Its tests have ${quote([...covered])}.`);
      }
    }
  }
}
function checkChanges(rows,identify,records,values,headers,schema,issue){
  const {baselines,records:controlled}=schema.controls,idColumn=schema.idColumn??"ID";
  const authorised=new Set();
  for(const record of records.values()){
    if(record.type==="Change request"&&approvedChangeStates.includes(verificationState(values,"Change status",record.row["Change status"]))){
      for(const target of traceIds(record.row.Affects))authorised.add(target);
    }
  }
  const scopes=baselines.map(baseline=>baselineScopeIds(rows,idColumn,baseline.system,baseline.includes));
  const text=value=>String(value??"");
  for(const row of rows){
    const id=identify(row);
    if(authorised.has(id))continue;
    if(Object.hasOwn(controlled,id)){
      const {baseline:name,row:old}=controlled[id],baseline=baselines.find(item=>item.name===name);
      const ignored=baseline.capturesStatus?[]:baseline.statusColumns;
      const changed=[...new Set([...headers,...Object.keys(old),...Object.keys(row)])]
        .filter(column=>!ignored.includes(column)&&text(old[column])!==text(row[column]));
      if(changed.length)issue(id,changed[0],`Changed since ${name} (${changed.join(", ")}) without an approved change request.`);
      continue;
    }
    let latest=null;
    baselines.forEach((baseline,position)=>{
      if(scopes[position].has(id)&&(!latest||baseline.created>latest.created))latest=baseline;
    });
    if(latest)issue(id,idColumn,`Added since ${latest.name} without an approved change request.`);
  }
  const present=new Set(rows.map(identify));
  for(const [id,{baseline}] of Object.entries(controlled)){
    if(!present.has(id)&&!authorised.has(id))issue(id,idColumn,`Removed since ${baseline} without an approved change request.`);
  }
}
function buildTraceIndex(rows,identify,schema={}){
  const headers=schema.headers??[...new Set(rows.flatMap(row=>Object.keys(row)))];
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
    if(!["System","Requirement","Need","Source","Term","Value","Field","Test","Test plan","Change request"].includes(type))issue(id,"Type",`Unknown record type “${type}”.`);
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
        else if(!target){
          if(!(field==="Affects"&&schema.controls&&Object.hasOwn(schema.controls.records,targetId)))issue(id,field,`Target ${targetId} is missing.`);
        }
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
  const glossary=buildGlossary(records.values(),issue);
  const values=buildValueRules(records.values(),headers,schema.idColumn,issue);
  checkTestCoverage(records,values,issue);
  checkVerification(records,values,issue);
  if(schema.controls)checkChanges(rows,identify,records,values,headers,schema,issue);
  return {records,systems,roots,issues,glossary,values};
}
function groupFindingsByCell(issues){
  const cells=new Map();
  for(const finding of issues){
    if(!finding.id)continue;
    const columns=cells.get(finding.id)??new Map();
    columns.set(finding.field,[...(columns.get(finding.field)??[]),finding]);
    cells.set(finding.id,columns);
  }
  return cells;
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
function traceLocationHash(place){
  const params=new URLSearchParams();
  const put=(key,value,fallback)=>{if(value!==fallback)params.set(key,value);};
  put("view",place.view,"requirements");
  if(place.view==="glossary")put("kind",place.kind,"terms");
  put("mode",place.mode??"","");
  put("system",place.system??"","");
  put("unallocated",place.unallocated?"1":"0","0");
  put("descendants",place.descendants===false?"0":"1","1");
  put("record",place.record??"","");
  const text=params.toString();
  return text?"#"+text:"";
}
function parseTraceLocation(hash){
  const params=new URLSearchParams(String(hash??"").replace(/^#/,""));
  const text=key=>params.get(key)??"";
  const flag=(key,fallback)=>{const value=params.get(key);return value==="1"?true:value==="0"?false:fallback;};
  return {view:text("view")||"requirements",kind:text("kind")==="values"?"values":"terms",mode:text("mode"),system:text("system"),
    unallocated:flag("unallocated",false),descendants:flag("descendants",true),record:text("record")};
}
const workspaceAddActions={requirements:"trace-view-add",sources:"trace-source-actions",tests:"trace-test-actions",
  changes:"trace-change-actions",glossary:{terms:"trace-term-add",values:"trace-value-add"}};
const workspaceControlIds=["trace-scope","trace-descendants","trace-glossary-kind","trace-view-mode",
  "trace-view-add","trace-term-add","trace-value-add","trace-source-actions","trace-test-actions","trace-change-actions","trace-selected-links"];
function workspaceControls({view,develop,systemScope,modes,matrix,system,glossaryKind}){
  const shown=[];
  if(systemScope&&view!=="gates")shown.push("trace-scope",...system?["trace-descendants"]:[]);
  if(view==="glossary")shown.push("trace-glossary-kind");
  if(modes)shown.push("trace-view-mode");
  const add=workspaceAddActions[view];
  if(develop&&add)shown.push(typeof add==="string"?add:add[glossaryKind]);
  if(view!=="systems"&&view!=="gates"&&!matrix)shown.push("trace-selected-links");
  return shown;
}
"""

TRACE_UI_JS = GLOSSARY_UI_JS + r"""
const trace=(()=>{
  const panel=$("#trace-panel"),detail=$("#trace-record"),tree=$("#trace-tree");
  const editor=$("#trace-editor"),picker=$("#trace-picker"),deletion=$("#trace-delete");
  const viewBar=$("#trace-views"),systemSelect=$("#trace-system"),status=$("#trace-status");
  const wrap=$(".table-wrap"),systemsPage=$("#trace-systems"),matrixPage=$("#trace-matrix"),modeBar=$("#trace-view-mode");
  const selectedLinks=$("#trace-selected-links"),gatesPage=$("#trace-gates"),gatesList=$("#trace-gates-list"),gatesSystem=$("#trace-gates-system");
  const gates=data.gates??[];
  let gateEvaluations=[];
  const requirementsDefaults=new Set([
    data.meta.idColumn,"Category","Requirement","Priority","Acceptance Criteria","Verification Method"
  ]);
  const sourceColumns=new Set([data.meta.idColumn,"Type","Name","Requirement","Reference"]);
  const sourceLayout={
    defaults:new Map([[data.meta.idColumn,100],["Type",84],["Name",168],["Requirement",240],["Reference",260]]),
    flexible:new Set(["Requirement","Reference"]),
    overrides:new Map(),
  };
  const testTypes=["Test","Test plan"];
  const constrainedColumns=types=>{
    const records=[...(index?.records.values()??[])].filter(record=>types.includes(record.type));
    return [...(index?.values.keys()??[])].filter(name=>records.some(record=>record.row[name]?.trim()));
  };
  const testColumnOrder=()=>[data.meta.idColumn,"Type","Name","Test plan",...constrainedColumns(testTypes),"Reference","Requirement"];
  const testLayout={
    defaults:new Map([[data.meta.idColumn,110],["Type",84],["Name",168],["Test plan",110],["Reference",220],["Requirement",260]]),
    flexible:new Set(["Requirement","Reference"]),
    overrides:new Map(),
  };
  const verificationColumns=()=>[data.meta.idColumn,"Requirement","Verification Method","Verification Level","Verified by","Compliance"];
  const verificationLayout={
    defaults:new Map([[data.meta.idColumn,110],["Requirement",280],["Verification Method",120],["Verification Level",120],["Verified by",240],["Compliance",130]]),
    flexible:new Set(["Requirement"]),
    overrides:new Map(),
  };
  const changesColumns=()=>[data.meta.idColumn,"Name","Change status","Affects","Requirement","Reference"];
  const changesLayout={
    defaults:new Map([[data.meta.idColumn,110],["Name",200],["Change status",120],["Affects",200],["Requirement",280],["Reference",220]]),
    flexible:new Set(["Requirement","Reference"]),
    overrides:new Map(),
  };
  const listViews={
    sources:{types:["Need","Source"],columns:sourceColumns,layout:sourceLayout,summary:count=>`${count} needs and sources`},
    tests:{types:testTypes,get columns(){return new Set(testColumnOrder());},layout:testLayout,order:testColumnOrder,summary:count=>`${count} test records`},
    verification:{types:["Requirement"],systemScope:true,get columns(){return new Set(verificationColumns());},order:verificationColumns,
      layout:verificationLayout,summary:count=>`${count} requirements`,modes:{grid:"Grid",matrix:"Matrix"},
      cells:{"Verification Method":methodCell,"Verified by":verifiedByCell},strip:verificationStrip},
    changes:{types:["Change request"],get columns(){return new Set(changesColumns());},layout:changesLayout,order:changesColumns,
      summary:count=>`${count} change ${count===1?"request":"requests"}`},
    gates:{types:[],systemScope:true,columns:new Set([data.meta.idColumn]),summary:()=>`${gates.length} ${gates.length===1?"gate":"gates"}`},
  };
  const glossaryFields=["Definition","Aliases","Auto Link"];
  const traceMetadata=new Set([...Object.keys(traceFields),"Type","Name","Reference","Origin","Field","Multiple","Change status",...glossaryFields]);
  const glossaryKinds={
    terms:{types:["Term"],columns:new Set([data.meta.idColumn,"Name",...glossaryFields]),
      summary:count=>`${count} glossary ${count===1?"term":"terms"}`},
    values:{types:["Value","Field"],
      columns:new Set([data.meta.idColumn,"Type","Field","Name","Definition","Multiple","Aliases","Reference"]),
      summary:count=>`${count} value ${count===1?"record":"records"}`},
  };
  const glossaryPopover=createGlossaryPopover(id=>navigate(id));
  const labels={
    "Part of":["Parent system","Move to…"],
    "Allocated to":["Applies to","Allocate to…"],
    "Owner":["Owner","Set owner…"],
    "Derived from":["Parent requirements","Link parent requirement…"],
    "Source refs":["Needs and sources","Link need or source…"],
    "Verified by":["Verified by","Link test…"],
    "Test plan":["Test plan","Set test plan…"],
    "Affects":["Affects","Link affected record…"],
  };
  const removedSince=id=>data.controls&&Object.hasOwn(data.controls.records,id)?data.controls.records[id].baseline:null;
  let index,indexVersion=null,view="requirements",glossaryKind="terms",system="",unallocated=false,descendants=true;
  const syncIndex=()=>{
    if(indexVersion!==dataVersion){
      index=buildTraceIndex(state.currentRows,rowId,{headers:data.source.new.headers,idColumn:data.meta.idColumn,controls:data.controls});
      indexVersion=dataVersion;
    }
    return index;
  };
  let selected=null,selectedSystem=null,revealed=null,pending=null;
  let scope=new Set(),recordEdit=null,linkEdit=null,deleteEdit=null;

  const label=record=>record.row.Name?.trim()||record.id;
  const caption=record=>label(record)===record.id?record.id:`${label(record)} (${record.id})`;
  const writable=()=>developMode()&&!state.editingCell;
  const visible=id=>displayIndex(id)>=0;
  const children=record=>record.incoming.filter(edge=>edge.field==="Part of").map(edge=>edge.record);
  const link=(id,text)=>`<button type="button" class="trace-link" data-trace-jump="${escapeHtml(id)}">${escapeHtml(text)}</button>`;
  const focusControl=(container,attribute,value)=>{
    [...container.querySelectorAll(`[${attribute}]`)].find(button=>button.getAttribute(attribute)===value)?.focus();
  };

  const usesScope=()=>view==="requirements"||!!listViews[view]?.systemScope;
  const viewModes=new Map();
  const viewMode=()=>{const modes=listViews[view]?.modes;return modes?viewModes.get(view)??Object.keys(modes)[0]:"";};
  const matrixShown=()=>viewMode()==="matrix";
  let matrixRecords=[];
  function methodCell(record){
    const rule=index.values.get("Verification Method");
    if(!rule)return null;
    const cell=record.row["Verification Method"]??"";
    const marks=verificationMethodMarks(rule,cell);
    const extra=(rule.multiple?traceIds(cell):[cell.trim()]).filter(part=>part&&!rule.values.has(part)&&!rule.aliases.has(part));
    const listed=[...marks.filter(mark=>mark.filled).map(mark=>mark.name),...extra];
    const slots=marks.map(mark=>`<span class="vcrm-slot${mark.filled?" on":""}" aria-hidden="true">${escapeHtml(mark.letter)}</span>`).join("");
    return `<span class="vcrm-methods" role="img" aria-label="Methods: ${escapeHtml(listed.join(", ")||"none")}">${slots}</span>`
      +extra.map(part=>` <span class="vcrm-extra">${escapeHtml(part)}</span>`).join("");
  }
  function verifiedByCell(record){
    const ids=[...new Set(traceIds(record.row["Verified by"]))];
    if(!ids.length)return null;
    return ids.map(id=>{
      const test=index.records.get(id);
      if(test?.type!=="Test")return `<span class="vcrm-test">${escapeHtml(id)}</span>`;
      const result=verificationState(index.values,"Result",test.row.Result);
      const tone=result?"vcrm-result-"+result.toLowerCase().replace(/[^a-z0-9]+/g,"-"):"vcrm-result-none";
      return `<span class="vcrm-test">${escapeHtml(label(test))} <span class="vcrm-result ${tone}">${escapeHtml(result||"No result")}</span></span>`;
    }).join("");
  }
  function verificationStrip(records){
    const compliance=record=>verificationState(index.values,"Compliance",record.row.Compliance);
    const count=test=>records.filter(test).length;
    const states=data.source.new.headers.includes("Compliance")?verificationStates.Compliance.states:[];
    return [...states.map(name=>[name,count(record=>compliance(record)===name)]),
      ["No compliance",count(record=>!compliance(record))],
      ["No method",count(record=>!record.row["Verification Method"]?.trim())],
      ["No linked tests",count(record=>!(record.outgoing.get("Verified by")??[]).length)]];
  }
  function paintMatrix(){
    const matrix=buildVerificationMatrix(matrixRecords,index.values,data.meta.idColumn);
    const cols=(names,group)=>names.length?`<th scope="colgroup" colspan="${names.length}">${group}</th>`:"";
    const marks=(row,kind,names)=>verificationMatrixMarks(row,kind,names)
      .map(([mark,extra])=>`<td class="vcrm-mark">${mark}${extra?` <span class="vcrm-extra">${escapeHtml(extra)}</span>`:""}</td>`).join("");
    const count=(totals,names)=>names.map(name=>`<td class="vcrm-mark">${totals[name]}</td>`).join("");
    const head=names=>{
      const labels=verificationMatrixLabels(names);
      return names.map((name,i)=>`<th scope="col" class="vcrm-mark"><abbr title="${escapeHtml(name)}">${escapeHtml(labels[i])}</abbr></th>`).join("");
    };
    const legend=(names,group)=>{
      const labels=verificationMatrixLabels(names);
      return names.length?`<span>${group}: ${names.map((name,i)=>`<b>${escapeHtml(labels[i])}</b> ${escapeHtml(name)}`).join(", ")}</span>`:"";
    };
    const scopeText=filters().map(([text])=>text).join(" · ");
    $("#trace-matrix-table").innerHTML=`<caption>${matrix.rows.length} ${matrix.rows.length===1?"requirement":"requirements"}${scopeText?" · "+escapeHtml(scopeText):""}<span class="vcrm-legend">${legend(matrix.methods,"Method")}${legend(matrix.levels,"Level")}</span></caption>
<thead><tr><th scope="col" rowspan="2">ID</th><th scope="col" rowspan="2">Requirement</th>${cols(matrix.methods,"Method")}${cols(matrix.levels,"Level")}<th scope="col" rowspan="2">Tests</th><th scope="col" rowspan="2">Compliance</th></tr>
<tr>${head(matrix.methods)}${head(matrix.levels)}</tr></thead>
<tbody>${matrix.rows.map(row=>`<tr><th scope="row">${escapeHtml(row.id)}</th><td>${escapeHtml(row.requirement)}</td>${marks(row,"methods",matrix.methods)}${marks(row,"levels",matrix.levels)}<td>${row.tests.map(test=>`<span class="vcrm-test"><span class="vcrm-nowrap">${escapeHtml(test.id)}</span> <span class="vcrm-nowrap">(${escapeHtml(test.result||"No result")})</span></span>`).join("")}</td><td>${escapeHtml(row.compliance)}</td></tr>`).join("")}</tbody>
<tfoot><tr><th scope="row" colspan="2">Totals</th>${count(matrix.totals.methods,matrix.methods)}${count(matrix.totals.levels,matrix.levels)}<td></td><td>${escapeHtml(Object.entries(matrix.totals.compliance).map(([name,total])=>`${name} ${total}`).join(" · "))}</td></tr></tfoot>`;
  }
  function downloadMatrix(){
    const delimiter=data.options.csvDelimiter||",";
    const lines=verificationMatrixCsvRows(buildVerificationMatrix(matrixRecords,index.values,data.meta.idColumn))
      .map(row=>row.map(field=>csvField(field,delimiter)).join(delimiter));
    downloadBlob(new Blob(["\ufeff"+lines.join("\r\n")+"\r\n"],{type:"text/csv;charset=utf-8"}),`${data.meta.baseFilename}-vcrm.csv`);
  }
  function paintStrip(){
    const records=grid.display.map(row=>index.records.get(row.id)).filter(Boolean);
    const box=$("#trace-verification-summary"),items=listViews[view]?.strip?.(records);
    matrixRecords=records;
    if(matrixShown())paintMatrix();
    box.hidden=!items;
    box.replaceChildren(...(items??[]).map(([name,count])=>{
      const item=document.createElement("span");
      item.textContent=`${name} ${count}`;
      return item;
    }));
  }

  function columnAvailable(name){
    if(view==="requirements")return !traceMetadata.has(name);
    if(listViews[view])return listViews[view].columns.has(name);
    if(view==="glossary")return glossaryKinds[glossaryKind].columns.has(name);
    return true;
  }
  function defaultHidden(){
    const shown=new Set([...requirementsDefaults,...constrainedColumns(["Requirement"])]);
    return new Set(data.columns.filter(({name,hidden})=>name===data.meta.idColumn
      ?view==="glossary":hidden||(view==="requirements"&&!shown.has(name))).map(({name})=>name));
  }
  const viewStates=new Map();
  const collapsed=new Set();
  const stateKey=(name,kind)=>name==="glossary"?`glossary:${kind}`:name;
  const kindOf=id=>glossaryKinds.values.types.includes(index.records.get(id)?.type)?"values":"terms";
  function switchView(next,reveal=null,kind=glossaryKind){
    if(view===next&&(next!=="glossary"||kind===glossaryKind))return false;
    viewStates.set(stateKey(view,glossaryKind),{hidden:state.hidden,filters:state.filters,valueFilters:state.valueFilters,
      sort:state.sort,focus:state.focus,scroll:[wrap.scrollLeft,wrap.scrollTop],
      commentsOnly:state.commentsOnly,idFilter:state.idFilter,qualityOnly:quality.only});
    view=next;
    if(next==="glossary")glossaryKind=kind;
    const saved=viewStates.get(stateKey(next,glossaryKind));
    state.hidden=saved?.hidden??defaultHidden();
    state.filters=saved?.filters??new Map();
    state.valueFilters=saved?.valueFilters??new Map();
    state.sort=saved?.sort??null;
    state.focus=saved?.focus??{row:0,column:0};
    state.commentsOnly=saved?.commentsOnly??false;
    state.idFilter=saved?.idFilter??null;
    quality.only=saved?.qualityOnly??false;
    revealed=reveal;
    pending=null;
    closeValueFilter();
    wrap.hidden=view==="systems";
    render();
    [wrap.scrollLeft,wrap.scrollTop]=saved?.scroll??[0,0];
    return true;
  }
  function canNavigate(){
    if(!state.editingCell){
      status.textContent="";
      return true;
    }
    status.textContent="Apply or cancel the cell edit before changing views or editing links.";
    return false;
  }
  function selectView(next){
    if(view===next||!canNavigate())return;
    close();
    step(()=>switchView(next));
  }
  function matches(row){
    if(view==="all")return true;
    if(view==="systems")return false;
    const record=index.records.get(row.id);
    const type=record?.type||(row.cells.Type?.old?.trim()||"Requirement");
    if(view==="glossary")return glossaryKinds[glossaryKind].types.includes(type);
    if(!(listViews[view]?.types??["Requirement"]).includes(type))return false;
    if(listViews[view]&&!listViews[view].systemScope)return true;
    if(!system&&!unallocated)return true;
    const allocated=record?(record.outgoing.get("Allocated to")??[]).map(target=>target.id)
      :traceIds(row.cells["Allocated to"]?.old);
    return unallocated?!allocated.length:allocated.some(id=>scope.has(id));
  }
  function refresh(){
    glossaryPopover.close();
    syncIndex();
    if(index.records.get(system)?.type!=="System")system="";
    if(revealed&&!index.records.has(revealed)&&!data.rows.some(row=>row.id===revealed))revealed=null;
    scope=new Set();
    const queue=system?[index.records.get(system)]:[];
    for(let i=0;i<queue.length;i++){
      const record=queue[i];
      if(scope.has(record.id))continue;
      scope.add(record.id);
      if(descendants)queue.push(...children(record));
    }
    renderWorkspace();
    if(!panel.hidden)renderIssues();
  }
  function filters(){
    const result=[];
    if(usesScope()){
      if(system)result.push([`System: ${caption(index.records.get(system))}${descendants?" and subsystems":""}`,
        ()=>{system="";}]);
      if(unallocated)result.push(["Unallocated requirements",()=>{unallocated=false;}]);
    }
    if(revealed)result.push([`Revealed record: ${revealed}`,()=>{revealed=null;}]);
    return result;
  }
  function reset(){system="";unallocated=false;revealed=null;pending=null;}
  function systemEntries(respectCollapse=false){
    const visited=new Set(),entries=[];
    const starts=[...index.roots,...index.systems.filter(record=>!record.outgoing.get("Part of")?.length),...index.systems];
    for(const root of starts){
      const stack=[[root,0]];
      while(stack.length){
        const [record,depth]=stack.pop();
        if(visited.has(record.id))continue;
        visited.add(record.id);
        entries.push([record,depth]);
        for(const child of children(record).reverse())stack.push([child,depth+1]);
      }
    }
    if(!respectCollapse)return entries;
    let collapsedDepth=Infinity;
    return entries.filter(([record,depth])=>{
      if(depth>collapsedDepth)return false;
      collapsedDepth=collapsed.has(record.id)?depth:Infinity;
      return true;
    });
  }
  function renderWorkspace(){
    for(const button of viewBar.querySelectorAll("[data-trace-view]")){
      button.setAttribute("aria-pressed",String(button.dataset.traceView===view));
    }
    const inSystems=view==="systems",inGates=view==="gates",inPage=inSystems||inGates;
    const inMatrix=matrixShown();
    wrap.hidden=inPage||inMatrix;
    systemsPage.hidden=!inSystems;
    gatesPage.hidden=!inGates;
    matrixPage.hidden=!inMatrix;
    for(const button of modeBar.querySelectorAll("[data-view-mode]")){
      button.setAttribute("aria-pressed",String(button.dataset.viewMode===viewMode()));
    }
    $("#columns-menu").hidden=inPage||inMatrix;
    $("#filter-menu").hidden=inPage;
    const shown=workspaceControls({view,develop:developMode(),systemScope:usesScope(),modes:!!listViews[view]?.modes,
      matrix:inMatrix,system,glossaryKind});
    for(const id of workspaceControlIds){
      const control=$("#"+id);
      (id==="trace-descendants"?control.closest("label"):control).hidden=!shown.includes(id);
    }
    $("#trace-controls").hidden=!shown.length;
    for(const button of $("#trace-glossary-kind").querySelectorAll("[data-glossary-kind]")){
      button.setAttribute("aria-pressed",String(button.dataset.glossaryKind===glossaryKind));
    }
    $("#trace-system-add").hidden=!developMode()||!!index.systems.length;
    if(usesScope()){
      const options=inGates?[new Option("No system chosen","all")]:[new Option("All requirements","all"),new Option("Unallocated requirements","unallocated")];
      for(const [record,depth] of systemEntries())options.push(new Option("  ".repeat(Math.min(depth,8))+caption(record),"system:"+record.id));
      const value=unallocated&&!inGates?"unallocated":system?"system:"+system:"all";
      for(const select of [systemSelect,gatesSystem]){
        select.replaceChildren(...options.map(option=>option.cloneNode(true)));
        select.value=value;
      }
      $("#trace-descendants").checked=descendants;
    }
    if(inSystems)renderTree();
    if(inGates)renderGates();
  }
  function renderGates(){
    const headers=data.source.new.headers;
    gateEvaluations=gates.map(gate=>gate.scope==="system"&&!system?null
      :gate.checks.map(check=>evaluateGateCheck(check,state.currentRows,data.meta.idColumn,headers,gate.scope==="system"?system:null,index.issues,data.controls??null)));
    gatesList.innerHTML=gates.length?gates.map((gate,gateIndex)=>{
      const results=gateEvaluations[gateIndex];
      const badge=results?(({tone,mark})=>`<span class="gate-badge ${tone}">${mark}</span>`)(gateBadgeLabel(results)):"";
      const scopeText=gate.scope==="system"&&system?` · Scope: ${escapeHtml(caption(index.records.get(system)))}`:"";
      const body=results?`<ul class="gate-checks">${results.map((result,checkIndex)=>gateCheckItem(result,gateIndex,checkIndex)).join("")}</ul>`
        :'<p class="meta">Choose a system in the System selector to check this gate.</p>';
      return `<section class="gate" data-gate="${escapeHtml(gate.id)}" aria-labelledby="gate-title-${gateIndex}">
<header><h2 id="gate-title-${gateIndex}">${escapeHtml(gate.name||gate.id)} <span class="meta">(${escapeHtml(gate.id)})</span></h2>${badge}</header>
<p class="meta">Produces: ${escapeHtml(gate.produces||"nothing recorded")}${scopeText}</p>${body}</section>`;
    }).join(""):"<p>No gates are configured.</p>";
  }
  function gateCheckItem(result,gateIndex,checkIndex){
    const {tone,mark}=gateCheckLabel(result);
    const records=result.error?[]:result.failing.filter(Boolean);
    const count=result.error?escapeHtml(result.error):`${result.failing.length} of ${result.total} failing`;
    const show=records.length?` <button type="button" data-gate-show="${gateIndex}:${checkIndex}">Show records</button>`:"";
    const table=result.global?.length?`<ul class="gate-table-findings"><li><strong>Table-level findings</strong> (${result.global.length}): ${result.global.map(escapeHtml).join(" ")}</li></ul>`:"";
    return `<li data-check="${escapeHtml(result.id)}"><span class="gate-mark ${tone}">${mark}</span> ${escapeHtml(result.description||result.id)} <span class="meta">${count}</span>${show}${table}</li>`;
  }
  function gateDestination(ids){
    const views=new Set(ids.map(id=>{
      const type=index.records.get(id)?.type;
      return type==="Requirement"?"requirements":viewForType(type);
    }));
    const [only]=views;
    return views.size===1&&["requirements","tests","sources"].includes(only)?only:"all";
  }
  function showGateRecords(gate,check){
    const result={...check,failing:check.failing.filter(Boolean)};
    if(!canNavigate())return;
    close();
    step(()=>{
      if(gate.scope==="system")descendants=true;
      else{system="";unallocated=false;}
      revealed=null;
      switchView(gateDestination(result.failing));
      showIdFilter(`Gate check ${result.id}: ${result.failing.length} ${result.failing.length===1?"record":"records"}`,result.failing);
      render();
    });
  }
  function renderTree(){
    const entries=systemEntries(true);
    if(!entries.some(([record])=>record.id===selectedSystem))selectedSystem=entries[0]?.[0].id??null;
    tree.innerHTML=entries.length?entries.map(([record,depth])=>{
      const count=record.incoming.filter(edge=>edge.field==="Allocated to").length;
      const expanded=!collapsed.has(record.id);
      const toggle=children(record).length?`<button type="button" data-trace-collapse="${escapeHtml(record.id)}"
        aria-label="${expanded?"Collapse":"Expand"} ${escapeHtml(label(record))}" aria-expanded="${expanded}">${expanded?"▾":"▸"}</button>`:'<span class="trace-tree-leaf"></span>';
      return `<li style="--trace-depth:${Math.min(depth,8)}">
        <div class="trace-tree-node">
          ${toggle}
          <button type="button" data-trace-system="${escapeHtml(record.id)}" aria-pressed="${selectedSystem===record.id}">${escapeHtml(caption(record))}</button>
        </div>
        <span class="meta">${count} allocated</span></li>`;
    }).join(""):"<li>No systems yet.</li>";
    const record=index.records.get(selectedSystem),actions=$("#trace-system-actions");
    actions.hidden=!record;
    $("#trace-system-name").textContent=record?caption(record):"";
    const parent=record?.outgoing.get("Part of")?.[0];
    $("#trace-system-parent").textContent=record?(parent?`Parent system: ${caption(parent)}`:"Top-level system"):"";
    $("#trace-system-edit").hidden=!developMode();
  }
  function renderIssues(){
    $("#trace-findings").querySelector("summary").textContent=`Trace findings (${index.issues.length})`;
    $("#trace-issues").innerHTML=index.issues.length?index.issues.map(({id,field,message})=>
      `<li data-finding-id="${escapeHtml(id??"")}" data-finding-field="${escapeHtml(field)}">${id?(index.records.has(id)?link(id,id):escapeHtml(id))+" · ":""}<strong>${escapeHtml(field)}</strong><br>${escapeHtml(message)}</li>`
    ).join(""):"<li>No trace findings.</li>";
  }
  function showFindings(id,column){
    openPanel(id);
    $("#trace-findings").open=true;
    let first=null;
    for(const item of $("#trace-issues").children){
      const match=item.dataset.findingId===id&&item.dataset.findingField===column;
      item.classList.toggle("trace-finding-active",match);
      first??=match?item:null;
    }
    first?.scrollIntoView({block:"nearest"});
  }
  function paintMarkers(rows){
    const cells=groupFindingsByCell(index.issues);
    for(const row of rows){
      const columns=cells.get(row.dataset.rowId);
      if(!columns)continue;
      for(const cell of row.querySelectorAll("[data-grid-cell]")){
        const column=cell.dataset.column,issues=columns.get(column);
        const wrapper=cell.querySelector(".cell-wrap");
        if(!issues||!wrapper||wrapper.querySelector(".trace-marker"))continue;
        const id=row.dataset.rowId;
        const label=`${issues.length} trace ${issues.length===1?"finding":"findings"} for ${id}, ${column}`;
        wrapper.append(findingMarker("trace-marker","⚑",label,marker=>findingPopover.open(marker,{
          heading:`${id} · ${columnLabel(column)}`,
          findings:issues.map(issue=>({detail:issue.message})),
          actions:[{label:"Show in Links",run:()=>showFindings(id,column)}]
        })));
      }
    }
  }
  function renderDetail(){
    if(panel.hidden)return;
    const record=index.records.get(selected);
    const reveal=pending?`<div class="trace-reveal">${escapeHtml(pending)} is outside the current filters.
      <button type="button" id="trace-reveal">Reveal in grid</button></div>`:"";
    paintBack();
    if(!record){
      detail.innerHTML=reveal+"<p>Select a current record to see its links.</p>";
      return;
    }
    const {id,row,type}=record;
    const incomingLabels={"Part of":"Subsystems","Allocated to":"Allocated requirements","Owner":"Owned requirements",
      "Derived from":"Child requirements","Source refs":"Referenced by","Verified by":"Verifies","Test plan":"Tests","Affects":"Change requests"};
    const sections=[];
    for(const [field,rule] of Object.entries(traceFields)){
      const ids=[...new Set(traceIds(row[field]))];
      if(!rule.from.includes(type)&&!ids.length)continue;
      const [heading,action]=field==="Source refs"&&type==="Term"?["Sources","Link source…"]:labels[field];
      const targets=ids.map(targetId=>{
        const target=index.records.get(targetId);
        const remove=writable()? ` <button type="button" class="trace-remove" data-trace-remove="${escapeHtml(field)}"
          data-trace-target="${escapeHtml(targetId)}" aria-label="Remove ${escapeHtml(heading)} link to ${escapeHtml(targetId)}">×</button>`:"";
        const gone=removedSince(targetId);
        return `<li>${target?link(targetId,caption(target)):escapeHtml(targetId)+(gone?` (removed since ${escapeHtml(gone)})`:" (missing)")}${remove}</li>`;
      });
      const edit=writable()&&rule.from.includes(type)?` <button type="button" data-trace-pick="${escapeHtml(field)}">${action}</button>`:"";
      sections.push(`<section><h4>${heading}</h4>${targets.length?`<ul>${targets.join("")}</ul>`:'<p class="meta">None</p>'}${edit}</section>`);
    }
    for(const [field,heading] of Object.entries(incomingLabels)){
      const links=record.incoming.filter(edge=>edge.field===field);
      const addChild=field==="Derived from"&&type==="Requirement"&&writable()
        ?'<button type="button" id="trace-add-child">Add child requirement…</button>':"";
      if(links.length||addChild||(field==="Derived from"&&type==="Requirement")){
        const list=links.length?`<ul>${links.map(({record:source})=>`<li>${link(source.id,caption(source))}</li>`).join("")}</ul>`:'<p class="meta">None</p>';
        sections.push(`<section><h4>${heading}</h4>${list}${addChild}</section>`);
      }
    }
    const origin=row.Origin?.trim()||(traceIds(row["Source refs"]).length||traceIds(row["Derived from"]).length?"":"No origin recorded");
    const notes=[row.Requirement,row.Definition,row.Reference,type==="Requirement"?origin:"",row.Rationale].filter(Boolean);
    detail.innerHTML=reveal+`<h3 tabindex="-1">${escapeHtml(caption(record))}</h3><p class="meta">${escapeHtml(type)}</p>`
      +notes.map(note=>`<p class="trace-note">${escapeHtml(note)}</p>`).join("")+sections.join("");
  }
  function syncSelection(id,force=false){
    if(view==="systems")id=selectedSystem;
    if(id===selected&&!force)return;
    selected=id;
    if(ready&&!guard&&!force&&id&&id!==recordId){recordId=id;writeHistory(false);}
    selectedLinks.disabled=!index.records.has(id);
    selectedLinks.title=selectedLinks.disabled?"Select a current record to see its links":`Links and trace findings for ${id}`;
    selectedLinks.setAttribute("aria-label",selectedLinks.disabled?"Links and trace findings":`Links and trace findings for ${id}`);
    pending=null;
    renderDetail();
  }
  function viewForType(type){
    if(type==="System")return "systems";
    if(type==="Term"||type==="Value"||type==="Field")return "glossary";
    if(type==="Requirement")return listViews[view]?.systemScope?view:"requirements";
    return Object.keys(listViews).find(name=>listViews[name].types.includes(type))??"all";
  }
  const recordView=id=>viewForType(index.records.get(id)?.type);
  const linksTarget=()=>view==="systems"?selectedSystem:view==="gates"||matrixShown()?null:selectedRequirementId();
  function openPanel(id){
    closeReview();
    closeQuality();
    panel.hidden=false;
    $("#open-trace").setAttribute("aria-expanded","true");
    selectedLinks.setAttribute("aria-expanded","true");
    renderIssues();
    syncSelection(id,true);
    renderLayout();
    (detail.querySelector("h3")??$("#trace-title")).focus({preventScroll:true});
  }
  function close(){
    if(panel.hidden)return;
    panel.hidden=true;
    $("#open-trace").setAttribute("aria-expanded","false");
    selectedLinks.setAttribute("aria-expanded","false");
    renderLayout();
  }
  function focusRecord(id){
    if(view==="systems"){
      const seen=new Set([id]);
      let parent=index.records.get(id)?.outgoing.get("Part of")?.[0];
      while(parent&&!seen.has(parent.id)){
        seen.add(parent.id);
        collapsed.delete(parent.id);
        parent=parent.outgoing.get("Part of")?.[0];
      }
      selectedSystem=id;
      renderTree();
    }else focusRequirement(id,data.meta.idColumn);
    syncSelection(id,true);
    (detail.querySelector("h3")??$("#trace-title")).focus({preventScroll:true});
  }
  function navigate(id){
    if(!canNavigate())return;
    const destination=recordView(id);
    if(destination===view&&!visible(id)&&view!=="systems"){
      pending=id;
      renderDetail();
      $("#trace-reveal").focus();
      return;
    }
    step(()=>{
      switchView(destination,null,kindOf(id));
      if(view!=="systems"&&!visible(id)){revealed=id;render();}
      focusRecord(id);
    },id);
  }
  const historyOn=window.top===window&&!!history.pushState;
  let guard=false,ready=false,histIndex=0,histHash="",recordId="";
  const paintBack=()=>{$("#trace-back").hidden=!(histIndex>0);};
  function place(){
    const modes=listViews[view]?.modes,mode=viewMode();
    return {view,kind:glossaryKind,mode:modes&&mode!==Object.keys(modes)[0]?mode:"",system,unallocated,descendants,record:recordId};
  }
  function writeHistory(push){
    if(!ready)return;
    const hash=traceLocationHash(place());
    if(hash===histHash)return;
    const next=histIndex+(push?1:0);
    try{history[push?"pushState":"replaceState"]({reqtable:true,index:next,place:place()},"",hash||location.href.split("#")[0]);}
    catch{return;}
    histIndex=next;
    histHash=hash;
    paintBack();
  }
  function step(change,id=""){
    guard=true;
    try{change();}finally{guard=false;}
    recordId=id;
    writeHistory(true);
  }
  function applyPlace(target){
    guard=true;
    try{
      const views=[...viewBar.querySelectorAll("[data-trace-view]")].map(button=>button.dataset.traceView);
      const next=views.includes(target.view)?target.view:"requirements";
      system=index.records.get(target.system)?.type==="System"?target.system:"";
      unallocated=!system&&target.unallocated;
      descendants=target.descendants;
      const modes=listViews[next]?.modes;
      if(modes)viewModes.set(next,target.mode in modes?target.mode:Object.keys(modes)[0]);
      if(!switchView(next,null,target.kind))render();
      recordId=index.records.has(target.record)?target.record:"";
      if(recordId){
        if(view!=="systems"&&!visible(recordId)){revealed=recordId;render();}
        focusRecord(recordId);
      }
    }finally{guard=false;}
  }
  function goBack(){
    if(canNavigate())history.back();
  }
  function restoreHistory(){
    if(!historyOn)return;
    const target=parseTraceLocation(location.hash);
    if(traceLocationHash(target))applyPlace(target);
    histIndex=history.state?.reqtable===true?history.state.index:0;
    ready=true;
    histHash="\0";
    writeHistory(false);
  }
  function popHistory(event){
    if(!ready)return;
    const ours=event.state?.reqtable===true,known=ours?event.state.index:histIndex;
    if(!canNavigate()){
      history.pushState({reqtable:true,index:known+1,place:place()},"",traceLocationHash(place())||location.href.split("#")[0]);
      histIndex=known+1;
      paintBack();
      return;
    }
    applyPlace(ours?event.state.place:parseTraceLocation(location.hash));
    histIndex=ours?known:known+1;
    histHash="\0";
    writeHistory(false);
  }
  function restoreGridSelection(id,column){
    const row=id?displayIndex(id):-1;
    state.focus.row=row>=0&&visibleColumns().some(item=>item.name===column)?row:0;
    setRovingFocus();
  }
  function changeScope(id,onlyUnallocated=false){
    const current=selectedRequirementId(),column=visibleColumns()[state.focus.column]?.name;
    step(()=>{
      system=id;
      unallocated=onlyUnallocated;
      revealed=null;
      if(!switchView(usesScope()?view:"requirements"))render();
    });
    restoreGridSelection(current,column);
  }
  function updateLink(record,field,value){
    if(!writable()||!record||record.row[field]===value)return;
    remember();
    record.row[field]=value;
    updateDirty();
    render();
    if(view==="systems")focusRecord(record.id);
    else syncSelection(record.id,true);
    if(!panel.hidden)focusControl(detail,"data-trace-pick",field);
    else if(view==="systems")focusControl(tree,"data-trace-system",record.id);
  }
  function showCandidates(){
    const {id,field,checked}=linkEdit,record=index.records.get(id);
    const query=$("#trace-query").value.trim().toLocaleLowerCase();
    const matches=text=>text.toLocaleLowerCase().includes(query);
    const detailOf=target=>String(target.row.Requirement||target.row.Definition||"").replace(/\s+/g," ").trim();
    const targets=[...index.records.values()].filter(target=>(matches(caption(target))||matches(detailOf(target)))
      &&(checked?.has(target.id)||traceCanLink(record,field,target)));
    const names=new Map(targets.map(target=>[target.id,caption(target)]));
    const details=new Map(targets.map(target=>[target.id,detailOf(target)]));
    const body=(id,name)=>{
      const detail=details.get(id)??"";
      return `<span class="trace-candidate-name">${escapeHtml(name)}</span>`
        +(detail?`<span class="trace-candidate-detail" title="${escapeHtml(detail)}">${escapeHtml(detail)}</span>`:"");
    };
    if(field==="Affects"){
      for(const removedId of Object.keys(data.controls?.records??{})){
        const label=`${removedId} (removed since ${removedSince(removedId)})`;
        if(!index.records.has(removedId)&&!traceIds(record.row.Affects).includes(removedId)&&matches(label))names.set(removedId,label);
      }
    }
    if(checked){
      for(const id of checked){
        const target=index.records.get(id);
        if(!target&&matches(id))names.set(id,`${id} (missing)`);
      }
    }
    $("#trace-candidates").innerHTML=names.size?[...names].map(([id,name])=>checked
      ?`<li><label><input type="checkbox" data-trace-target="${escapeHtml(id)}" ${checked.has(id)?"checked":""}> ${body(id,name)}</label></li>`
      :`<li><button type="button" data-trace-target="${escapeHtml(id)}">${body(id,name)}</button></li>`
    ).join(""):"<li>No eligible targets match.</li>";
  }
  function editLink(field,id=selected){
    if(!writable()||!index.records.has(id))return;
    const checked=field==="Allocated to"?new Set(traceIds(index.records.get(id).row[field])):null;
    linkEdit={id,field,checked};
    $("#trace-picker-title").textContent=field==="Source refs"&&index.records.get(id).type==="Term"
      ?"Link source":labels[field][1].replace("…","");
    $("#trace-query").value="";
    $("#trace-picker-apply").hidden=!checked;
    showCandidates();
    picker.showModal();
    $("#trace-query").focus();
  }
  function editRecord(type,{record=null,parent=null}={}){
    if(!writable())return;
    recordEdit={type,record,parent};
    $("#trace-editor-title").textContent=record?"Rename system":parent?(type==="System"?"Add subsystem":"Add child requirement"):`Add ${type.toLowerCase()}`;
    const idInput=$("#trace-record-id");
    const generatedId=type==="Term"||type==="Value";
    $("#trace-record-id-field").hidden=idInput.disabled=generatedId;
    $("#trace-value-field-label").hidden=type!=="Value";
    $("#trace-value-aliases-label").hidden=type!=="Value";
    $("#trace-value-aliases").value="";
    if(type==="Value")fillValueFields();
    idInput.value=record?.id??(type==="Requirement"?nextRecordId():"");
    idInput.readOnly=!!record;
    $("#trace-record-name").value=record?.row.Name??"";
    $("#trace-record-name").required=type!=="Requirement";
    $("#trace-record-name-field").hidden=type==="Requirement";
    $("#trace-record-content").value="";
    $("#trace-record-content").required=type==="Requirement"||type==="Term"||type==="Value";
    $("#trace-test-plan-label").hidden=type!=="Test";
    if(type==="Test")optionList($("#trace-test-plan"),[...index.records.values()].filter(({type})=>type==="Test plan"),"No test plan");
    $("#trace-record-content-field").hidden=type==="System";
    $("#trace-record-content-label").textContent=type==="Term"||type==="Value"?"Definition":type==="Source"?"Citation":type==="Need"?"Need statement":type==="Test"||type==="Test plan"||type==="Change request"?"Description":"Requirement statement";
    $("#trace-term-options").hidden=type!=="Term";
    $("#trace-term-aliases").value="";
    $("#trace-term-single-word").checked=false;
    editor.showModal();
    if(type==="Value")$("#trace-value-field").focus();
    else if(!$("#trace-record-id").disabled&&!$("#trace-record-id-field").hidden)$("#trace-record-id").focus();
    else $("#trace-record-name").focus();
  }
  function fillValueFields(){
    const names=valueFieldNames(data.source.new.headers,data.meta.idColumn);
    const open=data.source.new.headers.filter(name=>!traceMetadata.has(name)&&!valueColumnProblem(name,names));
    const defined=open.filter(name=>index.values.has(name));
    $("#trace-value-field").replaceChildren(...[...defined,...open.filter(name=>!index.values.has(name))]
      .map(name=>new Option(name,name)));
  }
  function takenIds(){
    return new Set([...state.currentRows,...state.savedRows,...(data.source.old?.rows??[])].map(rowId));
  }
  function optionList(select,choices,empty){
    select.replaceChildren(new Option(empty,""),...choices.map(record=>new Option(caption(record),record.id)));
  }
  function openDeletion(id){
    if(!writable())return;
    const record=index.records.get(id);
    if(record?.type!=="System")return;
    const changes=traceIncomingChanges(state.currentRows,id,null).filter(change=>change.row!==record.row);
    const fields=["Part of","Allocated to","Owner"];
    deleteEdit={id,changes};
    $("#trace-delete-title").textContent=`Delete system ${caption(record)}?`;
    const comments=state.comments.filter(comment=>comment.requirementId===id).length;
    $("#trace-delete-impact").textContent=`This affects ${changes.length} incoming links and deletes ${comments} attached comments.`;
    let described=0;
    for(const [i,field] of fields.entries()){
      const group=$("#trace-delete-group-"+i),select=group.querySelector("select");
      const related=changes.filter(change=>change.field===field&&traceFields[field].from.includes(traceType(change.row)));
      described+=related.length;
      const eligible=index.systems.filter(target=>target!==record&&(
        field!=="Part of"||related.every(change=>traceCanLink(index.records.get(rowId(change.row)),field,target))));
      group.hidden=!related.length;
      group.querySelector("span").textContent=`${related.length} ${["direct subsystems","requirement allocations","requirement owners"][i]}`;
      optionList(select,eligible,["Make top-level","Remove this allocation","Clear owner"][i]);
      if(field==="Part of"){
        const parent=record.outgoing.get(field)?.[0];
        if(eligible.includes(parent))select.value=parent.id;
      }
    }
    $("#trace-delete-other").textContent=described<changes.length?"Other invalid references to this system will also be cleared.":"";
    deletion.showModal();
  }
  function clearCopy(clone){
    clone.querySelector("#glossary-definition").hidden=true;
    for(const id of ["glossary-definition-title","glossary-definition-content","glossary-definition-sources"]){
      clone.querySelector("#"+id).replaceChildren();
    }
    clone.querySelector("#trace-panel").hidden=true;
    clone.querySelector("#trace-back").hidden=true;
    clone.querySelector(".table-wrap").hidden=false;
    clone.querySelector("#trace-systems").hidden=true;
    clone.querySelector("#trace-gates").hidden=true;
    clone.querySelector("#trace-gates").replaceChildren();
    clone.querySelector("#trace-matrix").hidden=true;
    clone.querySelector("#trace-matrix-table").replaceChildren();
    clone.querySelector("#open-trace").setAttribute("aria-expanded","false");
    clone.querySelector("#trace-selected-links").setAttribute("aria-expanded","false");
    for(const id of ["trace-tree","trace-record","trace-issues","trace-candidates","trace-status","trace-system",
      "trace-system-name","trace-system-parent","trace-verification-summary","trace-delete-impact","trace-delete-other"]){
      clone.querySelector("#"+id).replaceChildren();
    }
    clone.querySelector("#trace-delete-title").textContent="Delete system?";
    clone.querySelectorAll("#trace-delete-form select").forEach(select=>select.replaceChildren());
    for(const id of ["trace-editor","trace-picker","trace-delete","trace-findings"]){
      clone.querySelector("#"+id).removeAttribute("open");
    }
  }

  if(!gates.length)viewBar.querySelector('[data-trace-view="gates"]').remove();
  gatesPage.addEventListener("click",event=>{
    const [gateIndex,checkIndex]=(event.target.closest("[data-gate-show]")?.dataset.gateShow??"").split(":").map(Number);
    if(gateIndex>=0)showGateRecords(gates[gateIndex],gateEvaluations[gateIndex][checkIndex]);
  });
  syncIndex();
  if(!data.controls&&!data.source.new.headers.some(name=>name==="Change status"||name==="Affects")
      &&![...index.records.values()].some(record=>record.type==="Change request")){
    viewBar.querySelector('[data-trace-view="changes"]').remove();
  }
  state.hidden=defaultHidden();
  wrap.hidden=false;
  viewBar.addEventListener("click",event=>{
    const button=event.target.closest("[data-trace-view]");
    if(button)selectView(button.dataset.traceView);
  });
  for(const select of [systemSelect,gatesSystem]){
    select.addEventListener("change",()=>{
      if(!canNavigate()){renderWorkspace();return;}
      const value=select.value;
      changeScope(value.startsWith("system:")?value.slice(7):"",value==="unallocated");
    });
  }
  $("#trace-descendants").addEventListener("change",event=>{
    if(!canNavigate()){event.target.checked=descendants;return;}
    descendants=event.target.checked;
    changeScope(system);
  });
  $("#trace-view-add").addEventListener("click",()=>{if(canNavigate())addRequirement("end");});
  $("#trace-need-add").addEventListener("click",()=>editRecord("Need"));
  $("#trace-source-add").addEventListener("click",()=>editRecord("Source"));
  $("#trace-test-plan-add").addEventListener("click",()=>editRecord("Test plan"));
  $("#trace-test-add").addEventListener("click",()=>editRecord("Test"));
  $("#trace-change-add").addEventListener("click",()=>editRecord("Change request"));
  $("#trace-term-add").addEventListener("click",()=>editRecord("Term"));
  $("#trace-value-add").addEventListener("click",()=>editRecord("Value"));
  $("#trace-glossary-kind").addEventListener("click",event=>{
    const kind=event.target.closest("[data-glossary-kind]")?.dataset.glossaryKind;
    if(!kind||kind===glossaryKind||!canNavigate())return;
    close();
    step(()=>switchView("glossary",null,kind));
  });
  modeBar.addEventListener("click",event=>{
    const mode=event.target.closest("[data-view-mode]")?.dataset.viewMode;
    if(!mode||mode===viewMode()||!canNavigate())return;
    step(()=>{
      viewModes.set(view,mode);
      renderWorkspace();
      paintStrip();
    });
  });
  $("#trace-matrix-print").addEventListener("click",()=>window.print());
  $("#trace-matrix-csv").addEventListener("click",downloadMatrix);
  $("#trace-system-add").addEventListener("click",()=>editRecord("System"));
  $("#trace-subsystem-add").addEventListener("click",()=>editRecord("System",{parent:selectedSystem}));
  $("#trace-system-rename").addEventListener("click",()=>editRecord("System",{record:index.records.get(selectedSystem)}));
  $("#trace-system-move").addEventListener("click",()=>editLink("Part of",selectedSystem));
  $("#trace-system-delete").addEventListener("click",()=>openDeletion(selectedSystem));
  $("#trace-system-requirements").addEventListener("click",()=>{
    if(!canNavigate())return;
    close();
    changeScope(selectedSystem);
    systemSelect.focus();
  });
  $("#trace-system-links").addEventListener("click",()=>openPanel(selectedSystem));
  tree.addEventListener("click",event=>{
    const toggle=event.target.closest("[data-trace-collapse]");
    if(toggle){
      const id=toggle.dataset.traceCollapse;
      if(collapsed.has(id))collapsed.delete(id);
      else collapsed.add(id);
      renderTree();
      syncSelection(selectedSystem);
      focusControl(tree,"data-trace-collapse",id);
      return;
    }
    const button=event.target.closest("[data-trace-system]");
    if(!button)return;
    selectedSystem=button.dataset.traceSystem;
    renderTree();
    syncSelection(selectedSystem);
    focusControl(tree,"data-trace-system",selectedSystem);
  });
  $("#open-trace").addEventListener("click",()=>{
    if(!canNavigate())return;
    if(panel.hidden)openPanel(linksTarget());
    else {close();restoreSelectedCell();}
  });
  selectedLinks.addEventListener("click",()=>{
    if(!canNavigate())return;
    openPanel(linksTarget());
  });
  for(const dialog of [editor,picker,deletion])dialog.addEventListener("keydown",event=>event.stopPropagation());
  $("#close-trace").addEventListener("click",()=>{
    close();
    if(view==="systems")focusControl(tree,"data-trace-system",selectedSystem);
    else restoreSelectedCell();
  });
  $("#trace-back").addEventListener("click",goBack);
  panel.addEventListener("click",event=>{
    const button=event.target.closest("button");
    if(!button)return;
    const {traceJump,tracePick,traceRemove,traceTarget}=button.dataset;
    const record=index.records.get(selected);
    if(traceJump!==undefined)navigate(traceJump);
    else if(tracePick)editLink(tracePick);
    else if(traceRemove&&record)updateLink(record,traceRemove,traceIds(record.row[traceRemove])
      .filter(id=>id!==traceTarget).join("; "));
    else if(button.id==="trace-add-child")editRecord("Requirement",{parent:selected});
    else if(button.id==="trace-reveal"&&pending&&canNavigate()){
      const id=pending;
      step(()=>{
        revealed=id;
        render();
        focusRecord(id);
      },id);
    }
  });
  $("#trace-query").addEventListener("input",showCandidates);
  picker.addEventListener("keydown",event=>{
    if(event.key!=="ArrowDown"&&event.key!=="ArrowUp")return;
    const query=$("#trace-query"),options=[...$("#trace-candidates").querySelectorAll("[data-trace-target]")];
    const at=options.indexOf(document.activeElement);
    if(document.activeElement!==query&&at<0)return;
    event.preventDefault();
    const next=document.activeElement===query?(event.key==="ArrowDown"?0:-1):at+(event.key==="ArrowDown"?1:-1);
    if(next<0)query.focus();
    else options[Math.min(next,options.length-1)]?.focus();
  });
  $("#trace-picker-cancel").addEventListener("click",()=>picker.close());
  $("#trace-picker-apply").addEventListener("click",()=>{
    const {id,field,checked}=linkEdit;
    picker.close();
    updateLink(index.records.get(id),field,[...checked].join("; "));
  });
  $("#trace-candidates").addEventListener("change",event=>{
    const input=event.target.closest("input[data-trace-target]");
    if(!input||!linkEdit?.checked)return;
    if(input.checked)linkEdit.checked.add(input.dataset.traceTarget);
    else linkEdit.checked.delete(input.dataset.traceTarget);
  });
  $("#trace-candidates").addEventListener("click",event=>{
    const targetId=event.target.closest("button[data-trace-target]")?.dataset.traceTarget;
    if(!targetId||!linkEdit)return;
    const {id,field}=linkEdit,record=index.records.get(id),target=index.records.get(targetId);
    const removed=field==="Affects"&&!target&&removedSince(targetId)!==null&&!traceIds(record?.row.Affects).includes(targetId);
    if(!writable()||!record||!(removed||(target&&traceCanLink(record,field,target))))return;
    picker.close();
    const value=traceFields[field].single?targetId:[...traceIds(record.row[field]),targetId].join("; ");
    updateLink(record,field,value);
  });
  $("#trace-editor-cancel").addEventListener("click",()=>editor.close());
  $("#trace-record-form").addEventListener("submit",event=>{
    event.preventDefault();
    if(!writable())return;
    const {type,record,parent}=recordEdit;
    const name=$("#trace-record-name").value.trim(),content=$("#trace-record-content").value.trim();
    const valueField=$("#trace-value-field").value;
    if(type==="Value"&&!valueField){
      $("#trace-value-field").focus();
      return;
    }
    const id=record?.id??(type==="Term"?nextRecordId("TERM-"):type==="Value"?valueRecordId(valueField,name,takenIds())
      :validateNewId($("#trace-record-id").value));
    if(!id)return;
    if((type==="Requirement"||type==="Term"||type==="Value")&&!content){
      $("#trace-record-content").focus();
      return;
    }
    if(type!=="Requirement"&&!name){
      $("#trace-record-name").focus();
      return;
    }
    editor.close();
    if(record?.row.Name===name)return;
    remember();
    if(record)record.row.Name=name;
    else{
      const row={...newRequirement(id),Type:type,Name:name};
      if(type==="System"&&parent)row["Part of"]=parent;
      if(type==="Requirement"){
        row["Derived from"]=parent;
        if(system)row["Allocated to"]=system;
      }
      if(type!=="System")row[{Term:"Definition",Value:"Definition",Source:"Reference"}[type]??"Requirement"]=content;
      if(type==="Test")row["Test plan"]=$("#trace-test-plan").value;
      if(type==="Change request"&&"Change status" in row)row["Change status"]="Proposed";
      if(type==="Value"){
        row.Field=valueField;
        row.Aliases=$("#trace-value-aliases").value.trim();
      }
      if(type==="Term"){
        row.Aliases=$("#trace-term-aliases").value.trim();
        row["Auto Link"]=$("#trace-term-single-word").checked?"Yes":"";
      }
      state.currentRows.push(row);
    }
    updateDirty();
    const destination=viewForType(type);
    if(type==="System")selectedSystem=id;
    if(!switchView(destination,null,type==="Value"?"values":"terms"))render();
    if(view!=="systems"&&!visible(id)){revealed=id;render();}
    focusRecord(id);
    if(panel.hidden&&view==="systems")focusControl(tree,"data-trace-system",id);
  });
  $("#trace-delete-cancel").addEventListener("click",()=>deletion.close());
  $("#trace-delete-form").addEventListener("submit",event=>{
    event.preventDefault();
    if(!writable())return;
    const {id,changes}=deleteEdit;
    const targets=Object.fromEntries(["Part of","Allocated to","Owner"].map((field,i)=>
      [field,$("#trace-delete-group-"+i+" select").value]));
    const updated=changes.map(change=>{
      const {row,field,value}=change,target=targets[field];
      if(!target||!traceFields[field].from.includes(traceType(row)))return change;
      const ids=traceFields[field].single?[target]:[...new Set([...traceIds(value),target])];
      return {...change,value:ids.join("; ")};
    });
    deletion.close();
    deleteRecord(id,updated);
    if(view==="systems")focusControl(tree,"data-trace-system",selectedSystem);
  });

  function followValueRename(row,column,before){
    if(column!=="Name"||traceType(row)!=="Value")return;
    const field=row.Field?.trim(),rule=index.values.get(field),old=before.trim(),name=row.Name.trim();
    if(!rule||!old||!name||old===name||rule.values.get(old)?.row!==row)return;
    const changes=renameValueUses(state.currentRows,field,rule.multiple,old,name);
    if(!changes.length)return;
    const n=changes.length;
    if(!confirm(`Rename “${old}” to “${name}” in ${n} ${n===1?"row that uses":"rows that use"} it?`))return;
    for(const change of changes)change.row[field]=change.value;
  }

  if(historyOn){
    window.addEventListener("popstate",popHistory);
    queueMicrotask(restoreHistory);
  }

  return {recordType:id=>index.records.get(id)?.type,refresh,followValueRename,paintMarkers,valueRule:column=>index.values.get(column),matches,filters,reset,syncSelection,close,clearCopy,columnAvailable,defaultHidden,openDeletion,
    columnLayout:()=>listViews[view]?.layout??null,
    columnRank:name=>view==="glossary"&&glossaryKind==="values"?[...glossaryKinds.values.columns].indexOf(name)
      :listViews[view]?.order?.().indexOf(name)??0,
    linkGlossary:rows=>glossaryPopover.decorate(index.glossary,rows),
    viewKey:()=>[view,glossaryKind,viewMode()].join(":"),
    cellDisplay:(id,column)=>{
      const record=index.records.get(id);
      return record&&listViews[view]?.cells?.[column]?.(record)||null;
    },
    paintStrip,
    revealed:id=>view!=="systems"&&id===revealed,
    scoped:()=>view==="systems"||view==="glossary"||!!listViews[view]||(view==="requirements"&&(!!system||unallocated))||!!revealed,
    rowOrderIds:()=>view==="requirements"?state.currentRows.filter(row=>traceType(row)==="Requirement").map(rowId):null,
    entry:()=>view==="requirements"||view==="all",
    pageView:()=>view==="systems"||view==="gates",
    recordNoun:()=>view==="requirements"?"requirements":view==="all"?"records":view==="changes"?"change requests":"records",
    gridSummary:count=>{
      if(view==="systems")return `${index.systems.length} systems`;
      if(listViews[view])return listViews[view].summary(count);
      if(view==="glossary")return glossaryKinds[glossaryKind].summary(count);
      if(view==="all")return `${count} of ${data.rows.length} records`;
      return `${count} requirements`;
    },
    rowMarker:id=>{
      const record=index.records.get(id);
      if(!record||(!record.incoming.length&&!Object.keys(traceFields).some(field=>traceIds(record.row[field]).length)))return "";
      return '<span class="trace-row-marker" role="img" aria-label="Has links" title="Has links"></span>';
    },
    rename:(oldId,newId)=>{
      if(system===oldId)system=newId;
      if(selectedSystem===oldId)selectedSystem=newId;
      if(collapsed.delete(oldId))collapsed.add(newId);
      if(revealed===oldId)revealed=newId;
      if(recordId===oldId)recordId=newId;
    },
    incomingChanges:(oldId,newId)=>traceIncomingChanges(state.currentRows,oldId,newId),
    isRequirement:row=>traceType(row)==="Requirement",
    allocate:row=>{if(view==="requirements"&&system)row["Allocated to"]=system;},
    reveal:(id,column)=>{
      const destination=recordView(id);
      if(view!=="all"&&(view!==destination||(destination==="glossary"&&glossaryKind!==kindOf(id))))
        switchView(destination==="systems"?"all":destination,null,kindOf(id));
      if(view==="systems"||(column&&!columnAvailable(column)))switchView("all");
      revealed=id;
    },
    panel};
})();
"""

TRACE_MENU = '<button id="open-trace" aria-expanded="false" aria-controls="trace-panel" aria-label="Links and trace findings">Links</button>'

TRACE_WORKSPACE = """
<section id="trace-workspace" aria-label="Traceability workspace">
  <nav id="trace-views" aria-label="Record views">
    <div role="group" aria-label="Define">
      <button type="button" data-trace-view="sources" aria-pressed="false">Needs &amp; sources</button>
      <button type="button" data-trace-view="requirements" aria-pressed="true">Requirements</button>
      <button type="button" data-trace-view="systems" aria-pressed="false">Systems</button>
    </div>
    <div role="group" aria-label="Verify">
      <button type="button" data-trace-view="tests" aria-pressed="false">Tests</button>
      <button type="button" data-trace-view="verification" aria-pressed="false">Verification</button>
      <button type="button" data-trace-view="gates" aria-pressed="false">Gates</button>
      <button type="button" data-trace-view="changes" aria-pressed="false">Change requests</button>
    </div>
    <div role="group" aria-label="Reference">
      <button type="button" data-trace-view="glossary" aria-pressed="false">Glossary</button>
      <button type="button" data-trace-view="all" aria-pressed="false">All fields</button>
    </div>
  </nav>
  <div id="trace-controls">
  <div id="trace-scope">
    <label>System <select id="trace-system"><option>All requirements</option></select></label>
    <label><input type="checkbox" id="trace-descendants" checked> Include subsystems</label>
  </div>
  <button id="trace-view-add" type="button" hidden>Add requirement…</button>
  <span id="trace-glossary-kind" role="group" aria-label="Glossary content" hidden>
    <button type="button" data-glossary-kind="terms" aria-pressed="true">Terms</button>
    <button type="button" data-glossary-kind="values" aria-pressed="false">Values</button>
  </span>
  <span id="trace-view-mode" role="group" aria-label="Layout" hidden>
    <button type="button" data-view-mode="grid" aria-pressed="true">Grid</button>
    <button type="button" data-view-mode="matrix" aria-pressed="false">Matrix</button>
  </span>
  <button id="trace-term-add" type="button" hidden>Add term…</button>
  <button id="trace-value-add" type="button" hidden>Add value…</button>
  <span id="trace-source-actions" hidden>
    <button id="trace-need-add" type="button">Add need…</button>
    <button id="trace-source-add" type="button">Add source…</button>
  </span>
  <span id="trace-test-actions" hidden>
    <button id="trace-test-plan-add" type="button">Add test plan…</button>
    <button id="trace-test-add" type="button">Add test…</button>
  </span>
  <span id="trace-change-actions" hidden>
    <button id="trace-change-add" type="button">Add change request…</button>
  </span>
  <button id="trace-selected-links" type="button" aria-controls="trace-panel" aria-expanded="false" disabled>Links</button>
  </div>
  <p id="trace-status" class="meta" role="status"></p>
  <p id="trace-verification-summary" class="meta" hidden></p>
</section>
"""

TRACE_SYSTEMS = """
<section id="trace-matrix" aria-label="Verification cross-reference matrix" hidden>
  <div class="trace-matrix-actions">
    <button type="button" id="trace-matrix-print">Print…</button>
    <button type="button" id="trace-matrix-csv">Download CSV</button>
  </div>
  <div class="trace-matrix-scroll"><table id="trace-matrix-table"></table></div>
</section>
<section id="trace-gates" aria-label="Gate readiness" hidden>
  <div id="trace-gates-scope"><label>System <select id="trace-gates-system"></select></label></div>
  <div id="trace-gates-list"></div>
</section>
<section id="trace-systems" aria-label="System hierarchy" hidden>
  <div>
    <h2>System hierarchy</h2>
    <button type="button" id="trace-system-add" hidden>Add system…</button>
    <ul id="trace-tree" aria-label="Systems"></ul>
  </div>
  <div id="trace-system-actions" hidden>
    <h2 id="trace-system-name" tabindex="-1"></h2>
    <p class="meta" id="trace-system-parent"></p>
    <div class="trace-actions">
      <button type="button" id="trace-system-requirements">Allocated requirements</button>
      <button type="button" id="trace-system-links" aria-controls="trace-panel">Links</button>
    </div>
    <div class="trace-actions" id="trace-system-edit" hidden>
      <button type="button" id="trace-subsystem-add">Add subsystem…</button>
      <button type="button" id="trace-system-rename">Rename…</button>
      <button type="button" id="trace-system-move">Move to…</button>
      <button type="button" id="trace-system-delete">Delete system…</button>
    </div>
  </div>
</section>
"""

TRACE_HTML = """
<aside id="trace-panel" class="review-panel" hidden aria-labelledby="trace-title">
  <div class="review-head"><h2 id="trace-title" tabindex="-1">Links</h2><button id="close-trace">Close</button></div>
  <div class="review-body">
    <button type="button" id="trace-back" hidden>Back to previous record</button>
    <div id="trace-record"></div>
    <details id="trace-findings"><summary>Trace findings</summary><ul id="trace-issues"></ul></details>
  </div>
</aside>
<dialog id="trace-picker" class="help-dialog" aria-labelledby="trace-picker-title">
  <div class="help-head"><h2 id="trace-picker-title">Choose target</h2><button type="button" id="trace-picker-cancel">Cancel</button></div>
  <div class="help-body"><label for="trace-query">Search by ID, name or text</label>
    <input type="search" id="trace-query" autofocus><ul id="trace-candidates" aria-label="Eligible targets"></ul>
    <button type="button" id="trace-picker-apply" class="primary" hidden>Apply allocations</button>
  </div>
</dialog>
<dialog id="trace-editor" class="help-dialog" aria-labelledby="trace-editor-title">
  <form id="trace-record-form">
    <div class="help-head"><h2 id="trace-editor-title">Add record</h2><button type="button" id="trace-editor-cancel">Cancel</button></div>
    <div class="help-body">
      <label id="trace-value-field-label" hidden>Field <select id="trace-value-field"></select></label>
      <label id="trace-record-id-field">ID <input id="trace-record-id" required></label>
      <label id="trace-record-name-field">Name <input id="trace-record-name"></label>
      <label id="trace-record-content-field"><span id="trace-record-content-label"></span>
        <textarea id="trace-record-content" rows="3"></textarea></label>
      <label id="trace-test-plan-label" hidden>Test plan <select id="trace-test-plan"></select></label>
      <label id="trace-value-aliases-label" hidden>Aliases (separated by semicolons) <input id="trace-value-aliases"></label>
      <div id="trace-term-options" hidden>
        <label>Aliases (separated by semicolons) <input id="trace-term-aliases"></label>
        <label><input type="checkbox" id="trace-term-single-word"> Also link single-word Title Case spellings</label>
      </div>
      <button type="submit" class="primary">Apply</button>
    </div>
  </form>
</dialog>
<dialog id="trace-delete" class="help-dialog" aria-labelledby="trace-delete-title">
  <form id="trace-delete-form">
    <div class="help-head"><h2 id="trace-delete-title">Delete system?</h2><button type="button" id="trace-delete-cancel">Cancel</button></div>
    <div class="help-body">
      <p id="trace-delete-impact"></p>
      <label id="trace-delete-group-0"><span></span><select></select></label>
      <label id="trace-delete-group-1"><span></span><select></select></label>
      <label id="trace-delete-group-2"><span></span><select></select></label>
      <p class="meta" id="trace-delete-other"></p>
      <button type="submit" class="primary">Delete system</button>
    </div>
  </form>
</dialog>
"""

TRACE_CSS = """
#trace-workspace {display:flex;align-items:center;flex-wrap:wrap;gap:6px 12px;padding:5px 12px;background:var(--panel);border-bottom:1px solid var(--line);flex:none}
#trace-views,#trace-scope,#trace-glossary-kind,#trace-view-mode,.trace-actions {display:flex;flex-wrap:wrap;align-items:center;gap:5px}
#trace-views button[aria-pressed="true"],#trace-glossary-kind button[aria-pressed="true"],#trace-view-mode button[aria-pressed="true"],#trace-tree button[aria-pressed="true"] {background:var(--selected);border-color:var(--accent)}
#trace-views [role="group"] {display:flex;flex-wrap:wrap;align-items:center;gap:5px}
#trace-views {gap:5px 12px}
#trace-controls {display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;gap:6px 12px;margin-inline-start:auto}
#trace-views [role="group"]+[role="group"] {padding-inline-start:12px;border-inline-start:1px solid var(--line)}
#trace-system {max-width:min(24ch,60vw)}
#trace-status {flex-basis:100%;margin:0}
#trace-status:empty {display:none}
#trace-systems {display:grid;grid-template-columns:minmax(14rem,1fr) minmax(16rem,1fr);gap:16px;padding:14px 18px;overflow:auto}
#trace-systems h2 {font-size:1.08em;margin:0 0 8px}
#trace-gates {display:grid;gap:14px;align-content:start;padding:14px 18px;overflow:auto}
#trace-gates-list {display:grid;gap:14px}
#trace-gates-system {max-width:min(24ch,60vw)}
.gate {border:1px solid var(--line);border-radius:6px;padding:12px;background:var(--panel)}
.gate header {display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 12px}
.gate h2 {font-size:1.08em;margin:0}
.gate-checks,.gate-table-findings {list-style:none;padding:0;margin:8px 0 0}
.gate-checks>li {padding:6px 0;border-top:1px solid var(--line)}
.gate-table-findings {margin-inline-start:1.5rem}
.gate-badge,.gate-mark {display:inline-block;padding:0 8px;border:1px solid var(--line);border-radius:9px;font-size:.88em;font-weight:600;white-space:nowrap;color:var(--text)}
.gate-pass {background:var(--add);border-color:var(--addStrong)}
.gate-fail {background:var(--remove);border-color:var(--removeStrong)}
.gate-error,.gate-advisory {background:var(--changed)}
#trace-system-actions {align-self:start;border:1px solid var(--line);border-radius:6px;padding:12px;background:var(--panel)}
.trace-actions+.trace-actions {margin-top:8px}
#trace-tree,#trace-record ul,#trace-candidates {list-style:none;padding:0;margin:4px 0 8px}
#trace-tree {display:grid;grid-template-columns:minmax(0,1fr) max-content;gap:4px 6px}
#trace-tree li {display:grid;grid-column:1/-1;grid-template-columns:subgrid;align-items:center}
.trace-tree-node {
  display:flex;align-items:center;gap:6px;min-width:0;
  padding-inline-start:calc(var(--trace-depth,0) * .8rem);
}
#trace-tree [data-trace-system] {flex:1;min-width:0;text-align:start;overflow-wrap:anywhere}
#trace-tree [data-trace-collapse],.trace-tree-leaf {width:26px;flex:none}
#trace-tree .meta {white-space:nowrap;text-align:end;font-variant-numeric:tabular-nums}
#trace-verification-summary {display:flex;flex-wrap:wrap;gap:2px 14px;flex-basis:100%;margin:0}
#trace-verification-summary[hidden] {display:none}
.vcrm-methods {display:inline-flex;gap:3px;vertical-align:middle}
.vcrm-slot {display:inline-grid;place-items:center;width:20px;height:20px;border:1px dashed var(--line);border-radius:4px;color:var(--muted);font-size:.8em;font-weight:700}
.vcrm-slot.on {border:1px solid var(--accent);background:var(--accent);color:var(--panel)}
.vcrm-test {display:block;margin-bottom:3px}
.vcrm-result {display:inline-block;padding:0 6px;border:1px solid var(--line);border-radius:9px;font-size:.85em;background:var(--panel);color:var(--text)}
.vcrm-result-passed {background:var(--add);border-color:var(--addStrong)}
.vcrm-result-failed {background:var(--remove);border-color:var(--removeStrong)}
.vcrm-result-blocked {background:var(--changed)}
.vcrm-result-none {border-style:dashed;color:var(--muted)}
.trace-row-marker {position:absolute;inset-block-start:5px;inset-inline-end:4px;width:5px;height:5px;border-radius:50%;background:var(--accent)}
#trace-panel {width:min(380px,100vw)}
#trace-panel h3 {font-size:1.05em;margin:8px 0 4px}
#trace-record {margin:8px 0;overflow-wrap:anywhere}
#trace-record h4 {font-size:inherit;margin:0}
#trace-record section {border-top:1px solid var(--line);padding:7px 0}
#trace-record p {margin:4px 0}
#trace-record li {margin-bottom:3px}
.trace-link {text-align:start;color:var(--accent);overflow-wrap:anywhere}
.trace-note {white-space:pre-wrap}
.trace-remove {min-width:24px}
.trace-reveal {background:var(--selected);padding:6px;border-radius:4px}
#trace-findings summary {cursor:pointer}
#trace-issues {padding-inline-start:20px;overflow-wrap:anywhere}
#trace-issues li {margin-bottom:6px}
#trace-issues li.trace-finding-active {background:var(--selected);outline:2px solid var(--accent);border-radius:4px;padding:2px 4px}
:root {--trace-finding:#b42318}
@media(prefers-color-scheme:dark) {:root {--trace-finding:#ff9a8f}}
.cell-wrap:has(.trace-marker) {padding-right:24px}
.cell-wrap:has(.quality-marker):has(.trace-marker) {padding-right:46px}
.trace-marker {
  position:absolute; top:-4px; right:0; width:22px; height:24px;
  border:0; padding:0; background:transparent; color:var(--trace-finding); font-weight:700;
}
.quality-marker~.trace-marker {right:22px}
#trace-query {display:block;width:100%}
#trace-picker {width:min(900px,calc(100vw - 24px));max-height:calc(100vh - 80px)}
#trace-candidates button,#trace-candidates label {display:flex;align-items:baseline;gap:12px;width:100%;text-align:start;margin-top:4px}
.trace-candidate-name {flex:none;max-width:60%;overflow-wrap:anywhere}
.trace-candidate-detail {flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted)}
#trace-record-form label,#trace-delete-form label {display:grid;gap:3px;margin-bottom:10px}
#trace-matrix {padding:14px 18px;background:var(--panel)}
.trace-matrix-actions {display:flex;gap:6px;margin-bottom:10px}
.trace-matrix-scroll {overflow:auto}
#trace-matrix-table {table-layout:auto;border-collapse:collapse;min-width:0;width:100%;border:1px solid var(--line)}
#trace-matrix-table caption {position:static;clip:auto;text-align:left;font-weight:700;padding:0 0 6px}
#trace-matrix-table th,#trace-matrix-table td {border:1px solid var(--line);padding:4px 8px}
#trace-matrix-table thead th {position:static;height:auto;text-align:center}
#trace-matrix-table thead th[rowspan] {text-align:left}
#trace-matrix-table tbody th,#trace-matrix-table tfoot th {text-align:left;background:var(--panel);color:var(--text);font-weight:600}
#trace-matrix-table tfoot {font-weight:600;background:var(--bg)}
#trace-matrix-table .vcrm-mark {text-align:center;font-weight:700}
#trace-matrix-table .vcrm-extra {font-weight:400;color:var(--muted);font-size:.85em}
#trace-matrix-table th,#trace-matrix-table td:last-child {overflow-wrap:normal;white-space:nowrap}
#trace-matrix-table .vcrm-mark {width:2.4em;min-width:2.4em;padding-inline:2px}
#trace-matrix-table abbr {text-decoration:none;cursor:help}
#trace-matrix-table .vcrm-nowrap {white-space:nowrap}
.vcrm-legend {display:flex;flex-wrap:wrap;gap:2px 18px;font-weight:400;color:var(--muted);margin-top:3px}
#trace-matrix-table tbody td:nth-child(2) {min-width:12rem;width:100%}
#trace-matrix[hidden],#trace-controls[hidden],#trace-view-mode[hidden],#trace-systems[hidden],#trace-gates[hidden],#trace-scope[hidden],#trace-glossary-kind[hidden],.trace-actions[hidden],#trace-record-form label[hidden],#trace-delete-form label[hidden] {display:none}
@media screen and (min-width:901px) {body:has(#trace-panel:not([hidden])) .page {margin-right:380px}}
@media screen and (max-width:650px) {#trace-systems {grid-template-columns:1fr}}
@page matrix {size:landscape}
@media print {
  body:has(#trace-matrix:not([hidden])) {page:matrix}
  body:has(#trace-matrix:not([hidden])),body:has(#trace-matrix:not([hidden])) .page {background:#fff}
  body:has(#trace-matrix:not([hidden])) .print-details,body:has(#trace-matrix:not([hidden])) .mode-badge,.trace-matrix-actions {display:none}
  body:has(#trace-matrix:not([hidden])) .report-identity h1 {color:#000}
  #trace-matrix {padding:0;background:none}
  .trace-matrix-scroll {overflow:visible}
  #trace-matrix-table {color:#000;width:100%}
  #trace-matrix-table caption,.vcrm-legend {color:#000}
  #trace-matrix-table th,#trace-matrix-table td {border:1px solid #000;font-size:8.5pt;padding:2px 4px}
  #trace-matrix-table thead th,#trace-matrix-table tbody th,#trace-matrix-table tfoot th {background:none;color:#000}
  #trace-matrix-table td:last-child {white-space:normal}
  #trace-matrix-table tbody td:nth-child(2) {min-width:0}
  #trace-matrix-table thead {display:table-header-group}
  #trace-matrix-table tfoot {display:table-row-group}
  #trace-matrix-table tr {break-inside:avoid}
}
@media print {#trace-workspace,#trace-panel,.trace-row-marker,.trace-marker,#trace-system-edit,#trace-system-add,.trace-actions {display:none}}
"""
