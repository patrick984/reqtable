"""Page script for the last page of a task: the command, Run, the result, and what usually comes next."""

RUN_JS = r"""
let previewSeq = 0;
function refreshPreview() { persistSession(); later("preview", fetchPreview, 120); }
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
    h("h2", {}, "The command that will run"),
    h("div", { class: "commandbar" }, shellTabs(),
      h("button", { class: "small", type: "button", disabled: !ready, onclick: (e) => copyText(text, e.target) }, "Copy command")),
    ready ? h("pre", { class: "command", tabindex: "0", "aria-label": "Command for " + shellName() }, text)
          : h("p", { class: "hint" }, p && p.error ? p.error : "Working out the command…"),
    replaces, h("div", { class: "actions" }, run, add));
  renderWorkflow();
}
shellViews.push(() => { renderPreview(); });

function makeStep(w, values, command) {
  return { id: String(Date.now()) + Math.random().toString(16).slice(2), workflow: w.id, title: w.title, records: w.records,
    values, sh: command.sh, powershell: command.powershell, argv: command.argv };
}
const stepFromForm = () => makeStep(workflow(), JSON.parse(JSON.stringify(state.values[state.current])), state.preview);

function pushStep(step, announceIt) {
  const last = state.steps[state.steps.length - 1];
  if (last && last.workflow === step.workflow && JSON.stringify(last.argv) === JSON.stringify(step.argv)) return false;
  state.steps.push(step); remember(); renderWorkflow();
  if (announceIt) announce("Added to your workflow: " + step.title);
  return true;
}
function addStep(announceIt) { return pushStep(stepFromForm(), announceIt); }

async function runNow() {
  const id = state.current; const w = workflow();
  const button = $("runbtn"); button.disabled = true; button.textContent = "Running…";
  $("result").replaceChildren(h("div", { class: "card" }, h("p", { class: "hint" }, "Running. Big spreadsheets can take a moment…")));
  const values = JSON.parse(JSON.stringify(state.values[id]));
  let data;
  try { data = await api("/api/run", { workflow: id, values }); }
  catch (e) { data = { error: e.message }; }
  if (state.current !== id || !$("result")) return;
  button.disabled = false; button.textContent = "Run";
  renderResult(w, data, values);
}

const EXIT_WORDS = { 2: "reqtable could not use these settings.", 3: "reqtable could not read an input file.", 4: "reqtable could not write the result file." };

function outputTable(w, text) {
  const lines = text.split("\n").filter((l) => l.trim());
  if (!lines.length || !lines.every((l) => l.includes("\t"))) return h("pre", { class: "output" }, text);
  return h("div", { class: "xscroll" }, h("table", { class: "grid" }, h("thead", {}, h("tr", {}, w.table.map((c) => h("th", {}, c)))),
    h("tbody", {}, lines.map((l) => h("tr", {}, l.split("\t").map((c) => h("td", { title: c }, c)))))));
}

function renderResult(w, data, values) {
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
    if (w.records) card.append(h("p", { class: "note" }, "This step was not added to your workflow, because running the script again would record it again. Use “Add to workflow” if you want that."));
    else if (pushStep(makeStep(w, values, data), false)) card.append(h("p", { class: "note" }, "This step was added to your workflow."));
  } else if (answer) {
    card.append(h("div", { class: "banner soft", role: "status" }, h("strong", {}, outcome + "."), h("span", {}, "That is an answer, not a failure. Nothing was recorded and nothing was added to your workflow.")));
  } else {
    const words = data.exit_code === null ? "reqtable stopped because this took too long." : (EXIT_WORDS[data.exit_code] || "Something went wrong.");
    card.append(h("div", { class: "banner bad", role: "alert" }, h("strong", {}, words + " Nothing was added to your workflow."),
      errors.map((e) => h("span", { class: "cli-error" }, e)), errors.length ? null : h("span", {}, "See the details below.")));
  }
  if (warnings.length) card.append(h("div", { class: "banner warn" }, h("strong", {}, "Worth a look"), warnings.map((l) => h("div", {}, l.replace(/^warning:\s*/, "")))));
  const html = data.outputs.find((p) => /\.html$/i.test(p));
  if (ok && html) card.append(h("div", { class: "actions" }, h("button", { class: "primary", type: "button", onclick: (e) => openReport(html, e.target) }, w.id === "gate_package" ? "Open package" : "Open report")));
  if (data.stdout.trim()) card.append(h("h2", { style: "margin-top:14px" }, "Result"), w.table.length && ok ? outputTable(w, data.stdout) : h("pre", { class: "output" }, data.stdout));
  const rest = stderr.split("\n").filter((l) => l && !/^(error|warning):/.test(l)).join("\n");
  if (answer && rest) card.append(h("h2", { style: "margin-top:14px" }, "Why"), h("pre", { class: "output" }, rest));
  if (!ok && !answer && rest) card.append(h("details", {}, h("summary", {}, "Technical details"), h("pre", { class: "output" }, rest)));
  if (data.blocked && data.blocked.length) card.append(waiveOffer(w, data.blocked));
  box.replaceChildren(card);
  if (ok || answer) box.append(...whatNext(w, ok));
  renderWorkflow();
  announce(ok ? "Done" : (answer ? outcome : "Failed"));
  refreshPreview();
  if (ok && (w.recorded || w.id === "create_baseline")) lookupGateData();
}

async function openReport(path, button) {
  try { await api("/api/open", { path }); } catch (e) { button.textContent = e.message; }
}

const journeyNext = () => {
  const j = state.journey;
  return j && j.def.steps[j.step] ? { number: j.step + 1, step: j.def.steps[j.step], work: workflowById(j.def.steps[j.step].workflow) } : null;
};

function whatNext(w, ok) {
  const out = [];
  const upcoming = journeyNext();
  if (upcoming) {
    const label = "Continue to step " + upcoming.number + ": " + upcoming.work.title;
    out.push(h("div", { class: "card" }, h("h2", {}, "Next in this job"), h("p", {}, upcoming.step.why),
      h("div", { class: "actions", style: "margin-top:0" }, h("button", { class: ok ? "primary" : "", type: "button", id: "continue", onclick: () => startNext(upcoming.work.id) }, label))));
  } else if (state.journey) {
    out.push(h("div", { class: "card" }, h("div", { class: "banner ok", role: "status", style: "margin:0" }, h("strong", {}, "That was the last step of “" + state.journey.def.title + "”."))));
  }
  const others = ok ? (state.next[w.id] || []).filter((s) => !upcoming || s.workflow !== upcoming.work.id) : [];
  if (others.length) {
    out.push(h("div", { class: "card" }, h("h2", {}, "What next?"),
      h("div", { class: "cards next" }, others.map((s) => h("button", { type: "button", class: "opt", onclick: () => startNext(s.workflow) },
        h("span", { class: "opt-title" }, s.label), h("span", { class: "opt-desc" }, s.why))))));
  }
  return out;
}
"""
