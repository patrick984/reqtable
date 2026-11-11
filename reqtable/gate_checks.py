"""Gate readiness check evaluator shared by the report and its Node tests."""

GATE_CHECKS_JS = r"""
const gateFindingIds=new WeakMap();
const gateConditions={
  filled:{columns:spec=>[spec],passes:(row,spec,context)=>context.cell(row,spec)!==""},
  in:{columns:spec=>Object.keys(spec),passes:(row,spec,context)=>Object.entries(spec).every(([column,allowed])=>{
    const parts=context.parts(context.cell(row,column));
    return parts.length>0&&parts.every(part=>allowed.includes(part));
  })},
  linked:{columns:spec=>[spec],passes:(row,spec,context,check)=>context.parts(context.cell(row,spec)).some(target=>
    check.leaf?context.leaves.has(target):context.records.has(target))},
  no_findings:{columns:()=>[],passes:(row,spec,context)=>!context.findingIds.has(context.id(row))},
  unchanged_since:{columns:()=>[]},
};
const changeFindingMessage=/^(?:Changed|Added|Removed) since .+ without an approved change request\.$/;
function gateCondition(check){
  const name=Object.keys(gateConditions).find(key=>key in check);
  return name?{name,spec:check[name]}:null;
}
function gateAppliesTo(check,context){
  const spec=check.applies_to??(check.no_findings||check.unchanged_since?{}:{type:"Requirement"});
  const accepted=value=>[].concat(value);
  return {
    columns:Object.keys(spec).filter(key=>key!=="type"),
    matches:row=>Object.entries(spec).every(([key,value])=>
      accepted(value).includes(key==="type"?context.cell(row,"Type")||"Requirement":context.cell(row,key))),
  };
}
function evaluateGateCheck(check,rows,idColumn,headers,system,findings,controls=null){
  const cell=(row,column)=>String(row[column]??"").trim(),parts=text=>text.split(";").map(part=>part.trim()).filter(Boolean);
  const id=row=>cell(row,idColumn);
  const base={id:check.id,description:check.description};
  const condition=gateCondition(check);
  if(!condition)return {...base,error:"The check has no condition."};
  const context={cell,parts,id};
  const applies=gateAppliesTo(check,context);
  const missing=[...applies.columns,...gateConditions[condition.name].columns(condition.spec)].find(column=>!headers.includes(column));
  if(missing!==undefined)return {...base,error:`The table has no “${missing}” column.`};
  const systems=rows.filter(row=>(cell(row,"Type")||"Requirement")==="System");
  const parents=new Set(systems.flatMap(row=>parts(cell(row,"Part of"))));
  context.records=new Set(rows.map(id));
  context.leaves=new Set(systems.map(id).filter(systemId=>!parents.has(systemId)));
  if(!gateFindingIds.has(findings))gateFindingIds.set(findings,new Set(findings.filter(finding=>finding.id!=null).map(finding=>finding.id)));
  context.findingIds=gateFindingIds.get(findings);
  let scoped=rows;
  if(system){
    const types=[...new Set(rows.map(row=>cell(row,"Type")||"Requirement"))],scope=baselineScopeIds(rows,idColumn,system,types);
    scoped=rows.filter(row=>scope.has(id(row)));
  }
  const applicable=scoped.filter(applies.matches),{passes}=gateConditions[condition.name];
  if(condition.name==="unchanged_since"){
    let removed=Object.keys(controls?.records??{}).filter(removedId=>!context.records.has(removedId));
    if(system&&removed.length){
      const all=[...rows,...removed.map(removedId=>controls.records[removedId].row)];
      const scope=baselineScopeIds(all,idColumn,system,[...new Set(all.map(row=>cell(row,"Type")||"Requirement"))]);
      removed=removed.filter(removedId=>scope.has(removedId));
    }
    const counted=new Set([...applicable.map(id),...removed]);
    const changed=[...new Set(findings.filter(finding=>changeFindingMessage.test(finding.message)).map(finding=>finding.id))];
    return {...base,total:applicable.length+removed.length,failing:changed.filter(changedId=>counted.has(changedId)),global:[],error:null};
  }
  const failing=applicable.filter(row=>!passes(row,condition.spec,context,check)).map(id),messages=[];
  if(condition.name==="no_findings")messages.push(...findings.filter(finding=>finding.id==null).map(finding=>finding.message));
  return {...base,total:applicable.length+(messages.length?1:0),failing:messages.length?[...failing,""]:failing,global:messages,error:null};
}
function gateCheckFailed(result){
  return !!result.error||result.failing.length>0;
}
function gateCheckBlocks(result){
  return result.enforcement==="strict"&&gateCheckFailed(result);
}
function gateCheckLabel(result){
  const level=result.enforcement==="strict"?"blocking":"advisory";
  if(result.error)return {tone:"gate-error",mark:result.enforcement==="strict"?"! Error · blocking":"! Error"};
  if(!gateCheckFailed(result))return {tone:"gate-pass",mark:"✓ Pass"};
  return {tone:level==="blocking"?"gate-fail":"gate-advisory",mark:`✗ Fail · ${level}`};
}
function gateBadgeLabel(results){
  if(results.some(gateCheckBlocks))return {tone:"gate-fail",mark:"✗ Blocked"};
  if(results.some(gateCheckFailed))return {tone:"gate-advisory",mark:"✗ Not ready"};
  return {tone:"gate-pass",mark:"✓ Ready"};
}
"""
