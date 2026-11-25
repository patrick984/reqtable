"""Page script shared by every screen: state, DOM helpers, the API call, browser storage, clipboard and the file picker."""

CORE_JS = r"""
const TOKEN = __TOKEN__;
const $ = (id) => document.getElementById(id);
const freshLookups = () => ({
  columns: [], rowCount: 0, previewRows: [], tables: [], sheets: [], columnsError: "", idNote: "", tablesError: "", tablesLoaded: false, configMaps: false,
  gates: [], gatesError: "", store: "", baselines: [], baselinesError: "", systems: [],
});
const state = { workflows: [], journeys: [], next: {}, mapping: null, workdir: "", current: null, page: "", journey: null, values: {}, autoId: {}, runs: {}, drafts: {}, shell: "sh", steps: [], preview: null, rows: {}, lookups: freshLookups() };

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null) el.append(kid);
  return el;
}

function fill(box, ...kids) { box.replaceChildren(...kids.flat(Infinity).filter((k) => k != null)); }

async function api(path, body) {
  const options = { headers: { "X-Reqtable-Token": TOKEN } };
  if (body !== undefined) { options.method = "POST"; options.headers["Content-Type"] = "application/json"; options.body = JSON.stringify(body); }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({ error: "The reqtable server sent something unexpected." }));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

const stepsKey = () => "reqtable.steps:" + state.workdir;
const sessionKey = () => "reqtable.session:" + state.workdir;
const SESSION_PARTS = ["values", "autoId", "runs", "drafts"];
const isRecord = (v) => !!v && typeof v === "object" && !Array.isArray(v);
function remember() {
  try { localStorage.setItem(stepsKey(), JSON.stringify(state.steps)); localStorage.setItem("reqtable.shell", state.shell); } catch (e) {}
}
function persistSession() {
  try { sessionStorage.setItem(sessionKey(), JSON.stringify(Object.fromEntries(SESSION_PARTS.map((k) => [k, state[k]])))); } catch (e) {}
}
function restore() {
  try {
    const steps = JSON.parse(localStorage.getItem(stepsKey()) || "[]");
    if (Array.isArray(steps)) state.steps = steps.filter((s) => s && s.workflow && s.sh && s.powershell);
    const shell = localStorage.getItem("reqtable.shell");
    if (shell === "sh" || shell === "powershell") state.shell = shell;
  } catch (e) {}
  try {
    const saved = JSON.parse(sessionStorage.getItem(sessionKey()) || "{}");
    if (isRecord(saved)) for (const k of SESSION_PARTS) if (isRecord(saved[k])) state[k] = saved[k];
  } catch (e) {}
}

const workflow = () => state.workflows.find((w) => w.id === state.current);
const workflowById = (id) => state.workflows.find((w) => w.id === id);
const shellName = () => (state.shell === "sh" ? "macOS / Linux (sh)" : "Windows (PowerShell)");

function announce(text) { $("live").textContent = text; }

let timers = {};
function later(name, fn, ms) { clearTimeout(timers[name]); timers[name] = setTimeout(fn, ms); }

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

const shellViews = [];
function shellTabs() {
  const tab = (value, label) => h("button", { type: "button", "aria-pressed": String(state.shell === value), onclick: () => { state.shell = value; remember(); shellViews.forEach((redraw) => redraw()); } }, label);
  return h("div", { class: "tabs", role: "group", "aria-label": "Shell" }, tab("sh", "macOS / Linux"), tab("powershell", "Windows"));
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
"""
