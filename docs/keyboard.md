# Keyboard use

Choose **Keyboard help**, or press `?`, for the complete shortcut list. Use the arrow keys or Vim's `h`, `j`, `k`, and `l` to move one cell. Use Home/End or `0`/`$` to reach either end of a row. Press `/` to focus the selected column's filter or, when browsing comments, the comment search field.

Screen readers announce the requirements table as a grid. The ID cell is each row's header, every row and column reports its position in the whole table, including rows a large table has not drawn yet, and selected cells are announced as selected. Tab still moves through the grid as one stop, and the arrow keys move between cells.

Develop reports open in **Spreadsheet** mode. Open **View → Settings** to switch to **Vim**. In Spreadsheet mode, typing on an editable cell starts replacing its value. In Vim mode, `i` edits, `c` opens comments, and `o` / `O` insert a requirement below or above. Use `gg` and Shift+G to reach the first row or the blank entry row.

In both modes, Enter or F2 opens a cell for editing. While editing, Tab and Shift+Tab apply the edit and move to the next or previous visible cell. Ctrl/Cmd+Enter applies in place, and Escape cancels. In Vim mode, Enter inserts a newline. Outside the editor, Ctrl/Cmd+Arrow jumps through filled cells, Ctrl/Cmd+Home and Ctrl/Cmd+End reach the data corners, and Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z undo and redo. Ctrl/Cmd+Y also redoes an edit.

While editing in Spreadsheet mode, Enter commits and moves down, Shift+Enter commits and moves up, and Alt/Option+Enter inserts a newline. Clicking another cell commits the edit and selects that cell. Double-click or press F2 to select the existing value in a categorical field or place the caret at the end of a text field.

Narrow cells open a wider editor anchored to the selected cell. It fits within the grid's visible width and uses the same shortcuts and suggestions as the inline editor.

With a grid cell focused in Spreadsheet mode, Ctrl/Cmd+Shift+Up or Down adds a requirement above or below. Alt/Option+Shift+Up or Down moves the selected requirement. Ctrl/Cmd+Backspace or Delete opens the delete confirmation. Plain Delete or Backspace clears the selected cells; the ID column, protected columns and removed rows are skipped, and one Undo restores them. The Edit menu shows shortcuts for the active keyboard mode. Press Alt/Option+/ to search available menu commands, then use the arrow keys and Enter to run one.

Committing an edit removes trailing whitespace and blank lines. Columns with up to 50 distinct nonempty values, each a single line of at most 60 characters, suggest existing values as you type. Click a suggestion or use Down Arrow and Enter to select it and commit the edit. Columns with defined values suggest those values instead, with their definitions, and a `Multiple` column keeps the editor open after you choose one. You can also enter a new value.

In Develop mode, right-click a cell or press Shift+F10 on a focused cell to open its actions. Drag the grip beside a requirement ID to reorder it in the normal view with source order and no filters. The line shows where the row will land. One Undo reverses the move.

Drag across cells to select a range, or use Shift+click or Shift+Arrow to extend a cell selection. Dragging past the top or bottom of the table scrolls it. Ctrl/Cmd+C copies the underlying values as tab-separated text. Selecting and copying also work in Review mode. Paste and Clear cells are Develop only. Ctrl/Cmd+V pastes starting at the active cell, in visible row and column order. The whole paste is rejected if it would touch a protected cell, a removed row, or the edge of the table. One Undo reverses a paste. The **Edit** menu lists Undo and Redo first, then **Copy**, **Paste** and **Clear cells**, which act on the selected cells. Menu **Paste** reads the system clipboard, so the browser may ask for permission. If it is refused, the status line says so and Ctrl/Cmd+V still works. **Clear cells** is separate from **Delete requirement**, which removes the whole row.

Click an ID cell to select the row, then Shift+click another ID or use Shift+Up/Down to select a block. Drag any selected row’s grip to move the whole block in its existing order.

In Develop mode, choose **View → Check requirement quality** to scan all current requirements, including filtered rows. The sidebar shows the flagged wording and a suggestion. Click a finding card or activate its title to focus the relevant cell. **Edit wording** opens the cell editor with the exact match selected. Select the amber warning icon in a cell, or press Enter on it, to open a small popover that lists that cell's findings with **Dismiss…** for each and **Show in quality panel**. Escape, a click elsewhere or scrolling closes it and returns focus to the cell. **Show rows with findings** narrows the grid. Findings refresh after committed edits and are advisory.

Open **Quality settings** in the sidebar to choose the statement column, required fields, obligation keyword and enabled checks. The defaults recognize `Requirement` or `Requirement Text` and use `shall`. A blank keyword turns off obligation checks. Set initial values in the generator configuration with `quality.requirement_column`, `quality.required_columns` and `quality.obligation`.

Use **Dismiss…** to accept a finding with a reason. The exception applies to that exact cell content and finding. **Show dismissed findings** displays the reasons and lets you restore findings. Use **File → Save report copy** to keep quality settings and dismissals with the report. Browser draft recovery can also recover these changes.

In Spreadsheet mode, use Shift+Up/Down from any cell to select consecutive requirements, then Alt/Option+Shift+Up/Down to move them together. Use the normal view in source order with no filters. The selection follows the moved rows, and one Undo reverses each move.
