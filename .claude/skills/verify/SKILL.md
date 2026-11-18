---
name: verify
description: Drive reqtable's generated HTML reports in the Claude browser pane to prove a change works the way a user sees it. Covers launching fixture reports from the working tree on localhost, a doctor check, driving Review and Develop reports through real menus and cells, capturing downloads such as Save report copy and Export for review, and cleanup. Use after changing reqtable/html_report.py, quality.py, traceability.py, glossary.py or the CLI, or when asked to verify, demo or reproduce report behavior.
---

# Verify reqtable

reqtable is a Python CLI that writes self-contained HTML reports. Users touch two surfaces: the CLI (`python3 dist/reqtable.pyz …`) and the generated report in a browser. Most behavior lives in the report's embedded JavaScript, so most proofs drive the report.

Read [features/README.md](features/README.md) before driving, then use the matching feature file as the recipe.

## Launch

From the repo root:

```sh
.claude/skills/verify/scripts/launch.sh            # run id defaults to a timestamp
.claude/skills/verify/scripts/launch.sh my-run     # or name it
```

It rebuilds `dist/reqtable.pyz` from the working tree, generates these reports into `.verify-runs/<run>/site/`, and serves that directory with `python3 -m http.server` on a free `127.0.0.1` port:

- `snapshot.html` is a Review snapshot of `fixtures/base.csv` (R1 to R4).
- `develop.html` is a Develop report of the same CSV.
- `diff.html` is a Review diff of `examples/requirements-old.csv` against `examples/requirements-new.csv`.
- `uat-develop.html` is a Develop traceability report of `requirements-uat.csv`.

Ready means the script printed `RUN_DIR=` and `URL=`. It polls until `develop.html` serves a report and exits non-zero otherwise. Each run gets its own directory and port, so runs can share the machine. A report is a static file, so reloading the page resets it to the generated state.

## Doctor

```sh
.claude/skills/verify/scripts/doctor.sh .verify-runs/<run>
```

Read-only. It checks that the recorded pid is alive and is this run's `http.server`, that the pid owns the port, that all four pages serve a report, and that `reqtable/*.py` has not changed since launch. Any `FAIL` on the last line means the reports are stale. Clean up and launch a new run.

## Drive

Use the built-in browser (`mcp__Claude_Browser__*`). Open `<URL>develop.html` (or another page) with `navigate`. Never open the report as `file://`, because the pane shows local files as static snapshots with no JavaScript.

**Install the harness hooks once per page load,** before the action that needs them. They record native dialogs and capture downloads instead of letting them reach the pane:

```js
window.__dialogs=[];window.__downloads=[];
window.confirm=message=>{window.__dialogs.push({type:"confirm",message});return true;};
window.alert=message=>{window.__dialogs.push({type:"alert",message});};
window.prompt=(message,value)=>{window.__dialogs.push({type:"prompt",message,value});return window.__promptAnswer??null;};
window.showSaveFilePicker=undefined;
const create=URL.createObjectURL.bind(URL);
URL.createObjectURL=blob=>{window.__downloads.push(blob);return create(blob);};
const click=HTMLAnchorElement.prototype.click;
HTMLAnchorElement.prototype.click=function(){if(this.download){window.__downloads.at(-1).filename=this.download;return;}return click.call(this);};
```

The pane auto-cancels native `confirm()`, and reqtable uses it for Delete requirement. Set `window.__promptAnswer` before an action that calls `prompt()`, such as Rename ID…, which asks `Rename requirement <ID>:`. Record `window.__dialogs` in the evidence so the dialog text is proven too.

**Act like a user.** Use `computer` clicks and keys on cells and menu items. Use `find` to get refs for buttons by accessible name, for example `find("Export changes for review")`. Stable handles:

- Tables with more than 300 display rows are windowed: only rows near the viewport are in `#requirements-body`, between `tr.window-spacer` rows. Find rows through `grid.display` (the ordered display model) and move to one with `focusGridCell(row, column)` before reading its cells. Scroll updates run in `requestAnimationFrame`, which does not fire while the pane is hidden: after setting `scrollTop` from script, call `updateWindow()` or use a real wheel scroll.
- To test performance, generate a large table by repeating the `requirements-uat.csv` requirements with new IDs (about 5,000 rows) and time `render()` with `performance.now()` plus a forced layout. Run more than three renders in separate calls, because each call has a 45 s limit.
- Menus are `<details class="popup-menu">` with summaries `File`, `Edit`, `View`, `Filter`, `Columns`, `Help`.
- Menu buttons have ids: `#save-csv`, `#save-as`, `#save-copy`, `#export-review`, `#export-review-changes`, `#add-end`, `#add-above`, `#add-below`, `#move-up`, `#move-down`, `#rename-requirement`, `#delete-requirement`, `#undo-edit`, `#redo-edit`, `#unsaved-diff`, `#review-comparison`, `#view-toggle`, `#check-quality`.
- Grid rows are `tbody tr[data-row-id="<ID>"]`, with status classes `row-added`, `row-removed`, `row-changed` and `row-unchanged`. The blank entry row has `data-row-id=""`.
- Cells are `[data-grid-cell][data-column="<column>"]`. Comment buttons are `button[data-comment-row="<ID>"][data-comment-column="<column>"]`, named `Add comment for <ID>, <column>`.
- Reviewer initials are `#reviewer-initials`. The quick comment form is `#quick-comment-form` with `#quick-comment-text`.
- The embedded report data is the JSON in `script#reqtable-data`.

