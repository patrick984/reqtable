# Browser history and unsaved drafts

In a traceability report, view tabs, Terms/Values, Grid/Matrix, System scope, Include subsystems and record jumps each add a browser history entry whose address ends in `#view=…&…`. Back and Forward restore that place, and opening a report with such a fragment lands there. In Develop mode, leaving with unsaved changes triggers the browser's leave warning, and unsaved edits are kept as an IndexedDB draft that a reopened report offers to restore.

## Sub-features

- `history-steps` Back and Forward walk tab, layout and scope steps, and the Links panel Back (`#trace-back`) uses the same history.
- `history-deeplink` a fragment such as `#view=glossary&record=TERM-CSV` opens that view with the record selected.
- `history-blocked` Back with a cell editor open is refused and the address stays put.
- `leave-warning` `beforeunload` is cancelled only while the report is dirty.
- `draft-restore` an edit is written to IndexedDB `reqtable-drafts`, offered on reload, and restored as an edit.
- `draft-regenerated` a draft for a regenerated report offers Download CSV, never Restore.

## How to get to it (user POV)

- Click tabs, Grid/Matrix or Terms/Values, change the System selector, or follow a link, then press the browser's Back or Forward.
- Open a report with an address ending in `#view=…`.
- Edit a cell in Develop mode, then close or reload the report and reopen it.

## Driving it with the browser pane

Preconditions:

- `<URL>uat-develop.html` is loaded fresh and the harness hooks are installed. Set the viewport to 1280x800 if the pane is hidden.

- **History steps.** Click `[data-trace-view="verification"]`, `[data-view-mode="matrix"]` and `[data-trace-view="glossary"]`. The URL ends `#view=verification`, `#view=verification&mode=matrix`, then `#view=glossary`. `navigate("back")` three times returns through Matrix, Grid and Requirements (empty fragment, `#trace-back` hidden). `navigate("forward")` returns to Verification. Setting `#trace-system` to `system:SYS-EXTRACT` adds `#system=SYS-EXTRACT`, and Back restores `All requirements` with 267 rows.
- **Deep link.** Navigate to `<URL>uat-develop.html?fresh=1#view=glossary&record=TERM-CSV`. The Glossary tab is pressed and the focused cell's row is `TERM-CSV`.
- **Blocked.** In Tests, select a cell, press `Return`, then `navigate("back")`. The editor stays open, the address keeps the Tests entry, and `#trace-status` reads `Apply or cancel the cell edit before changing views or editing links.`
- **Draft restore.** Edit REQ-001 Priority to `Should`, wait 2 s. IndexedDB `reqtable-drafts` store `drafts` has a record for `location.pathname` with `changedCount` 1. Reload with `force:true`. `#draft-banner` shows `Unsaved edits from … (1 row changed).` with `#draft-restore`. Click it: the cell reads `Should` with `.edited-cell`. `cmd+z` returns to `Must` and the record is deleted after the debounce.
- **Leave warning.** Dispatch `new Event("beforeunload",{cancelable:true})`. `defaultPrevented` is true only while the report has unsaved changes.
- **Regenerated report.** With a draft stored, regenerate the report at the same path from a CSV with one changed cell and reload with `force:true`. The banner reads `Unsaved edits from an earlier version of this report (…).` with `#draft-download` and no Restore. Download gives `<name>-draft.csv` with a UTF-8 BOM and the draft rows. `#draft-discard` deletes the record.

## Gotchas

- The pane's own reload does not show the browser's Leave site dialog, so the warning is proven through the event, not the dialog.
- The pane cannot open `file:///`. For file proofs, inject a probe script into a scratch copy and run Chrome `--headless=new --dump-dom` against `file://<copy>#view=…`.
- A hidden pane does not run `requestAnimationFrame`; read layout synchronously.
- Drafts follow the File menu Autosave checkbox. With Autosave off, no draft is written; the leave warning still works.
