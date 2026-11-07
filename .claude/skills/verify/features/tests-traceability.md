# Tests traceability

In a traceability report, `Test` and `Test plan` records sit in the same table. A requirement lists the tests that verify it in `Verified by`, a test names its plan in `Test plan`, and a test's Verification Method is checked against the defined Values.

## Sub-features

- `tests-view` lists Test plan and Test records under the Tests view, with the Add buttons in Develop mode.
- `verified-by-panel` shows a requirement's Verified by section and a test's Test plan and Verifies sections.
- `link-test` links a test to a requirement from the picker.
- `add-test` adds a Test with an optional plan through the shared record form.
- `method-check` flags an undefined Verification Method on a test.

## How to get to it (user POV)

- Open `<URL>uat-develop.html` and choose **Tests** in the view bar.
- Select a requirement and open **Links**, or select a test and open **Links**.
- Edit a test's Verification Method cell.

## Driving it with the browser pane

Preconditions:

- `<URL>uat-develop.html` is loaded fresh and the harness hooks are installed.

- **Tests view.** Click `[data-trace-view="tests"]`. It has `aria-pressed="true"` and sits between the Glossary and All fields buttons. Body rows include `tr[data-row-id="TP-UNIT"]`, `tr[data-row-id="TP-UAT"]` and the `TEST-` rows (Type `Test`). Column headers read ID, Type, Name, Test plan, Verification Method, Reference, Requirement, and `#result-count` reads `N test records`. `#trace-test-actions` is visible with `#trace-test-plan-add` and `#trace-test-add`.
- **Requirement panel.** Click `[data-trace-view="requirements"]`, select a cell in `tr[data-row-id="REQ-248"]`, click `#trace-selected-links`. `#trace-record section` with `h4` text `Verified by` lists `Traceability tests (TEST-TRACEABILITY)` and holds `[data-trace-pick="Verified by"]`, labelled `Link test…`.
- **Test panel.** In the Tests view select a cell in `tr[data-row-id="TEST-TRACEABILITY"]` and open Links. Sections `Test plan` (with `Automated unit tests (TP-UNIT)` and `[data-trace-pick="Test plan"]`) and `Verifies` (REQ-248 and others) appear. Selecting TP-UNIT shows a `Tests` section listing every test.
- **Link test.** Select REQ-001, open Links, click `[data-trace-pick="Verified by"]`. `#trace-picker` lists only Test records. Click the `TEST-CORE` button in `#trace-candidates`. REQ-001's panel then shows `TEST-CORE` under Verified by, and TEST-CORE's panel lists REQ-001 under Verifies.
- **Add test.** In the Tests view click `#trace-test-add`. In `#trace-editor`, `#trace-test-plan` lists `No test plan`, then the plans. Set `#trace-record-id` to `TEST-NEW`, `#trace-record-name` to `New test`, choose `Automated unit tests (TP-UNIT)` with `form_input`, and submit Apply. `tr[data-row-id="TEST-NEW"]` exists with Type `Test` and Test plan `TP-UNIT`. Undo with `cmd+z` removes it.
- **Method check.** Edit the Verification Method cell of `tr[data-row-id="TEST-NEW"]`, select all, type `Eyeball it`, press `Return`. The cell carries a `.trace-marker`, and clicking it opens `#trace-findings` with a message about an undefined value.

## Gotchas

- **Verified by** and **Test plan** are hidden in the Requirements view like the other link columns. Use All fields to see them as cells.
- The Tests view lists only Test and Test plan rows. A Test never appears in the Systems tree because it has no `Part of`.
- **Reference** only becomes a clickable link for HTTP, HTTPS and mailto targets. The UAT data therefore stores repository paths as code spans, such as `` `tests/test_core.py` ``, not as relative Markdown links.
- `TEST-XLSX` and `TEST-GIT-BASELINE` verify no requirement. Their Verifies section is empty by design.
