# User acceptance checklist

Use `requirements-uat.html` for the full snapshot and `examples/requirements-diff.html` for diff behavior.

## Snapshot report

1. Open `requirements-uat.html` with networking disabled.
2. Confirm all requirements appear and no Status column is shown. Confirm the header does not repeat the requirement total above the toolbar count.
3. Hide and restore columns using the column chooser.
4. Filter Category for `security`, then add a second filter in Priority for `must`.
5. Clear filters and confirm all requirements return.
6. Sort ID ascending, descending, and back to source order.
7. Confirm long requirements and acceptance criteria wrap without becoming unreadable.
8. Confirm typed filter text and placeholder text are readable in both light and dark modes.
9. Drag each header divider and confirm only the column to its left resizes.
10. Double-click a divider and confirm the column to its left auto-sizes to representative content.
11. Confirm narrow categorical columns start compact while narrative columns receive more width.
12. Click and keyboard-focus different cells and confirm the selected cell retains a clearly shaded background.
13. Use `/` from several selected cells and confirm the matching column filter receives focus with its text selected.
14. Enter filter text, use its `×` button to clear it, and confirm all matching rows return.
15. Press Down Arrow and Enter from filters and confirm focus moves to the same column in the first matching row.

## Diff report

1. Open `examples/requirements-diff.html`.
2. Confirm counts show three changed, one added, one removed, and zero unchanged requirements.
3. Switch between unified and side-by-side views.
4. Confirm changed words and lines are highlighted, including the multiline SYS-002 requirement.
5. Use status controls and the Changes only action.
6. Sort by Requirement and confirm the removed row uses its old value.
7. Narrow the browser window and confirm old/new panes stack with labels.
8. In unified view, confirm added rows show no empty red block and removed rows show no empty green block.

## Comments and saving

1. Enter reviewer initials if the field is blank.
2. Select a cell `+`, confirm a nearby popup opens, add a comment, and use its full-sidebar action.
3. Add a second comment to that cell and one comment to another cell.
4. Confirm comment indicators show the correct counts and `Unsaved comments` appears.
5. Hover and keyboard-focus a numbered indicator and confirm its comment preview appears.
6. Confirm the numbered indicator color is visibly different from an unpopulated `+` control.
7. Reopen the quick-comment popup and confirm the latest existing comment remains visible and earlier comments are summarized.
8. Confirm the popup action is labelled `Show sidebar` and opens that cell in the sidebar.
9. Browse comments and search by text, initials, requirement ID, and column. Select Browse comments again and confirm the sidebar closes.
10. Filter the comments browser by reviewer, column, and diff status.
11. Navigate from a comment back to its cell.
12. Edit one comment inline and confirm it is marked edited, no new comment is created, and the sidebar returns to the same browse or single-cell view. Cancel another inline edit and confirm the same view and scroll position are retained. Delete another comment and confirm the prompt.
13. Choose Save report copy and confirm the suggested name ends in `-reviewed-<initials>-YYYYMMDD-HHMMSS.html`.
14. Reopen the saved copy offline and confirm all retained comments appear with no initial unsaved indicator.
15. Extract comments with:

    ```sh
    python reqtable.pyz --extract-comments REPORT-reviewed-PN.html --id-column ID -o comments.csv
    ```

16. Open `comments.csv` and confirm each row's Comments field is a valid JSON array.
17. Add a comment to removed requirement SYS-005, save, and confirm default diff extraction refuses comment loss.
18. Repeat extraction with `--csv-base union` and confirm SYS-005 and `_Diff Status=removed` appear.

## Export for review

1. In Develop, edit a requirement and choose **File → Export for review**. Confirm the `-for-review-…html` download and verify the Develop report still marks the edit unsaved.
2. Open the download offline in a fresh browser profile. Confirm it opens in Review mode with the edited value, traceability views if enabled, and existing comments on current rows. Enter reviewer initials, add a comment, and use **Save report copy** to download the annotated Review file.
3. Export from a Develop comparison report. Confirm the download shows the current rows as a snapshot, with the old baseline, removed rows, and comments on removed rows excluded.
4. With an established saved baseline, edit, add, remove, and reorder rows in Develop. Before saving, choose **File → Export changes for review**. Open the copy offline and verify the comparison shows these changes against the last save. Switch to **Show current requirements**, then back to **Show changes since last save**. Comment on a removed row, save a report copy, and verify the comment and comparison survive reopening.
19. Confirm the ID column never shows an add-comment control and Enter/C does not open comments there.
20. Confirm a blue `+` appears only in the selected cell and a cell under the pointer, while populated comment counts remain red and visible.
21. Confirm stored timestamps include an offset and displayed timestamps use local `YYYY-MM-DD HH:MM:SS` format.
22. Open a cell from Browse comments, use Back, and confirm the searchable browse view returns. Cancel an edit and confirm it also returns there.
23. Use Go to cell, add, and edit while the sidebar is open; confirm it stays open. In Browse comments, press `/` and confirm search receives focus.
24. Resize the sidebar using its left edge and confirm its default width is narrower than the earlier report.
25. Change reviewer initials and confirm distinct reviewer colors. Reopen a quick popup using matching initials and edit the latest comment.
26. Select Comments only and confirm requirements without comments are hidden.
27. Focus Priority, Verification Method, and Category filters and select exact values from their checkbox lists.
28. Reload another generated report and confirm reviewer initials persist when the browser permits local-file storage.
29. In the quick popup, confirm the author action is labelled Edit.
30. Select exact filter values, clear them with `×`, and confirm the input returns to the `Filter…` placeholder.

