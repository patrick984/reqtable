# Allowed values

In a traceability Develop report, a column with `Value` records (Priority and Verification Method in the UAT table) edits against its defined values. The editor lists exactly those values with their definitions, Verification Method accepts several semicolon-separated values, and a cell with trace findings carries a flag button that opens the finding.

## Sub-features

- `value-suggestions` lists the defined values and their definitions for a constrained column, in table order, with aliases left out.
- `value-filter` narrows the list by prefix first, then by contained text.
- `multi-segment` completes the semicolon-separated segment under the caret on a `Multiple=Yes` column.
- `trace-marker` flags every cell with a trace finding and opens that finding.
- `values-view` lists Value and Field records under Glossary → Values.
- `add-value` adds a Value record from the Field, Name, Definition and Aliases form.
- `rename-value` rewrites the rows that use a renamed value in the same undo step.

## How to get to it (user POV)

- Open `<URL>uat-develop.html`.
- Edit a Priority or Verification Method cell with `Return`, `F2` or a double-click.
- Click the flag button in a cell, or open **View → Links**.

## Driving it with the browser pane

Preconditions:

- `<URL>uat-develop.html` is loaded fresh and the harness hooks are installed.
- The Requirements view is showing and `Priority`, `Verification Method` and `Verification Level` columns are visible (they are by default).

- **Suggestions with definitions.** Select REQ-016's Priority cell (`td[data-column="Priority"]` in `tr[data-row-id="REQ-016"]`), press `Return`. `.cell-suggestions button` yields the Priority values other than the current one, in table order (`Must`, `Could`). Each button holds the value and a `small.suggestion-detail` with the definition, and carries `title` and `aria-description` with the same text. Observed-values columns such as Category show buttons with no `.suggestion-detail`.
- **Filter by contained text.** In a Verification Method editor type `str`. The only button is `Demonstration`. Clear the text and type `A`: `Analysis` (starts with the text) comes before `Demonstration` (only contains an `a`).
- **Single value commit.** In the Priority editor press `ArrowDown`, then `Return` on a button. The editor closes and the cell shows the chosen value.
- **Segment completion.** Select a Verification Method cell, press `Return`, type `Test; de`. The buttons exclude `Test`. Press `ArrowDown`, `Return` on `Demonstration`. The textarea reads `Test; Demonstration`, the editor is still open, and the caret is at the end. Type `; ` and the buttons list the remaining values. Press `Return` in the textarea to commit.
- **Marker appears.** In REQ-016's Priority editor select all, type `Shoud`, press `Return`. `tr[data-row-id="REQ-016"] td[data-column="Priority"] .trace-marker` exists with `aria-label` `1 trace finding for REQ-016, Priority`, and its `title` includes the message.
- **Marker opens the finding.** Click the marker. `#trace-panel` is visible, `#trace-findings` has `open`, and the matching `#trace-issues li` has class `trace-finding-active`.
- **Marker clears on Undo.** Click a grid cell and press `cmd+z`. The `.trace-marker` in that cell is gone and the Priority cell reads its previous value.
- **Values view.** Install the stubs from SKILL.md (`window.__dialogs`, `confirm` returns true). Click `[data-trace-view="glossary"]`, then `[data-glossary-kind="values"]`. That button has `aria-pressed="true"`, `[data-glossary-kind="terms"]` has `false`, and `#trace-term-add` is hidden while `#trace-value-add` is visible. Every body row is Type `Value` or `Field` (read the `td[data-column="Type"]` cells). The ID column is hidden and `#result-count` reads `N value records`. Click `[data-glossary-kind="terms"]` and the Term rows return.
- **Add value.** In Values mode click `#trace-value-add`. In `#trace-editor`, `#trace-value-field` lists the constrained columns (`Priority`, `Verification Method`, `Verification Level`, `Execution`) before other columns. Choose `Priority` with `form_input`, set `#trace-record-name` to `Won't`, `#trace-record-content` to any definition, and submit with the Apply button. A row `tr[data-row-id="VAL-PRIORITY-WON-T"]` exists with Type `Value`, Field `Priority` and Name `Won't`, and it holds focus. Adding `Won't` again gives `tr[data-row-id="VAL-PRIORITY-WON-T-2"]`.
- **Rename follows.** In Values mode select the Name cell of `tr[data-row-id="VAL-PRIORITY-COULD"]` (`td[data-column="Name"]`), press `Return`, select all, type `May`, press `Return`. `window.__dialogs` ends with `{type:"confirm", message:"Rename “Could” to “May” in 1 row that uses it?"}`. Switch to Requirements: `tr[data-row-id="REQ-166"] td[data-column="Priority"]` reads `May` and has no `.trace-marker`. Click a grid cell and press `cmd+z` once: REQ-166's Priority reads `Could` again and the Value row's Name reads `Could`.

## Gotchas

- Suggestions come from the Value records, not the cells. A value typed by hand that is not defined is accepted and flagged, never blocked.
- A cell that is open in the inline editor has no marker until the edit is applied or cancelled.
- A cell can hold both `.quality-marker` and `.trace-marker`. Select by class, not by position.
- If `confirm` returns false the Name still changes and the rows keep the old value, now flagged.
- Print hides `.trace-marker`. Do not look for it in a print preview.
