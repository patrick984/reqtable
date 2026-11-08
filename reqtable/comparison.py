"""Pure comparison model shared by the report and its Node tests."""

COMPARISON_JS = r"""
function rowStatus(oldRow,newRow,columnNames,ignored,normalize){
  if(!oldRow)return "added";
  if(!newRow)return "removed";
  const changed=columnNames.some(name=>!ignored.has(name)
    &&normalize(String(oldRow[name]??""))!==normalize(String(newRow[name]??"")));
  return changed?"changed":"unchanged";
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
"""
