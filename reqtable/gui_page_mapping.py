"""Page script for the "Import several tables" task: choose a workbook, say what each table holds, preview and save, then make the report."""

MAPPING_JS = r"""
const mp = { workbook: "", sources: [], idColumn: "ID", extra: {}, xlsxExtra: {}, notes: [], loadPath: "", savePath: "mapping.json",
  preview: null, saved: "", exists: false, follow: null, bookError: "", busy: false };

const MAPPING_PAGES = {
  workbook: { build: buildWorkbookPage, draw: drawBookMessage },
  tables: { build: () => h("div", { id: "mp-sources" }), draw: drawSources },
  save: { build: () => h("div", { id: "mp-save-box" }), draw: drawSave },
  report: { build: () => h("div", { id: "mp-follow-box" }), draw: drawFollow },
};

function mappingBlocker(pageId) {
  if (pageId === "workbook") {
    if (!mp.workbook.trim()) return "Choose the workbook to read";
    if (mp.bookError) return "Fix the problem with the workbook first";
    return mp.sources.length ? "" : "Choose a workbook that has tables or sheets";
  }
  if (pageId === "tables") return mp.sources.some((s) => s.role || s.raw) ? "" : "Say what at least one table holds";
  if (pageId === "save") return mp.saved ? "" : "Save the mapping to continue";
  return "";
}

function enterMapping() {
  const carried = (state.values.mapping || {}).input;
  if (carried && carried !== mp.workbook) { mp.workbook = carried; mp.bookError = ""; loadBook(); }
  fetchFollow();
}

const mappingRoles = () => state.mapping.roles;
const roleOf = (s) => mappingRoles().find((r) => r.id === s.role);
let sourceUid = 0;
const newSource = (kind, name, where) => ({ uid: ++sourceUid, seq: 0, dup: false, kind, name, where, role: "", header_row: "", field: "", id_prefix: "", columns: [], extra: {}, headings: null, raw: null, missing: false, error: "" });
const hasTarget = (s, column) => s.columns.some((c) => c.action === "map" && c.to === column);
const mpKey = (s) => s.kind + ":" + s.name;

function buildWorkbookPage() {
  const book = h("input", { type: "text", id: "mp-workbook", spellcheck: "false", placeholder: "Choose a workbook…", oninput: (e) => { mp.workbook = e.target.value; later("mp-book", loadBook, 300); } });
  book.value = mp.workbook;
  const loadInput = h("input", { type: "text", id: "mp-load", spellcheck: "false", placeholder: "Choose a mapping file…", oninput: (e) => { mp.loadPath = e.target.value; } });
  loadInput.value = mp.loadPath;
  return h("div", {},
    h("div", { class: "field" }, h("label", { for: "mp-workbook" }, "Excel workbook", h("span", { class: "req" }, "required")),
      h("div", { class: "pathrow" }, book, h("button", { type: "button", onclick: () => pickPath({ kind: "open", label: "Excel workbook", extensions: [".xlsx"], default: "" }, book, (v) => { mp.workbook = v; loadBook(); }) }, "Browse…")),
      h("p", { class: "help" }, "The .xlsx file that holds your requirements and the other tables.")),
    h("details", { class: "more" }, h("summary", {}, "Edit a mapping you saved earlier"),
      h("div", { class: "field" }, h("label", { for: "mp-load" }, "Mapping file"),
        h("div", { class: "pathrow" }, loadInput,
          h("button", { type: "button", onclick: () => pickPath({ kind: "open", label: "mapping file", extensions: [".json"], default: "" }, loadInput, (v) => { mp.loadPath = v; }) }, "Browse…"),
          h("button", { type: "button", onclick: loadSaved }, "Load")),
        h("p", { class: "help" }, "Loads the tables and columns from a mapping.json. Settings this form cannot show are kept untouched."))),
    h("div", { id: "mp-bookmsg" }));
}

function drawBookMessage() {
  updateFooter();
  const box = $("mp-bookmsg"); if (!box) return;
  fill(box,
    mp.bookError ? h("div", { class: "banner bad", role: "alert" }, h("strong", {}, "Could not read the workbook."), h("span", { class: "cli-error" }, mp.bookError)) : null,
    mp.notes.length ? h("div", { class: "banner warn" }, h("strong", {}, "About the loaded mapping"), h("ul", { class: "plain" }, mp.notes.map((n) => h("li", {}, n)))) : null);
}

let bookSeq = 0;
async function loadBook() {
  const seq = ++bookSeq;
  mp.bookError = "";
  (state.values.mapping = state.values.mapping || {}).input = mp.workbook; persistSession();
  if (!mp.workbook.trim()) { mp.sources = []; drawBookMessage(); drawSources(); schedulePreview(); return; }
  let data;
  try { data = await api("/api/tables?path=" + encodeURIComponent(mp.workbook)); } catch (e) { data = { error: e.message }; }
  if (seq !== bookSeq) return;
  if (data.error) { mp.bookError = data.error; mp.sources = []; drawBookMessage(); drawSources(); schedulePreview(); return; }
  const onTable = new Set(data.tables.map((t) => t.sheet));
  const found = [
    ...data.tables.map((t) => newSource("table", t.name, "table on sheet " + t.sheet)),
    ...data.sheets.filter((s) => !onTable.has(s.name)).map((s) => newSource("sheet", s.name, s.state === "visible" ? "sheet" : s.state + " sheet")),
  ];
  const before = new Map();
  for (const s of mp.sources) before.set(mpKey(s), [...(before.get(mpKey(s)) || []), s]);
  const refetch = [];
  const kept = found.flatMap((fresh) => (before.get(mpKey(fresh)) || [fresh]).map((s) => {
    if (s !== fresh && s.missing) { s.missing = false; s.where = fresh.where; if (s.role) refetch.push(s); }
    return s;
  }));
  const foundKeys = new Set(found.map(mpKey));
  const lost = mp.sources.filter((s) => (s.role || s.raw) && !foundKeys.has(mpKey(s)));
  for (const s of lost) { s.missing = true; s.where = "not in this workbook"; }
  mp.sources = [...kept, ...lost];
  drawBookMessage(); drawSources(); schedulePreview(); fetchFollow();
  for (const s of refetch) fetchColumns(s, false);
}

async function loadSaved() {
  let data;
  try { data = await api("/api/mapping/load?path=" + encodeURIComponent(mp.loadPath)); } catch (e) { data = { error: e.message }; }
  if (data.error) { mp.bookError = data.error; mp.notes = []; drawBookMessage(); return; }
  mp.bookError = ""; mp.notes = data.notes;
  const form = data.form;
  mp.idColumn = form.id_column; mp.extra = form.extra; mp.xlsxExtra = form.xlsx_extra;
  const wanted = new Set(form.sources.map((fs) => fs.kind + ":" + fs.name));
  mp.sources = mp.sources.filter((s) => !s.dup);
  for (const s of mp.sources) if (!wanted.has(mpKey(s))) { s.role = ""; s.columns = []; s.raw = null; s.headings = null; }
  const used = new Set();
  for (const fs of form.sources) {
    let s = mp.sources.find((x) => x.kind === fs.kind && x.name === fs.name && !used.has(x));
    if (!s) {
      const siblings = mp.sources.filter((x) => x.kind === fs.kind && x.name === fs.name);
      s = newSource(fs.kind, fs.name, siblings.length ? siblings[0].where : "not in this workbook");
      s.missing = !siblings.length; s.dup = siblings.length > 0;
      mp.sources.splice(siblings.length ? mp.sources.indexOf(siblings[siblings.length - 1]) + 1 : mp.sources.length, 0, s);
    }
    used.add(s);
    if (fs.raw) { s.raw = fs.raw; s.role = ""; continue; }
    Object.assign(s, { raw: null, role: fs.role, header_row: fs.header_row == null ? "" : String(fs.header_row), field: fs.field, id_prefix: fs.id_prefix, columns: fs.columns.map((c) => ({ ...c })), extra: fs.extra,
      headings: fs.headings ? { column: fs.headings.column, values: fs.headings.values.join(", "), text: fs.headings.text || "", into: fs.headings.into, auto: "" } : null });
  }
  drawBookMessage(); drawSources(); schedulePreview();
  for (const s of mp.sources) if (s.role && !s.missing) fetchColumns(s, false);
}

async function fetchColumns(s, fresh) {
  const seq = ++s.seq;
  const query = new URLSearchParams({ path: mp.workbook, role: s.role });
  query.set(s.kind, s.name);
  if (s.kind === "sheet" && s.header_row) query.set("header_row", s.header_row);
  let data;
  try { data = await api("/api/mapping/suggest?" + query); } catch (e) { data = { error: e.message }; }
  if (seq !== s.seq) return;
  if (data.error) { s.error = data.error; if (fresh) s.columns = []; drawSources(); schedulePreview(); return; }
  s.error = "";
  if (fresh) { s.columns = data.columns; s.id_prefix = data.id_prefix; }
  else {
    const have = new Map(s.columns.map(({ missing, ...c }) => [c.header, c]));
    const headers = data.columns.map((c) => c.header);
    const taken = new Set([...have.values()].filter((c) => headers.includes(c.header) && c.action === "map").map((c) => c.to));
    const unmatched = roleOf(s).merge ? "exclude" : "keep";
    s.columns = data.columns.map((c) => have.get(c.header) || (c.action === "map" && taken.has(c.to) ? { ...c, action: unmatched, to: "", separator: "" } : c));
    for (const c of have.values()) if (!headers.includes(c.header)) s.columns.push({ ...c, missing: true });
  }
  drawSources(); schedulePreview();
}

function setRole(s, roleId) {
  s.seq++;
  s.role = roleId; s.columns = []; s.field = ""; s.id_prefix = ""; s.error = ""; s.headings = null;
  if (!roleId) { drawSources(); schedulePreview(); return; }
  drawSources();
  fetchColumns(s, true);
}

const MARKER_GUESS = /^(requirement type|req\.? type|type)$/i;
const markerChoices = (s) => s.columns.filter((c) => !c.missing).map((c) => c.header);
const columnNamed = (s, header) => s.columns.find((c) => c.header === header);

function restoreMarker(s) {
  const h = s.headings; if (!h || !h.auto) return;
  const c = columnNamed(s, h.auto);
  if (c && c.action === "exclude") { c.action = "keep"; c.to = ""; c.separator = ""; }
  h.auto = "";
}

function leaveMarkerOut(s) {
  const h = s.headings; const c = h.column && columnNamed(s, h.column);
  if (c && c.action === "keep") { c.action = "exclude"; h.auto = c.header; }
}

function enableHeadings(s) {
  const headers = markerChoices(s);
  const text = s.columns.find((c) => c.action === "map" && c.to === "Requirement");
  s.headings = { column: headers.find((x) => MARKER_GUESS.test(x.trim())) || "", values: "Heading", text: text ? text.header : "", into: "Category", auto: "" };
  leaveMarkerOut(s);
}

function setMarker(s, header) {
  restoreMarker(s); s.headings.column = header; leaveMarkerOut(s);
  drawSources(); schedulePreview();
}

function toggleHeadings(s, on) {
  if (on) enableHeadings(s); else { restoreMarker(s); s.headings = null; }
  drawSources(); schedulePreview();
}

function headerSelect(s, id, label, value, empty, onpick) {
  const headers = markerChoices(s);
  const options = [h("option", { value: "" }, empty), ...headers.map((x) => h("option", { value: x }, x))];
  if (value && !headers.includes(value)) options.push(h("option", { value }, value + " (not in this table)"));
  const select = h("select", { id, "aria-label": label, onchange: (e) => onpick(e.target.value) }, options);
  select.value = value;
  return select;
}

function headingsSection(s, i) {
  const hd = s.headings;
  const on = h("input", { type: "checkbox", id: "hd-on-" + i, checked: !!hd, onchange: (e) => toggleHeadings(s, e.target.checked) });
  const box = h("div", { class: "headings", style: "margin-top:12px" },
    h("label", { for: on.id, style: "display:flex;gap:8px;align-items:center;font-weight:600" }, on, "This table has heading rows that group requirements into categories"));
  if (!hd) return box;
  const values = h("input", { type: "text", id: "hd-values-" + i, spellcheck: "false", style: "max-width:240px", oninput: (e) => { hd.values = e.target.value; schedulePreview(); } });
  values.value = hd.values;
  const into = h("input", { type: "text", id: "hd-into-" + i, spellcheck: "false", style: "max-width:240px", oninput: (e) => { hd.into = e.target.value; schedulePreview(); } });
  into.value = hd.into;
  const field = (label, id, control, help) => h("div", { class: "field", style: "margin-top:10px" }, h("label", { class: "mini", for: id }, label), control, help ? h("p", { class: "help" }, help) : null);
  box.append(
    h("p", { class: "help" }, "Rows whose marker column says Heading become category names. Every requirement below a heading, up to the next one, gets that category."),
    field("Which column marks a heading row?", "hd-col-" + i, headerSelect(s, "hd-col-" + i, "Which column marks a heading row?", hd.column, "Choose a column…", (v) => setMarker(s, v)),
      "The marker column is left out of the table by default, because every row that stays is a requirement. Change it back in the table above to keep it."),
    field("Marker value(s)", "hd-values-" + i, values, "The words that mark a heading row. Separate several with commas. Capital letters and spaces do not matter."),
    field("Which column holds the heading text?", "hd-text-" + i, headerSelect(s, "hd-text-" + i, "Which column holds the heading text?", hd.text, "First non-empty cell", (v) => { hd.text = v; schedulePreview(); })),
    field("Put the category in", "hd-into-" + i, into, "A column of this name is added to the table when it is missing. A row that already has a value there keeps it."));
  return box;
}

function headingsForm(s) {
  const hd = s.headings;
  if (!hd) return null;
  return { column: hd.column, values: hd.values.split(",").map((v) => v.trim()).filter(Boolean), text: hd.text, into: hd.into.trim() };
}

function targetValue(c) { return c.action === "map" ? "map:" + c.to : c.action; }

function setTarget(s, c, value) {
  const role = roleOf(s); const hadId = hasTarget(s, "ID");
  if (value.startsWith("map:")) { c.action = "map"; c.to = value.slice(4); } else { c.action = value; c.to = ""; }
  const target = role.targets.find((t) => t.column === c.to);
  c.separator = c.action !== "exclude" && target && target.list_separator ? (c.separator || ",") : "";
  const hasId = hasTarget(s, "ID");
  if (hasId && !hadId && s.id_prefix === role.id_prefix) s.id_prefix = "";
  if (!hasId && hadId && !s.id_prefix) s.id_prefix = role.id_prefix;
  if (hasTarget(s, "Field")) s.field = "";
  drawSources(); schedulePreview();
}

function columnTable(s) {
  const role = roleOf(s);
  const rows = s.columns.map((c) => {
    const options = [h("option", { value: "keep" }, "Keep as is"),
      ...role.targets.map((t) => h("option", { value: "map:" + t.column }, t.label + (t.label === t.column ? "" : "  (" + t.column + ")"))),
      h("option", { value: "exclude" }, "Leave out")];
    if (c.action === "map" && !role.targets.some((t) => t.column === c.to)) options.push(h("option", { value: "map:" + c.to }, c.to));
    const pick = h("select", { "aria-label": "Where " + c.header + " goes", onchange: (e) => setTarget(s, c, e.target.value) }, options);
    pick.value = targetValue(c);
    const sep = c.separator || (c.action === "map" && (role.targets.find((t) => t.column === c.to) || {}).list_separator);
    const separator = sep ? h("select", { "aria-label": "Separator in " + c.header, onchange: (e) => { c.separator = e.target.value; schedulePreview(); } },
      state.mapping.separators.map((x) => h("option", { value: x.value }, x.label))) : null;
    if (separator) separator.value = c.separator || ",";
    return h("tr", {}, h("td", { class: "src" }, c.header, c.missing ? h("span", { class: "badge" }, "not in this table") : null), h("td", {}, pick), h("td", {}, separator ? ["Split on ", separator] : null));
  });
  return h("div", { class: "xscroll" }, h("table", { class: "cols" }, h("thead", {}, h("tr", {}, h("th", {}, "Column in the workbook"), h("th", {}, "Goes into"), h("th", {}, "If it holds a list"))), h("tbody", {}, rows)));
}

function fieldPicker(s) {
  const fields = state.mapping.fields;
  const custom = !!s.field && !fields.some((f) => f.value === s.field);
  const select = h("select", { id: "field-" + s.uid, "aria-label": "Which column are these values for?", onchange: (e) => { s.field = e.target.value === "__other" ? " " : e.target.value; drawSources(); schedulePreview(); } },
    h("option", { value: "" }, "Choose a column…"), fields.map((f) => h("option", { value: f.value }, f.label)), h("option", { value: "__other" }, "Another column…"));
  select.value = custom ? "__other" : s.field;
  const other = custom ? h("input", { type: "text", "aria-label": "Column name", placeholder: "Column name", spellcheck: "false", style: "margin-top:6px", onchange: (e) => { s.field = e.target.value.trim(); schedulePreview(); } }) : null;
  if (other) other.value = s.field.trim();
  return h("div", { style: "margin-top:10px;max-width:340px" }, h("label", { class: "mini", for: select.id }, "Which column are these values for?"), select, other);
}

function drawSource(s, i) {
  const role = roleOf(s);
  const title = h("div", {}, h("div", { class: "nm" }, s.name), h("div", { class: "sub" }, s.where));
  if (s.raw) {
    return h("div", { class: "srcrow" }, h("div", { class: "top" }, title, h("p", { class: "note", style: "grid-column: span 2" }, "Kept exactly as it is in the file, because this form cannot edit it."),
      ), h("div", { class: "actions" }, h("button", { class: "small", type: "button", onclick: () => { s.raw = null; drawSources(); schedulePreview(); } }, "Stop importing this")));
  }
  const pick = h("select", { id: "role-" + i, "aria-label": "What does " + s.name + " hold?", onchange: (e) => setRole(s, e.target.value) },
    h("option", { value: "" }, "Don't import"), mappingRoles().map((r) => h("option", { value: r.id }, r.label)));
  pick.value = s.role;
  const row = h("div", { class: "srcrow" }, h("div", { class: "top" }, title,
    h("div", {}, h("label", { class: "mini", for: pick.id }, "What is it?"), pick),
    s.kind === "sheet" ? h("div", {}, h("label", { class: "mini", for: "hr-" + i }, "Header row"),
      h("input", { type: "number", id: "hr-" + i, min: "1", placeholder: "first", value: s.header_row, onchange: (e) => { s.header_row = e.target.value; if (s.role) fetchColumns(s, false); } })) : h("div", {})));
  const again = h("div", { class: "actions", style: "margin-top:8px" },
    h("button", { class: "small", type: "button", onclick: () => { const c = newSource(s.kind, s.name, s.where); c.dup = true; mp.sources.splice(i + 1, 0, c); drawSources(); } }, "Add this table again with another role"),
    s.dup ? h("button", { class: "small", type: "button", onclick: () => { mp.sources.splice(i, 1); drawSources(); schedulePreview(); } }, "Remove this extra row") : null);
  if (!role) { row.append(again); return row; }
  row.append(h("p", { class: "note" }, role.help));
  if (s.error) row.append(h("div", { class: "banner bad" }, s.error));
  if (role.needs_field && !hasTarget(s, "Field")) row.append(fieldPicker(s));
  else if (role.needs_field) row.append(h("p", { class: "note" }, "The column you sent to Field says which column each value is for."));
  if (s.columns.length) row.append(columnTable(s));
  if (role.headings && s.columns.length) row.append(headingsSection(s, i));
  if (!role.merge && !hasTarget(s, "ID") && (role.id_prefix || s.id_prefix)) {
    const prefix = h("input", { type: "text", id: "prefix-" + i, spellcheck: "false", style: "max-width:160px", onchange: (e) => { s.id_prefix = e.target.value.trim(); schedulePreview(); } });
    prefix.value = s.id_prefix;
    row.append(h("div", { style: "margin-top:10px" }, h("label", { class: "mini", for: prefix.id }, "No ID column here, so reqtable makes IDs that start with"), prefix));
  }
  row.append(again);
  return row;
}

function drawSources() {
  updateFooter();
  const box = $("mp-sources"); if (!box) return;
  if (!mp.workbook.trim() || mp.bookError) { box.replaceChildren(); return; }
  fill(box, mp.sources.length ? mp.sources.map(drawSource) : h("p", { class: "empty" }, "Nothing found in this workbook."));
}

function buildForm() {
  return {
    id_column: mp.idColumn, extra: mp.extra, xlsx_extra: mp.xlsxExtra,
    sources: mp.sources.filter((s) => s.raw || s.role).map((s) => s.raw ? { kind: s.kind, name: s.name, raw: s.raw } : {
      kind: s.kind, name: s.name, role: s.role, header_row: s.header_row === "" ? null : Number(s.header_row), field: s.field, id_prefix: s.id_prefix, extra: s.extra, headings: headingsForm(s),
      columns: s.columns.map((c) => ({ header: c.header, action: c.action, to: c.to, separator: c.separator })),
    }),
  };
}

let mapPreviewSeq = 0;
function schedulePreview() { mp.saved = ""; mp.exists = false; later("mp-preview", fetchMapPreview, 300); }
async function fetchMapPreview() {
  const seq = ++mapPreviewSeq;
  if (!mp.workbook.trim() || mp.bookError) { mp.preview = null; drawSave(); return; }
  let data;
  try { data = await api("/api/mapping/preview", { path: mp.workbook, form: buildForm() }); } catch (e) { data = { error: e.message }; }
  if (seq !== mapPreviewSeq) return;
  mp.preview = data; drawSave();
}

const followValues = () => ({ input: mp.workbook, config: mp.savePath, traceability: "on", output: "requirements-report.html", document_mode: "review" });
async function fetchFollow() {
  if (!mp.workbook.trim() || !mp.savePath.trim()) { mp.follow = null; drawFollow(); return; }
  try { mp.follow = await api("/api/command", { workflow: "report", values: followValues() }); } catch (e) { mp.follow = { error: e.message }; }
  drawFollow();
}

async function saveMapping(overwrite) {
  let data;
  try { data = await api("/api/mapping/save", { path: mp.savePath, form: buildForm(), overwrite }); } catch (e) { data = { error: e.message }; }
  if (data.error) { mp.preview = { ...(mp.preview || {}), error: data.error }; mp.saved = ""; drawSave(); return; }
  mp.exists = !!data.exists;
  mp.saved = data.saved ? mp.savePath : "";
  if (data.saved) {
    await fetchFollow();
    if (mp.follow && !mp.follow.error) {
      const base = baseName(mp.savePath);
      const added = pushStep({ id: String(Date.now()), workflow: "report", title: "Make a report with " + base, note: "needs " + base + ", saved by “Import several tables”",
        values: followValues(), sh: mp.follow.sh, powershell: mp.follow.powershell, argv: mp.follow.argv }, true);
      mp.stepAdded = added;
    }
    announce("Saved " + mp.savePath);
  }
  drawSave(); drawFollow();
}

function reportWithMapping() { startNext("report", followValues()); }

function headingSummary(src) {
  const hd = src.headings;
  if (hd.warning) return h("div", { class: "banner warn", style: "margin-top:8px", role: "status" }, src.name + ": " + hd.warning);
  const named = hd.categories.map((c) => c.name + " (" + c.count + ")");
  if (hd.uncategorised) named.push("No category (" + hd.uncategorised + ")");
  return h("div", { style: "margin-top:6px" }, h("strong", {}, "Categories" + (mp.sources.filter((x) => x.headings).length > 1 ? " in " + src.name : "") + ": "),
    named.length ? named.join(", ") : "none yet",
    ". " + hd.removed + " heading row" + (hd.removed === 1 ? " is" : "s are") + " removed.");
}

function drawSave() {
  updateFooter();
  const box = $("mp-save-box"); if (!box) return;
  const p = mp.preview;
  const pathInput = h("input", { type: "text", id: "mp-save", spellcheck: "false", onchange: (e) => { mp.savePath = e.target.value.trim(); mp.saved = ""; mp.exists = false; fetchFollow(); drawSave(); } });
  pathInput.value = mp.savePath;
  const ready = p && p.mapping && !p.error;
  const status = !p ? h("p", { class: "hint" }, "Say what each table holds on the previous page. A preview of the import appears here.")
    : p.error ? h("div", { class: p.mapping ? "banner fail" : "banner soft", role: "status" }, h("strong", {}, p.mapping ? "This mapping does not import yet." : "Not ready yet."), h("span", { class: p.mapping ? "cli-error" : "" }, p.error))
    : h("div", { class: "banner ok", role: "status" }, h("strong", {}, p.total + " row" + (p.total === 1 ? "" : "s") + " would be imported."),
        h("div", { class: "xscroll" }, h("table", { class: "grid", style: "margin-top:8px;background:var(--surface)" }, h("thead", {}, h("tr", {}, h("th", {}, "Table"), h("th", {}, "Rows"))),
          h("tbody", {}, p.sources.map((s) => h("tr", {}, h("td", {}, s.name), h("td", {}, s.rows == null ? "fills in existing rows" : String(s.rows))))))),
        h("div", { style: "margin-top:6px" }, "Record types: " + Object.entries(p.types).map(([k, v]) => k + " " + v).join(", ")),
        p.sources.filter((x) => x.headings).map(headingSummary));
  const warnings = p && p.warnings && p.warnings.length ? h("div", { class: "banner warn" }, h("strong", {}, "Worth a look"), p.warnings.map((x) => h("div", {}, x))) : null;
  const json = p && p.mapping ? JSON.stringify(p.mapping, null, 2) : "";
  const confirm = mp.exists ? h("div", { class: "banner warn", role: "alert" }, h("strong", {}, baseName(mp.savePath) + " already exists."), "Replacing it throws away what is in it now.",
    h("div", { class: "actions" }, h("button", { type: "button", onclick: () => saveMapping(true) }, "Replace it"), h("button", { type: "button", onclick: () => { mp.exists = false; drawSave(); $("mp-save").focus(); } }, "Choose another name"))) : null;
  const saved = mp.saved ? h("div", { class: "banner ok", role: "status" }, h("strong", {}, "Saved " + mp.saved + "."),
    mp.stepAdded ? "The report command was added to your workflow, with a note that it needs " + baseName(mp.saved) + ". " : "", "Press Next to make the report.") : null;
  fill(box,
    status, warnings,
    json ? h("div", {}, h("div", { class: "commandbar" }, h("strong", {}, "mapping.json"), h("button", { class: "small", type: "button", onclick: (e) => copyText(json, e.target) }, "Copy JSON")),
      h("pre", { class: "json", tabindex: "0", "aria-label": "Mapping JSON" }, json)) : null,
    h("div", { class: "field", style: "margin-top:14px" }, h("label", { for: "mp-save" }, "Save the mapping as"),
      h("div", { class: "pathrow" }, pathInput, h("button", { type: "button", onclick: () => pickPath({ kind: "save", label: "mapping", extensions: [".json"], default: "mapping.json" }, pathInput, (v) => { mp.savePath = v; mp.saved = ""; mp.exists = false; fetchFollow(); drawSave(); }) }, "Choose location…")),
      h("p", { class: "help" }, "Saving never replaces an existing file without asking.")),
    confirm, saved,
    h("div", { class: "actions" }, h("button", { class: "primary", id: "mp-savebtn", type: "button", disabled: !ready, onclick: () => saveMapping(false) }, "Save mapping")));
}

function drawFollow() {
  const box = $("mp-follow-box"); if (!box) return;
  const f = mp.follow;
  fill(box,
    mp.saved ? h("div", { class: "banner ok", role: "status" }, h("strong", {}, "Saved " + mp.saved + "."), "The report below reads your tables the way you described them.") : h("div", { class: "banner soft" }, "Save the mapping first."),
    h("h2", {}, "The command that will make the report"),
    h("div", { class: "commandbar" }, shellTabs(), f && !f.error ? h("button", { class: "small", type: "button", onclick: (e) => copyText(f[state.shell], e.target) }, "Copy command") : null),
    f && !f.error ? h("pre", { class: "command", tabindex: "0", "aria-label": "Command for " + shellName() }, f[state.shell]) : h("p", { class: "hint" }, f && f.error ? f.error : "Choose a workbook to see the command."),
    h("p", { class: "note" }, "It needs " + baseName(mp.savePath || "mapping.json") + " in the same folder."),
    h("div", { class: "actions" }, h("button", { class: "primary", type: "button", disabled: !mp.saved, onclick: reportWithMapping }, "Make a report with this mapping")));
}
shellViews.push(drawFollow);
"""
