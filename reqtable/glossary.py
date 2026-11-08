"""Project glossary matching and inline definitions for traceability reports."""

GLOSSARY_COLUMNS = ("Definition", "Aliases", "Auto Link")

GLOSSARY_MODEL_JS = r"""
function glossaryEligible(spelling,allowSingle){
  const words=spelling.split(/[\s-]+/u);
  const acronym=/^[\p{Lu}0-9]+(?:-[\p{Lu}0-9]+)*$/u.test(spelling)
    &&(spelling.match(/\p{Lu}/gu)?.length??0)>=2;
  if(acronym)return true;
  const titleWord=/^\p{Lu}[\p{L}\p{M}\p{N}'’]*$/u;
  const connector=/^(?:a|an|and|for|in|of|on|or|the|to|with)$/u;
  if(words.length===1)return allowSingle&&titleWord.test(spelling);
  return titleWord.test(words[0])&&titleWord.test(words.at(-1))
    &&words.slice(1,-1).every(word=>titleWord.test(word)||connector.test(word));
}
function buildGlossary(records,issue){
  const names=new Map(),spellings=new Map();
  for(const record of records){
    if(record.type!=="Term")continue;
    const {id,row}=record,name=row.Name?.trim()??"",definition=row.Definition?.trim()??"";
    if(!name)issue(id,"Name","Enter a glossary term name.");
    if(!definition)issue(id,"Definition","Enter a glossary definition.");
    if(name){
      const key=name.toLowerCase(),group=names.get(key)??[];
      group.push(record);
      names.set(key,group);
    }
    const allowSingle=row["Auto Link"]?.trim().toLowerCase()==="yes";
    for(const [spelling,field] of [[name,"Name"],...traceIds(row.Aliases).map(alias=>[alias,"Aliases"])]){
      if(!spelling)continue;
      const group=spellings.get(spelling)??new Map();
      if(!group.has(id))group.set(id,{record,field,eligible:glossaryEligible(spelling,allowSingle)});
      spellings.set(spelling,group);
    }
  }
  const ambiguousNames=new Set();
  for(const group of names.values()){
    if(group.length<2)continue;
    for(const {id,row} of group){
      issue(id,"Name","Another glossary record uses this term name.");
      ambiguousNames.add(row.Name.trim());
    }
  }
  const lookup=new Map();
  for(const [spelling,group] of spellings){
    const entries=[...group.values()];
    if(entries.length>1){
      for(const {record,field} of entries){
        if(field!=="Name"||!ambiguousNames.has(spelling)){
          issue(record.id,field,`Glossary spelling “${spelling}” is shared by multiple terms.`);
        }
      }
    }
    if(!entries.some(entry=>entry.eligible))continue;
    const {record}=entries[0];
    lookup.set(spelling,group.size===1&&!ambiguousNames.has(spelling)
      &&record.row.Name?.trim()&&record.row.Definition?.trim()?record:null);
  }
  const patterns=[...lookup.keys()].sort((a,b)=>b.length-a.length)
    .map(spelling=>spelling.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
  const address=String.raw`(?:[a-zA-Z][a-zA-Z\d+.-]*://|www\.|mailto:)[^\s<>]+|[\p{L}\p{N}._%+-]+@[\p{L}\p{N}.-]+\.[\p{L}]{2,}`;
  const word=String.raw`[\p{L}\p{M}\p{N}_]`;
  const pattern=patterns.length&&new RegExp(
    `(?:${address})|(?<!${word})(${patterns.join("|")})(?!${word})`,"gu");
  return {enabled:Boolean(pattern),matches(text){
    if(!pattern)return [];
    return [...text.matchAll(pattern)].flatMap(match=>{
      const record=lookup.get(match[1]);
      return record?[{record,start:match.index,text:match[0]}]:[];
    });
  }};
}
"""

