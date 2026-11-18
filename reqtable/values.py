"""Allowed values for table columns, defined by Value and Field records."""

VALUE_COLUMNS = ("Field", "Multiple")

VALUE_MODEL_JS = r"""
function valueFieldNames(headers,idColumn){
  return {headers:new Set(headers),reserved:new Set([...Object.keys(traceFields),"Type","Field","Multiple",idColumn])};
}
function valueColumnProblem(name,names){
  if(!name)return null;
  if(names.reserved.has(name))return `“${name}” is a reserved column and cannot have defined values.`;
  if(!names.headers.has(name))return `There is no “${name}” column.`;
  return null;
}
function valueGroups(records,key){
  const groups=new Map();
  for(const record of records){
    const name=key(record);
    if(!name)continue;
    const group=groups.get(name)??[];
    group.push(record);
    groups.set(name,group);
  }
  return groups;
}
function buildValueRules(records,headers,idColumn,issue){
  const names=valueFieldNames(headers,idColumn),rules=new Map();
  const all=[...records],fieldRecords=all.filter(record=>record.type==="Field");
  const column=record=>record.row.Field?.trim()??"";
  const target=record=>record.row.Name?.trim()??"";
  for(const [name,group] of valueGroups(fieldRecords,target)){
    const problem=valueColumnProblem(name,names);
    if(problem){
      for(const {id} of group)issue(id,"Name",problem);
      continue;
    }
    if(group.length>1)for(const {id} of group)issue(id,"Name",`Another Field record describes ${name}.`);
    const multiple=group[0].row.Multiple?.trim().toLowerCase()==="yes";
    rules.set(name,{field:group[0],multiple,values:new Map(),aliases:new Map()});
  }
  for(const record of fieldRecords){
    const {id,row}=record,multiple=row.Multiple?.trim()??"";
    if(!target(record))issue(id,"Name","Enter the column this record describes.");
    if(!row.Definition?.trim())issue(id,"Definition","Describe this column.");
    if(multiple&&!/^(?:yes|no)$/i.test(multiple))issue(id,"Multiple","Enter Yes or No.");
  }
  const valueRecords=all.filter(record=>record.type==="Value");
  for(const record of valueRecords){
    const {id,row}=record,name=target(record),field=column(record);
    if(!field)issue(id,"Field","Enter the column this value belongs to.");
    else{
      const problem=valueColumnProblem(field,names);
      if(problem)issue(id,"Field",problem);
    }
    if(!name)issue(id,"Name","Enter the allowed value.");
    if(!row.Definition?.trim())issue(id,"Definition","Explain what this value means.");
  }
  for(const [field,group] of valueGroups(valueRecords,column)){
    if(valueColumnProblem(field,names))continue;
    const rule=rules.get(field)??{field:null,multiple:false,values:new Map(),aliases:new Map()};
    rules.set(field,rule);
    const claims=new Map();
    for(const record of group){
      const name=target(record);
      if(!name)continue;
      const key=name.toLowerCase(),owner=claims.get(key);
      if(owner&&owner!==record){
        issue(record.id,"Name",`Another ${field} value is named “${name}”.`);
        continue;
      }
      claims.set(key,record);
      rule.values.set(name,record);
    }
    for(const record of group){
      if(!target(record))continue;
      for(const alias of traceIds(record.row.Aliases)){
        const key=alias.toLowerCase(),owner=claims.get(key);
        if(owner&&owner!==record){
          issue(record.id,"Aliases",`“${alias}” is already a ${field} value name or alias.`);
          continue;
        }
        if(!owner){
          claims.set(key,record);
          rule.aliases.set(alias,record);
        }
      }
    }
  }
  for(const [field,rule] of rules)if(!rule.values.size)rules.delete(field);
  for(const record of all){
    if(record.type==="Value"||record.type==="Field")continue;
    for(const [field,rule] of rules){
      const cell=record.row[field]?.trim()??"";
      if(!cell)continue;
      const parts=rule.multiple?traceIds(cell):[cell],seen=new Set();
      for(const part of parts){
        const key=part.toLowerCase();
        if(seen.has(key))issue(record.id,field,`“${part}” is listed more than once.`);
        seen.add(key);
        if(rule.values.has(part))continue;
        const replaced=rule.aliases.get(part)??[...rule.aliases].find(([alias])=>alias.toLowerCase()===key)?.[1];
        const canonical=replaced??[...rule.values.values()].find(value=>target(value).toLowerCase()===key);
        if(canonical){
          const spelling=replaced?"a replaced spelling":"spelled differently from the defined value";
          issue(record.id,field,`“${part}” is ${spelling}; use “${target(canonical)}”.`);
        }else{
          issue(record.id,field,`“${part}” is not a defined ${field} value.`
            +(!rule.multiple&&part.includes(";")?` ${field} allows one value.`:""));
        }
      }
    }
  }
  return rules;
}
"""

