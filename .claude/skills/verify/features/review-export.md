# Review export

An author working in a Develop report exports a self-contained Review copy for someone else. **Export for review** shares a snapshot of the current rows. **Export changes for review** also carries the last saved rows, so the reviewer opens a comparison of additions, removals, edits and moves, and can switch to the full current table and back.

## Sub-features

- `snapshot-export` downloads a `-for-review-` Review snapshot with current rows and no old baseline.
- `changes-export` downloads a `-changes-for-review-` Review diff against the last save, including moved rows.
- `review-toggle` switches the reviewer between `Show current requirements` and `Show changes since last save`.
- `removed-row-comment` lets the reviewer comment on a removed row and keep it in a saved report copy.

## How to get to it (user POV)

- In a Develop report, open **File** and choose **Export for review**.
- In a Develop report, open **File** and choose **Export changes for review**.
- In the downloaded Review copy, open **View** and choose **Show current requirements** or **Show changes since last save**.

## Driving it with the browser pane

Preconditions:

- `<URL>develop.html` is loaded fresh and the harness hooks are installed.
- The page shows R1 to R4 from `fixtures/base.csv` with no `Unsaved changes` badge.

- **Edit a row.** Click R2's Requirement cell, press `Return`, `cmd+a`, type `The report shall show every current requirement.`, press `Return`. R2's cell shows a change marker and `Unsaved changes` appears.
- **Delete a row.** Select R3's Requirement cell, open **Edit** (confirm it is open), choose **Delete requirement**. `window.__dialogs` records `Delete requirement R3?` and R3 leaves the grid.
- **Move a row.** Select R1, choose **Edit → Move down** twice, checking the menu is open each time. The DOM row order reads `R2, R4, R1`.
- **Add a row.** Double-click the entry row's Requirement cell, type `The report shall list glossary terms.`, press `Return`. R5 appears.
- **Export changes.** Open **File** and click the ref for `find("Export changes for review")`. The last captured download is named `develop-changes-for-review-<timestamp>.html`. Its `reqtable-data` has `meta.documentMode` `review`, `meta.mode` `diff`, `meta.oldFilename` `Last saved version`, old IDs `R1, R2, R3, R4`, new IDs `R2, R4, R1, R5`, and `diffStatus` `{R1: changed, R2: changed, R3: removed, R4: unchanged, R5: added}`.
- **Open as the reviewer.** Load the download in the iframe (SKILL.md). The page shows `Review mode`. Rows read `R2:row-changed, R3:row-removed, R1:row-changed, R5:row-added`, and `#review-comparison` reads `Show current requirements`.
- **Toggle.** Click `#review-comparison` in the frame. Rows read `R2, R4, R1, R5`, all `row-unchanged`, and the button reads `Show changes since last save`. Click again to return to the comparison.
- **Comment on the removed row.** In the frame, set `#reviewer-initials`, click `button[data-comment-row="R3"]`, fill `#quick-comment-text`, submit `#quick-comment-form`. Install the download hook on `frame.contentWindow`, choose **File → Save report copy**, and parse the new download. Its comments include the R3 comment and its `diffStatus` still marks R3 `removed`.
- **Snapshot export.** On a fresh page, make one edit, choose **File → Export for review**. The download is named `-for-review-`, `meta.mode` is `snapshot`, and `source.old` is `null`.

## Gotchas

- R4 is hidden in the reviewer's comparison because changes-only is on at open. It reappears with **Show current requirements**.
- Moving R1 to the end flags only R1 as changed. If R2 or R4 also show as changed, move detection has regressed.
- Saving CSV in the author's page advances the baseline. Export changes before saving, or the comparison will be empty.
- Comments on removed rows are kept only in the changes export. The snapshot export drops them by design.