GLOSSARY_UI_JS = r"""
function createGlossaryPopover(jump){
  const popup=$("#glossary-definition"),title=$("#glossary-definition-title");
  const content=$("#glossary-definition-content"),sources=$("#glossary-definition-sources");
  let anchor=null;
  function close(restoreFocus=false){
    if(!anchor)return;
    popup.hidden=true;
    content.replaceChildren();
    sources.replaceChildren();
    anchor.setAttribute("aria-expanded","false");
    if(restoreFocus)anchor.focus({preventScroll:true});
    anchor=null;
  }
  function open(button,record){
    if(anchor===button){close(true);return;}
    close();
    anchor=button;
    anchor.setAttribute("aria-expanded","true");
    title.textContent=record.row.Name.trim();
    content.innerHTML=renderCommentMarkdown(record.row.Definition.trim());
    const references=record.outgoing.get("Source refs")??[];
    const jumpButton=(id,text)=>{
      const button=document.createElement("button");
      button.type="button";
      button.className="glossary-jump";
      button.textContent=text;
      button.addEventListener("click",()=>{close();jump(id);});
      return button;
    };
    if(references.length){
      sources.append("Sources: ");
      references.forEach(({row,id},i)=>sources.append(...(i?[", "]:[]),jumpButton(id,row.Name?.trim()||id)));
      sources.append(document.createElement("br"));
    }
    sources.append(jumpButton(record.id,"Show in glossary"));
    positionPopover(popup,button);
    title.focus({preventScroll:true});
  }
  $("#glossary-definition-close").addEventListener("click",()=>close(true));
  document.addEventListener("click",event=>{
    if(anchor&&!popup.contains(event.target)&&!event.target.closest(".glossary-link"))close();
  });
  document.addEventListener("keydown",event=>{
    if(event.key!=="Escape"||!anchor)return;
    event.preventDefault();
    event.stopImmediatePropagation();
    close(true);
  },true);
  $(".table-wrap").addEventListener("scroll",()=>close());
  window.addEventListener("resize",()=>close());
  return {close,decorate(glossary){
    if(!glossary.enabled)return;
    const columns=["Requirement","Acceptance Criteria","Rationale"];
    for(const cell of tableBody.querySelectorAll("[data-grid-cell]")){
      if(!columns.includes(cell.dataset.column))continue;
      const wrapper=cell.querySelector(".cell-wrap");
      if(!wrapper)continue;
      const walker=document.createTreeWalker(wrapper,NodeFilter.SHOW_TEXT,{acceptNode(node){
        return node.parentElement.closest("a,code,pre,button,.empty-value,.missing,.pane-label")
          ?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT;
      }});
      const nodes=[];
      while(walker.nextNode())nodes.push(walker.currentNode);
      for(const node of nodes){
        const matches=glossary.matches(node.data);
        if(!matches.length)continue;
        const fragment=document.createDocumentFragment();
        let end=0;
        for(const {record,start,text} of matches){
          fragment.append(node.data.slice(end,start));
          const button=document.createElement("button");
          button.type="button";
          button.className="glossary-link";
          button.textContent=text;
          button.setAttribute("aria-haspopup","dialog");
          button.setAttribute("aria-controls",popup.id);
          button.setAttribute("aria-expanded","false");
          button.addEventListener("click",()=>open(button,record));
          fragment.append(button);
          end=start+text.length;
        }
        fragment.append(node.data.slice(end));
        node.replaceWith(fragment);
      }
    }
  }};
}
"""

GLOSSARY_HTML = """
<section id="glossary-definition" class="floating-popover" role="dialog" aria-labelledby="glossary-definition-title" hidden>
  <div class="glossary-definition-head">
    <h3 id="glossary-definition-title" tabindex="-1"></h3>
    <button type="button" id="glossary-definition-close" aria-label="Close definition">×</button>
  </div>
  <div class="markdown" id="glossary-definition-content"></div>
  <p id="glossary-definition-sources" class="meta"></p>
</section>
"""

GLOSSARY_CSS = """
.glossary-link {max-width:100%;padding:0;border:0;border-radius:2px;background:transparent;color:inherit;text-align:inherit;overflow-wrap:anywhere;text-decoration:underline dotted var(--accent);text-underline-offset:.19em}
.glossary-link:hover,.glossary-link[aria-expanded="true"] {color:var(--accent)}
.glossary-definition-head {display:flex;align-items:start;justify-content:space-between;gap:8px;margin-bottom:6px}
.glossary-definition-head h3 {margin:0}
#glossary-definition-close {padding:0 6px;line-height:1.2}
#glossary-definition-sources {margin:8px 0 0}
.glossary-jump {display:inline;width:auto;height:auto;padding:0;border:0;background:none;color:var(--accent);font:inherit;text-decoration:underline;cursor:pointer}
#glossary-definition-sources:empty {display:none}
@media print {.glossary-link {text-decoration:none}}
"""
