# Develop editing

In a Develop report, an author edits cells, adds, deletes and reorders requirements, undoes mistakes, compares with the last save, and saves the result to CSV. The `Unsaved changes` badge tracks whether the current rows differ from the last save.

## Sub-features

- `edit-cell` changes a cell value through the inline editor.
- `add-row` creates a requirement from the entry row or **Edit → Add requirement**.
- `delete-row` removes a requirement after confirmation.
- `move-row` reorders a requirement with **Edit → Move up/down** or `Alt+Shift+Up/Down`.
- `rename-id` renames an ID through a prompt and keeps comments attached.
- `undo` reverses the last change with `cmd+z` or **Edit → Undo**, and `redo` repeats it.
- `compare-last-save` shows a live diff against the last save with **View → Compare with last save**.
- `save-csv` writes the current rows and comments to CSV and clears the badge.
- `clear-cells` empties the editable cells in the selection with plain Delete/Backspace or **Edit → Clear cells**, skipping ID and removed rows, with one Undo.
- `menu-copy` and `menu-paste` run **Edit → Copy** and **Edit → Paste** on the selection as tab-separated text.

## How to get to it (user POV)

- Open `<URL>develop.html` (small fixture) or `<URL>uat-develop.html` (traceability).
- Edit a cell with `Return`, `F2` or a double-click, or by typing over it in Spreadsheet mode.
- Use the **Edit** menu, its keyboard shortcuts, or right-click a cell for actions.
- Use **File → Save CSV** or **Save CSV As…**.

## Driving it with the browser pane

Preconditions:

- `<URL>develop.html` is loaded fresh and the harness hooks are installed, including `window.showSaveFilePicker=undefined`.

- **Edit a cell.** Click R2's Requirement cell, press `Return`, `cmd+a`, type a new value, press `Return`. The cell text changes, a change marker appears, and `Unsaved changes` shows.
- **Add a row.** Double-click the entry row's Requirement cell, type text, press `Return`. A row with the next ID (R5) appears.
- **Delete a row.** Select a cell in R3, choose **Edit → Delete requirement**. `window.__dialogs` records `Delete requirement R3?` and the row is gone.
- **Move a row.** Select R1, choose **Edit → Move down**. The DOM order changes and the selection follows R1.
- **Rename.** Set `window.__promptAnswer="R9"`, select R4, choose **Edit → Rename ID**. `window.__dialogs` records `Rename requirement R4:` and the row's ID reads R9.
- **Undo.** Select a grid cell and press `cmd+z`. The last change reverts. Read the DOM order to confirm.
- **Compare.** Choose **View → Compare with last save**. Changed rows carry `row-changed`, `row-added` or `row-removed`, and unchanged rows are hidden.
- **Clear cells.** Select R2's Requirement cell, press `shift+Down`, press `Delete`. R2 and R3 read `Empty` and `Unsaved changes` shows. `cmd+z` restores both.
- **Menu Paste.** Stub `navigator.clipboard.readText=async()=>"Pasted one\tMust\r\nPasted two\tShould"`, select R3's Requirement cell, choose **Edit → Paste**. R3 and R4 read `Pasted one | Must` and `Pasted two | Should`. One `cmd+z` restores both.
- **Menu Copy.** Wrap `navigator.clipboard.writeText` to record its argument, select R1 to R2 in Requirement, choose **Edit → Copy**. The recorded text is R1 and R2's values joined by `\r\n`.
- **Save.** Open **File** via `find("File")`, choose `find("Save CSV")`. The captured download is `base.csv` with header `ID,Requirement,Priority,Comments` and the current rows in grid order. `#save-status` reads `CSV download initiated` and `Unsaved changes` disappears.

## Gotchas

- The `Alt+Shift+Down` move works, but a screenshot taken straight after it can still show the old order. Read the DOM.
- Undo needs focus in the grid. Click a cell first, or `cmd+z` goes to whatever control has focus.
- After the first save the status line pushes the grid down. Refresh refs and coordinates before the next click.
- With the real file picker available, Save CSV opens a native dialog the pane cannot answer. Keep the picker removed.
