from __future__ import annotations

import html
import json
from typing import Any


CSS = r"""
:root{color-scheme:light dark;--bg:#f7f8fa;--panel:#fff;--text:#202124;--muted:#5f6368;--placeholder:#9aa0a6;--line:#d9dde3;--head:#2f3542;--headText:#fff;--accent:#0969da;--comment:#cf222e;--selected:#dbeafe;--add:#dafbe1;--addStrong:#aceebb;--remove:#ffebe9;--removeStrong:#ffcecb;--changed:#fff8c5;--shadow:0 4px 18px #0002}
@media(prefers-color-scheme:dark){:root{--bg:#16181d;--panel:#22252b;--text:#e6e8eb;--muted:#a8adb7;--placeholder:#7d8590;--line:#454a53;--head:#303640;--headText:#fff;--accent:#6da9ff;--comment:#ff7b72;--selected:#263b5c;--add:#173c25;--addStrong:#285c38;--remove:#4a2022;--removeStrong:#6b3033;--changed:#453f18;--shadow:0 5px 22px #0008}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,input,select,textarea{font:inherit;color:var(--text);background:var(--panel)}button{cursor:pointer}.page{padding:14px 18px}.report-header{display:flex;gap:16px;justify-content:space-between;align-items:flex-start;margin-bottom:8px}.report-header h1{margin:0 0 2px;font-size:1.55rem}.meta{color:var(--muted)}.summary{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px}.summary:empty{display:none}.badge{border:1px solid var(--line);border-radius:99px;padding:2px 8px;background:var(--panel)}.badge.added{background:var(--add)}.badge.removed{background:var(--remove)}.badge.changed{background:var(--changed)}.save-area{display:flex;gap:7px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.save-area input{width:8rem}.dirty{font-weight:700;color:#b54708}.dirty[hidden]{display:none}.toolbar{position:sticky;top:0;z-index:10;display:flex;gap:3px;align-items:center;flex-wrap:wrap;padding:2px 5px;border:1px solid var(--line);border-radius:7px 7px 0 0;background:var(--panel);box-shadow:0 1px 4px #0001}.toolbar .spacer{flex:1}.control,button,input,select,textarea{border:1px solid var(--line);border-radius:5px;padding:5px 8px}button:hover{border-color:var(--accent)}button[aria-pressed="true"]{background:var(--selected);border-color:var(--accent)}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,[data-grid-cell]:focus-visible{outline:3px solid color-mix(in srgb,var(--accent),transparent 55%);outline-offset:-1px}.primary{background:var(--accent);color:#fff;border-color:var(--accent)}details{position:relative}details>summary{list-style:none;cursor:pointer;border:1px solid var(--line);border-radius:5px;padding:5px 8px}.popover{position:absolute;top:calc(100% + 5px);left:0;z-index:30;min-width:230px;max-height:360px;overflow:auto;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:10px;box-shadow:var(--shadow)}.popover label:not([hidden]){display:block;padding:4px}.table-wrap{overflow:auto;max-height:calc(100vh - 145px);border:1px solid var(--line);border-top:0;background:var(--panel)}table{border-collapse:separate;border-spacing:0;table-layout:fixed;min-width:100%}caption{position:absolute;clip:rect(0 0 0 0)}th,td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:8px 10px;vertical-align:top;min-width:0;white-space:normal;overflow-wrap:anywhere}thead th{position:sticky;top:0;z-index:5;background:var(--head);color:var(--headText);text-align:left;height:37px}.heading-cell{position:sticky;padding-right:10px}.filter-row th{top:37px;height:29px;padding:2px 4px;background:var(--panel);color:var(--text)}.filter-control{position:relative}.filter-row input{display:block;width:100%;height:24px;min-width:0;padding:2px 27px 2px 6px;color:var(--text);background:var(--panel);caret-color:var(--text)}.filter-row input::placeholder{color:var(--placeholder);opacity:1}.clear-filter{position:absolute;right:1px;top:50%;transform:translateY(-50%);width:21px;height:21px;padding:0;border:0;background:transparent;color:var(--muted);font-weight:700}.clear-filter[hidden]{display:none}.sort-button{background:transparent;border:0;color:inherit;font-weight:700;padding:0;width:calc(100% - 7px);height:100%;text-align:left}.resize-handle{position:absolute;top:0;right:-4px;width:9px;height:100%;z-index:8;cursor:col-resize;touch-action:none}.resize-handle::after{content:"";position:absolute;right:3px;top:5px;bottom:5px;width:1px;background:#fff6}.resize-handle:hover::after,.resize-handle.dragging::after{width:3px;background:var(--accent)}.status-cell{position:sticky;left:0;z-index:2;background:var(--panel)}.row-added .status-cell{border-left:5px solid #1a7f37}.row-removed .status-cell{border-left:5px solid #cf222e}.row-changed .status-cell{border-left:5px solid #bf8700}[data-grid-cell].selected-cell{background:var(--selected)!important;box-shadow:inset 0 0 0 2px var(--accent)}.cell-wrap{position:relative;padding-right:24px;min-height:24px}.comment-button{position:absolute;right:-4px;top:-4px;width:24px;height:24px;padding:1px;border:0;background:transparent;color:var(--accent);font-weight:700}.comment-button:not(.has-comments){opacity:0;pointer-events:none}.selected-cell .comment-button:not(.has-comments),[data-grid-cell]:hover .comment-button:not(.has-comments){opacity:1;pointer-events:auto}.comment-button.has-comments{color:var(--comment);border:1px solid var(--comment);border-radius:99px;background:var(--panel)}.markdown p{margin:0 0 .65em}.markdown p:last-child{margin-bottom:0}.markdown ul,.markdown ol{margin:.3em 0;padding-left:1.5em}.markdown pre{white-space:pre-wrap;background:#8882;padding:7px;border-radius:4px}.markdown blockquote{border-left:3px solid var(--line);margin:.4em 0;padding-left:8px;color:var(--muted)}.empty-value{color:var(--muted);font-style:italic}.diff-line{white-space:pre-wrap;min-height:1.35em;margin:0 -4px;padding:1px 4px}.removed-line{background:var(--remove)}.added-line{background:var(--add)}.removed-word{background:var(--removeStrong);text-decoration:line-through}.added-word{background:var(--addStrong)}.split{display:grid;grid-template-columns:minmax(12rem,1fr) minmax(12rem,1fr);gap:4px}.pane{min-width:0;border:1px solid var(--line);border-radius:4px;overflow:hidden}.pane-label{display:block;padding:2px 5px;background:#8882;color:var(--muted);font-size:.78rem;font-weight:700}.missing{padding:5px;color:var(--muted);font-style:italic}.review-panel{position:fixed;right:0;top:0;bottom:0;z-index:50;width:min(400px,100vw);min-width:min(300px,100vw);max-width:90vw;background:var(--panel);border-left:1px solid var(--line);box-shadow:var(--shadow);display:flex;flex-direction:column}.review-panel[hidden]{display:none}.sidebar-resize{position:absolute;left:-5px;top:0;bottom:0;width:10px;cursor:col-resize;touch-action:none}.sidebar-resize:hover,.sidebar-resize.dragging{background:color-mix(in srgb,var(--accent),transparent 75%)}.review-head{display:flex;align-items:center;gap:8px;padding:12px;border-bottom:1px solid var(--line)}.review-head h2{font-size:1.1rem;margin:0;flex:1}.review-body{padding:12px;overflow:auto;flex:1}.comment-search{width:100%;margin-bottom:10px}.comment-card{border:1px solid var(--line);border-left:5px solid var(--reviewer-color,var(--line));border-radius:6px;padding:10px;margin-bottom:9px}.reviewer-chip{display:inline-block;border:1px solid var(--reviewer-color,var(--line));border-radius:99px;padding:0 5px;color:var(--text)}.comment-meta{color:var(--muted);font-size:.82rem;margin-bottom:6px}.comment-actions{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}.comment-editor textarea,.inline-comment-editor textarea{width:100%;min-height:100px;margin:7px 0;resize:vertical}.comment-editor-actions{display:flex;gap:7px}.floating-popover{position:fixed;z-index:70;width:min(380px,calc(100vw - 20px));max-height:min(520px,calc(100vh - 20px));overflow:auto;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:7px;padding:11px;box-shadow:var(--shadow)}.floating-popover[hidden]{display:none}.floating-popover h3{margin:0 0 7px;font-size:1rem}.floating-popover textarea{width:100%;min-height:90px;resize:vertical;margin:6px 0}.quick-previous{margin-bottom:9px}.quick-previous .comment-card{margin:5px 0}.comment-tooltip{pointer-events:none;max-width:360px}.comment-tooltip .comment-card{margin:6px 0 0}.value-filter{width:min(300px,calc(100vw - 20px));max-height:300px}.value-filter label{display:block;padding:4px}.value-filter .meta{margin-bottom:5px}.help-dialog{width:min(650px,calc(100vw - 24px));max-height:calc(100vh - 24px);background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);padding:0}.help-dialog::backdrop{background:#0008}.help-head{display:flex;align-items:center;padding:14px;border-bottom:1px solid var(--line)}.help-head h2{margin:0;flex:1;font-size:1.2rem}.help-body{padding:14px;overflow:auto}.shortcut-table{width:100%;border-collapse:collapse}.shortcut-table th,.shortcut-table td{min-width:0;padding:6px;border:0;border-bottom:1px solid var(--line)}kbd{border:1px solid var(--line);border-bottom-width:2px;border-radius:4px;padding:1px 5px;background:var(--bg)}.notice{padding:9px;border-radius:5px;background:var(--changed);margin-bottom:10px}.empty-state{color:var(--muted);padding:20px 0}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:700px){.page{padding:7px}.report-header{display:block}.save-area{justify-content:flex-start;margin-top:7px}.split{grid-template-columns:1fr}.table-wrap{max-height:none}.toolbar{position:static}.review-panel{max-width:100vw}}@media print{.toolbar,.save-area,.comment-button,.review-panel,.floating-popover,.help-dialog{display:none!important}.page{padding:0}.table-wrap{max-height:none;overflow:visible;border:0}thead th,.status-cell{position:static}table{width:100%!important;table-layout:auto}th,td{font-size:9pt}}
.mode-badge{font-weight:700}.mode-badge.develop{color:#1a7f37;border-color:#1a7f37}.mode-badge.review{color:var(--comment);border-color:var(--comment)}.cell-editor{display:grid;gap:6px}.cell-editor textarea{width:100%;min-height:92px;resize:vertical}.cell-editor-actions{display:flex;gap:6px}.cell-suggestions{display:grid;gap:2px;max-height:9rem;overflow:auto}.cell-suggestions[hidden]{display:none}.cell-suggestions button{text-align:left;overflow-wrap:anywhere}.edited-cell{position:relative}.edited-cell::before{content:"";position:absolute;left:-6px;inset-block:0;width:3px;background:#bf8700;pointer-events:none}.cell-editor-actions button{padding:0 6px;line-height:1.35;font-weight:bold}.apply-edit{color:#187439}.cancel-edit{color:#a62327}
.recovery-notice{margin:0 0 6px;padding:5px 9px;background:#fff4c2;color:#453500;border:1px solid #d9bf63;border-radius:6px}.recovery-notice button{margin-inline-start:8px}
.toolbar .popup-menu>summary,.toolbar>button{padding:2px 7px}
.toolbar .popup-menu>summary{border-color:transparent}
#command-query{width:100%}
#command-results{display:grid;gap:2px;max-height:45vh;overflow:auto;margin-top:8px}
#command-results button{display:flex;justify-content:space-between;gap:12px;text-align:left}
#command-results small{color:var(--muted)}
#command-results kbd{white-space:nowrap;font:inherit;font-size:.85em}
.toolbar .popup-menu>summary:hover,.toolbar .popup-menu[open]>summary{background:var(--selected)}
.toolbar .popover{top:100%;padding:5px 0;min-width:200px;max-width:calc(100vw - 20px)}
.toolbar .popover button:not([hidden]){display:flex;align-items:center;justify-content:space-between;gap:18px;width:100%;padding:6px 12px;text-align:left;border:0;border-radius:0;background:transparent}
.toolbar .popover button:enabled:hover,.toolbar .popover button:focus-visible,.toolbar .popover label:focus-within,.toolbar .popover label:hover{background:var(--selected)}
.toolbar .popover button[aria-pressed="true"]{font-weight:700}
.toolbar .popover button:disabled{opacity:.55;cursor:default}
.toolbar .popover label:not([hidden]){padding:5px 12px;cursor:pointer}
.toolbar .popover kbd{font:inherit;font-size:.8em;color:var(--muted);white-space:nowrap;border:0;padding:0}
.toolbar .popover .menu-section{border-top:1px solid var(--line);margin-top:4px;padding-top:4px}
.toolbar .popover #hidden-filter-warning:not(:empty){padding:5px 12px}
.order-change{display:block}.entry-row{color:var(--muted)}.entry-add{padding:0 6px;line-height:1.4}.entry-hint{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
"""