## Develop mode

Generate and open an editable report:

```sh
python reqtable.pyz requirements-uat.csv --id-column ID --document-mode develop -o requirements-uat-develop.html
```

1. Confirm the header says Develop mode and the editing controls are visible. Open the ordinary Review report and confirm those controls are hidden and editing gestures have no effect.
2. Double-click a non-ID cell, edit its Markdown source, and Apply. Repeat using Enter and F2. Confirm Escape and Cancel discard an edit.
3. Confirm an ID cell cannot be edited inline.
4. Select a row and use Rename ID. Confirm empty and duplicate IDs are rejected, then complete a valid rename and verify its comments follow the new ID.
5. Add a uniquely identified requirement and edit its blank fields.
6. Delete a requirement without comments and undo/redo the deletion.
7. Delete a requirement with comments and confirm the warning explicitly includes comment deletion; undo and confirm both return.
8. Apply several edits and confirm the unsaved indicator distinguishes requirements, comments, and both.
9. Choose Compare with → Last save and verify added, removed, changed, and unchanged statuses. Switch the unsaved comparison between unified and side-by-side views.
10. Revert a cell to its saved value and confirm its diff disappears.
11. Save report copy, confirm the developed filename convention, reopen it, and verify it is clean and remains in Develop mode with all current rows.
12. Use Save CSV. Where a native picker is offered, save directly; otherwise confirm a download occurs. Parse the file and verify quoted, multiline, Unicode, and comma-containing values round-trip.
13. Confirm the exported CSV contains the Comments column by default and its entries are valid JSON arrays.
14. After CSV saving, choose Compare with → Last save and confirm there are no outstanding requirement changes. Make another edit and confirm only that edit appears.

## Accessibility and print

1. Navigate every control with the keyboard and confirm focus is visible.
2. Confirm controls and comment indicators have understandable accessible names.
3. Confirm statuses remain understandable without relying on color.
4. Check light and dark browser color schemes.
5. Open print preview and confirm interactive controls are hidden while the table remains readable.
6. Open Columns, then Status, and confirm the first popup closes. Confirm Show all and Defaults close Columns.
7. Open Keyboard help (button and `?`) and verify the shortcut list.
8. Focus a table cell and test Arrow keys, `H`/`J`/`K`/`L`, Home/End, `0`/`$`, Ctrl+Home/Ctrl+End, `G`/Shift+`G`, Page Up/Page Down, Enter or `C`, `/`, and Escape.
9. Navigate to cells beyond every edge of the viewport and confirm the entire selected cell remains visible below the sticky headers.
10. In a diff report, scroll horizontally and confirm keyboard navigation never leaves a selected cell behind the sticky Status column.
11. Navigate up and down beside the horizontal scrollbar and confirm both the top and bottom cell borders remain visible.

## Develop editor and save workflow (2.1)

1. Navigate File, Edit, View, Filter, and Columns using Tab, Left/Right, Up/Down, Home/End, Enter, and Escape. Verify Escape returns focus to the menu heading and disabled items are skipped. Check Review mode hides Edit and the Develop-only File actions.
2. Double-click a non-ID field to enter editing. Inside the textarea double-click a word and triple-click the field. Check the green tick and red cross have accessible names and that Enter on the tick commits. Verify Ctrl/Cmd+Enter and Escape. Check the edit marker stays in the padding.
3. Apply an edit, then test Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, and Ctrl/Cmd+Y outside the editor. Repeat in a textarea and verify native text editing handles the shortcuts.
4. Add above and below a selected row using the Edit menu and the `O`/`o` shortcuts. Confirm the new row opens for editing. Move a row, then rename its ID. Export and verify CSV row order. Undo and redo the structural changes.
5. Edit the final blank row, cancel, and confirm no row appears in the CSV. Commit a non-empty value, confirm the generated ID is unique, and verify there is still exactly one blank entry row.
6. Open **Compare with → Last save** from View. Verify unchanged rows are hidden initially and the Filter menu can show them. Move a row and look for the order-change indicator. Edit Markdown and verify bold, lists, code, and safe links still render in unified and side-by-side views with changed words highlighted.
7. With the native file picker available, use Save CSV As, make a change, then use Save CSV and verify it reuses the same destination. Cancel a later Save As and confirm the saved baseline is unchanged. Verify ordinary downloads in a browser without the picker.
8. With local storage available, edit a cell, close the report and reopen it from the same path. Confirm the browser warns before closing, then choose Restore on the banner and confirm the edit is present. With a writable handle, commit another change and verify autosave updates the CSV. Pause autosave and verify subsequent changes require a manual save.

