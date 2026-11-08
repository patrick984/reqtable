"""Pure comparison model shared by the report and its Node tests."""

COMPARISON_JS = r"""
function rowStatus(oldRow,newRow,columnNames,ignored,normalize){
  if(!oldRow)return "added";
  if(!newRow)return "removed";
  const changed=columnNames.some(name=>!ignored.has(name)
    &&normalize(String(oldRow[name]??""))!==normalize(String(newRow[name]??"")));
  return changed?"changed":"unchanged";
}
function baselineScopeIds(rows,idColumn,system,includes){
  const cell=(row,column)=>String(row[column]??"").trim(),type=row=>cell(row,"Type")||"Requirement",id=row=>cell(row,idColumn),
    links=(row,column)=>cell(row,column).split(";").map(part=>part.trim()).filter(Boolean),
    included=new Set(includes),candidates=rows.filter(row=>included.has(type(row)));
  if(system===null)return new Set(candidates.map(id));
  const subtree=new Set([system]),systems=rows.filter(row=>type(row)==="System");
  for(let grew=true;grew;){
    grew=false;
    for(const row of systems){
      if(!subtree.has(id(row))&&links(row,"Part of").some(parent=>subtree.has(parent))){subtree.add(id(row));grew=true;}
    }
  }
  const scope=new Set(),add=(kind,test)=>{for(const row of candidates)if(type(row)===kind&&test(row))scope.add(id(row));},
    cited=(kind,column)=>new Set(rows.filter(row=>type(row)===kind&&scope.has(id(row))).flatMap(row=>links(row,column)));
  add("System",row=>subtree.has(id(row)));
  add("Requirement",row=>links(row,"Allocated to").some(target=>subtree.has(target)));
  const tests=cited("Requirement","Verified by");
  add("Test",row=>tests.has(id(row)));
  const plans=cited("Test","Test plan"),gated=new Set(["System","Requirement","Test","Test plan"]);
  add("Test plan",row=>plans.has(id(row)));
  return new Set(candidates.filter(row=>scope.has(id(row))||!gated.has(type(row))).map(id));
}
function baselineSource(baseline,currentRows,idColumn,ignoredColumns){
  const scope=baselineScopeIds(currentRows,idColumn,baseline.system,baseline.includes),
    ignored=new Set(ignoredColumns);
  if(!baseline.capturesStatus)for(const column of baseline.statusColumns)ignored.add(column);
  return{kind:"baseline",label:baseline.name,rows:baseline.rows,inScope:row=>scope.has(String(row[idColumn]??"").trim()),
    ignoredColumns:ignored,moves:false};
}
function comparisonPairs(currentRows,source,idColumn){
  const identify=row=>String(row[idColumn]??"").trim(),oldMap=new Map((source?.rows??[]).map(row=>[identify(row),row])),
    newMap=new Map(currentRows.map(row=>[identify(row),row])),ids=currentRows.map(identify);
  if(source){
    let following=null;
    for(let index=source.rows.length-1;index>=0;index--){
      const id=identify(source.rows[index]);
      if(!newMap.has(id)){
        if(following===null)ids.push(id);
        else ids.splice(ids.indexOf(following),0,id);
      }
      following=id;
    }
  }
  return ids.map(id=>{
    const newRow=newMap.get(id);
    return{id,newRow,oldRow:newRow&&source&&!source.inScope(newRow)?newRow:oldMap.get(id)};
  });
}
function comparisonStatuses(currentRows,source,idColumn,columnNames,normalize){
  return Object.fromEntries(comparisonPairs(currentRows,source,idColumn).map(({id,oldRow,newRow})=>
    [id,source?rowStatus(oldRow,newRow,columnNames,source.ignoredColumns,normalize):"unchanged"]));
}
"""