JS = r"""
"use strict";
const data=JSON.parse(document.getElementById("reqtable-data").textContent);
function configuredPixels(column){const raw=column.width;if(!raw)return column.estimatedWidth||160;const n=parseFloat(raw);if(raw.endsWith("rem")||raw.endsWith("em"))return n*16;if(raw.endsWith("ch"))return n*8;if(raw.endsWith("%"))return Math.max(70,document.documentElement.clientWidth*n/100);return n;}
const cloneValue=value=>JSON.parse(JSON.stringify(value));
const state={hidden:new Set(data.columns.filter(c=>c.hidden).map(c=>c.name)),filters:new Map(),valueFilters:new Map(),statuses:new Set(["added","removed","changed","unchanged"]),commentsOnly:false,view:data.options.initialView,sort:null,comments:cloneValue(data.comments),savedComments:cloneValue(data.comments),currentRows:cloneValue(data.source.new.rows),savedRows:cloneValue(data.source.new.rows),dirty:false,requirementsDirty:false,commentsDirty:false,unsavedDiff:false,undo:[],redo:[],editingCell:null,commentContext:null,editingId:null,widths:new Map(data.columns.map(c=>[c.name,configuredPixels(c)])),focus:{row:0,column:0}};
if(data.meta.mode==="diff"&&data.options.initialChangesOnly)state.statuses.delete("unchanged");
const $=s=>document.querySelector(s),table=$("#requirements-table"),tableBody=$("#requirements-body"),headRow=$("#heading-row"),filterRow=$("#filter-row"),resultCount=$("#result-count"),quick=$("#quick-comment"),hover=$("#comment-hover"),valuePopover=$("#value-filter-popover"),review=$("#review-panel"),help=$("#keyboard-help");
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function commentInline(text){
  const pattern=/`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\n]+)\)|\*\*([^*\n]+)\*\*|__([^_\n]+)__|(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)/g;
  let result="",end=0;
  for(const match of text.matchAll(pattern)){
    const [source,code,label,target,strong,underline,em,italic]=match;
    result+=escapeHtml(text.slice(end,match.index));
    if(code!==undefined)result+=`<code>${escapeHtml(code)}</code>`;
    else if(label!==undefined){
      const url=target.trim();
      result+=/^(?:https?:\/\/|mailto:)/i.test(url)?`<a href="${escapeHtml(url)}">${escapeHtml(label)}</a>`:`${escapeHtml(label)} (${escapeHtml(url)})`;
    }else if(strong!==undefined||underline!==undefined)result+=`<strong>${escapeHtml(strong??underline)}</strong>`;
    else result+=`<em>${escapeHtml(em??italic)}</em>`;
    end=match.index+source.length;
  }
  return result+escapeHtml(text.slice(end));
}
function renderCommentMarkdown(s){const lines=String(s).split("\n"),out=[];let para=[],list=null,quote=[],code=null;const flushPara=()=>{if(para.length){out.push(`<p>${para.map(commentInline).join("<br>")}</p>`);para=[];}},closeList=()=>{if(list){out.push(`</${list}>`);list=null;}},flushQuote=()=>{if(quote.length){out.push(`<blockquote>${quote.map(commentInline).join("<br>")}</blockquote>`);quote=[];}};for(const line of lines){if(code){if(line.startsWith("```")){out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);code=null;}else code.push(line);continue;}if(line.startsWith("```")){flushPara();closeList();flushQuote();code=[];continue;}const h=line.match(/^(#{1,6})\s+(.+)$/);if(h){flushPara();closeList();flushQuote();const level=Math.min(6,h[1].length+2);out.push(`<h${level}>${commentInline(h[2])}</h${level}>`);continue;}const item=line.match(/^\s*[-+*]\s+(.+)$/),ordered=line.match(/^\s*\d+[.)]\s+(.+)$/);if(item||ordered){flushPara();flushQuote();const wanted=item?"ul":"ol";if(list!==wanted){closeList();out.push(`<${wanted}>`);list=wanted;}out.push(`<li>${commentInline((item||ordered)[1])}</li>`);continue;}if(line.startsWith(">")){flushPara();closeList();quote.push(line.slice(1).trimStart());continue;}if(!line.trim()){flushPara();closeList();flushQuote();}else{closeList();flushQuote();para.push(line);}}if(code)out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);flushPara();closeList();flushQuote();return out.join("");}
function localTimestamp(){const d=new Date(),off=-d.getTimezoneOffset(),sign=off>=0?"+":"-",pad=n=>String(Math.abs(n)).padStart(2,"0");return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${sign}${pad(Math.trunc(Math.abs(off)/60))}:${pad(Math.abs(off)%60)}`;}
function displayTimestamp(value){const d=new Date(value);if(Number.isNaN(d.getTime()))return value;const pad=n=>String(n).padStart(2,"0");return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;}
function filenameTimestamp(){const d=new Date(),pad=n=>String(n).padStart(2,"0");return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;}
function reviewerColor(initials){let hash=0;for(const ch of initials.toLocaleUpperCase())hash=(hash*31+ch.codePointAt(0))>>>0;return `hsl(${hash%360} 68% 48%)`;}
function visibleColumns(){return data.columns.filter(c=>!state.hidden.has(c.name));}function valueFor(row,col){const cell=row.cells[col];return(cell.new===null?cell.old:cell.new)??"";}function commentsFor(rid,column){return state.comments.filter(c=>c.requirementId===rid&&c.column===column);}

function sortedRows(){const rows=data.rows.filter(matches);if(!state.sort)return rows.sort((a,b)=>a.sourceOrder-b.sourceOrder);const{column,direction}=state.sort;return rows.sort((a,b)=>{const av=valueFor(a,column),bv=valueFor(b,column);if(!av&&!bv)return a.sourceOrder-b.sourceOrder;if(!av)return 1;if(!bv)return-1;const cmp=av.localeCompare(bv,undefined,{numeric:true,sensitivity:"base"});return(cmp||a.sourceOrder-b.sourceOrder)*direction;});}
function commentCard(c,actions=""){const stamp=displayTimestamp(c.modified||c.created);return `<article class="comment-card" style="--reviewer-color:${reviewerColor(c.initials)}"><div class="comment-meta"><strong class="reviewer-chip">${escapeHtml(c.initials)}</strong> · ${escapeHtml(stamp)}${c.modified?' (edited)':''}<br>${escapeHtml(c.requirementId)} · ${escapeHtml(c.column)}</div><div class="markdown">${renderCommentMarkdown(c.text)}</div>${actions}</article>`;}

function dataCell(row,column,ri,ci){const tag=column.name===data.meta.idColumn?"th":"td",scope=tag==="th"?' scope="row"':"";return `<${tag}${scope} tabindex="-1" data-grid-cell data-row-index="${ri}" data-column-index="${ci}" data-column="${escapeHtml(column.name)}">${renderCell(row,column)}</${tag}>`;}

function renderHead(){const cols=visibleColumns();headRow.innerHTML=statusHead()+cols.map(c=>`<th scope="col" class="heading-cell" data-header-column="${escapeHtml(c.name)}"><button class="sort-button" data-sort="${escapeHtml(c.name)}">${escapeHtml(c.label)} <span aria-hidden="true">${state.sort&&state.sort.column===c.name?(state.sort.direction===1?'▲':'▼'):''}</span></button><span class="resize-handle" data-resize="${escapeHtml(c.name)}" role="separator" aria-orientation="vertical" aria-label="Resize ${escapeHtml(c.label)} column" title="Drag to resize; double-click to auto-size"></span></th>`).join("");filterRow.innerHTML=statusFilterHead()+cols.map(c=>{const value=state.filters.get(c.name)||'',selected=state.valueFilters.get(c.name),active=value||selected?.size;return `<th><label class="sr-only" for="filter-${escapeHtml(c.name)}">Filter ${escapeHtml(c.label)}</label><div class="filter-control"><input id="filter-${escapeHtml(c.name)}" data-filter="${escapeHtml(c.name)}" value="${escapeHtml(value)}" placeholder="${selected?.size?`${selected.size} selected`:'Filter…'}"><button class="clear-filter" data-clear-filter="${escapeHtml(c.name)}" aria-label="Clear ${escapeHtml(c.label)} filter" ${active?'':'hidden'}>×</button></div></th>`;}).join("");}
function setRovingFocus(){const cells=[...document.querySelectorAll("[data-grid-cell]")];cells.forEach(c=>{c.tabIndex=-1;c.classList.remove("selected-cell");});if(cells.length){const maxRow=Math.max(...cells.map(c=>+c.dataset.rowIndex)),row=Math.min(state.focus.row,maxRow),col=Math.min(state.focus.column,visibleColumns().length-1),target=cells.find(c=>+c.dataset.rowIndex===row&&+c.dataset.columnIndex===col)||cells[0];state.focus={row:+target.dataset.rowIndex,column:+target.dataset.columnIndex};target.tabIndex=0;target.classList.add("selected-cell");}}


function filterActive(column){return Boolean(state.filters.get(column)||state.valueFilters.get(column)?.size);}function renderColumnChooser(){const box=$("#column-list");box.innerHTML=data.columns.map(c=>`<label><input type="checkbox" data-column-toggle="${escapeHtml(c.name)}" ${state.hidden.has(c.name)?'':'checked'}> ${escapeHtml(c.label)}</label>`).join("");const hiddenFiltered=data.columns.filter(c=>state.hidden.has(c.name)&&filterActive(c.name)).length;$("#hidden-filter-warning").textContent=hiddenFiltered?`${hiddenFiltered} hidden column filter${hiddenFiltered===1?' is':'s are'} active`:"";}function renderStatusControls(){document.querySelectorAll("[data-status]").forEach(el=>el.checked=state.statuses.has(el.dataset.status));}function cycleSort(column){if(!state.sort||state.sort.column!==column)state.sort={column,direction:1};else if(state.sort.direction===1)state.sort.direction=-1;else state.sort=null;render();}
function closeHeaderPopups(except=null){document.querySelectorAll("details.popup-menu[open]").forEach(d=>{if(d!==except)d.removeAttribute("open");});}function positionPopover(element,anchor){const r=anchor.getBoundingClientRect(),margin=8;element.hidden=false;const width=element.offsetWidth,height=element.offsetHeight;let left=Math.min(r.left,innerWidth-width-margin),top=r.bottom+5;if(top+height>innerHeight-margin)top=Math.max(margin,r.top-height-5);element.style.left=`${Math.max(margin,left)}px`;element.style.top=`${Math.max(margin,top)}px`;}function closeQuick(){quick.hidden=true;quick.innerHTML="";state.editingId=null;}function sameReviewer(c){return c&&c.initials.toLocaleUpperCase()===reviewerInitials().toLocaleUpperCase()&&Boolean(reviewerInitials());}
function openQuick(button){hover.hidden=true;closeHeaderPopups();const cell=button.closest("[data-grid-cell]");if(cell){state.focus={row:+cell.dataset.rowIndex,column:+cell.dataset.columnIndex};setRovingFocus();}const rid=button.dataset.commentRow,column=button.dataset.commentColumn,existing=commentsFor(rid,column).sort((a,b)=>a.created.localeCompare(b.created)),previous=existing[existing.length-1];state.commentContext={rid,column};state.editingId=null;const previousHtml=previous?`<div class="quick-previous"><div class="meta">Previous comment${existing.length>1?` · ${existing.length-1} earlier`:''}</div>${commentCard(previous,sameReviewer(previous)?`<div class="comment-actions"><button type="button" data-quick-edit-comment="${escapeHtml(previous.id)}">Edit</button></div>`:"")}</div>`:"";quick.innerHTML=`<h3>${escapeHtml(rid)} / ${escapeHtml(column)}</h3>${previousHtml}<form id="quick-comment-form"><label for="quick-comment-text">New comment</label><textarea id="quick-comment-text" required></textarea><div class="comment-actions"><button class="primary" id="quick-comment-save" type="submit">Add comment</button><button type="button" id="open-comment-sidebar">Show sidebar</button><button type="button" id="close-quick-comment">Cancel</button></div></form>`;positionPopover(quick,button);$("#quick-comment-form").addEventListener("submit",saveQuickComment);$("#open-comment-sidebar").addEventListener("click",()=>{closeQuick();openComments(rid,column,true);});$("#close-quick-comment").addEventListener("click",()=>{closeQuick();restoreSelectedCell();});$("#quick-comment-text").focus();}
function addComment(text,rid,column){if(column===data.meta.idColumn){alert("Comments cannot be attached to the ID column.");return false;}const initials=reviewerInitials();if(!validInitials(initials)){alert("Enter 1–16 reviewer initials without control characters.");$("#reviewer-initials").focus();return false;}persistReviewerInitials();if(developMode())remember();state.comments.push({id:(globalThis.crypto&&crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random()}`),requirementId:rid,column,initials,created:localTimestamp(),modified:null,text});setDirty(true);return true;}
function saveQuickComment(e){e.preventDefault();const text=$("#quick-comment-text").value.trim();if(!text)return;if(state.editingId){const c=state.comments.find(x=>x.id===state.editingId);if(!sameReviewer(c)){alert("Only the same reviewer can edit this comment from the quick view.");return;}if(developMode())remember();c.text=text;c.modified=localTimestamp();setDirty(true);}else if(!addComment(text,state.commentContext.rid,state.commentContext.column))return;closeQuick();render();restoreSelectedCell();}
function showCommentHover(button){if(!button.classList.contains("has-comments")||!quick.hidden)return;const list=commentsFor(button.dataset.commentRow,button.dataset.commentColumn);hover.innerHTML=`<strong>${escapeHtml(button.dataset.commentRow)} / ${escapeHtml(button.dataset.commentColumn)}</strong>`+list.map(c=>commentCard(c)).join("");positionPopover(hover,button);}function hideCommentHover(){hover.hidden=true;hover.innerHTML="";}
function showValueFilter(input){const column=input.dataset.filter,values=[...new Set(data.rows.map(r=>valueFor(r,column)).filter(v=>v!==""))].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true,sensitivity:"base"}));if(values.length<2||values.length>50){valuePopover.hidden=true;return;}const selected=state.valueFilters.get(column)||new Set();valuePopover.innerHTML=`<div class="meta">Select ${escapeHtml(column)} values</div>`+values.map(v=>`<label><input type="checkbox" data-value-filter="${escapeHtml(column)}" value="${escapeHtml(v)}" ${selected.has(v)?'checked':''}> ${escapeHtml(v)}</label>`).join("");positionPopover(valuePopover,input);}function closeValueFilter(){valuePopover.hidden=true;valuePopover.innerHTML="";}
let resize=null,sidebarResize=null;document.addEventListener("pointerdown",e=>{const sidebar=e.target.closest("[data-sidebar-resize]");if(sidebar){e.preventDefault();sidebarResize={handle:sidebar};sidebar.classList.add("dragging");sidebar.setPointerCapture?.(e.pointerId);return;}const handle=e.target.closest("[data-resize]");if(!handle)return;e.preventDefault();resize={column:handle.dataset.resize,startX:e.clientX,startWidth:state.widths.get(handle.dataset.resize),handle};handle.classList.add("dragging");handle.setPointerCapture?.(e.pointerId);});document.addEventListener("pointermove",e=>{if(sidebarResize){review.style.width=`${Math.max(300,Math.min(innerWidth*.9,innerWidth-e.clientX))}px`;return;}if(!resize)return;state.widths.set(resize.column,Math.max(70,Math.min(900,resize.startWidth+e.clientX-resize.startX)));renderLayout();});document.addEventListener("pointerup",()=>{if(resize)resize.handle.classList.remove("dragging");if(sidebarResize)sidebarResize.handle.classList.remove("dragging");resize=null;sidebarResize=null;});function autoSizeColumn(column){const values=sortedRows().slice(0,1000).map(r=>valueFor(r,column)),label=data.columns.find(c=>c.name===column).label,lengths=[label,...values.flatMap(v=>String(v).split("\n"))].map(s=>s.length).sort((a,b)=>a-b),p=lengths[Math.floor((lengths.length-1)*.95)]||label.length;state.widths.set(column,Math.max(82,Math.min(640,34+p*7)));renderLayout();}document.addEventListener("dblclick",e=>{const handle=e.target.closest("[data-resize]");if(handle){e.preventDefault();e.stopPropagation();autoSizeColumn(handle.dataset.resize);}});
document.addEventListener("click",e=>{const quickEdit=e.target.closest("[data-quick-edit-comment]");if(quickEdit){const c=state.comments.find(x=>x.id===quickEdit.dataset.quickEditComment);if(c&&sameReviewer(c)){state.editingId=c.id;$("#quick-comment-text").value=c.text;$("#quick-comment-form label").textContent="Edit previous comment";$("#quick-comment-save").textContent="Save changes";$("#quick-comment-text").focus();}return;}const handle=e.target.closest("[data-resize],[data-sidebar-resize]");if(handle){e.preventDefault();return;}const clear=e.target.closest("[data-clear-filter]");if(clear){const column=clear.dataset.clearFilter;state.filters.delete(column);state.valueFilters.delete(column);closeValueFilter();renderHead();renderBodyOnly();requestAnimationFrame(()=>{const input=[...document.querySelectorAll("[data-filter]")].find(x=>x.dataset.filter===column);if(input){input.focus();showValueFilter(input);}});return;}const sort=e.target.closest("[data-sort]");if(sort){cycleSort(sort.dataset.sort);return;}const comment=e.target.closest("[data-comment-row]");if(comment){openQuick(comment);return;}const edit=e.target.closest("[data-edit-comment]");if(edit){state.editingId=edit.dataset.editComment;renderReviewPanel(true);return;}const del=e.target.closest("[data-delete-comment]");if(del){deleteComment(del.dataset.deleteComment);return;}const nav=e.target.closest("[data-go-comment]");if(nav){const c=state.comments.find(x=>x.id===nav.dataset.goComment);if(c)goToComment(c);return;}const cell=e.target.closest("[data-grid-cell]");if(cell){state.focus={row:+cell.dataset.rowIndex,column:+cell.dataset.columnIndex};setRovingFocus();}if(!e.target.closest("#quick-comment"))closeQuick();if(!e.target.closest("#value-filter-popover")&&!e.target.matches("[data-filter]"))closeValueFilter();});
document.addEventListener("mouseover",e=>{const button=e.target.closest(".comment-button.has-comments");if(button)showCommentHover(button);});document.addEventListener("mouseout",e=>{const button=e.target.closest(".comment-button.has-comments");if(button&&!button.contains(e.relatedTarget))hideCommentHover();});document.addEventListener("focusin",e=>{const cell=e.target.closest("[data-grid-cell]");if(cell){state.focus={row:+cell.dataset.rowIndex,column:+cell.dataset.columnIndex};setRovingFocus();}const button=e.target.closest(".comment-button.has-comments");if(button)showCommentHover(button);if(e.target.matches("[data-filter]"))showValueFilter(e.target);});document.addEventListener("focusout",e=>{const button=e.target.closest(".comment-button.has-comments");if(button)hideCommentHover();});
let filterTimer=null;document.addEventListener("input",e=>{if(e.target.matches("[data-cell-editor] textarea")&&state.editingCell){
  state.editingCell.draft=e.target.value;
  updateCellSuggestions(e.target.form);
}if(e.target.matches("[data-filter]")){const column=e.target.dataset.filter;state.valueFilters.delete(column);state.filters.set(column,e.target.value.toLocaleLowerCase());const clear=e.target.parentElement.querySelector("[data-clear-filter]");if(clear)clear.hidden=!e.target.value;clearTimeout(filterTimer);filterTimer=setTimeout(renderBodyOnly,100);showValueFilter(e.target);}if(e.target.id==="comment-search")renderReviewPanel();if(e.target.id==="reviewer-initials")persistReviewerInitials();});
document.addEventListener("change",e=>{if(e.target.matches("[data-column-toggle]")){
  const column=e.target.dataset.columnToggle,hadFocus=e.target===document.activeElement;
  e.target.checked?state.hidden.delete(column):state.hidden.add(column);
  render();
  if(hadFocus){
    [...document.querySelectorAll("[data-column-toggle]")].find(input=>input.dataset.columnToggle===column)?.focus();
  }
}if(e.target.matches("[data-status]")){e.target.checked?state.statuses.add(e.target.dataset.status):state.statuses.delete(e.target.dataset.status);render();}if(e.target.matches("[data-value-filter]")){const column=e.target.dataset.valueFilter,chosen=new Set([...valuePopover.querySelectorAll("[data-value-filter]")].filter(x=>x.checked).map(x=>x.value));if(chosen.size)state.valueFilters.set(column,chosen);else state.valueFilters.delete(column);state.filters.delete(column);renderHead();renderBodyOnly();requestAnimationFrame(()=>{const input=[...document.querySelectorAll("[data-filter]")].find(x=>x.dataset.filter===column);if(input)showValueFilter(input);});}});
$("#view-toggle").addEventListener("click",()=>{state.view=state.view==="unified"?"side-by-side":"unified";render();});$("#changes-only").addEventListener("click",()=>{state.statuses=new Set(["added","removed","changed"]);render();});$("#comments-only-rows").addEventListener("click",()=>{state.commentsOnly=!state.commentsOnly;renderBodyOnly();});$("#clear-filters").addEventListener("click",()=>{state.filters.clear();state.valueFilters.clear();state.commentsOnly=false;render();});$("#reset-view").addEventListener("click",()=>{state.hidden=new Set(data.columns.filter(c=>c.hidden).map(c=>c.name));state.filters.clear();state.valueFilters.clear();state.commentsOnly=false;state.statuses=new Set(["added","removed","changed","unchanged"]);state.view=data.options.initialView;state.sort=null;state.widths=new Map(data.columns.map(c=>[c.name,configuredPixels(c)]));render();});$("#show-all-columns").addEventListener("click",()=>{state.hidden.clear();closeHeaderPopups();render();});$("#default-columns").addEventListener("click",()=>{state.hidden=new Set(data.columns.filter(c=>c.hidden).map(c=>c.name));closeHeaderPopups();render();});document.querySelectorAll("details.popup-menu").forEach(details=>details.addEventListener("toggle",()=>{if(details.open)closeHeaderPopups(details);}));
$("#browse-comments").addEventListener("click",()=>{if(!review.hidden){closeReview();return;}showAllComments(true);});$("#close-review").addEventListener("click",closeReview);$("#back-comments").addEventListener("click",()=>showAllComments(true));function closeReview(){review.hidden=true;$("#browse-comments").setAttribute("aria-expanded","false");}function resetReviewFilters(){$("#reviewer-filter").value="";$("#comment-column-filter").value="";$("#comment-status-filter").value="";populateReviewFilters();}
function populateReviewFilters(){const setOptions=(el,values,label)=>{const current=el.value;el.innerHTML=`<option value="">${label}</option>`+[...values].sort().map(v=>`<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");el.value=current;};setOptions($("#reviewer-filter"),new Set(state.comments.map(c=>c.initials)),"All reviewers");setOptions($("#comment-column-filter"),new Set(data.columns.filter(c=>c.name!==data.meta.idColumn).map(c=>c.name)),"All columns");}
function showAllComments(focusSearch=false){state.commentContext=null;state.editingId=null;review.hidden=false;$("#browse-comments").setAttribute("aria-expanded","true");renderReviewPanel();if(focusSearch)requestAnimationFrame(()=>$("#comment-search").focus());}function openComments(rid,column,focusEditor=false){if(column===data.meta.idColumn)return;state.commentContext={rid,column};state.editingId=null;$("#comment-search").value="";resetReviewFilters();review.hidden=false;$("#browse-comments").setAttribute("aria-expanded","true");renderReviewPanel(focusEditor);}
function renderReviewPanel(focusEditor=false){populateReviewFilters();const reviewBody=$(".review-body"),previousScroll=reviewBody.scrollTop,context=state.commentContext,q=($("#comment-search").value||"").toLocaleLowerCase(),reviewer=$("#reviewer-filter").value,column=$("#comment-column-filter").value,status=$("#comment-status-filter").value,statusMap=new Map(data.rows.map(r=>[r.id,r.status]));let list=state.comments.filter(c=>!context||(c.requirementId===context.rid&&c.column===context.column));list=list.filter(c=>(!reviewer||c.initials===reviewer)&&(!column||c.column===column)&&(!status||statusMap.get(c.requirementId)===status)&&`${c.text}\n${c.initials}\n${c.requirementId}\n${c.column}\n${c.created}\n${c.modified||''}`.toLocaleLowerCase().includes(q)).sort((a,b)=>a.created.localeCompare(b.created));const cellCount=new Set(state.comments.map(c=>`${c.requirementId}\u0000${c.column}`)).size;$("#review-title").textContent=context?`Comments: ${context.rid} / ${context.column}`:"All comments";$("#back-comments").hidden=!context;$("#comment-counts").textContent=`${state.comments.length} comments across ${cellCount} cells · ${list.length} shown`;let body=list.map(c=>c.id===state.editingId?`<article class="comment-card" style="--reviewer-color:${reviewerColor(c.initials)}"><div class="comment-meta"><strong class="reviewer-chip">${escapeHtml(c.initials)}</strong> · ${escapeHtml(displayTimestamp(c.modified||c.created))}${c.modified?' (edited)':''}<br>${escapeHtml(c.requirementId)} · ${escapeHtml(c.column)}</div><form class="inline-comment-editor" data-inline-comment-id="${escapeHtml(c.id)}"><label class="sr-only" for="inline-comment-text-${escapeHtml(c.id)}">Edit comment</label><textarea id="inline-comment-text-${escapeHtml(c.id)}" required>${escapeHtml(c.text)}</textarea><div class="comment-editor-actions"><button class="primary" type="submit">Save changes</button><button type="button" data-cancel-inline-edit>Cancel</button></div></form></article>`:commentCard(c,`<div class="comment-actions"><button data-go-comment="${escapeHtml(c.id)}">Go to cell</button><button data-edit-comment="${escapeHtml(c.id)}">Edit</button><button data-delete-comment="${escapeHtml(c.id)}">Delete</button></div>`)).join("");if(!list.length)body='<div class="empty-state">No comments match.</div>';const editor=context&&!state.editingId?`<form id="comment-form" class="comment-editor"><label for="comment-text">New comment</label><textarea id="comment-text" required></textarea><div class="comment-editor-actions"><button class="primary" type="submit">Add comment</button></div></form>`:"";$("#comment-list").innerHTML=body+editor;reviewBody.scrollTop=previousScroll;const form=$("#comment-form");if(form)form.addEventListener("submit",saveComment);document.querySelectorAll(".inline-comment-editor").forEach(el=>el.addEventListener("submit",saveInlineComment));document.querySelectorAll("[data-cancel-inline-edit]").forEach(el=>el.addEventListener("click",cancelInlineEdit));if(focusEditor)requestAnimationFrame(()=>$(".inline-comment-editor textarea,#comment-text")?.focus());}
function reviewerInitials(){return $("#reviewer-initials").value.trim();}function validInitials(s){return s.length>=1&&s.length<=16&&![...s].some(c=>c.charCodeAt(0)<32||c.charCodeAt(0)===127);}function loadReviewerInitials(){try{return localStorage.getItem("reqtable-reviewer-initials")||"";}catch{return "";}}function persistReviewerInitials(){const initials=reviewerInitials();if(!validInitials(initials))return;try{localStorage.setItem("reqtable-reviewer-initials",initials);}catch{}}
function restoreSidebarFocus(id){requestAnimationFrame(()=>{const button=[...document.querySelectorAll("[data-edit-comment]")].find(x=>x.dataset.editComment===id);(button||$("#comment-search"))?.focus();});}function cancelInlineEdit(){const id=state.editingId;state.editingId=null;renderReviewPanel();restoreSidebarFocus(id);}function saveInlineComment(e){e.preventDefault();const id=e.currentTarget.dataset.inlineCommentId,c=state.comments.find(x=>x.id===id),text=e.currentTarget.querySelector("textarea").value.trim(),initials=reviewerInitials();if(!c||!text)return;if(!validInitials(initials)){alert("Enter 1–16 reviewer initials without control characters.");return;}if(developMode())remember();c.text=text;c.initials=initials;c.modified=localTimestamp();state.editingId=null;persistReviewerInitials();setDirty(true);render();renderReviewPanel();restoreSidebarFocus(id);}function saveComment(e){e.preventDefault();const text=$("#comment-text").value.trim();if(!text||!state.commentContext)return;if(!addComment(text,state.commentContext.rid,state.commentContext.column))return;render();renderReviewPanel();restoreSelectedCell();}function deleteComment(id){if(!confirm("Delete this comment?"))return;if(developMode())remember();state.comments=state.comments.filter(c=>c.id!==id);setDirty(true);render();renderReviewPanel();restoreSelectedCell();}
function goToComment(c){state.hidden.delete(c.column);state.filters.clear();state.valueFilters.clear();state.commentsOnly=false;state.statuses=new Set(["added","removed","changed","unchanged"]);render();requestAnimationFrame(()=>{const row=[...document.querySelectorAll("tr[data-row-id]")].find(r=>r.dataset.rowId===c.requirementId),cell=row&&[...row.querySelectorAll("[data-column]")].find(x=>x.dataset.column===c.column);if(cell){state.focus={row:+cell.dataset.rowIndex,column:+cell.dataset.columnIndex};setRovingFocus();cell.focus({preventScroll:true});ensureCellVisible(cell);}});}
function safeJson(value){return JSON.stringify(value).replace(/</g,"\\u003c").replace(/>/g,"\\u003e").replace(/&/g,"\\u0026").replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029");}function filenameInitials(s){return s.replace(/[^A-Za-z0-9_-]+/g,"-").replace(/^[-_]+|[-_]+$/g,"");}
function downloadBlob(blob,filename){const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function showHelp(){closeHeaderPopups();closeQuick();if(typeof help.showModal==="function")help.showModal();else help.setAttribute("open","");}$("#show-help").addEventListener("click",showHelp);$("#close-help").addEventListener("click",()=>help.close());function gridCells(){return[...document.querySelectorAll("[data-grid-cell]")];}

function focusGridCell(row,column){const cells=gridCells();if(!cells.length)return;const maxRow=Math.max(...cells.map(c=>+c.dataset.rowIndex)),maxCol=visibleColumns().length-1;row=Math.max(0,Math.min(maxRow,row));column=Math.max(0,Math.min(maxCol,column));const cell=cells.find(c=>+c.dataset.rowIndex===row&&+c.dataset.columnIndex===column);if(cell){state.focus={row,column};setRovingFocus();cell.focus({preventScroll:true});ensureCellVisible(cell);}}function restoreSelectedCell(){requestAnimationFrame(()=>focusGridCell(state.focus.row,state.focus.column));}function focusSelectedFilter(){const column=visibleColumns()[state.focus.column],input=column&&[...document.querySelectorAll("[data-filter]")].find(x=>x.dataset.filter===column.name);if(input){input.focus();input.select();}}function enterTableFromFilter(input){const column=visibleColumns().findIndex(c=>c.name===input.dataset.filter);clearTimeout(filterTimer);closeValueFilter();renderBodyOnly();requestAnimationFrame(()=>focusGridCell(0,Math.max(0,column)));}
const arrowSteps={
  ArrowLeft:[0,-1],ArrowRight:[0,1],ArrowUp:[-1,0],ArrowDown:[1,0]
};
const keyboardMode=$("#keyboard-mode");
function vimKeys(){return !developMode()||keyboardMode.value==="vim";}
const appleKeyboard=/Mac|iPhone|iPad|iPod/.test(navigator.platform);
function syncKeyboardShortcuts(){
  const glyphs={Mod:appleKeyboard?"⌘":"Ctrl+",Alt:appleKeyboard?"⌥":"Alt+",Shift:appleKeyboard?"⇧":"Shift+",Backspace:"⌫",Delete:"⌦"};
  document.querySelectorAll("[data-shortcut]").forEach(hint=>{
    const keys=vimKeys()&&hint.hasAttribute("data-vim-shortcut")?hint.dataset.vimShortcut:hint.dataset.shortcut;
    hint.hidden=!keys;
    hint.textContent=keys.split(" ").map(key=>glyphs[key]??key).join("");
  });
}
keyboardMode.addEventListener("change",()=>{
  pendingG=null;
  syncKeyboardShortcuts();
});
syncKeyboardShortcuts();
function tabNeighbor(cell,backward){
  const sibling=backward?"previousElementSibling":"nextElementSibling";
  const neighbor=cell[sibling];
  if(neighbor?.matches("[data-grid-cell]"))return neighbor;
  const cells=cell.parentElement[sibling]?.querySelectorAll("[data-grid-cell]");
  return cells?.[backward?cells.length-1:0];
}
let pendingG=null;
function jumpGridRegion(row,column,dr,dc){
  const rows=sortedRows(),columns=visibleColumns();
  const inGrid=(r,c)=>r>=0&&r<=rows.length&&c>=0&&c<columns.length;
  const filled=(r,c)=>Boolean(rows[r]&&valueFor(rows[r],columns[c].name).trim());
  if(!inGrid(row+dr,column+dc))return;
  const followRun=filled(row,column)&&filled(row+dr,column+dc);
  while(inGrid(row+dr,column+dc)){
    const nextFilled=filled(row+dr,column+dc);
    if(followRun&&!nextFilled)break;
    row+=dr;
    column+=dc;
    if(!followRun&&nextFilled)break;
  }
  focusGridCell(row,column);
}
document.addEventListener("focusout",e=>{
  if(e.target===pendingG)pendingG=null;
});
document.addEventListener("keydown",e=>{
  const previousG=pendingG;
  pendingG=null;
  if(e.defaultPrevented||e.isComposing)return;
  if(e.key==="Escape"){
    closeHeaderPopups();closeQuick();closeValueFilter();hideCommentHover();closeReview();restoreSelectedCell();
    return;
  }
  if(e.target.matches("[data-filter]")&&(e.key==="ArrowDown"||e.key==="Enter")){
    e.preventDefault();
    enterTableFromFilter(e.target);
    return;
  }
  if(e.target.matches("input,textarea,select")||e.target.isContentEditable)return;
  const modified=e.ctrlKey||e.metaKey;
  if(!modified&&!e.altKey&&e.key==="?"){e.preventDefault();showHelp();return;}
  if(!modified&&!e.altKey&&e.key==="/"){
    e.preventDefault();
    if(!review.hidden&&!state.commentContext){$("#comment-search").focus();$("#comment-search").select();}
    else focusSelectedFilter();
    return;
  }
  const cell=e.target.closest("[data-grid-cell]");
  if(!cell)return;
  let row=+cell.dataset.rowIndex,column=+cell.dataset.columnIndex;
  const develop=developMode(),vim=vimKeys(),key=e.key.toLowerCase(),step=Object.hasOwn(arrowSteps,e.key)&&arrowSteps[e.key];
  const lastColumn=visibleColumns().length-1;
  if(develop&&!vim&&e.target===cell&&!state.editingCell&&handleSpreadsheetRowShortcut(e))return;
  if(e.altKey)return;
  if(modified){
    if(e.shiftKey)return;
    if(develop&&step&&e.target===cell){
      e.preventDefault();
      jumpGridRegion(row,column,...step);
      return;
    }
    if(e.key!=="Home"&&e.key!=="End")return;
    if(!develop&&!e.ctrlKey)return;
    row=e.key==="Home"?0:develop?sortedRows().length-1:Number.MAX_SAFE_INTEGER;
    column=e.key==="Home"?0:lastColumn;
  }else if(develop&&e.key==="Tab"&&e.target===cell){
    const next=tabNeighbor(cell,e.shiftKey);
    if(!next)return;
    row=+next.dataset.rowIndex;
    column=+next.dataset.columnIndex;
  }else if(step){
    row+=step[0];
    column+=step[1];
  }else if(vim&&key==="h")column--;
  else if(vim&&key==="l")column++;
  else if(vim&&key==="k")row--;
  else if(vim&&key==="j")row++;
  else if(e.key==="Home"||(vim&&e.key==="0"))column=0;
  else if(e.key==="End"||(vim&&e.key==="$"))column=lastColumn;
  else if(e.key==="PageUp")row-=10;
  else if(e.key==="PageDown")row+=10;
  else if(vim&&key==="g"){
    if(develop&&!e.shiftKey){
      e.preventDefault();
      if(e.repeat||previousG!==cell){pendingG=cell;return;}
    }
    row=e.shiftKey?Number.MAX_SAFE_INTEGER:0;
  }else if(develop&&(vim&&key==="i")&&e.target===cell){
    e.preventDefault();
    startCellEdit(cell);
    return;
  }else if(develop&&(vim&&key==="o")&&e.target===cell&&!state.editingCell){
    e.preventDefault();
    if(!e.repeat)addRequirement(e.shiftKey?"above":"below");
    return;
  }else if((e.key==="Enter"||(vim&&key==="c"))&&data.options.commentsEnabled&&cell.dataset.column!==data.meta.idColumn){
    if(e.key==="Enter"&&e.target!==cell)return;
    e.preventDefault();
    cell.querySelector(".comment-button")?.click();
    return;
  }else if(develop&&!vim&&e.target===cell&&[...e.key].length===1){
    if(startCellEdit(cell,false,e.key))e.preventDefault();
    return;
  }else return;
  e.preventDefault();
  focusGridCell(row,column);
});
document.querySelectorAll("#reviewer-filter,#comment-column-filter,#comment-status-filter").forEach(el=>el.addEventListener("change",renderReviewPanel));if(data.meta.mode!=="diff")document.querySelectorAll(".diff-only").forEach(el=>el.hidden=true);if(!data.options.commentsEnabled)document.querySelectorAll(".comments-only").forEach(el=>el.hidden=true);const storedInitials=loadReviewerInitials();if(storedInitials)$("#reviewer-initials").value=storedInitials;populateReviewFilters();

/* Develop-mode editing and browser-side persistence. */
function developMode(){return data.meta.documentMode==="develop";}function diffActive(){return data.meta.mode==="diff"||state.unsavedDiff;}function rowId(row){return String(row[data.meta.idColumn]??"").trim();}function byId(rows){return new Map(rows.map(row=>[rowId(row),row]));}
function wordChanges(a,b){
  const removed=new Set(),added=new Set();
  if(!a.length||!b.length||a.length*b.length>20000)return [removed,added];
  const dp=Array.from({length:a.length+1},()=>new Uint32Array(b.length+1));
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--){
    dp[i][j]=a[i]===b[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
  }
  let i=0,j=0;
  while(i<a.length||j<b.length){
    if(i<a.length&&j<b.length&&a[i]===b[j]){i++;j++;}
    else if(j>=b.length||(i<a.length&&dp[i+1][j]>=dp[i][j+1]))removed.add(i++);
    else added.add(j++);
  }
  return [removed,added];
}
const diffTokens=/\s+|[\p{L}\p{N}_]+|[^\p{L}\p{N}_\s]/gu;
function highlightToken(token,changed,kind){
  const text=escapeHtml(token);
  return changed&&token.trim()?`<span class="diff-word ${kind}-word">${text}</span>`:text;
}
function diffWords(oldText,newText){
  const left=oldText.match(diffTokens)??[],right=newText.match(diffTokens)??[];
  const [removed,added]=wordChanges(left,right);
  return [left.map((token,i)=>highlightToken(token,removed.has(i),"removed")).join(""),
          right.map((token,i)=>highlightToken(token,added.has(i),"added")).join("")];
}
function markdownDiff(oldText,newText){
  function parse(text){
    const template=document.createElement("template");
    template.innerHTML=renderCommentMarkdown(text);
    const walker=document.createTreeWalker(template.content,NodeFilter.SHOW_TEXT);
    const tokens=[],nodes=[];
    for(let node=walker.nextNode();node;node=walker.nextNode()){
      const words=node.data.match(diffTokens)??[];
      nodes.push({node,start:tokens.length,words});
      tokens.push(...words);
    }
    return {template,tokens,nodes};
  }
  function highlight(side,changed,kind){
    if(!side.template.innerHTML)return "";
    const fragment=document.createElement("template");
    for(const {node,start,words} of side.nodes){
      if(!words.some((_,i)=>changed.has(start+i)))continue;
      fragment.innerHTML=words.map((token,i)=>highlightToken(token,changed.has(start+i),kind)).join("");
      node.replaceWith(fragment.content);
    }
    return `<div class="diff-line ${kind}-line">${side.template.innerHTML}</div>`;
  }
  const left=parse(oldText),right=parse(newText);
  const [removed,added]=wordChanges(left.tokens,right.tokens);
  const oldHtml=highlight(left,removed,"removed"),newHtml=highlight(right,added,"added");
  return {oldHtml,newHtml,unifiedHtml:oldHtml+newHtml};
}
function browserDiff(oldText,newText){oldText=String(oldText);newText=String(newText);if(!oldText&&newText){const h=newText.split("\n").map(x=>`<div class="diff-line added-line">${escapeHtml(x)||"&nbsp;"}</div>`).join("");return{oldHtml:"",newHtml:h,unifiedHtml:h};}if(oldText&&!newText){const h=oldText.split("\n").map(x=>`<div class="diff-line removed-line">${escapeHtml(x)||"&nbsp;"}</div>`).join("");return{oldHtml:h,newHtml:"",unifiedHtml:h};}const a=oldText.split("\n"),b=newText.split("\n"),count=Math.max(a.length,b.length),oldParts=[],newParts=[],unified=[];for(let i=0;i<count;i++){if(i>=a.length){const h=`<div class="diff-line added-line">${escapeHtml(b[i])||"&nbsp;"}</div>`;newParts.push(h);unified.push(h);}else if(i>=b.length){const h=`<div class="diff-line removed-line">${escapeHtml(a[i])||"&nbsp;"}</div>`;oldParts.push(h);unified.push(h);}else if(a[i]===b[i]){const h=`<div class="diff-line context-line">${escapeHtml(a[i])||"&nbsp;"}</div>`;oldParts.push(h);newParts.push(h);unified.push(h);}else{const pair=diffWords(a[i],b[i]),oh=`<div class="diff-line removed-line">${pair[0]||"&nbsp;"}</div>`,nh=`<div class="diff-line added-line">${pair[1]||"&nbsp;"}</div>`;oldParts.push(oh);newParts.push(nh);unified.push(oh,nh);}}return{oldHtml:oldParts.join(""),newHtml:newParts.join(""),unifiedHtml:unified.join("")};}
function renderRequirementValue(value,column){value=String(value??"");if(!value)return'<span class="empty-value">Empty</span>';return column.markdown?renderCommentMarkdown(value):escapeHtml(value).replace(/\n/g,"<br>");}function comparisonValue(value){return data.options.ignoreTrailingWhitespace?value.split("\n").map(line=>line.trimEnd()).join("\n"):value;}
function runtimeCell(column,oldValue,newValue,comparison){const oldText=oldValue??"",newText=newValue??"",changed=Boolean(comparison)&&!data.meta.ignoredColumns.includes(column.name)&&comparisonValue(oldText)!==comparisonValue(newText),result={column:column.name,old:oldValue,new:newValue,changed,search:`${oldText}\n${newText}`.toLocaleLowerCase()};if(changed)Object.assign(result,column.markdown?markdownDiff(oldText,newText):browserDiff(oldText,newText));else{const display=newValue===null?oldText:newText,rendered=renderRequirementValue(display,column);Object.assign(result,{oldHtml:renderRequirementValue(oldText,column),newHtml:renderRequirementValue(newText,column),unifiedHtml:rendered});}return result;}
function requirementStatus(oldRow,newRow){
  if(!oldRow)return "added";
  if(!newRow)return "removed";
  const changed=data.columns.some(({name})=>!data.meta.ignoredColumns.includes(name)
    &&comparisonValue(String(oldRow[name]??""))!==comparisonValue(String(newRow[name]??"")));
  return changed?"changed":"unchanged";
}
function savedDiffStatuses(){
  const oldRows=byId(data.source.old.rows),newRows=byId(state.currentRows);
  const ids=new Set([...oldRows.keys(),...newRows.keys()]);
  const statuses=Object.create(null);
  for(const id of ids){
    const status=requirementStatus(oldRows.get(id),newRows.get(id));
    if(status!=="unchanged"||data.options.includeUnchanged)statuses[id]=status;
  }
  return statuses;
}
let savedRowIndex;
function rebuildRows(){savedRowIndex=byId(state.savedRows);const comparison=state.unsavedDiff?state.savedRows:(data.meta.mode==="diff"?data.source.old.rows:null),oldMap=comparison?byId(comparison):new Map(),newMap=byId(state.currentRows),ids=state.currentRows.map(rowId),previousOrder=comparison?.map(rowId).filter(id=>newMap.has(id))??[],currentOrder=ids.filter(id=>oldMap.has(id)),moved=new Set(state.unsavedDiff?currentOrder.filter((id,i)=>id!==previousOrder[i]):[]);if(comparison){
  let following=null;
  for(let index=comparison.length-1;index>=0;index--){
    const id=rowId(comparison[index]);
    if(!newMap.has(id)){
      if(following===null)ids.push(id);
      else ids.splice(ids.indexOf(following),0,id);
    }
    following=id;
  }
}data.rows=ids.map((id,index)=>{const oldRow=oldMap.get(id),newRow=newMap.get(id);const status=!comparison?"unchanged":moved.has(id)?"changed":requirementStatus(oldRow,newRow);const cells=Object.create(null);for(const column of data.columns){const oldValue=oldRow?(Object.hasOwn(oldRow,column.name)?String(oldRow[column.name]??""):null):null,newValue=newRow?(Object.hasOwn(newRow,column.name)?String(newRow[column.name]??""):null):null;cells[column.name]=runtimeCell(column,oldValue,newValue,comparison);}return{id,status,moved:moved.has(id),sourceOrder:index,cells};});}
function renderCell(row,column){const cell=row.cells[column.name],count=commentsFor(row.id,column.name).length,editing=state.editingCell&&state.editingCell.rid===row.id&&state.editingCell.column===column.name;if(editing){const value=state.editingCell.draft??valueFor(row,column.name);return `<form class="cell-editor" data-cell-editor data-row-id="${escapeHtml(row.id)}" data-column="${escapeHtml(column.name)}"><textarea aria-label="Edit ${escapeHtml(column.label)}">
${escapeHtml(value)}</textarea><div class="cell-suggestions" role="group" aria-label="Suggested values" hidden></div><div class="cell-editor-actions"><button class="apply-edit" type="submit" aria-label="Apply" title="Apply">✓</button><button class="cancel-edit" type="button" data-cancel-cell-edit aria-label="Cancel" title="Cancel">✕</button></div></form>`;}let content;if(row.id!==""&&diffActive()&&state.view==="side-by-side"&&(cell.changed||cell.old===null||cell.new===null)){content=`<div class="split"><div class="pane"><span class="pane-label">Old</span>${cell.old===null?'<div class="missing">Not present</div>':cell.oldHtml}</div><div class="pane"><span class="pane-label">New</span>${cell.new===null?'<div class="missing">Not present</div>':cell.newHtml}</div></div>`;}else if(row.id===""){
  if(column.name===data.meta.idColumn)content='<button type="button" class="entry-add" tabindex="-1" data-add-entry aria-label="Add requirement" title="Add requirement">+</button>';
  else if(column.name.toLowerCase()==="requirement"&&data.source.new.headers.includes(column.name)){
    content='<span class="entry-hint">Type to add a requirement…</span>';
  }else content="";
}else content=cell.unifiedHtml;const allowed=row.id!==""&&data.options.commentsEnabled&&column.name!==data.meta.idColumn,button=allowed?`<button class="comment-button ${count?'has-comments':''}" data-comment-row="${escapeHtml(row.id)}" data-comment-column="${escapeHtml(column.name)}" aria-label="${count?`${count} comments`:'Add comment'} for ${escapeHtml(row.id)}, ${escapeHtml(column.label)}">${count||'+'}</button>`:"",saved=savedRowIndex.get(row.id),edited=developMode()&&cell.new!==null&&String(saved?.[column.name]??"")!==cell.new;return `<div class="cell-wrap markdown ${edited?'edited-cell':''}">${content}${button}</div>`;}
function statusHead(){return diffActive()?'<th scope="col" class="heading-cell">Status</th>':"";}function statusFilterHead(){return diffActive()?'<th><span class="sr-only">Status filters</span></th>':"";}function statusCell(row){return diffActive()?(row.id===""?'<td class="status-cell"></td>':`<td class="status-cell"><span class="badge ${row.status}">${row.status}</span>${row.moved?'<small class="order-change">Order changed</small>':""}</td>`):"";}function renderLayout(){const cols=visibleColumns(),status=diffActive()?118:0,widths=cols.map(c=>state.widths.get(c.name)),natural=status+widths.reduce((a,b)=>a+b,0),target=Math.max($(".table-wrap").clientWidth,natural);if(cols.length&&target>natural){let flex=0;for(let i=1;i<widths.length;i++)if(widths[i]>widths[flex])flex=i;widths[flex]+=target-natural;}$("#column-widths").innerHTML=(status?'<col style="width:118px">':"")+cols.map((c,i)=>`<col data-col-width="${escapeHtml(c.name)}" style="width:${Math.round(widths[i])}px">`).join("");table.style.width=`${target}px`;}
function renderBody(){const rows=sortedRows(),cols=visibleColumns(),display=developMode()?[...rows,{id:"",status:"unchanged",cells:Object.fromEntries(data.columns.map(c=>[c.name,{old:null,new:"",unifiedHtml:""}]))}]:rows;tableBody.innerHTML=display.map((row,ri)=>`<tr class="${row.id===""?"entry-row":`row-${row.status}`}" data-row-id="${escapeHtml(row.id)}">${statusCell(row)}${cols.map((c,ci)=>dataCell(row,c,ri,ci)).join("")}</tr>`).join("");resultCount.textContent=`${cols.length} of ${data.columns.length} columns · ${rows.length} of ${data.rows.length} requirements`;$("#comments-only-rows").setAttribute("aria-pressed",String(state.commentsOnly));setRovingFocus();}
function syncModeUi(){document.querySelectorAll(".develop-only").forEach(el=>el.hidden=!developMode());document.querySelectorAll(".diff-only").forEach(el=>el.hidden=!diffActive());if(!data.options.commentsEnabled)document.querySelectorAll(".comments-only").forEach(el=>el.hidden=true);$("#unsaved-diff").setAttribute("aria-pressed",String(state.unsavedDiff));$("#unsaved-diff").textContent=state.unsavedDiff?"Show normal view":"Show changes since save";$("#undo-edit").disabled=!state.undo.length;$("#redo-edit").disabled=!state.redo.length;}function render(){rebuildRows();renderLayout();renderHead();renderBody();$("#view-toggle").textContent=state.view==="unified"?"Side-by-side view":"Unified view";renderColumnChooser();renderStatusControls();syncModeUi();}function renderBodyOnly(){renderBody();renderColumnChooser();}
function updateDirty(){state.requirementsDirty=JSON.stringify(state.currentRows)!==JSON.stringify(state.savedRows);state.commentsDirty=JSON.stringify(state.comments)!==JSON.stringify(state.savedComments);state.dirty=state.requirementsDirty||state.commentsDirty;const label=state.requirementsDirty&&state.commentsDirty?"Unsaved requirements and comments":state.requirementsDirty?"Unsaved requirements":state.commentsDirty?"Unsaved comments":"";$("#dirty-indicator").textContent=label;$("#dirty-indicator").hidden=!state.dirty;scheduleAutosave();}function setDirty(value){if(!value){state.savedComments=cloneValue(state.comments);}updateDirty();}
function remember(){state.undo.push({rows:cloneValue(state.currentRows),comments:cloneValue(state.comments)});if(state.undo.length>100)state.undo.shift();state.redo=[];}function restoreHistory(snapshot){state.currentRows=cloneValue(snapshot.rows);state.comments=cloneValue(snapshot.comments);state.editingCell=null;updateDirty();render();}function undoEdit(){if(!state.undo.length)return;state.redo.push({rows:cloneValue(state.currentRows),comments:cloneValue(state.comments)});restoreHistory(state.undo.pop());}function redoEdit(){if(!state.redo.length)return;state.undo.push({rows:cloneValue(state.currentRows),comments:cloneValue(state.comments)});restoreHistory(state.redo.pop());}
function selectedRequirementId(){return document.querySelector("[data-grid-cell].selected-cell")?.closest("tr")?.dataset.rowId||null;}function findCurrentRow(id){return state.currentRows.find(row=>rowId(row)===id);}function validateNewId(value,current=null){const id=String(value??"").trim();if(!id){alert("The requirement ID cannot be empty.");return null;}if(state.currentRows.some(row=>rowId(row)===id&&rowId(row)!==current)){alert(`Requirement ID ${id} already exists.`);return null;}return id;}
function nextRequirementId(){
  const ids=[...state.currentRows,...state.savedRows,...(data.source.old?.rows??[])].map(rowId);
  const numbered=ids.map(id=>id.match(/^(.*?)([0-9]+)$/)).filter(Boolean);
  const families=new Map();
  for(const [,prefix,digits] of numbered){
    const family=families.get(prefix)??{count:0,max:0n,width:0};
    family.count++;
    const number=BigInt(digits);
    if(number>family.max)family.max=number;
    family.width=Math.max(family.width,digits.length);
    families.set(prefix,family);
  }
  const [prefix,family]=[...families].sort((a,b)=>b[1].count-a[1].count)[0]??["REQ-",{max:0n,width:3}];
  return prefix+String(family.max+1n).padStart(family.width,"0");
}
function newRequirement(id){
  return Object.fromEntries(data.source.new.headers.map(header=>[header,header===data.meta.idColumn?id:""]));
}
function focusRequirement(id,column){
  const row=[...tableBody.rows].find(tr=>tr.dataset.rowId===id);
  const cells=[...row?.querySelectorAll("[data-grid-cell]")??[]];
  const cell=cells.find(c=>c.dataset.column===column)??cells.find(c=>c.dataset.column!==data.meta.idColumn)??cells[0];
  if(cell)focusGridCell(+cell.dataset.rowIndex,+cell.dataset.columnIndex);
  return cell;
}
function addRequirement(position){
  const selected=state.currentRows.findIndex(row=>rowId(row)===selectedRequirementId());
  if(selected<0&&position!=="end"){alert("Select a current requirement first.");return;}
  const proposed=prompt(`New requirement ID (${data.meta.idColumn}):`,nextRequirementId());
  if(proposed===null)return;
  const id=validateNewId(proposed);
  if(!id)return;
  const index=position==="end"?state.currentRows.length:selected+(position==="below"?1:0);
  remember();
  state.currentRows.splice(index,0,newRequirement(id));
  state.sort=null;
  updateDirty();
  render();
  let cell=focusRequirement(id);
  if(!cell){
    state.filters.clear();
    state.valueFilters.clear();
    state.commentsOnly=false;
    state.statuses.add(state.unsavedDiff||data.meta.mode==="diff"?"added":"unchanged");
    render();
    cell=focusRequirement(id);
  }
  if(cell)startCellEdit(cell,true);
}
function handleSpreadsheetRowShortcut(event){
  const command=event.ctrlKey||event.metaKey;
  const direction=event.key==="ArrowUp"?-1:event.key==="ArrowDown"?1:0;
  let action;
  if(event.shiftKey&&direction&&command!==event.altKey){
    action=command?(direction<0?"add-above":"add-below"):(direction<0?"move-up":"move-down");
  }else if(command&&!event.shiftKey&&!event.altKey&&["Backspace","Delete"].includes(event.key)){
    action="delete-requirement";
  }
  if(!action)return false;
  event.preventDefault();
  if(!event.repeat)$(`#${action}`).click();
  return true;
}
function moveRequirement(delta){
  const id=selectedRequirementId(),index=state.currentRows.findIndex(row=>rowId(row)===id),target=index+delta;
  if(index<0||target<0||target>=state.currentRows.length)return;
  const column=visibleColumns()[state.focus.column]?.name;
  remember();
  const [row]=state.currentRows.splice(index,1);
  state.currentRows.splice(target,0,row);
  state.sort=null;
  updateDirty();
  render();
  focusRequirement(id,column);
}
function renameRequirement(){if(!developMode())return;const oldId=selectedRequirementId(),row=oldId&&findCurrentRow(oldId);if(!row){alert("Select a current requirement before renaming it.");return;}const proposed=prompt(`Rename requirement ${oldId}:`,oldId);if(proposed===null)return;const id=validateNewId(proposed,oldId);if(!id||id===oldId)return;remember();row[data.meta.idColumn]=id;for(const comment of state.comments)if(comment.requirementId===oldId)comment.requirementId=id;if(state.commentContext?.rid===oldId)state.commentContext.rid=id;const column=visibleColumns()[state.focus.column]?.name;updateDirty();render();focusRequirement(id,column);}
function deleteRequirement(){if(!developMode())return;const id=selectedRequirementId(),index=state.currentRows.findIndex(row=>rowId(row)===id);if(index<0){alert("Select a current requirement before deleting it.");return;}const commentCount=state.comments.filter(c=>c.requirementId===id).length,message=commentCount?`Delete requirement ${id} and its ${commentCount} attached comment${commentCount===1?'':'s'}?`:`Delete requirement ${id}?`;if(!confirm(message))return;remember();state.currentRows.splice(index,1);state.comments=state.comments.filter(c=>c.requirementId!==id);updateDirty();render();}
function columnSuggestions(column){
  const values=new Set();
  for(const row of state.currentRows){
    const value=String(row[column]??"").trimEnd();
    if(!value)continue;
    if(value.length>60||value.includes("\n"))return [];
    values.add(value);
    if(values.size>50)return [];
  }
  return [...values].sort((a,b)=>a.localeCompare(b));
}
function updateCellSuggestions(form){
  const list=form.querySelector(".cell-suggestions");
  const value=form.querySelector("textarea").value;
  const prefix=value.toLocaleLowerCase();
  const matches=state.editingCell.suggestions.filter(item=>item!==value&&item.toLocaleLowerCase().startsWith(prefix));
  list.replaceChildren(...matches.map(value=>{
    const button=document.createElement("button");
    button.type="button";
    button.tabIndex=-1;
    button.textContent=value;
    button.addEventListener("click",()=>{
      form.querySelector("textarea").value=value;
      applyCellEdit(form);
    });
    return button;
  }));
  list.hidden=!matches.length;
}
function startCellEdit(cell,selectAll=false,initialText){
  const rid=cell?.closest("tr")?.dataset.rowId,column=cell?.dataset.column;
  if(!developMode()||state.editingCell||column===data.meta.idColumn||!data.source.new.headers.includes(column)||(rid!==""&&!findCurrentRow(rid)))return;
  state.editingCell={rid,column,suggestions:columnSuggestions(column)};
  cell.innerHTML=renderCell({id:rid,cells:{[column]:{new:findCurrentRow(rid)?.[column]??""}}},visibleColumns()[+cell.dataset.columnIndex]);
  const textarea=cell.querySelector("textarea");
  textarea.focus({preventScroll:true});
  if(initialText!==undefined){
    textarea.value=initialText;
    state.editingCell.draft=initialText;
  }else if(selectAll)textarea.select();
  updateCellSuggestions(textarea.form);
  ensureCellVisible(cell);
  return true;
}
function cancelCellEdit(){
  const {rid,column}=state.editingCell;
  state.editingCell=null;
  render();
  focusRequirement(rid,column);
}
function applyCellEdit(form,next,continueAtEntry=false){
  const originalCell=form.closest("[data-grid-cell]");
  const sameRow=next?.parentElement===originalCell.parentElement;
  const nextId=next?.parentElement.dataset.rowId;
  const nextColumn=next?.dataset.column;
  let id=form.dataset.rowId;
  const column=form.dataset.column,value=form.querySelector("textarea").value.replace(/\r\n?/g,"\n").trimEnd();
  const row=findCurrentRow(id);
  if(id===""&&value){
    remember();
    id=nextRequirementId();
    const added=newRequirement(id);
    added[column]=value;
    state.currentRows.push(added);
  }else if(row&&String(row[column]??"")!==value){
    remember();
    row[column]=value;
  }
  state.editingCell=null;
  updateDirty();
  render();
  if(next&&focusRequirement(sameRow?id:nextId,nextColumn))return;
  if(continueAtEntry&&form.dataset.rowId===""&&id!==""&&focusRequirement("",column))return;
  if(!focusRequirement(id,column))restoreSelectedCell();
}
function exportedComments(id,comments){return comments.filter(c=>c.requirementId===id).sort((a,b)=>a.created.localeCompare(b.created)).map(c=>({column:c.column,initials:c.initials,created:c.created,modified:c.modified||null,text:c.text}));}function commentsText(list){return list.map(c=>`[${c.modified||c.created}] [${c.initials}] [${c.column}]\n${c.text}`).join("\n\n---\n\n");}function csvField(value,delimiter){const text=String(value??"");return(/["\r\n]/.test(text)||text.includes(delimiter))?'"'+text.replace(/"/g,'""')+'"':text;}function makeCsv(snapshot){const headers=[...data.source.new.headers],commentColumn=data.options.commentsColumn||"Comments";if(data.options.commentsEnabled&&headers.includes(commentColumn)){alert(`Cannot export comments because the CSV already has a ${commentColumn} column.`);return null;}if(data.options.commentsEnabled)headers.push(commentColumn);const delimiter=data.options.csvDelimiter||",",lines=[headers.map(x=>csvField(x,delimiter)).join(delimiter)];for(const source of snapshot.rows){const row={...source};if(data.options.commentsEnabled){const list=exportedComments(rowId(source),snapshot.comments);row[commentColumn]=data.options.commentsFormat==="text"?commentsText(list):JSON.stringify(list);}lines.push(headers.map(h=>csvField(row[h]??"",delimiter)).join(delimiter));}return"\ufeff"+lines.join("\r\n")+"\r\n";}
function currentSnapshot(){
  return {rows:cloneValue(state.currentRows),comments:cloneValue(state.comments)};
}
function snapshotKey(snapshot){
  let hash=2166136261;
  for(const ch of JSON.stringify(snapshot))hash=Math.imul(hash^ch.codePointAt(0),16777619);
  return (hash>>>0).toString(16);
}
const openedSnapshot=currentSnapshot();
const draftKey=`reqtable:draft:${location.pathname}:${snapshotKey([data.meta, data.source.old, openedSnapshot])}`;
let csvHandle=null,writingCsv=false,autosaveTimer=null,recoveryPending=false;
function loadDraft(){
  try{return JSON.parse(localStorage.getItem(draftKey));}catch{return null;}
}
function persistDraft(){
  if(!$("#autosave").checked||recoveryPending)return;
  try{
    const current=currentSnapshot();
    if(JSON.stringify(current)===JSON.stringify(openedSnapshot)&&!state.dirty)localStorage.removeItem(draftKey);
    else localStorage.setItem(draftKey,JSON.stringify({current,saved:{rows:state.savedRows,comments:state.savedComments}}));
  }catch{
    if(!csvHandle)$("#save-status").textContent="Local draft storage unavailable";
  }
}
function scheduleAutosave(){
  clearTimeout(autosaveTimer);
  if(!developMode()||!$("#autosave").checked)return;
  if(!recoveryPending)persistDraft();
  if(csvHandle&&state.dirty&&!writingCsv){
    autosaveTimer=setTimeout(()=>{if(!state.editingCell)saveCsv(false,true);},1200);
  }
}
function markSaved(snapshot,message){
  state.savedRows=snapshot.rows;
  state.savedComments=snapshot.comments;
  updateDirty();
  if(state.unsavedDiff&&!state.editingCell)render();
  $("#save-status").textContent=message;
}
async function saveCsv(saveAs=false,automatic=false){
  if(writingCsv||!developMode())return;
  if(state.editingCell){
    if(!automatic)$("#save-status").textContent="Apply or cancel the cell edit before saving";
    return;
  }
  clearTimeout(autosaveTimer);
  writingCsv=true;
  let writer,succeeded=false;
  try{
    const filename=data.meta.newFilename||`${data.meta.baseFilename}.csv`;
    let handle=saveAs?null:csvHandle;
    if(!handle&&typeof window.showSaveFilePicker==="function"){
      try{
        handle=await window.showSaveFilePicker({suggestedName:filename,types:[{description:"CSV file",accept:{"text/csv":[".csv"]}}]});
      }catch(error){
        if(error.name==="AbortError")return;
        if(!["SecurityError","NotAllowedError"].includes(error.name))throw error;
      }
    }
    const snapshot=currentSnapshot(),source=makeCsv(snapshot);
    if(source===null)return;
    const blob=new Blob([source],{type:"text/csv;charset=utf-8"});
    if(handle){
      writer=await handle.createWritable();
      await writer.write(blob);
      await writer.close();
      csvHandle=handle;
      succeeded=true;
      markSaved(snapshot,`${automatic?"CSV autosaved":"CSV saved"} at ${new Date().toLocaleTimeString()}`);
    }else{
      downloadBlob(blob,filename);
      markSaved(snapshot,"CSV download initiated");
    }
  }catch(error){
    try{await writer?.abort();}catch{}
    if(automatic)csvHandle=null;
    $("#save-status").textContent=`CSV save failed: ${error.message}`;
  }finally{
    writingCsv=false;
    if(state.dirty&&csvHandle&&$("#autosave").checked&&!state.editingCell&&succeeded)scheduleAutosave();
  }
}
const recovery=developMode()?loadDraft():null;
if(recovery?.current&&recovery?.saved){
  recoveryPending=true;
  $("#recover-draft").hidden=false;
  $("#discard-draft").hidden=false;
  $("#recovery-notice").hidden=false;
}
$("#recover-draft").addEventListener("click",()=>{
  if((state.dirty||state.editingCell)&&!confirm("Replace the current changes with the recovered draft?"))return;
  recoveryPending=false;
  $("#recover-draft").hidden=true;
  $("#discard-draft").hidden=true;
  $("#recovery-notice").hidden=true;
  state.savedRows=recovery.saved.rows;
  state.savedComments=recovery.saved.comments;
  restoreHistory(recovery.current);
  $("#save-status").textContent="Autosaved draft recovered";
  restoreSelectedCell();
});
$("#discard-draft").addEventListener("click",()=>{
  if(!confirm("Discard the previous autosaved draft?"))return;
  recoveryPending=false;
  $("#recover-draft").hidden=true;
  $("#discard-draft").hidden=true;
  $("#recovery-notice").hidden=true;
  try{localStorage.removeItem(draftKey);}catch{}
  scheduleAutosave();
  $("#save-status").textContent="Previous draft discarded";
});
$("#recover-draft-notice").addEventListener("click",()=>$("#recover-draft").click());
$("#autosave").addEventListener("change",scheduleAutosave);
function saveReportCopy(){if(writingCsv)return;if(state.editingCell){$("#save-status").textContent="Apply or cancel the cell edit before saving";return;}let token="";if(data.options.commentsEnabled){const initials=reviewerInitials();if(!validInitials(initials)){alert("Enter 1–16 reviewer initials before saving.");$("#reviewer-initials").focus();return;}token=filenameInitials(initials);if(!token){alert("Enter initials containing at least one ASCII letter or digit for the filename.");return;}persistReviewerInitials();data.options.reviewerInitials=initials;}const clone=document.documentElement.cloneNode(true);
const embedded={...data};
delete embedded.rows;
embedded.comments=state.comments;
embedded.source={...data.source,new:{...data.source.new,rows:state.currentRows}};
if(data.meta.mode==="diff")embedded.diffStatus=savedDiffStatuses();
clone.querySelector("#reqtable-data").textContent=safeJson(embedded);
clone.querySelector("#requirements-body").replaceChildren();
clone.querySelector("#comment-list").replaceChildren();
for(const option of clone.querySelector("#keyboard-mode").options){
  option.toggleAttribute("selected",option.value===keyboardMode.value);
}
clone.querySelectorAll("details[open]").forEach(d=>d.removeAttribute("open"));for(const selector of["#quick-comment","#comment-hover","#value-filter-popover","#review-panel","#dirty-indicator"])clone.querySelector(selector).hidden=true;clone.querySelector("#save-status").textContent="";clone.querySelector("#recovery-notice").hidden=true;clone.querySelector("#recover-draft").hidden=true;clone.querySelector("#discard-draft").hidden=true;const kind=developMode()?"developed":"reviewed",suffix=token?`-${token}`:"";downloadBlob(new Blob(['<!doctype html>\n'+clone.outerHTML],{type:"text/html;charset=utf-8"}),`${data.meta.baseFilename}-${kind}${suffix}-${filenameTimestamp()}.html`);markSaved(currentSnapshot(),`Report download initiated at ${new Date().toLocaleTimeString()}`);}
tableBody.addEventListener("click",event=>{
  if(event.target.closest("[data-add-entry]")&&!state.editingCell)addRequirement("end");
  if(vimKeys()||!state.editingCell||event.target.closest("button,a,form"))return;
  const cell=event.target.closest("[data-grid-cell]");
  const editor=tableBody.querySelector("[data-cell-editor]");
  if(cell&&editor&&cell!==editor.closest("[data-grid-cell]")){
    event.stopPropagation();
    applyCellEdit(editor,cell);
  }
});
for(const position of ["above","below","end"])$("#add-"+position).addEventListener("click",()=>addRequirement(position));$("#move-up").addEventListener("click",()=>moveRequirement(-1));$("#move-down").addEventListener("click",()=>moveRequirement(1));$("#rename-requirement").addEventListener("click",renameRequirement);$("#delete-requirement").addEventListener("click",deleteRequirement);$("#undo-edit").addEventListener("click",undoEdit);$("#redo-edit").addEventListener("click",redoEdit);$("#unsaved-diff").addEventListener("click",()=>{if(!state.unsavedDiff)state.previousStatuses=state.statuses;state.unsavedDiff=!state.unsavedDiff;state.statuses=state.unsavedDiff?new Set(["added","removed","changed"]):state.previousStatuses;render();});$("#save-csv").addEventListener("click",()=>saveCsv());$("#save-as").addEventListener("click",()=>saveCsv(true));$("#save-copy").addEventListener("click",saveReportCopy);
document.addEventListener("submit",event=>{const form=event.target.closest("[data-cell-editor]");if(form){event.preventDefault();event.stopImmediatePropagation();applyCellEdit(form);}},true);document.addEventListener("dblclick",event=>{const cell=event.target.closest("[data-grid-cell]");if(cell&&developMode()&&!event.target.closest("form,button,a")){startCellEdit(cell);}},true);document.addEventListener("click",event=>{if(event.detail===3&&event.target.matches("[data-cell-editor] textarea")){event.preventDefault();event.target.select();}if(event.target.closest("[data-cancel-cell-edit]")){event.preventDefault();event.stopImmediatePropagation();cancelCellEdit();}},true);document.addEventListener("keydown",event=>{const editor=event.target.closest("[data-cell-editor]");if(editor){
  event.stopImmediatePropagation();
  if(event.isComposing)return;
  const suggestions=editor.querySelector(".cell-suggestions");
  const suggestion=event.target.closest(".cell-suggestions button");
  if(!event.altKey&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey){
    let next;
    if(event.key==="ArrowDown"&&!suggestions.hidden){
      next=suggestion?suggestion.nextElementSibling:event.target.matches("textarea")?suggestions.firstElementChild:null;
    }else if(event.key==="ArrowUp"&&suggestion){
      next=suggestion.previousElementSibling||editor.querySelector("textarea");
    }
    if(next){
      event.preventDefault();
      next.focus();
      return;
    }
  }
  if((event.target.matches("textarea")||suggestion)&&event.key==="Tab"&&!event.ctrlKey&&!event.metaKey&&!event.altKey){
    event.preventDefault();
    applyCellEdit(editor,tabNeighbor(editor.closest("[data-grid-cell]"),event.shiftKey));
    return;
  }
  if(!vimKeys()&&event.target.matches("textarea")&&event.key==="Enter"&&!event.ctrlKey&&!event.metaKey){
    event.preventDefault();
    if(event.altKey){
      const textarea=event.target;
      textarea.setRangeText("\n",textarea.selectionStart,textarea.selectionEnd,"end");
      textarea.dispatchEvent(new Event("input",{bubbles:true}));
    }else{
      const cell=editor.closest("[data-grid-cell]");
      const row=cell.parentElement[event.shiftKey?"previousElementSibling":"nextElementSibling"];
      const next=row?.querySelectorAll("[data-grid-cell]")[+cell.dataset.columnIndex];
      applyCellEdit(editor,next,!event.shiftKey&&!row);
    }
    return;
  }
  if(event.key==="Escape"){event.preventDefault();event.stopImmediatePropagation();cancelCellEdit();}else if(event.key==="Enter"&&(event.ctrlKey||event.metaKey)){event.preventDefault();event.stopImmediatePropagation();applyCellEdit(editor);}return;}if(state.editingCell&&event.key==="Escape"){event.preventDefault();event.stopImmediatePropagation();cancelCellEdit();return;}if(developMode()&&(event.ctrlKey||event.metaKey)&&event.key.toLocaleLowerCase()==="z"&&!event.target.matches("input,textarea,select")){event.preventDefault();event.stopImmediatePropagation();event.shiftKey?redoEdit():undoEdit();if(event.target.matches("[data-grid-cell]"))focusGridCell(state.focus.row,state.focus.column);return;}if(developMode()&&(event.ctrlKey||event.metaKey)&&event.key.toLocaleLowerCase()==="y"&&!event.target.matches("input,textarea,select")){event.preventDefault();event.stopImmediatePropagation();redoEdit();if(event.target.matches("[data-grid-cell]"))focusGridCell(state.focus.row,state.focus.column);return;}const cell=event.target.closest("[data-grid-cell]");if(developMode()&&cell&&!event.target.closest("button,a")&&(event.key==="Enter"||event.key==="F2")){event.preventDefault();event.stopImmediatePropagation();
  const addButton=event.key==="Enter"&&cell.querySelector("[data-add-entry]");
  if(addButton){
    if(!event.repeat)addButton.click();
  }else{
    const caretAtEnd=event.key==="F2"&&!vimKeys();
    if(startCellEdit(cell,!caretAtEnd)&&caretAtEnd){
      const textarea=cell.querySelector("textarea");
      textarea.setSelectionRange(textarea.value.length,textarea.value.length);
    }
  }
}},true);
function matches(row){if(!state.unsavedDiff&&diffActive()&&!data.options.includeUnchanged&&row.status==="unchanged")return false;if(!state.statuses.has(row.status))return false;if(state.commentsOnly&&!state.comments.some(c=>c.requirementId===row.id))return false;for(const[column,query]of state.filters){if(query&&!row.cells[column].search.includes(query.toLocaleLowerCase()))return false;}for(const[column,values]of state.valueFilters){if(values.size&&!values.has(valueFor(row,column)))return false;}return true;}function ensureCellVisible(cell){const wrap=$(".table-wrap"),wr=wrap.getBoundingClientRect(),cr=cell.getBoundingClientRect(),statusWidth=diffActive()?118:0,safeLeft=wr.left+statusWidth+2,safeTop=wr.top+68,safeBottom=wr.top+wrap.clientHeight-2,panelLeft=review.hidden?Infinity:review.getBoundingClientRect().left,safeRight=Math.min(wr.left+wrap.clientWidth-2,panelLeft-2);if(cr.left<safeLeft)wrap.scrollLeft+=cr.left-safeLeft;else if(cr.right>safeRight)wrap.scrollLeft+=cr.right-safeRight;if(cr.top<safeTop)wrap.scrollTop+=cr.top-safeTop;else if(cr.bottom>safeBottom)wrap.scrollTop+=cr.bottom-safeBottom;}
const menus=[...document.querySelectorAll(".toolbar details.popup-menu")];
for(const menu of menus){
  const summary=menu.querySelector("summary");
  summary.addEventListener("pointerenter",event=>{
    if(event.pointerType!=="mouse"||menu.open||menu.hidden)return;
    const openMenu=menus.find(item=>item.open);
    if(!openMenu)return;
    const hadFocus=openMenu.contains(document.activeElement);
    closeHeaderPopups(menu);
    menu.open=true;
    if(hadFocus)summary.focus({preventScroll:true});
  });
}
document.addEventListener("focusin",event=>{
  closeHeaderPopups(event.target.closest(".toolbar .popup-menu"));
});
const settings=$("#settings-dialog"),commandSearch=$("#command-search");
const commandQuery=$("#command-query"),commandResults=$("#command-results");
$("#open-settings").addEventListener("click",()=>{
  closeHeaderPopups();
  settings.showModal();
  keyboardMode.focus();
});
$("#close-settings").addEventListener("click",()=>settings.close());
settings.addEventListener("close",()=>restoreSelectedCell());
function renderCommandResults(){
  const terms=commandQuery.value.toLocaleLowerCase().trim().split(/\s+/);
  commandResults.replaceChildren();
  for(const menu of menus){
    const group=menu.querySelector("summary").textContent;
    for(const item of menu.querySelectorAll(".popover button,.popover input[type=checkbox]")){
      if(item.id==="search-menus"||item.disabled||item.closest("[hidden]"))continue;
      const hint=item.querySelector("kbd:not([hidden])");
      const labelNode=item.labels?.[0]??item;
      const label=[...labelNode.childNodes].filter(node=>!node.matches?.("kbd"))
        .map(node=>node.textContent).join("").trim();
      if(!terms.every(term=>`${group} ${label}`.toLocaleLowerCase().includes(term)))continue;
      const result=document.createElement("button");
      const name=document.createElement("span");
      const context=document.createElement("small");
      context.textContent=group;
      name.append(context,document.createElement("br"),label);
      result.append(name);
      if(hint)result.append(hint.cloneNode(true));
      result.addEventListener("click",()=>{
        commandSearch.close();
        item.click();
      });
      commandResults.append(result);
    }
  }
  $("#command-empty").hidden=commandResults.childElementCount>0;
}
function openCommandSearch(){
  if(document.querySelector("dialog[open]"))return;
  closeHeaderPopups();
  commandQuery.value="";
  renderCommandResults();
  commandSearch.showModal();
  commandQuery.focus();
}
$("#search-menus").addEventListener("click",event=>{
  event.currentTarget.closest(".popup-menu").querySelector("summary").focus();
  openCommandSearch();
});
$("#close-command-search").addEventListener("click",()=>commandSearch.close());
commandQuery.addEventListener("input",renderCommandResults);
commandSearch.addEventListener("keydown",event=>{
  if(event.isComposing)return;
  const active=event.target,results=[...commandResults.children];
  if(event.key==="ArrowDown"||event.key==="ArrowUp"){
    const index=results.indexOf(active);
    const next=event.key==="ArrowDown"?results[index+1]:results[index-1]||commandQuery;
    next?.focus();
  }else if(event.key==="Enter"&&active===commandQuery){
    results[0]?.click();
  }else return;
  event.preventDefault();
});
for(const dialog of [settings,commandSearch]){
  dialog.addEventListener("keydown",event=>{
    if(event.key==="Escape")event.stopPropagation();
  });
}
document.addEventListener("keydown",event=>{
  if(event.altKey&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.isComposing
      &&(event.code==="Slash"||event.key==="/")){
    event.preventDefault();
    openCommandSearch();
  }
});
function menuItems(menu){
  return [...menu.querySelectorAll("button,input")].filter(item=>!item.disabled&&item.getClientRects().length);
}
document.addEventListener("click",event=>{
  const menu=event.composedPath().find(node=>node.matches?.(".toolbar details.popup-menu"));
  if(!menu){closeHeaderPopups();return;}
  const summary=menu.querySelector("summary");
  if(event.target.closest("summary"))closeHeaderPopups(menu);
  else if(event.target.closest("button")){
    menu.open=false;
    if(menu.contains(document.activeElement)||document.activeElement===document.body)summary.focus();
  }
});
document.addEventListener("keydown",event=>{
  const menu=event.target.closest(".toolbar details.popup-menu");
  if(!menu||event.altKey||event.ctrlKey||event.metaKey||event.isComposing)return;
  const summary=menu.querySelector("summary");
  if(event.key==="Escape"&&menu.open){
    menu.open=false;
    summary.focus();
  }else if(event.target===summary&&["Enter"," "].includes(event.key)){
    closeHeaderPopups(menu);
    menu.open=true;
    menuItems(menu)[0]?.focus();
  }else if(event.key==="Enter"&&event.target.matches('input[type="checkbox"]')){
    event.target.click();
  }else if(["ArrowLeft","ArrowRight"].includes(event.key)){
    const visible=menus.filter(item=>!item.hidden),offset=event.key==="ArrowRight"?1:-1;
    const next=visible[(visible.indexOf(menu)+offset+visible.length)%visible.length];
    const wasOpen=menu.open;
    closeHeaderPopups();
    next.open=wasOpen;
    const target=wasOpen&&event.target!==summary?menuItems(next)[0]:null;
    (target||next.querySelector("summary")).focus();
  }else if(["ArrowDown","ArrowUp","Home","End"].includes(event.key)){
    closeHeaderPopups(menu);
    menu.open=true;
    const items=menuItems(menu),index=items.indexOf(event.target);
    const target=event.key==="Home"?0:event.key==="End"?items.length-1:event.key==="ArrowDown"?(index+1)%items.length:(index<=0?items.length-1:index-1);
    items[target]?.focus();
  }else return;
  event.preventDefault();
  event.stopImmediatePropagation();
},true);
render();
updateDirty();
"""


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; form-action 'none'"><title>__TITLE__</title><style>__CSS__</style></head>
<body><main class="page"><header class="report-header"><div><h1>__TITLE__</h1><div class="meta" id="metadata">__META__</div><div class="summary"><span id="document-mode" class="badge mode-badge __DOCUMENT_MODE__">__DOCUMENT_MODE_LABEL__</span>__SUMMARY__</div></div><div class="save-area"><span class="comments-only"><label for="reviewer-initials">Reviewer initials</label> <input id="reviewer-initials" maxlength="16" value="__INITIALS__"></span><span id="dirty-indicator" class="dirty" hidden>Unsaved changes</span><span id="save-status" class="meta" aria-live="polite"></span></div></header>
<div id="recovery-notice" class="recovery-notice" hidden><span>Autosaved draft available for this report.</span><button id="recover-draft-notice" type="button">Recover draft</button></div>
<section class="toolbar" aria-label="Table controls">
<details class="popup-menu"><summary>File</summary><div class="popover"><button id="save-csv" class="develop-only">Save CSV</button><button id="save-as" class="develop-only">Save CSV As…</button><button id="save-copy">Save report copy</button><label class="develop-only"><input id="autosave" type="checkbox" checked> Autosave</label><button id="recover-draft" hidden>Recover autosaved draft</button><button id="discard-draft" hidden>Discard autosaved draft</button></div></details>
<details class="popup-menu develop-only"><summary>Edit</summary><div class="popover"><button id="add-end">Add requirement</button><button id="add-above">Add above <kbd data-shortcut="Mod Shift ↑" data-vim-shortcut="O"></kbd></button><button id="add-below">Add below <kbd data-shortcut="Mod Shift ↓" data-vim-shortcut="o"></kbd></button><div class="menu-section"><button id="move-up">Move up <kbd data-shortcut="Alt Shift ↑" data-vim-shortcut=""></kbd></button><button id="move-down">Move down <kbd data-shortcut="Alt Shift ↓" data-vim-shortcut=""></kbd></button><button id="rename-requirement">Rename ID</button><button id="delete-requirement">Delete requirement <kbd data-shortcut="Mod Backspace" data-vim-shortcut=""></kbd></button></div><div class="menu-section"><button id="undo-edit" disabled>Undo <kbd data-shortcut="Mod Z"></kbd></button><button id="redo-edit" disabled>Redo <kbd data-shortcut="Mod Shift Z"></kbd></button></div></div></details>
<details class="popup-menu"><summary>View</summary><div class="popover"><button id="unsaved-diff" class="develop-only" aria-pressed="false">Show changes since save</button><button id="view-toggle" class="diff-only">Diff view</button><button id="reset-view">Reset view</button><button id="browse-comments" class="comments-only" aria-expanded="false" aria-controls="review-panel">Browse comments</button><button id="open-settings" class="develop-only">Settings…</button></div></details>
<details class="popup-menu"><summary>Filter</summary><div class="popover"><button id="comments-only-rows" class="comments-only" aria-pressed="false">Comments only</button><button id="clear-filters">Clear filters</button><div class="diff-only menu-section"><button id="changes-only">Changes only</button><label><input type="checkbox" data-status="added"> Added</label><label><input type="checkbox" data-status="removed"> Removed</label><label><input type="checkbox" data-status="changed"> Changed</label><label><input type="checkbox" data-status="unchanged"> Unchanged</label></div></div></details>
<details id="columns-menu" class="popup-menu"><summary>Columns</summary><div class="popover"><div id="column-list"></div><div class="menu-section"><button id="show-all-columns">Show all</button><button id="default-columns">Defaults</button></div><div id="hidden-filter-warning" class="meta"></div></div></details>
<details class="popup-menu"><summary>Help</summary><div class="popover"><button id="show-help">Keyboard help <kbd data-shortcut="?"></kbd></button><button id="search-menus">Search menus <kbd data-shortcut="Alt /"></kbd></button></div></details><span class="spacer"></span><strong id="result-count" aria-live="polite"></strong></section>
<div class="table-wrap"><table id="requirements-table"><caption>Requirements report</caption><colgroup id="column-widths"></colgroup><thead><tr id="heading-row"></tr><tr id="filter-row" class="filter-row"></tr></thead><tbody id="requirements-body"></tbody></table></div></main>
<div id="comment-hover" class="floating-popover comment-tooltip" role="tooltip" hidden></div><div id="quick-comment" class="floating-popover" role="dialog" aria-label="Add comment" hidden></div><div id="value-filter-popover" class="floating-popover value-filter" role="group" aria-label="Filter values" hidden></div>
<aside id="review-panel" class="review-panel" hidden aria-label="Comments"><div class="sidebar-resize" data-sidebar-resize role="separator" aria-orientation="vertical" aria-label="Resize comments sidebar"></div><div class="review-head"><button id="back-comments" hidden aria-label="Back to all comments">Back</button><h2 id="review-title">Comments</h2><button id="close-review" aria-label="Close comments">Close</button></div><div class="review-body"><label class="sr-only" for="comment-search">Search comments</label><input id="comment-search" class="comment-search" placeholder="Search comments…"><div class="comment-actions"><label class="sr-only" for="reviewer-filter">Reviewer</label><select id="reviewer-filter"><option value="">All reviewers</option></select><label class="sr-only" for="comment-column-filter">Column</label><select id="comment-column-filter"><option value="">All columns</option></select><label class="sr-only" for="comment-status-filter">Status</label><select id="comment-status-filter"><option value="">All statuses</option><option value="added">Added</option><option value="removed">Removed</option><option value="changed">Changed</option><option value="unchanged">Unchanged</option></select></div><div id="comment-counts" class="meta"></div><div id="comment-list"></div></div></aside>
<dialog id="settings-dialog" class="help-dialog" aria-labelledby="settings-title"><div class="help-head"><h2 id="settings-title">Settings</h2><button id="close-settings">Done</button></div><div class="help-body"><label>Keyboard mode <select id="keyboard-mode"><option value="spreadsheet">Spreadsheet</option><option value="vim">Vim</option></select></label></div></dialog>
<dialog id="command-search" class="help-dialog" aria-labelledby="command-title"><div class="help-head"><h2 id="command-title">Search menus</h2><button id="close-command-search">Close</button></div><div class="help-body"><label class="sr-only" for="command-query">Search menu items</label><input type="search" id="command-query" placeholder="Search menu items…"><div id="command-results"></div><p id="command-empty" hidden>No matching commands.</p></div></dialog>
<dialog id="keyboard-help" class="help-dialog"><div class="help-head"><h2>Keyboard shortcuts</h2><button id="close-help">Close</button></div><div class="help-body"><p>Focus a table cell with <kbd>Tab</kbd>, then use:</p><table class="shortcut-table"><tbody><tr><th><kbd>Arrow keys</kbd> or <kbd>H</kbd><kbd>J</kbd><kbd>K</kbd><kbd>L</kbd></th><td>Move one cell</td></tr><tr><th><kbd>Home</kbd> / <kbd>End</kbd> or <kbd>0</kbd> / <kbd>$</kbd></th><td>First / last visible column</td></tr><tr><th><kbd>Ctrl</kbd>+<kbd>Home</kbd> / <kbd>Ctrl</kbd>+<kbd>End</kbd></th><td>First / last table corner. In Develop, Cmd also works and End skips the blank entry row.</td></tr><tr><th><kbd>g</kbd> / <kbd>G</kbd></th><td>First / last table row. In Develop, press <kbd>g</kbd> twice for the first row.</td></tr><tr><th><kbd>Page Up</kbd> / <kbd>Page Down</kbd></th><td>Move ten rows</td></tr><tr class="develop-only"><th><kbd>Tab</kbd> / <kbd>Shift</kbd>+<kbd>Tab</kbd></th><td>Next / previous cell, wrapping across rows. Tab leaves the grid at its edges.</td></tr><tr class="develop-only"><th><kbd>Ctrl/Cmd</kbd>+<kbd>Arrow</kbd></th><td>Jump to the end of a block of filled cells, across a gap to the next filled cell, or to the grid edge.</td></tr><tr class="develop-only"><th><kbd>Enter</kbd>, <kbd>F2</kbd>, or <kbd>i</kbd></th><td>Edit a non-ID cell. The i shortcut is for Vim mode.</td></tr><tr class="develop-only"><th><kbd>o</kbd> / <kbd>Shift</kbd>+<kbd>o</kbd></th><td>Insert a requirement below / above the selected requirement</td></tr><tr><th><kbd>C</kbd></th><td>Open comments for a non-ID cell</td></tr><tr><th><kbd>Ctrl/Cmd</kbd>+<kbd>Z</kbd> / <kbd>Ctrl/Cmd</kbd>+<kbd>Y</kbd></th><td>Undo / redo requirement edits in Develop mode. Ctrl/Cmd+Shift+Z also redoes.</td></tr><tr><th><kbd>/</kbd></th><td>Focus the selected column filter, or comment search when browsing comments</td></tr><tr><th><kbd>Down Arrow</kbd> or <kbd>Enter</kbd> in a filter</th><td>Move to that column in the first matching row</td></tr><tr><th><kbd>?</kbd></th><td>Open this help page</td></tr><tr><th><kbd>Escape</kbd></th><td>Cancel editing or close menus, popups, or the comments sidebar</td></tr></tbody></table><p>Click a menu name, then hover over another name to switch menus. Left and Right also switch menus. Down and Up move through items. Enter activates an item, Space toggles a checkbox, and Escape closes the menu. In Develop mode, choose View → Settings to switch between Spreadsheet and Vim shortcuts. Press Alt/Option+/ to search menus. In Spreadsheet mode, type on a selected editable cell to replace its value. In either mode, Tab or Shift+Tab applies the edit and moves to the next or previous cell. In Spreadsheet mode, Enter and Shift+Enter apply the edit and move down or up. Alt/Option+Enter inserts a newline, F2 starts with the caret at the end, and clicking another cell applies the edit. In Vim mode, Enter inserts a newline. Ctrl/Cmd+Enter applies the edit and stays on the cell in both modes. Column dividers can be dragged. Double-click a divider to auto-size the column on its left.</p></div></dialog>
<script id="reqtable-data" type="application/json">__DATA__</script><script>__JS__</script></body></html>"""


def _safe_json(data: dict[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_report(data: dict[str, Any]) -> str:
    meta = data["meta"]
    title = html.escape(meta["title"])
    document_mode = meta.get("documentMode", "review")
    description = (
        f"Diff: {html.escape(meta['oldFilename'])} → {html.escape(meta['newFilename'])} · Generated {html.escape(meta['generated'])}"
        if meta["mode"] == "diff"
        else f"Source: {html.escape(meta['newFilename'])} · Generated {html.escape(meta['generated'])}"
    )
    summary = ""
    if meta["mode"] == "diff":
        summary = "".join(
            f'<span class="badge {name}">{name.title()}: {meta["counts"][name]}</span>'
            for name in ("added", "removed", "changed", "unchanged")
        )
    if meta["ignoredColumns"]:
        summary += '<span class="badge">Ignored for change detection: ' + html.escape(", ".join(meta["ignoredColumns"])) + "</span>"
    embedded = {key: value for key, value in data.items() if key != "rows"}
    embedded["formatVersion"] = 2
    if meta["mode"] == "diff":
        embedded["diffStatus"] = {row["id"]: row["status"] for row in data["rows"]}
    return (
        TEMPLATE.replace("__TITLE__", title)
        .replace("__DOCUMENT_MODE_LABEL__", "Develop mode" if document_mode == "develop" else "Review mode")
        .replace("__DOCUMENT_MODE__", document_mode)
        .replace("__META__", description)
        .replace("__SUMMARY__", summary)
        .replace("__INITIALS__", html.escape(data["options"]["reviewerInitials"], quote=True))
        .replace("__CSS__", CSS)
        .replace("__DATA__", _safe_json(embedded))
        .replace("__JS__", JS)
    )