9. In Develop mode, use Tab and Shift+Tab across row boundaries and out of the grid. Try Ctrl/Cmd+Arrow on filled cells and across a blank gap. With a filter active and a column hidden, verify Ctrl/Cmd+Home and Ctrl/Cmd+End reach the visible data corners. Use `gg` and Shift+G to reach the first row and blank entry row. Press `i` on a non-ID cell, type `hjkl` in the editor, and press Escape to return to the same cell.
10. In Chromium, click directly on the text in an editable cell, then paste a two-row, two-column block of tab-separated text. Verify all four values update and one Undo restores them. Click the text in another cell, copy it, and paste into a different cell. Verify pasting into an open cell editor or a column filter only inserts text into that field.
11. Use Alt/Option+/ to search menus and run a command. Apply two filters, then remove one from the active filter summary and verify the other remains.
12. Double-click and press F2 in Category and Acceptance Criteria. Confirm the former selects the existing text and the latter places the caret at the end. In a narrow column near the right edge, verify the editor expands within the visible grid. Choose a suggestion and confirm it commits.
13. In source order, drag one row and then a selected block. Check the drag preview and drop line. Move a selected block by holding the Spreadsheet move shortcut, then check its order and selection.
14. In **Compare with → Last save**, revert an edited cell and restore a deleted row that had a comment. Verify that the restored row includes the comment and that Undo reverses each operation.

## Requirement quality

1. Open **View → Check requirement quality** on a fixture with missing obligations, repeated keywords, placeholders and vague wording. Verify the report finds issues offline, including issues on filtered-out requirements.
2. Click a finding card to focus its cell, then use **Edit wording** to open its editor and verify the flagged occurrence is selected. Verify the grid marker opens the matching card and **Show rows with findings** filters the grid.
3. Change quality settings, dismiss a finding with a reason, then save and reopen an HTML copy. Confirm settings and the dismissal survive. Restore the finding. Dismiss it again and edit its source text to verify the old dismissal does not suppress the new finding.

## Systems and traceability pilot

Generate the Develop and Review reports using the `--traceability` commands in the [traceability guide](../traceability.md). Work on a copy of the CSV when testing saves.

1. Confirm **Requirements** opens with the core writing columns, including Verification Method. Narrow the ID column and confirm the ID sits below the grab handle. Use the **System** selector to show Python generator and Browser report in turn. Edit `REQ-003` in one scope and confirm the other shows the same edit. Select ReqTable with **Include subsystems** enabled and confirm `REQ-003` appears once.
2. Select `REQ-003`, check that its ID cell has a link indicator, and use **Links** in the workspace bar. Follow the offline workflow need into **Needs & Sources**, then return with **Back to previous record**. From the Python generator scope, follow the browser child and confirm **Reveal in grid** retains that scope. Remove the reveal via **Active filters**.
3. In **Systems**, add a subsystem under a selected parent and rename it. Use **Move to…** and verify the picker excludes the system and its descendants. Delete a system with allocations and owners, choose where to reassign each, and verify one Undo restores the system and its links.
4. Use **Allocate to…** to change several systems in one edit. Use **Add child requirement…** and verify the parent link. Enter a missing or wrong-type link in **All fields**, then confirm **Trace findings** identifies it and repair it from the Links panel.
5. Rename `REQ-003` and confirm both child references and an attached comment follow it. Cancel its deletion and confirm nothing changes. Confirm deletion, then undo and verify the record, links and comment return together.
6. In Chromium, use **Save CSV As…** and regenerate a report from the saved file with `--traceability`. Verify the edits, graph and any JSON comments survive. With networking disabled, open the Review report, navigate a trace, and save and reopen an HTML copy.
7. Open the Review report and confirm the tabs and Links are available. Generate a flat report without `--traceability` and confirm it uses the ordinary grid and preserves any project-specific `Type` column.

## Project glossary

1. With networking disabled, open **Glossary** in each traceability report. Verify both modes show the same terms with the ID column hidden. Use **Columns** to show IDs, then restore the default columns. Filter by **Name** or **Definition**, then clear the filters. Verify **Add term…** is available only in Develop mode.
2. In Requirements, activate a dotted-underlined `CSV` by click and by keyboard. Verify the definition and source appear beside the text. Press Escape and verify focus returns to the term.
3. In Develop, add a term named `Example Term` with aliases `ET; Example`. In a requirement, enter ``Example Term, ET, et, Example, ET2, https://example.test/ET, and `ET` ``. Verify only the full phrase and uppercase acronym initially link. Set the term's **Auto Link** to `Yes` and verify the standalone `Example` links. Add another term with alias `ET` and verify that spelling stops linking and appears in **Trace findings**.
4. Verify **Add term…** asks for the name and definition and assigns each new term a distinct ID. Attach a source to a term through **Links**. Save and reopen an HTML copy, then export the CSV and regenerate with `--traceability`. Verify the term, generated ID, aliases, single-word setting, and source survive.