Editing a cell means select it, press `Return`, `cmd+a`, type, `Return`. Adding a row means double-click the entry row's Requirement cell, type, `Return`.

**Read state from the DOM,** not from a screenshot taken right after an action. Screenshots can show the frame before the re-render. For example:

```js
[...document.querySelectorAll('tbody tr[data-row-id]')].map(r=>r.dataset.rowId+':'+[...r.classList].find(c=>c.startsWith('row-')))
```

Top-level `const` globals such as `state` and `data` are readable from `javascript_tool` on the top page. Read them only to observe. Never mutate them to stage a scenario.

**Open a captured download as the next user would** in an iframe over the page:

```js
const html=await window.__downloads.at(-1).text();
const frame=document.createElement("iframe");frame.id="opened-download";
frame.style.cssText="position:fixed;inset:0;width:100vw;height:100vh;background:white;z-index:9999;border:0";
document.body.append(frame);frame.srcdoc=html;await new Promise(r=>frame.onload=r);
const doc=frame.contentDocument;
```

Inside the frame, read data with `JSON.parse(doc.getElementById("reqtable-data").textContent)`. The report's CSP forbids `eval`, so `frame.contentWindow.eval` and reading its `const` globals fail. Drive the frame with `doc.querySelector(…).click()` and form events, and install the harness hooks on `frame.contentWindow` before an action inside it that downloads or confirms.

**CLI behavior** is driven directly, with output kept under the run:

```sh
python3 dist/reqtable.pyz --extract-comments <report.html> --id-column ID -o .verify-runs/<run>/evidence/<name>.csv
```

## Evidence

Write proof into `.verify-runs/<run>/evidence/` (gitignored). For each feature, save one JSON file with the feature ID, the entry point, the user actions taken, the DOM state read after each key action, the parsed fields of any captured download, recorded dialogs, and a `verdict`. For CLI proofs, save the command, stdout, stderr, exit code and output file.

Proof standards:

- Exercise the user path: menus, keys and cells. Do not set `state` or call internal functions to create the scenario.
- Capture the action and the resulting state, not only the final screen.
- For a download, prove the content by parsing its `reqtable-data` JSON and by opening it in the iframe as the recipient would.
- A screenshot is supporting evidence only, since the pane does not save it to disk.

## Cleanup

```sh
.claude/skills/verify/scripts/cleanup.sh .verify-runs/<run>
```

It stops only the server pid this run recorded (after checking its command line), removes `site/` and `server.env`, and keeps `evidence/`. Run it after every attempt, including failed ones. Delete `.verify-runs/<run>/` yourself only when the evidence is no longer needed.

## Gotchas

- Browser downloads cannot reach disk from the pane, so a browser-saved report cannot be fed to the CLI's `--extract-comments`. Prove extraction on a report that exists on disk (a generated one), and prove browser-saved content through its embedded JSON.
- Never click menus or cells by remembered coordinates. A save status line appears under the title after the first save or export and pushes the whole grid down, so an old coordinate hits a header and sorts the table. Get a fresh ref from `find` (the `File` summary is found by `find("File")`) or take a new screenshot first.
- Menus are `<details>` toggles. Confirm the menu is open (`document.querySelector('details.popup-menu[open] summary')?.textContent`) before clicking an item, because a second click on a summary closes it. Clicking a ref that resolves to an inner `<span>` label can miss the button. Prefer a ref that `find` reports as a `button`.
- The pane is Chromium and offers `showSaveFilePicker`, which would open a native Save dialog the agent cannot drive. The harness hooks remove it, so Save CSV and Save CSV as… fall back to a download that the hook captures. Writing through a real file handle (and autosave to that file) is not covered by this harness.
- The pane delivers no `copy` or `paste` events for `cmd+c`/`cmd+v`, and refuses `navigator.clipboard` reads and writes. To prove the Edit menu's Copy, wrap `navigator.clipboard.writeText` to record the text it receives. To prove Paste, stub `navigator.clipboard.readText` to return tab-separated text before choosing Edit → Paste. A real clipboard round trip is not covered by this harness.
- Autosave and reviewer initials use browser storage per origin. Each run has its own port, so storage from an older run does not leak in. Within a run, reload clears page state but not storage, so expect a recovery prompt for drafts autosaved earlier in the same run.
