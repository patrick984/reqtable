"""Page script for the gate, baseline, role, system and waiver fields, and the offer to waive a blocked check."""

GATES_JS = r"""
const LOOKUP_KINDS = new Set(["gate", "baseline", "baselines", "role", "system", "waivers"]);
const gateById = (id) => state.lookups.gates.find((g) => g.id === id);
const baselineNamed = (name) => state.lookups.baselines.find((b) => b.name === name);
const kindsOf = (w) => new Set(w.fields.map((f) => f.kind));
const hasKind = (...names) => { const kinds = kindsOf(workflow()); return names.some((n) => kinds.has(n)); };

function systemNeeded() {
  const values = state.values[state.current] || {};
  if (!values.gate) return false;
  const gate = gateById(values.gate);
  return gate ? gate.scope === "system" : true;
}

async function lookupGateData() {
  const w = workflow(); const id = state.current;
  if (!w || w.panel !== "form" || !hasKind(...LOOKUP_KINDS)) return;
  const values = state.values[id]; const L = state.lookups;
  const query = new URLSearchParams();
  if (values[w.lookup_input]) query.set("path", values[w.lookup_input]);
  for (const name of LOOKUP_FIELDS.slice(2)) if (values[name]) query.set(name, values[name]);
  const ask = async (path, apply) => {
    let data;
    try { data = await api(path + "?" + query); } catch (e) { data = { error: e.message }; }
    if (id === state.current) apply(data);
  };
  await Promise.all([
    hasKind("gate", "role", "waivers") ? ask("/api/gates", (d) => { L.gates = d.gates || []; L.gatesError = d.error || ""; }) : null,
    hasKind("baseline", "baselines", "role", "waivers") ? ask("/api/baselines", (d) => { L.baselines = d.baselines || []; L.baselinesError = d.error || ""; L.store = d.store || ""; }) : null,
    hasKind("system") ? ask("/api/systems", (d) => { L.systems = d.systems || []; }) : null,
  ]);
  if (id !== state.current) return;
  if (hasKind("system") && !systemNeeded()) values.system = "";
  renderLookups(); refreshPreview();
}

function renderLookups() {
  for (const row of Object.values(state.rows)) if (LOOKUP_KINDS.has(row.field.kind)) LOOKUP_RENDER[row.field.kind](row);
  syncVisibility();
}

function gateChecks(gateId) { const g = gateById(gateId); return g ? g.checks : []; }

function gitExplanation() {
  const L = state.lookups;
  if (!L.baselinesError) return null;
  const git = L.store === "git" || /git/i.test(L.baselinesError);
  return h("div", { class: "banner fail", role: "alert" },
    h("strong", {}, git ? "Baselines are stored in git, and git cannot be used here." : "The baselines could not be read."),
    git ? h("div", {}, "The requirements file must sit in a git repository and be committed. Otherwise choose a settings file that keeps baselines as plain files, with \"baselines\": {\"store\": \"files\"}.") : null,
    h("span", { class: "cli-error" }, L.baselinesError));
}

function selectOf(row, options, current, blank, onPick) {
  const select = h("select", { id: "f-" + row.field.name, onchange: (e) => onPick(e.target.value) }, h("option", { value: "" }, blank));
  for (const [v, text] of options) select.append(h("option", { value: v }, text));
  if (current && !options.some(([v]) => v === current)) select.append(h("option", { value: current }, current));
  select.value = current || "";
  return select;
}
function textFallback(row, current) {
  return h("input", { type: "text", id: "f-" + row.field.name, spellcheck: "false", value: current || "", oninput: (e) => setValue(row.field, e.target.value) });
}

function renderGate(row) {
  const L = state.lookups; const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren();
  if (L.gatesError || !L.gates.length) {
    holder.append(textFallback(row, values[f.name]));
    row.note.textContent = L.gatesError ? "Could not list the gates: " + L.gatesError : "";
  } else {
    const options = L.gates.map((g) => [g.id, g.id + "  ·  " + g.name + (g.scope === "system" ? "  (covers one system)" : "")]);
    holder.append(selectOf(row, options, values[f.name], "Choose a gate…", (v) => setValue(f, v)));
    row.note.textContent = "";
    const checks = gateChecks(values[f.name]);
    if (checks.length) holder.append(h("details", { class: "more", style: "margin:8px 0 0;padding-top:8px" }, h("summary", { style: "margin-bottom:6px" }, "What this gate checks (" + checks.length + ")"),
      h("ul", { class: "plain" }, checks.map((c) => h("li", {}, h("code", {}, c.id), "  " + c.description, h("span", { class: "badge" + (c.enforcement === "strict" ? " strict" : "") }, c.enforcement === "strict" ? "required" : "advisory"))))));
  }
  if (hasKind("waivers") && L.baselinesError) holder.append(gitExplanation());
}

function renderBaseline(row) {
  const L = state.lookups; const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren(); row.note.textContent = "";
  if (!values[state.workflows.find((w) => w.id === state.current).lookup_input]) { holder.append(h("select", { id: "f-" + f.name, disabled: true }, h("option", {}, "Choose the requirements file first"))); return; }
  if (L.baselinesError) { holder.append(gitExplanation()); return; }
  if (!L.baselines.length) { holder.append(h("select", { id: "f-" + f.name, disabled: true }, h("option", {}, "No baselines yet. Freeze one first"))); return; }
  const options = L.baselines.map((b) => [b.name, b.name + "  ·  frozen " + b.created.slice(0, 10) + " by " + b.created_by]);
  holder.append(selectOf(row, options, values[f.name], "Choose a baseline…", (v) => { if (hasKind("role")) values.role = ""; setValue(f, v); }));
}

function rolesOfBaseline(name) {
  const b = baselineNamed(name); const g = b && gateById(b.gate);
  return g ? g.roles : [];
}

function renderRole(row) {
  const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren(); row.note.textContent = "";
  if (!values.baseline) { holder.append(h("select", { id: "f-" + f.name, disabled: true }, h("option", {}, "Choose a baseline first"))); return; }
  const roles = rolesOfBaseline(values.baseline);
  if (!roles.length) { holder.append(textFallback(row, values[f.name])); row.note.textContent = "Type the role name. reqtable could not find the roles for this baseline's gate."; return; }
  if (!values[f.name] && roles.length === 1) { values[f.name] = roles[0].role; }
  holder.append(selectOf(row, roles.map((r) => [r.role, r.role + "  (needs " + r.min + ")"]), values[f.name], "Choose a role…", (v) => setValue(f, v)));
}

function renderSystem(row) {
  const L = state.lookups; const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren();
  if (!L.systems.length) { holder.append(textFallback(row, values[f.name])); row.note.textContent = "Type the System ID. reqtable could not list the systems yet; choose the table and ID column first."; return; }
  row.note.textContent = "";
  holder.append(selectOf(row, L.systems.map((s) => [s.id, s.id + (s.name ? "  ·  " + s.name : "")]), values[f.name], "Choose a system…", (v) => setValue(f, v)));
}

function renderBaselinePicks(row) {
  const L = state.lookups; const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren(); row.note.textContent = "";
  if (L.baselinesError) { holder.append(gitExplanation()); return; }
  if (!L.baselines.length) { holder.append(h("p", { class: "note" }, "No baselines to choose from yet.")); return; }
  const chosen = new Set((values[f.name] || "").split(",").filter(Boolean));
  for (const b of L.baselines) {
    const box = h("input", { type: "checkbox", value: b.name, onchange: () => {
      const picked = [...holder.querySelectorAll("input:checked")].map((i) => i.value);
      values[f.name] = picked.join(","); refreshPreview();
    } });
    box.checked = chosen.has(b.name);
    holder.append(h("label", { class: "check" }, box, b.name + "  ·  frozen " + b.created.slice(0, 10)));
  }
}

function renderWaivers(row) {
  const values = state.values[state.current]; const f = row.field;
  const holder = row.extra; holder.replaceChildren(); row.note.textContent = "";
  const rows = values[f.name] = values[f.name] || [];
  const strict = gateChecks(values.gate).filter((c) => c.enforcement === "strict");
  const known = !!gateById(values.gate);
  rows.forEach((item, i) => {
    const pick = known && strict.length
      ? selectOf({ field: { name: "waive-" + i } }, strict.map((c) => [c.id, c.id + "  ·  " + c.description]), item.check, "Choose a check…", (v) => { item.check = v; refreshPreview(); })
      : h("input", { type: "text", placeholder: "Check ID", "aria-label": "Check ID", spellcheck: "false", value: item.check, oninput: (e) => { item.check = e.target.value; refreshPreview(); } });
    pick.setAttribute("aria-label", "Check to waive");
    const reason = h("input", { type: "text", id: "waive-reason-" + i, placeholder: "Why is this check waived?", "aria-label": "Reason for waiving", value: item.reason, oninput: (e) => { item.reason = e.target.value; refreshPreview(); } });
    holder.append(h("div", { class: "waiver" }, pick, reason,
      h("button", { class: "small", type: "button", "aria-label": "Remove waiver " + (i + 1), onclick: () => { rows.splice(i, 1); renderWaivers(row); refreshPreview(); } }, "✕")));
  });
  if (known && !strict.length) row.note.textContent = "This gate has no required checks, so there is nothing to waive.";
  else holder.append(h("button", { class: "small", type: "button", onclick: () => { rows.push({ check: "", reason: "" }); renderWaivers(row); refreshPreview(); } }, "Add a waiver"));
}

const LOOKUP_RENDER = { gate: renderGate, baseline: renderBaseline, baselines: renderBaselinePicks, role: renderRole, system: renderSystem, waivers: renderWaivers };

function waiveOffer(w, blocked) {
  const values = state.values[state.current];
  const box = h("div", { class: "banner soft waiveoffer" },
    h("strong", {}, "To freeze anyway, waive the blocking checks."),
    h("div", { class: "note" }, "A waiver records who skipped a check, and why, inside the baseline. Add the reason, then come back and press Run again."));
  const actions = h("div", { class: "actions" });
  for (const id of blocked) {
    const check = gateChecks(values.gate).find((c) => c.id === id);
    actions.append(h("button", { type: "button", title: check ? check.description : "", onclick: () => {
      const rows = values.waivers = values.waivers || [];
      let at = rows.findIndex((r) => r.check === id);
      if (at < 0) { rows.push({ check: id, reason: "" }); at = rows.length - 1; }
      refreshPreview();
      const page = w.pages.find((p) => p.fields.includes("waivers"));
      state.focusAfter = "waive-reason-" + at;
      go(pageHash(page.id));
    } }, "Waive “" + id + "”…"));
  }
  box.append(actions);
  return box;
}
"""
