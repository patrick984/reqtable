"""Page script for navigation: hash routes, the home page, the wizard frame, and carrying values from one task to the next."""

WIZARD_JS = r"""
const RUN_PAGE = { id: "run", title: "Check and run", help: "Check the command, then press Run. Nothing happens until you do.", fields: [] };
const pagesOf = (w) => (w.panel === "form" ? [...w.pages, RUN_PAGE] : w.pages);

const taskHash = (id, page) => "#/task/" + id + (page ? "/" + page : "");
const journeyHash = (jid, step, page) => "#/journey/" + jid + "/" + step + (page ? "/" + page : "");
const pageHash = (page) => (state.journey ? journeyHash(state.journey.def.id, state.journey.step, page) : taskHash(state.current, page));
function go(hash) { if (location.hash === hash) route(); else location.hash = hash; }

function parseRoute() {
  let parts;
  try { parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent); }
  catch (e) { return { kind: "home" }; }
  if (parts[0] === "task" && parts[1]) return { kind: "task", id: parts[1], page: parts[2] || "" };
  if (parts[0] === "journey" && parts[1]) return { kind: "journey", jid: parts[1], step: Number(parts[2]) || 1, page: parts[3] || "" };
  return { kind: "home" };
}

function redirect(hash) { history.replaceState(history.state, "", hash); showRoute(); }

let shownHash = null;
function route() {
  if (!history.state) history.replaceState({ prev: shownHash }, "");
  showRoute();
  shownHash = location.hash;
}

function goBack(hash) {
  if (history.state && history.state.prev === hash) history.back();
  else { history.replaceState(history.state, "", hash); route(); }
}

function enterTask(w) {
  state.current = w.id; state.page = ""; state.rows = {}; state.preview = null; state.lookups = freshLookups();
  initValues(w);
  if (w.panel === "form") { lookupTables(); lookupColumns(); lookupGateData(); refreshPreview(); }
  else enterMapping();
}

function blockerFor(w, page) {
  if (w.panel !== "form") return mappingBlocker(page.id);
  return page.id === RUN_PAGE.id ? "" : formBlocker(w, page);
}

function showRoute() {
  for (const dialog of [$("drawer"), $("picker")]) if (dialog.open) dialog.close();
  const r = parseRoute();
  if (r.kind === "home") return showHome();
  let id = r.id; let journey = null;
  if (r.kind === "journey") {
    const def = state.journeys.find((j) => j.id === r.jid);
    const step = def && def.steps[r.step - 1];
    if (!step) return redirect("#/");
    journey = { def, step: r.step }; id = step.workflow;
  }
  const w = workflowById(id);
  if (!w) return redirect("#/");
  state.journey = journey;
  if (state.current !== id) enterTask(w);
  const pages = pagesOf(w);
  let index = Math.max(0, pages.findIndex((p) => p.id === r.page));
  const stuck = pages.findIndex((p) => blockerFor(w, p));
  if (stuck >= 0 && stuck < index) index = stuck;
  state.page = pages[index].id;
  if (location.hash !== pageHash(state.page)) history.replaceState(history.state, "", pageHash(state.page));
  renderWizard(w, pages, index);
}

let firstScreen = true;
function settle(text) {
  window.scrollTo(0, 0);
  const wanted = state.focusAfter && $(state.focusAfter);
  state.focusAfter = "";
  if (wanted) { wanted.scrollIntoView({ block: "center" }); wanted.focus(); }
  else if (!firstScreen && $("pagehead")) $("pagehead").focus({ preventScroll: true });
  firstScreen = false;
  announce(text);
}

const pageHead = (text) => h("h2", { class: "pagetitle", id: "pagehead", tabindex: "-1" }, text);

function showHome() {
  state.current = null; state.journey = null; state.page = ""; state.rows = {};
  const groups = [];
  for (const w of state.workflows) {
    if (!groups.length || groups[groups.length - 1].name !== w.group) groups.push({ name: w.group, tasks: [] });
    groups[groups.length - 1].tasks.push(w);
  }
  $("main").className = "";
  fill($("main"),
    pageHead("What would you like to do?"),
    h("p", { class: "hint" }, "Pick a typical job and reqtable guides you through it, step by step. Or choose a single task below. Everything runs on your computer; nothing is uploaded."),
    h("h2", { class: "section" }, "Typical jobs"),
    h("div", { class: "jobs" }, state.journeys.map((j) => h("a", { class: "tile job", href: journeyHash(j.id, 1, "") },
      h("h3", {}, j.title), h("span", { class: "sum" }, j.summary),
      h("ol", {}, j.steps.map((s) => h("li", {}, workflowById(s.workflow).title)))))),
    h("h2", { class: "section" }, "All tasks"),
    groups.map((g) => [h("h3", { class: "group" }, g.name),
      h("div", { class: "tiles" }, g.tasks.map((w) => h("a", { class: "tile", href: taskHash(w.id, "") }, h("h3", {}, w.title), h("span", { class: "when" }, w.when))))]));
  settle("All tasks");
}

function wizardBar(w) {
  const name = state.journey ? state.journey.def.title : w.title;
  return h("div", { class: "wizbar" }, h("a", { class: "btn", href: "#/" }, "← All tasks"), h("span", { class: "task" }, name));
}

function journeyBar() {
  const j = state.journey;
  if (!j) return null;
  const work = (i) => workflowById(j.def.steps[i].workflow);
  const title = (i) => work(i).title;
  const lastPage = (i) => pagesOf(work(i)).at(-1).id;
  return h("div", { class: "journeybar", role: "group", "aria-label": j.def.title },
    h("p", {}, h("strong", {}, "Step " + j.step + " of " + j.def.steps.length + ": " + title(j.step - 1))),
    h("p", { class: "note" }, j.def.steps[j.step - 1].why),
    h("ol", {}, j.def.steps.map((_, i) => i + 1 < j.step ? h("li", { class: "done" }, h("a", { href: journeyHash(j.def.id, i + 1, lastPage(i)) }, title(i)))
      : h("li", { "aria-current": i + 1 === j.step ? "step" : null }, title(i)))));
}

function stepper(pages, index) {
  return h("ol", { class: "stepper", "aria-label": "Steps" }, pages.map((p, i) => {
    const num = h("span", { class: "num", "aria-hidden": "true" }, i < index ? "✓" : String(i + 1));
    if (i < index) return h("li", { class: "done" }, h("a", { href: pageHash(p.id) }, num, " " + p.title));
    return h("li", { "aria-current": i === index ? "step" : null }, num, " " + p.title);
  }));
}

function runPage(w) {
  return h("div", {},
    w.fixed.length ? h("p", { class: "note", style: "margin:0 0 14px" }, "This task always runs with ", h("code", {}, w.fixed.join(" ")), ".") : null,
    h("div", { id: "commandcard" }), h("div", { id: "result" }));
}

function pageParts(w, page) {
  if (w.panel !== "form") return MAPPING_PAGES[page.id];
  if (page.id === RUN_PAGE.id) return { build: () => runPage(w), draw: () => { renderPreview(); drawResult(); } };
  return { build: () => fieldsPage(w, page), draw: drawFields };
}

function renderWizard(w, pages, index) {
  const page = pages[index];
  const parts = pageParts(w, page);
  const last = index === pages.length - 1;
  const back = index > 0 ? pageHash(pages[index - 1].id) : "";
  const next = last ? null : h("button", { class: "primary", type: "button", id: "wiznext", "aria-describedby": "wizwhy", onclick: () => go(pageHash(pages[index + 1].id)) }, "Next");
  $("main").className = "wizard";
  fill($("main"),
    wizardBar(w), journeyBar(), stepper(pages, index),
    h("div", { class: "card" }, pageHead(page.title), index === 0 && w.panel === "form" ? h("p", { class: "hint" }, w.summary) : null,
      h("p", { class: "hint", style: "margin-top:0" }, page.help), parts.build()),
    h("div", { class: "wizfoot" },
      back ? h("a", { class: "btn", href: back, onclick: (e) => { e.preventDefault(); goBack(back); } }, "Back") : h("span", {}),
      next ? h("div", { class: "go" }, h("p", { class: "why", id: "wizwhy" }), next) : null));
  parts.draw();
  updateFooter();
  settle("Step " + (index + 1) + " of " + pages.length + ": " + page.title);
}

function updateFooter() {
  const next = $("wiznext");
  if (!next || !state.current) return;
  const page = pagesOf(workflow()).find((p) => p.id === state.page);
  if (!page) return;
  const why = blockerFor(workflow(), page);
  next.disabled = !!why; $("wizwhy").textContent = why;
}

const DEPENDENT = ["table", "sheet", "header_row", "id_column"];
function carryValues(from, target, carry) {
  const to = state.values[target.id];
  const has = (name) => target.fields.some((f) => f.name === name);
  const carried = new Set(carry.map(([, b]) => b));
  let newFile = false;
  for (const [a, b] of carry) {
    const v = from[a];
    if (v == null || v === "" || !has(b)) continue;
    if (to[b] !== v && target.table_inputs.includes(b)) newFile = true;
    to[b] = v;
  }
  if (newFile) for (const name of DEPENDENT) if (has(name) && !carried.has(name)) to[name] = "";
}

function startNext(targetId, extra) {
  const from = state.current; const target = workflowById(targetId);
  const step = (state.next[from] || []).find((s) => s.workflow === targetId);
  const run = state.runs[runKey()];
  delete state.values[targetId]; delete state.autoId[targetId];
  initValues(target);
  carryValues(run ? run.values : state.values[from], target, step ? step.carry : []);
  Object.assign(state.values[targetId], extra || {});
  persistSession();
  const upcoming = journeyNext();
  const first = target.pages[0].id;
  go(upcoming && upcoming.work.id === targetId ? journeyHash(state.journey.def.id, state.journey.step + 1, first) : taskHash(targetId, first));
}

async function start() {
  try {
    const data = await api("/api/workflows");
    state.workflows = data.workflows; state.workdir = data.workdir; state.mapping = data.mapping;
    state.journeys = data.journeys; state.next = data.next;
    restore();
  } catch (e) {
    $("main").replaceChildren(h("div", { class: "card" }, h("div", { class: "banner bad" }, h("strong", {}, "Could not reach reqtable."), "Close this tab and start it again with --gui.")));
    return;
  }
  $("wfopen").addEventListener("click", openDrawer);
  $("drawer-close").addEventListener("click", () => $("drawer").close());
  $("drawer").addEventListener("click", (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });
  renderWorkflow();
  window.addEventListener("hashchange", route);
  route();
}
"""
