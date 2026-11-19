"""The single page the GUI serves. It renders every form from /api/workflows, so field lists live only in reqtable.gui."""
from __future__ import annotations

import json

from .gui_page_gates import GATES_JS
from .gui_page_mapping import MAPPING_JS

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>reqtable</title>
<style>
:root {
  --bg: #f5f6f8; --surface: #ffffff; --surface-2: #eef0f4; --text: #1d2330; --muted: #5b6475;
  --line: #d9dde6; --accent: #2457d6; --accent-text: #ffffff; --accent-soft: #e3ebfd;
  --ok: #1a7f4b; --ok-soft: #e1f4ea; --bad: #b42318; --bad-soft: #fde8e6; --warn-soft: #fff4d6;
  --code-bg: #111827; --code-text: #e5e7eb; --radius: 10px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --surface: #1a1e27; --surface-2: #232834; --text: #e6e9ef; --muted: #9aa3b5;
    --line: #2f3645; --accent: #7aa2ff; --accent-text: #0c1020; --accent-soft: #212c4a;
    --ok: #5fd39a; --ok-soft: #173326; --bad: #ff8d82; --bad-soft: #3a1c1a; --warn-soft: #3b3217;
    --code-bg: #0b0e14; --code-text: #dfe3ec;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
header { padding: 18px 24px 6px; }
header h1 { margin: 0; font-size: 22px; }
header p { margin: 2px 0 0; color: var(--muted); }
.layout { display: grid; grid-template-columns: 270px minmax(0, 1fr) 340px; gap: 20px; padding: 16px 24px 40px; align-items: start; }
@media (max-width: 1150px) { .layout { grid-template-columns: 250px minmax(0, 1fr); } #panel { grid-column: 1 / -1; } }
@media (max-width: 760px) { .layout { grid-template-columns: minmax(0, 1fr); padding: 12px 16px 32px; } header { padding: 16px 16px 0; } }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 10px; }
.card, #nav button.task { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
.card { padding: 18px; margin-bottom: 16px; }
#nav { display: flex; flex-direction: column; gap: 8px; }
#nav button.task { text-align: left; padding: 12px 14px; cursor: pointer; color: var(--text); font: inherit; }
#nav button.task:hover { border-color: var(--accent); }
#nav button.task[aria-current="true"] { border-color: var(--accent); background: var(--accent-soft); }
#nav .title { display: block; font-weight: 600; }
#nav .when { display: block; color: var(--muted); font-size: 13px; margin-top: 2px; }
#nav h3.group { margin: 12px 0 0; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
#nav h3.group:first-child { margin-top: 0; }
.intro ol { margin: 8px 0 0; padding-left: 20px; } .intro li { margin: 4px 0; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.cards .opt { position: relative; display: block; margin: 0; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); cursor: pointer; font-weight: 400; }
.cards .opt:hover { border-color: var(--accent); }
.cards .opt:has(input:checked) { border-color: var(--accent); background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent); }
.cards .opt:has(input:focus-visible) { outline: 3px solid var(--accent); outline-offset: 1px; }
.cards .opt input { position: absolute; opacity: 0; pointer-events: none; }
.cards .opt .opt-title { display: block; font-weight: 700; }
.cards .opt .opt-desc { display: block; color: var(--muted); font-size: 13px; margin-top: 2px; }
.preview { margin-top: 8px; font-size: 13px; }
.preview table, table.grid { border-collapse: collapse; width: 100%; font-size: 13px; }
.preview { overflow-x: auto; }
.preview th, .preview td, table.grid th, table.grid td { border: 1px solid var(--line); padding: 3px 8px; text-align: left; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview th, table.grid th { background: var(--surface-2); font-weight: 600; }
.preview .count { color: var(--muted); margin: 0 0 4px; } .preview .count strong { color: var(--text); }
.check { display: flex; gap: 8px; align-items: baseline; margin: 2px 0; font-weight: 400; }
.check input { width: auto; }
.badge { display: inline-block; font-size: 11px; padding: 0 6px; border-radius: 99px; background: var(--surface-2); color: var(--muted); margin-left: 6px; }
.badge.strict { background: var(--warn-soft); color: var(--text); }
.waiver { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(160px, 2fr) auto; gap: 6px; margin: 0 0 6px; }
ul.plain { margin: 6px 0 0; padding-left: 18px; font-size: 13px; }
.banner.soft { background: var(--warn-soft); }
.banner.fail { background: var(--bad-soft); white-space: pre-wrap; }
.waiveoffer { margin-top: 10px; }
.waiveoffer .actions { margin-top: 6px; }
.srcrow { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin: 0 0 10px; background: var(--surface); }
.srcrow .top { display: grid; grid-template-columns: minmax(0, 1fr) minmax(160px, 220px) 120px; gap: 10px; align-items: end; }
@media (max-width: 760px) { .srcrow .top { grid-template-columns: minmax(0, 1fr); } }
.srcrow .nm { font-weight: 600; word-break: break-word; } .srcrow .sub { color: var(--muted); font-size: 12px; }
.srcrow label.mini { font-size: 12px; margin: 0 0 2px; color: var(--muted); font-weight: 500; }
table.cols { width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 14px; }
table.cols th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 500; padding: 2px 6px; }
table.cols td { padding: 3px 6px; vertical-align: middle; border-top: 1px solid var(--line); }
table.cols td.src { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; word-break: break-word; }
table.cols select, table.cols input { padding: 4px 6px; }
pre.json { margin: 0; padding: 12px 14px; background: var(--code-bg); color: var(--code-text); border-radius: 8px; overflow: auto; max-height: 340px; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; user-select: all; }
.field { margin: 0 0 16px; } .field[hidden] { display: none; }
.field label { display: block; font-weight: 600; margin-bottom: 4px; }
.req { font-weight: 500; font-size: 12px; color: var(--accent); margin-left: 6px; }
.help { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
.note { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
input[type=text], input[type=number], select {
  width: 100%; padding: 8px 10px; font: inherit; color: var(--text); background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px;
}
.pathrow { display: flex; gap: 8px; } .pathrow input { flex: 1; min-width: 0; }
button { font: inherit; cursor: pointer; border-radius: 8px; border: 1px solid var(--line); background: var(--surface-2); color: var(--text); padding: 8px 14px; }
button:hover:not(:disabled) { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: not-allowed; }
button.primary { background: var(--accent); color: var(--accent-text); border-color: var(--accent); font-weight: 600; }
button.small { padding: 3px 9px; font-size: 13px; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 1px; }
details.more { margin: 8px 0 16px; border-top: 1px solid var(--line); padding-top: 12px; }
details.more > summary { cursor: pointer; font-weight: 600; color: var(--accent); margin-bottom: 12px; }
.tabs { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.tabs button { border: 0; border-radius: 0; background: var(--surface); padding: 4px 12px; font-size: 13px; }
.tabs button[aria-pressed="true"] { background: var(--accent); color: var(--accent-text); }
.commandbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
pre.command, pre.output { margin: 0; padding: 12px 14px; background: var(--code-bg); color: var(--code-text); border-radius: 8px; overflow-x: auto; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre; user-select: all; }
pre.output { user-select: text; max-height: 320px; overflow: auto; }
.hint { color: var(--muted); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.result { margin-top: 14px; }
.banner { padding: 12px 14px; border-radius: 8px; margin-bottom: 10px; }
.banner.ok { background: var(--ok-soft); } .banner.bad { background: var(--bad-soft); }
.banner strong { display: block; }
.banner .cli-error { display: block; margin-top: 6px; font: 600 14px ui-monospace, Menlo, Consolas, monospace; color: var(--bad); word-break: break-word; }
.banner.warn { background: var(--warn-soft); font-size: 14px; }
.steps { list-style: none; margin: 0 0 12px; padding: 0; }
.step { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 8px; background: var(--surface); }
.step .head { display: flex; align-items: center; gap: 6px; }
.step .head .name { flex: 1; font-weight: 600; min-width: 0; }
.step pre { margin: 8px 0 0; padding: 8px 10px; background: var(--code-bg); color: var(--code-text); border-radius: 6px; font: 12px/1.45 ui-monospace, Menlo, Consolas, monospace; overflow-x: auto; }
.empty { color: var(--muted); }
dialog { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); color: var(--text); padding: 0; width: min(640px, 94vw); }
dialog::backdrop { background: rgba(0,0,0,.45); }
.dlg { padding: 16px; display: flex; flex-direction: column; gap: 10px; max-height: 80vh; }
.dlg .where { font: 13px ui-monospace, Menlo, Consolas, monospace; word-break: break-all; color: var(--muted); }
.dlg .places { display: flex; gap: 6px; flex-wrap: wrap; }
.dlg ul { list-style: none; margin: 0; padding: 0; overflow: auto; border: 1px solid var(--line); border-radius: 8px; min-height: 120px; flex: 1; }
.dlg li button { display: block; width: 100%; text-align: left; border: 0; border-radius: 0; background: transparent; padding: 8px 12px; }
.dlg li button:hover { background: var(--accent-soft); }
.dlg .foot { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; align-items: center; }
.dlg .foot input { flex: 1; min-width: 160px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
</head>
<body>
<header>
  <h1>reqtable</h1>
  <p>Turn requirements spreadsheets into reports. Every step shows the exact command it runs, so you can repeat it later.</p>
</header>
<div class="layout">
  <nav aria-label="Tasks"><h2>What do you want to do?</h2><div id="nav"></div></nav>
  <main id="main"></main>
  <aside id="panel" class="card" aria-label="Your workflow"></aside>
</div>
<dialog id="picker" aria-label="Choose a file or folder"></dialog>
<div class="sr" role="status" aria-live="polite" id="live"></div>
<script>
const TOKEN = __TOKEN__;
const $ = (id) => document.getElementById(id);
const freshLookups = () => ({
  columns: [], rowCount: 0, previewRows: [], tables: [], sheets: [], columnsError: "", tablesError: "", tablesLoaded: false, configMaps: false,
  gates: [], gatesError: "", store: "", baselines: [], baselinesError: "", systems: [],
});
const state = { workflows: [], mapping: null, workdir: "", current: null, values: {}, shell: "sh", steps: [], preview: null, rows: {}, lookups: freshLookups() };

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid);
  return el;
}

function fill(box, ...kids) { box.replaceChildren(...kids.flat().filter((k) => k != null)); }

async function api(path, body) {
  const options = { headers: { "X-Reqtable-Token": TOKEN } };
  if (body !== undefined) { options.method = "POST"; options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({ error: "The reqtable server sent something unexpected." }));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

const stepsKey = () => "reqtable.steps:" + state.workdir;
function remember() {
  try { localStorage.setItem(stepsKey(), JSON.stringify(state.steps)); localStorage.setItem("reqtable.shell", state.shell); } catch (e) {}
}
function restore() {
  try {
    const steps = JSON.parse(localStorage.getItem(stepsKey()) || "[]");
    if (Array.isArray(steps)) state.steps = steps.filter((s) => s && s.workflow && s.sh && s.powershell);
    const shell = localStorage.getItem("reqtable.shell");
    if (shell === "sh" || shell === "powershell") state.shell = shell;
  } catch (e) {}
}

const workflow = () => state.workflows.find((w) => w.id === state.current);
const shellName = () => (state.shell === "sh" ? "macOS / Linux (sh)" : "Windows (PowerShell)");

function announce(text) { $("live").textContent = text; }

async function copyText(text, button) {
  let done = false;
  try { await navigator.clipboard.writeText(text); done = true; } catch (e) {}
  if (!done) {
    const area = h("textarea", { class: "sr" }); area.value = text; document.body.append(area); area.select();
    try { done = document.execCommand("copy"); } catch (e) {}
    area.remove();
  }
  const old = button.textContent;
  button.textContent = done ? "Copied" : "Press Ctrl+C to copy";
  setTimeout(() => { button.textContent = old; }, 1800);
}

function shellTabs(onChange) {
  const tab = (value, label) => h("button", { type: "button", "aria-pressed": String(state.shell === value), onclick: () => { state.shell = value; remember(); onChange(); } }, label);
  return h("div", { class: "tabs", role: "group", "aria-label": "Shell" }, tab("sh", "macOS / Linux"), tab("powershell", "Windows"));
}

function renderNav() {
  const nav = $("nav"); nav.replaceChildren();
  let group = null;
  for (const w of state.workflows) {
    if (w.group !== group) { group = w.group; nav.append(h("h3", { class: "group" }, group)); }
    nav.append(h("button", { class: "task", type: "button", "aria-current": String(w.id === state.current), onclick: () => choose(w.id) },
      h("span", { class: "title" }, w.title), h("span", { class: "when" }, w.when)));
  }
}

function renderIntro() {
  $("main").replaceChildren(h("div", { class: "card intro" },
    h("h2", {}, "Welcome"),
    h("p", {}, "Pick a task on the left. You will fill in a short form and press Run. reqtable then does the work on your computer; nothing is uploaded."),
    h("ol", {},
      h("li", {}, "Choose your spreadsheet, and where to save the result."),
      h("li", {}, "Check the command shown under the form. It is exactly what runs, and you can copy it."),
      h("li", {}, "Add steps to your workflow and save them as a script to repeat them later.")),
    h("p", { class: "note" }, "To edit requirements in the browser, choose “Edit requirements (Develop report)”. To keep a frozen record of a review, look under “Gates and sign-off”.")));
}

function isWorkbook(v) { return /\.xlsx$/i.test(v || ""); }
function workbookPath() {
  const values = state.values[state.current];
  for (const name of workflow().table_inputs) if (isWorkbook(values[name])) return values[name];
  return "";
}

const PANELS = {};
let panelRefresh = null;

async function choose(id) {
  state.current = id;
  const w = workflow();
  renderNav();
  state.rows = {}; state.preview = null; panelRefresh = null;
  if (w.panel !== "form") {
    PANELS[w.panel](w); renderPanel();
    if (window.innerWidth < 760) $("main").scrollIntoView({ behavior: "smooth" });
    return;
  }
  if (!state.values[id]) {
    state.values[id] = {};
    for (const f of w.fields) if (f.default) state.values[id][f.name] = f.default;
  }
  state.lookups = freshLookups();
  renderForm();
  if (window.innerWidth < 760) $("main").scrollIntoView({ behavior: "smooth" });
  lookupTables(); lookupColumns(); lookupGateData(); refreshPreview();
}

function renderForm() {
  const w = workflow();
  const main = h("div", {});
  const form = h("div", { class: "card" }, h("h2", {}, w.title), h("p", { class: "hint" }, w.summary));
  if (w.fixed.length) form.append(h("p", { class: "note", style: "margin:6px 0 14px" }, "This card always runs with ", h("code", {}, w.fixed.join(" ")), "."));
  const more = h("details", { class: "more" }, h("summary", {}, "More options"));
  let advanced = 0;
  for (const f of w.fields) {
    const row = buildField(f);
    state.rows[f.name] = row;
    if (f.advanced) { more.append(row.wrap); advanced++; } else form.append(row.wrap);
  }
  if (advanced) form.append(more);
  const commandBox = h("div", { class: "card", id: "commandcard" });
  main.append(form, commandBox, h("div", { id: "result" }));
  $("main").replaceChildren(main);
  syncVisibility(); renderColumns(); renderTableChoices(); renderLookups(); renderPreview();
}

function setValue(f, value) { state.values[state.current][f.name] = value; onChange(f); }

function radioCards(f, id, value, set) {
  const group = h("div", { class: "cards", role: "radiogroup", "aria-labelledby": id + "-label" });
  for (const [v, text] of f.choices) {
    const [title, ...rest] = text.split(": ");
    const input = h("input", { type: "radio", name: id, value: v, onchange: () => set(v) });
    input.checked = value === v;
    group.append(h("label", { class: "opt" }, input, h("span", { class: "opt-title" }, title), rest.length ? h("span", { class: "opt-desc" }, rest.join(": ")) : null));
  }
  return group;
}

function buildField(f) {
  const id = "f-" + f.name;
  const wrap = h("div", { class: "field" });
  const required = f.required ? h("span", { class: "req" }, "required") : null;
  const label = f.kind === "radio" ? h("div", { class: "lab", id: id + "-label", style: "font-weight:600;margin-bottom:6px" }, f.label, required) : h("label", { for: id }, f.label, required);
  const row = { field: f, wrap, control: null, extra: null, preview: null };
  const set = (value) => setValue(f, value);
  const value = state.values[state.current][f.name] || "";
  if (f.kind === "open" || f.kind === "save") {
    const input = h("input", { type: "text", id, value, spellcheck: "false", oninput: (e) => set(e.target.value), placeholder: f.kind === "open" ? "Choose a file…" : "Choose where to save…" });
    input.value = value;
    row.control = input;
    wrap.append(label, h("div", { class: "pathrow" }, input,
      h("button", { type: "button", onclick: () => pickPath(f, input, set) }, f.kind === "open" ? "Browse…" : "Choose location…")));
  } else if (f.kind === "radio") {
    wrap.append(label, radioCards(f, id, value, set));
  } else if (f.kind === "choice" || f.kind === "flag") {
    const select = h("select", { id, onchange: (e) => set(e.target.value) });
    const options = f.choices.slice();
    if (!f.default && !options.some(([v]) => v === "")) options.unshift(["", "Default"]);
    for (const [v, text] of options) select.append(h("option", { value: v }, text));
    select.value = value;
    row.control = select;
    wrap.append(label, select);
  } else if (f.kind === "column") {
    row.extra = h("div", {}); row.preview = h("div", { class: "preview" });
    wrap.append(label, row.extra);
  } else if (f.kind === "table" || f.kind === "sheet" || LOOKUP_KINDS.has(f.kind)) {
    row.extra = h("div", {});
    wrap.append(label, row.extra);
  } else {
    const input = h("input", { type: f.kind === "number" ? "number" : "text", id, min: f.kind === "number" ? "1" : null, oninput: (e) => set(e.target.value), spellcheck: "false" });
    input.value = value;
    row.control = input;
    wrap.append(label, input);
  }
  wrap.append(h("p", { class: "help" }, f.help));
  row.note = h("p", { class: "note" }); wrap.append(row.note);
  if (row.preview) wrap.append(row.preview);
  return row;
}

function syncVisibility() {
  const workbook = !!workbookPath();
  const values = state.values[state.current] || {};
  for (const row of Object.values(state.rows)) {
    const f = row.field;
    row.wrap.hidden = (f.xlsx_only && !workbook) || (!!f.requires && !values[f.requires]) || (f.kind === "system" && !systemNeeded());
  }
}

let timers = {};
function later(name, fn, ms) { clearTimeout(timers[name]); timers[name] = setTimeout(fn, ms); }

const LOOKUP_FIELDS = ["input", "new", "table", "sheet", "header_row", "id_column", "config", "traceability", "encoding", "delimiter"];

function onChange(f) {
  const values = state.values[state.current];
  if (f.name === "table" && values.table) { values.sheet = ""; values.header_row = ""; }
  if (f.name === "sheet" && values.sheet) values.table = "";
  if (f.name === "sheet" && !values.sheet) values.header_row = "";
  if (f.kind === "gate" && !systemNeeded()) values.system = "";
  syncVisibility();
  if (f.kind === "open") { later("tables", lookupTables, 200); }
  if (f.kind === "open" || ["table", "sheet", "header_row", "encoding", "delimiter", "config"].includes(f.name)) later("columns", lookupColumns, 250);
  if (["table", "sheet", "config"].includes(f.name)) { renderTableChoices(); renderColumns(); }
  if (LOOKUP_FIELDS.includes(f.name)) later("lookups", lookupGateData, 300);
  if (LOOKUP_KINDS.has(f.kind)) renderLookups();
  refreshPreview();
}

function textOrSelect(row, name, items, placeholder, blankLabel, emptyLabel) {
  const values = state.values[state.current];
  const holder = row.extra; holder.replaceChildren();
  const id = "f-" + name;
  const set = (v) => setValue(row.field, v);
  if (!items.length && emptyLabel) {
    holder.append(h("select", { id, disabled: true }, h("option", {}, emptyLabel)));
  } else if (items.length) {
    const select = h("select", { id, onchange: (e) => set(e.target.value) }, h("option", { value: "" }, blankLabel));
    for (const [v, label] of items) select.append(h("option", { value: v }, label));
    if (values[name] && !items.some(([v]) => v === values[name])) select.append(h("option", { value: values[name] }, values[name]));
    select.value = values[name] || "";
    holder.append(select);
  } else {
    const input = h("input", { type: "text", id, placeholder, spellcheck: "false", oninput: (e) => set(e.target.value) });
    input.value = values[name] || "";
    holder.append(input);
  }
}

function tableState() {
  const values = state.values[state.current] || {};
  const L = state.lookups;
  if (!workbookPath() || values.table || values.sheet) return { kind: "chosen" };
  if (L.configMaps) return { kind: "config" };
  if (L.tablesError) return { kind: "unknown" };
  if (!L.tablesLoaded) return { kind: "loading" };
  if (L.tables.length === 1) return { kind: "single", table: L.tables[0].name };
  return { kind: "choose" };
}

function renderColumns() {
  const L = state.lookups; const t = tableState();
  for (const row of Object.values(state.rows)) if (row.field.kind === "column") {
    const holder = row.extra;
    if (t.kind === "choose" || t.kind === "loading") {
      holder.replaceChildren(h("select", { id: "f-" + row.field.name, disabled: true }, h("option", {}, t.kind === "choose" ? "Choose a table or sheet first" : "Looking inside the workbook…")));
      row.note.textContent = t.kind === "choose" ? "This workbook has " + (L.tables.length === 0 ? "no tables" : L.tables.length + " tables") + ". Pick one of its tables or sheets above, then the columns appear here." : "";
      row.preview.replaceChildren();
      continue;
    }
    if (t.kind === "config") {
      textOrSelect(row, row.field.name, [], "Leave empty to use the ID column named in your settings file", "");
      row.note.textContent = "Your settings file decides which tables are read, so there is no table to choose here."; row.preview.replaceChildren();
      continue;
    }
    textOrSelect(row, row.field.name, L.columns.map((c) => [c, c]), "Type the column name, for example ID", "Choose a column…");
    row.note.textContent = L.columnsError || (t.kind === "single" ? "Reading table “" + t.table + "”, the only table in this workbook." : "");
    renderPreviewTable(row);
  }
}

function renderPreviewTable(row) {
  const L = state.lookups; const box = row.preview; box.replaceChildren();
  if (!L.columns.length) return;
  const rows = L.previewRows || [];
  const table = h("table", {}, h("thead", {}, h("tr", {}, L.columns.map((c) => h("th", {}, c)))),
    h("tbody", {}, rows.map((r) => h("tr", {}, L.columns.map((_, i) => h("td", { title: r[i] || "" }, r[i] || ""))))));
  box.append(h("p", { class: "count" }, h("strong", {}, "Preview: " + L.rowCount + " row" + (L.rowCount === 1 ? "" : "s")), rows.length < L.rowCount ? " (first " + rows.length + " shown)" : ""), table);
}

function renderTableChoices() {
  for (const row of Object.values(state.rows)) {
    if (row.field.kind === "table") textOrSelect(row, row.field.name, state.lookups.tables.map((t) => [t.name, t.name + "  (sheet " + t.sheet + ")"]), "Table name", "Automatic", state.lookups.tablesLoaded ? "This workbook has no tables" : "");
    if (row.field.kind === "sheet") textOrSelect(row, row.field.name, state.lookups.sheets.map((s) => [s.name, s.name]), "Sheet name", "None");
    if (row.field.kind === "table" || row.field.kind === "sheet") row.note.textContent = state.lookups.tablesError;
  }
}

let tablesSeq = 0;
async function lookupTables() {
  const path = workbookPath();
  const id = state.current;
  const L = state.lookups;
  const seq = ++tablesSeq;
  if (!path) { L.tables = []; L.sheets = []; L.tablesError = ""; L.tablesLoaded = false; L.configMaps = false; renderTableChoices(); renderColumns(); return; }
  try {
    const query = new URLSearchParams({ path, config: state.values[id].config || "" });
    const data = await api("/api/tables?" + query);
    if (id !== state.current || seq !== tablesSeq) return;
    L.tables = data.tables; L.sheets = data.sheets; L.tablesError = data.error || ""; L.tablesLoaded = !data.error; L.configMaps = data.config_maps_workbook;
  } catch (e) { if (seq !== tablesSeq) return; L.tablesError = e.message; L.tables = []; L.sheets = []; L.tablesLoaded = false; L.configMaps = false; }
  renderTableChoices(); renderColumns(); lookupColumns();
}

let columnsSeq = 0;
async function lookupColumns() {
  const w = workflow(); const id = state.current; const values = state.values[id]; const L = state.lookups;
  const path = values[w.column_source];
  const clear = () => { L.columns = []; L.columnsError = ""; L.rowCount = 0; L.previewRows = []; renderColumns(); };
  if (!path || ["choose", "loading", "config"].includes(tableState().kind)) { clear(); return; }
  const query = new URLSearchParams({ path });
  for (const name of ["table", "sheet", "header_row", "encoding", "delimiter", "config"]) if (values[name]) query.set(name, values[name]);
  const seq = ++columnsSeq;
  try {
    const data = await api("/api/columns?" + query);
    if (id !== state.current || seq !== columnsSeq) return;
    L.columns = data.columns; L.rowCount = data.row_count; L.previewRows = data.rows;
    L.columnsError = data.error ? "Could not list the columns yet: " + data.error : "";
    const idField = w.fields.find((f) => f.kind === "column");
    if (idField && !values[idField.name] && data.id_guess) { values[idField.name] = data.id_guess; refreshPreview(); lookupGateData(); }
  } catch (e) { if (seq !== columnsSeq) return; L.columns = []; L.columnsError = e.message; }
  renderColumns();
}

let previewSeq = 0;
function refreshPreview() { later("preview", fetchPreview, 120); }
async function fetchPreview() {
  const seq = ++previewSeq; const id = state.current;
  if (!id || workflow().panel !== "form") return;
  try {
    const data = await api("/api/command", { workflow: id, values: state.values[id] });
    if (seq !== previewSeq) return;
    state.preview = data;
  } catch (e) { if (seq !== previewSeq) return; state.preview = { error: e.message }; }
  renderPreview();
}

function renderPreview() {
  const box = $("commandcard"); if (!box) return;
  const p = state.preview;
  const ready = p && !p.error;
  const run = h("button", { class: "primary", type: "button", id: "runbtn", disabled: !ready, onclick: runNow }, "Run");
  const add = h("button", { type: "button", disabled: !ready, onclick: () => addStep(true) }, "Add to workflow");
  const text = ready ? p[state.shell] : "";
  const replaces = ready && p.replaces.length
    ? h("div", { class: "banner warn" }, "Run will replace " + p.replaces.map(shownPath).join(", ") + ", which already exists. Choose another name to keep it.")
    : null;
  fill(box,
    h("h2", {}, "The command behind this"),
    h("div", { class: "commandbar" }, shellTabs(renderPreview),
      h("button", { class: "small", type: "button", disabled: !ready, onclick: (e) => copyText(text, e.target) }, "Copy command")),
    ready ? h("pre", { class: "command", tabindex: "0", "aria-label": "Command for " + shellName() }, text)
          : h("p", { class: "hint" }, p && p.error ? p.error : "Fill in the form above to see the command."),
    replaces, h("div", { class: "actions" }, run, add));
  renderPanel();
}

function stepFromForm() {
  const w = workflow();
  return { id: String(Date.now()) + Math.random().toString(16).slice(2), workflow: w.id, title: w.title,
    values: JSON.parse(JSON.stringify(state.values[w.id])), sh: state.preview.sh, powershell: state.preview.powershell, argv: state.preview.argv };
}

function pushStep(step, announceIt) {
  const last = state.steps[state.steps.length - 1];
  if (last && last.workflow === step.workflow && JSON.stringify(last.argv) === JSON.stringify(step.argv)) return false;
  state.steps.push(step); remember(); renderPanel();
  if (announceIt) announce("Added to your workflow: " + step.title);
  return true;
}
function addStep(announceIt) { return pushStep(stepFromForm(), announceIt); }

async function runNow() {
  const id = state.current; const w = workflow();
  const button = $("runbtn"); button.disabled = true; button.textContent = "Running…";
  $("result").replaceChildren(h("div", { class: "card" }, h("p", { class: "hint" }, "Running. Big spreadsheets can take a moment…")));
  let data;
  try { data = await api("/api/run", { workflow: id, values: state.values[id] }); }
  catch (e) { data = { error: e.message }; }
  if (state.current !== id) return;
  button.disabled = false; button.textContent = "Run";
  renderResult(w, data);
}

const EXIT_WORDS = { 2: "reqtable could not use these settings.", 3: "reqtable could not read an input file.", 4: "reqtable could not write the result file." };

function outputTable(w, text) {
  const lines = text.split("\n").filter((l) => l.trim());
  if (!lines.length || !lines.every((l) => l.includes("\t"))) return h("pre", { class: "output" }, text);
  return h("table", { class: "grid" }, h("thead", {}, h("tr", {}, w.table.map((c) => h("th", {}, c)))),
    h("tbody", {}, lines.map((l) => h("tr", {}, l.split("\t").map((c) => h("td", { title: c }, c))))));
}

function renderResult(w, data) {
  const box = $("result");
  if (data.error) { box.replaceChildren(h("div", { class: "card" }, h("div", { class: "banner bad" }, h("strong", {}, "That did not run."), h("span", { class: "cli-error" }, data.error)))); return; }
  const stderr = data.stderr || "";
  const errors = stderr.split("\n").filter((l) => /^error:/.test(l));
  const warnings = stderr.split("\n").filter((l) => /^warning:/.test(l));
  const outcome = Object.fromEntries(w.outcomes)[data.exit_code];
  const ok = data.exit_code === 0;
  const answer = !ok && outcome;
  const card = h("div", { class: "card" });
  if (ok) {
    const saved = data.outputs.length ? "Saved: " + data.outputs.map(shownPath).join(", ") : "";
    card.append(h("div", { class: "banner ok", role: "status" }, h("strong", {}, outcome || "Done."), saved, w.recorded ? h("div", {}, w.recorded) : null));
    const added = addStep(false);
    if (added) card.append(h("p", { class: "note" }, "This step was added to your workflow."));
  } else if (answer) {
    card.append(h("div", { class: "banner soft", role: "status" }, h("strong", {}, outcome + "."), h("span", {}, "That is an answer, not a failure. Nothing was recorded and nothing was added to your workflow.")));
  } else {
    const words = data.exit_code === null ? "reqtable stopped because this took too long." : (EXIT_WORDS[data.exit_code] || "Something went wrong.");
    card.append(h("div", { class: "banner bad", role: "alert" }, h("strong", {}, words + " Nothing was added to your workflow."),
      errors.map((e) => h("span", { class: "cli-error" }, e)), errors.length ? null : h("span", {}, "See the details below.")));
  }
  if (warnings.length) card.append(h("div", { class: "banner warn" }, h("strong", {}, "Worth a look"), warnings.map((l) => h("div", {}, l.replace(/^warning:\s*/, "")))));
  const html = data.outputs.find((p) => /\.html$/i.test(p));
  if (ok && html && w.id !== "gate_package") card.append(h("div", { class: "actions" }, h("button", { class: "primary", type: "button", onclick: (e) => openReport(html, e.target) }, "Open report")));
  if (ok && html && w.id === "gate_package") card.append(h("div", { class: "actions" }, h("button", { class: "primary", type: "button", onclick: (e) => openReport(html, e.target) }, "Open package")));
  if (data.stdout.trim()) card.append(h("h2", { style: "margin-top:14px" }, "Result"), w.table.length && ok ? outputTable(w, data.stdout) : h("pre", { class: "output" }, data.stdout));
  const rest = stderr.split("\n").filter((l) => l && !/^(error|warning):/.test(l)).join("\n");
  if (answer && rest) card.append(h("h2", { style: "margin-top:14px" }, "Why"), h("pre", { class: "output" }, rest));
  if (!ok && !answer && rest) card.append(h("details", {}, h("summary", {}, "Technical details"), h("pre", { class: "output" }, rest)));
  if (data.blocked && data.blocked.length) card.append(waiveOffer(w, data.blocked));
  box.replaceChildren(card);
  renderPanel();
  announce(ok ? "Done" : (answer ? outcome : "Failed"));
  refreshPreview();
  if (ok && (w.recorded || w.id === "create_baseline")) lookupGateData();
}

async function openReport(path, button) {
  try { await api("/api/open", { path }); } catch (e) { button.textContent = e.message; }
}

function renderPanel() {
  const panel = $("panel");
  const steps = state.steps;
  const list = h("ol", { class: "steps" });
  steps.forEach((s, i) => {
    const move = (d) => { const j = i + d; [steps[i], steps[j]] = [steps[j], steps[i]]; remember(); renderPanel(); };
    list.append(h("li", { class: "step" },
      h("div", { class: "head" }, h("span", { class: "name" }, (i + 1) + ". " + s.title),
        h("button", { class: "small", type: "button", "aria-label": "Move step " + (i + 1) + " up", disabled: i === 0, onclick: () => move(-1) }, "↑"),
        h("button", { class: "small", type: "button", "aria-label": "Move step " + (i + 1) + " down", disabled: i === steps.length - 1, onclick: () => move(1) }, "↓"),
        h("button", { class: "small", type: "button", "aria-label": "Remove step " + (i + 1), onclick: () => { steps.splice(i, 1); remember(); renderPanel(); } }, "✕")),
      h("pre", {}, s[state.shell])));
  });
  fill(panel,
    h("h2", {}, "Your workflow"),
    steps.length ? list : h("p", { class: "empty" }, "Steps you run or add show up here. Put them in order, then save them as a script to repeat them any time."),
    h("div", { class: "commandbar" }, shellTabs(() => { renderPreview(); if (panelRefresh) panelRefresh(); })),
    h("div", { class: "actions", style: "margin-top:0" },
      h("button", { type: "button", disabled: !steps.length, onclick: (e) => withScript((s) => copyText(s.script, e.target)) }, "Copy script"),
      h("button", { type: "button", disabled: !steps.length, onclick: () => withScript(saveScript) }, "Save script"),
      h("button", { class: "small", type: "button", disabled: !steps.length, onclick: () => { state.steps = []; remember(); renderPanel(); } }, "Clear")));
}

async function withScript(use) {
  try { use(await api("/api/script", { steps: state.steps.map((s) => ({ workflow: s.workflow, values: s.values })), shell: state.shell })); }
  catch (e) { announce(e.message); alert(e.message); }
}
function saveScript(data) {
  const url = URL.createObjectURL(new Blob([data.script], { type: "text/plain" }));
  const link = h("a", { href: url, download: data.filename }); document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function pickPath(field, input, set) {
  const dialog = $("picker");
  const startValue = input.value.trim();
  const slash = Math.max(startValue.lastIndexOf("/"), startValue.lastIndexOf("\\"));
  let folder = slash >= 0 ? startValue.slice(0, slash) : "";
  const exts = field.extensions.join(",");
  const choose = (path) => { const shown = shownPath(path); input.value = shown; set(shown); dialog.close(); };
  const load = async (path) => {
    let data;
    try { data = await api("/api/browse?path=" + encodeURIComponent(path) + "&ext=" + encodeURIComponent(exts)); }
    catch (e) { dialog.querySelector(".dlg .err").textContent = e.message; return; }
    const sep = data.path.includes("\\") ? "\\" : "/";
    const name = h("input", { type: "text", "aria-label": "File name", value: field.kind === "save" ? (baseName(input.value) || field.default) : "" });
    const list = h("ul", {});
    if (!data.entries.length) list.append(h("li", { class: "empty", style: "padding:10px 12px" }, "Nothing to show here."));
    for (const e of data.entries) {
      list.append(h("li", {}, h("button", { type: "button", onclick: () => e.dir ? load(e.path) : (field.kind === "open" ? choose(e.path) : (name.value = e.name)) }, (e.dir ? "📁 " : "📄 ") + e.name)));
    }
    const foot = h("div", { class: "foot" });
    if (field.kind === "save") foot.append(name, h("button", { class: "primary", type: "button", onclick: () => name.value.trim() && choose(data.path.replace(/[\\/]$/, "") + sep + name.value.trim()) }, "Save here"));
    foot.append(h("button", { type: "button", onclick: () => dialog.close() }, "Cancel"));
    dialog.replaceChildren(h("div", { class: "dlg" },
      h("strong", {}, field.kind === "open" ? "Choose " + field.label.toLowerCase() : "Choose where to save"),
      h("div", { class: "places" }, data.places.map((p) => h("button", { class: "small", type: "button", onclick: () => load(p.path) }, p.name)),
        h("button", { class: "small", type: "button", disabled: !data.parent, onclick: () => load(data.parent) }, "↑ Up one folder")),
      h("div", { class: "where" }, data.path), h("div", { class: "err note" }), list, foot));
  };
  dialog.replaceChildren(h("div", { class: "dlg" }, h("div", { class: "err note" })));
  dialog.showModal();
  load(folder || state.workdir);
}
function baseName(path) { return path.split(/[\\/]/).pop(); }
function shownPath(path) {
  const root = state.workdir.replace(/[\\/]$/, "");
  return path.startsWith(root) && /^[\\/]/.test(path.slice(root.length)) ? path.slice(root.length + 1) : path;
}

async function start() {
  try {
    const data = await api("/api/workflows");
    state.workflows = data.workflows; state.workdir = data.workdir; state.mapping = data.mapping;
    restore();
  } catch (e) {
    $("main").replaceChildren(h("div", { class: "card" }, h("div", { class: "banner bad" }, h("strong", {}, "Could not reach reqtable."), "Close this tab and start it again with --gui.")));
    return;
  }
  renderNav(); renderIntro(); renderPanel();
}
__MODULES__
start();
</script>
</body>
</html>
"""


def render_page(token: str) -> str:
    return PAGE.replace("__MODULES__", GATES_JS + MAPPING_JS).replace("__TOKEN__", json.dumps(token))
