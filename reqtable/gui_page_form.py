"""Page script for a task's form pages: the fields, the Excel table and ID-column lookups, and what keeps Next waiting."""

FORM_JS = r"""
function isWorkbook(v) { return /\.xlsx$/i.test(v || ""); }
function workbookPath() {
  const values = state.values[state.current];
  for (const name of workflow().table_inputs) if (isWorkbook(values[name])) return values[name];
  return "";
}

function initValues(w) {
  if (state.values[w.id]) return;
  state.values[w.id] = {};
  for (const f of w.fields) if (f.default) state.values[w.id][f.name] = f.default;
}

function fieldsPage(w, page) {
  state.rows = {};
  const box = h("div", {});
  const more = h("details", { class: "more" }, h("summary", {}, "More options"));
  let advanced = 0;
  for (const name of page.fields) {
    const f = w.fields.find((x) => x.name === name);
    const row = buildField(f);
    state.rows[f.name] = row;
    if (f.advanced) { more.append(row.wrap); advanced++; } else box.append(row.wrap);
  }
  if (advanced) box.append(more);
  return box;
}

function drawFields() { syncVisibility(); renderColumns(); renderTableChoices(); renderLookups(); }

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

function fieldHidden(f) {
  const values = state.values[state.current] || {};
  return (f.xlsx_only && !workbookPath()) || (!!f.requires && !values[f.requires]) || (f.kind === "system" && !systemNeeded());
}

function syncVisibility() {
  for (const row of Object.values(state.rows)) row.wrap.hidden = fieldHidden(row.field);
  updateFooter();
}

const WAIT_FOR = { open: "Choose a file for", save: "Say where to save", choice: "Choose", radio: "Choose", gate: "Choose", baseline: "Choose", role: "Choose" };

function formBlocker(w, page) {
  const values = state.values[w.id] || {};
  for (const name of page.fields) {
    const f = w.fields.find((x) => x.name === name);
    if (f.required && !fieldHidden(f) && !String(values[f.name] || "").trim()) return (WAIT_FOR[f.kind] || "Fill in") + " “" + f.label + "”";
  }
  const kinds = page.fields.map((name) => w.fields.find((x) => x.name === name).kind);
  if (kinds.some((k) => k === "table" || k === "column") && tableState().kind === "choose") return "Choose the table or sheet to read";
  return "";
}

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
    row.note.textContent = L.columnsError || [L.idNote, t.kind === "single" ? "Reading table “" + t.table + "”, the only table in this workbook." : ""].filter(Boolean).join(" ");
    renderPreviewTable(row);
  }
  updateFooter();
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
    L.idNote = "";
    const idField = w.fields.find((f) => f.kind === "column");
    if (idField && data.columns.length) {
      const current = values[idField.name] || "";
      const guessed = !current || state.autoId[id] === current;
      if (guessed || !data.columns.includes(current)) {
        const next = data.id_guess || "";
        if (!guessed) L.idNote = "“" + current + "” is not a column of this table, so the ID column was " + (next ? "set to “" + next + "”." : "cleared.");
        values[idField.name] = next; state.autoId[id] = next; persistSession();
        if (next !== current) { refreshPreview(); lookupGateData(); }
      }
    }
  } catch (e) { if (seq !== columnsSeq) return; L.columns = []; L.columnsError = e.message; }
  renderColumns();
}
"""