VALUE_EDIT_JS = r"""
const BOOLEAN_COLUMNS=new Map([["Auto Link","Term"],["Multiple","Field"]]);
function booleanApplies(column,type){return type!==undefined&&BOOLEAN_COLUMNS.get(column)===type;}
function booleanOn(value){return String(value??"").trim().toLowerCase()==="yes";}
function booleanToggle(value){return booleanOn(value)?"":"Yes";}
function observedSuggestions(rows,column){
  const values=new Set();
  for(const row of rows){
    const value=String(row[column]??"").trimEnd();
    if(!value)continue;
    if(value.length>60||value.includes("\n"))return [];
    values.add(value);
    if(values.size>50)return [];
  }
  return [...values].sort((a,b)=>a.localeCompare(b)).map(value=>({value,detail:""}));
}
function suggestionSource(rule,rows,column){
  if(!rule){
    return {items:observedSuggestions(rows,column),defined:false,multiple:false};
  }
  const items=[...rule.values].map(([value,record])=>({value,detail:String(record.row.Definition??"").trim()}));
  return {items,defined:true,multiple:rule.multiple};
}
function valueSegments(text){
  return text.split(";").map(piece=>({text:piece.trim()}));
}
function segmentIndex(text,caret){
  return text.slice(0,caret).split(";").length-1;
}
function matchSuggestions(source,text,caret){
  let query=text,taken=new Set();
  if(source.multiple){
    const segments=valueSegments(text),at=segmentIndex(text,caret);
    query=segments[at].text;
    taken=new Set(segments.filter((_,i)=>i!==at).map(segment=>segment.text.toLocaleLowerCase()).filter(Boolean));
  }
  const needle=query.toLocaleLowerCase();
  const open=source.items.filter(item=>item.value!==query&&!taken.has(item.value.toLocaleLowerCase()));
  const prefix=open.filter(item=>item.value.toLocaleLowerCase().startsWith(needle));
  if(!source.defined)return prefix;
  return [...prefix,...open.filter(item=>!prefix.includes(item)&&item.value.toLocaleLowerCase().includes(needle))];
}
function chooseSuggestion(source,text,caret,value){
  if(!source.multiple)return {text:value,caret:value.length,commit:true};
  const parts=text.split(";").map(part=>part.trim());
  parts[segmentIndex(text,caret)]=value;
  const next=parts.filter(Boolean).join("; ");
  return {text:next,caret:next.length,commit:false};
}
"""

VALUE_RENAME_JS = r"""
function valueSlug(text){
  return text.toUpperCase().replace(/[^A-Z0-9]+/g,"-").replace(/^-+|-+$/g,"");
}
function valueRecordId(field,name,taken){
  const base=`VAL-${valueSlug(field)||"FIELD"}-${valueSlug(name)||"VALUE"}`;
  let id=base;
  for(let n=2;taken.has(id);n++)id=`${base}-${n}`;
  return id;
}
function renameValueUses(rows,column,multiple,oldName,newName){
  const changes=[];
  for(const row of rows){
    const type=String(row.Type??"").trim();
    if(type==="Value"||type==="Field")continue;
    const cell=String(row[column]??"");
    const parts=multiple?cell.split(";").map(part=>part.trim()):[cell.trim()];
    if(!parts.includes(oldName))continue;
    changes.push({row,value:parts.map(part=>part===oldName?newName:part).filter(Boolean).join("; ")});
  }
  return changes;
}
"""

VALUE_EDIT_JS += VALUE_RENAME_JS
