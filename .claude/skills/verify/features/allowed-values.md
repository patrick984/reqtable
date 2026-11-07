# Allowed values

In a traceability Develop report, a column with `Value` records (Priority and Verification Method in the UAT table) edits against its defined values. The editor lists exactly those values with their definitions, Verification Method accepts several semicolon-separated values, and a cell with trace findings carries a flag button that opens the finding.

## Sub-features

- `value-suggestions` lists the defined values and their definitions for a constrained column, in table order, with aliases left out.
- `value-filter` narrows the list by prefix first, then by contained text.
- `multi-segment` completes the semicolon-separated segment under the caret on a `Multiple=Yes` column.
- `trace-marker` flags every cell with a trace finding and opens that finding.

## How to get to it (user POV)

- Open `<URL>uat-develop.html`.
- Edit a Priority or Verification Method cell with `Return`, `F2` or a double-click.
- Click the flag button in a cell, or open **View → Record links and trace findings**.

## Driving it with the browser pane

Preconditions:

- `<URL>uat-develop.html` is loaded fresh and the harness hooks are installed.
- The Requirements view is showing and `Priority` and `Verification Method` columns are visible (they are by default).

- **Suggestions with definitions.** Select REQ-016's Priority cell (`td[data-column="Priority"]` in `tr[data-row-id="REQ-016"]`), press `Return`. `.cell-suggestions button` yields the Priority values other than the current one, in table order (`Must`, `Could`). Each button holds the value and a `small.suggestion-detail` with the definition, and carries `title` and `aria-description` with the same text. Observed-values columns such as Category show buttons with no `.suggestion-detail`.
- **Filter by contained text.** In a Verification Method editor type `browser`. The only button is `Manual browser test`. Clear the text and type `A`: `Automated test` and `Automated and manual test` come before values that only contain an `a`.
- **Single value commit.** In the Priority editor press `ArrowDown`, then `Return` on a button. The editor closes and the cell shows the chosen value.
- **Segment completion.** Select a Verification Method cell, press `Return`, type `Manual browser test; au`. The buttons exclude `Manual browser test`. Press `ArrowDown`, `Return` on `Automated test`. The textarea reads `Manual browser test; Automated test`, the editor is still open, and the caret is at the end. Type `; ` and the buttons list the remaining values. Press `Return` in the textarea to commit.
- **Marker appears.** In REQ-016's Priority editor select all, type `Shoud`, press `Return`. `tr[data-row-id="REQ-016"] td[data-column="Priority"] .trace-marker` exists with `aria-label` `1 trace finding for REQ-016, Priority`, and its `title` includes the message.
- **Marker opens the finding.** Click the marker. `#trace-panel` is visible, `#trace-findings` has `open`, and the matching `#trace-issues li` has class `trace-finding-active`.
- **Marker clears on Undo.** Click a grid cell and press `cmd+z`. The `.trace-marker` in that cell is gone and the Priority cell reads its previous value.

## Gotchas

- Suggestions come from the Value records, not the cells. A value typed by hand that is not defined is accepted and flagged, never blocked.
- A cell that is open in the inline editor has no marker until the edit is applied or cancelled.
- A cell can hold both `.quality-marker` and `.trace-marker`. Select by class, not by position.
- Print hides `.trace-marker`. Do not look for it in a print preview.
