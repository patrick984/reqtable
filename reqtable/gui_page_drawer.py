"""Page script for the workflow drawer: the steps collected so far, reordering, and saving them as a script."""

DRAWER_JS = r"""
function openDrawer() { renderWorkflow(); $("drawer").showModal(); }

function renderWorkflow() {
  $("wfopen").textContent = "Your workflow (" + state.steps.length + ")";
  const steps = state.steps;
  const list = h("ol", { class: "steps" });
  steps.forEach((s, i) => {
    const move = (d) => { const j = i + d; [steps[i], steps[j]] = [steps[j], steps[i]]; remember(); renderWorkflow(); };
    list.append(h("li", { class: "step" },
      h("div", { class: "head" }, h("span", { class: "name" }, (i + 1) + ". " + s.title),
        h("button", { class: "small", type: "button", "aria-label": "Move step " + (i + 1) + " up", disabled: i === 0, onclick: () => move(-1) }, "↑"),
        h("button", { class: "small", type: "button", "aria-label": "Move step " + (i + 1) + " down", disabled: i === steps.length - 1, onclick: () => move(1) }, "↓"),
        h("button", { class: "small", type: "button", "aria-label": "Remove step " + (i + 1), onclick: () => { steps.splice(i, 1); remember(); renderWorkflow(); } }, "✕")),
      s.records ? h("p", { class: "note", style: "margin:4px 0" }, "Running the script again records this again.") : null,
      h("pre", {}, s[state.shell])));
  });
  fill($("drawer-body"),
    steps.length ? list : h("p", { class: "empty" }, "Steps you run or add show up here. Put them in order, then save them as a script to repeat them any time."),
    h("div", { class: "commandbar" }, shellTabs()),
    h("div", { class: "actions", style: "margin-top:0" },
      h("button", { type: "button", disabled: !steps.length, onclick: (e) => withScript((s) => copyText(s.script, e.target)) }, "Copy script"),
      h("button", { type: "button", disabled: !steps.length, onclick: () => withScript(saveScript) }, "Save script"),
      h("button", { class: "small", type: "button", disabled: !steps.length, onclick: () => { state.steps = []; remember(); renderWorkflow(); } }, "Clear")));
}
shellViews.push(renderWorkflow);

async function withScript(use) {
  try { use(await api("/api/script", { steps: state.steps.map((s) => ({ workflow: s.workflow, values: s.values, note: s.note || "" })), shell: state.shell })); }
  catch (e) { announce(e.message); alert(e.message); }
}
function saveScript(data) {
  const url = URL.createObjectURL(new Blob([data.script], { type: "text/plain" }));
  const link = h("a", { href: url, download: data.filename }); document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
"""
