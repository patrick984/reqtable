# Requirements Table Generator

`reqtable` turns a requirements CSV into an interactive, self-contained HTML report. It can also compare two CSV snapshots and show line- and word-level changes in unified or side-by-side views. Tables support sorting, per-column filters, column visibility, drag resizing, and divider double-click auto-sizing.

The generator uses only the Python standard library. Generated reports contain all CSS, JavaScript, data, and review comments in one file and work offline.

## Quick start

Snapshot report:

```sh
python reqtable.pyz requirements.csv --id-column ID -o requirements.html
```

Editable Develop report:

```sh
python reqtable.pyz requirements.csv --id-column ID \
  --document-mode develop -o requirements-develop.html
```

Diff report:

```sh
python reqtable.pyz --old requirements-old.csv --new requirements-new.csv \
  --id-column ID -o requirements-diff.html
```

Extract comments from a reviewed report:

```sh
python reqtable.pyz --extract-comments requirements-reviewed-PN.html \
  --id-column ID -o requirements-reviewed.csv
```

Use `--csv-base union` when extracting a diff report if comments on removed requirements must be retained.

## Configuration

Generate the default JSON configuration:

```sh
python reqtable.pyz --print-default-config > reqtable.json
```

Pass it with `--config reqtable.json`. Explicit command-line options override configuration values.

## Review and Develop modes

Every report displays its fixed document mode prominently. **Review mode** is the default and permits comments without requirement changes. **Develop mode** is selected with `--document-mode develop` (or `"document_mode": "develop"` in JSON) and permits inline field editing, requirement addition/deletion, and validated ID renaming. A Review report cannot turn editing on from inside the HTML file.

In Develop mode, double-click a non-ID cell or press Enter/F2 to edit its Markdown source. The ID column is renamed only through **Rename ID**, which checks uniqueness and migrates attached comments. Use **Edit** to undo, redo, insert above or below, and move requirements. CSV row order records the manual position independently of the ID. The bottom entry row creates a requirement with the next ID when a non-empty field is committed. **View → Compare with last save** opens a diff with unchanged rows hidden by default. Diff cells retain safe Markdown formatting. In a Develop diff, use **Edit → Revert selected cell** to restore a changed value from the last save or the old CSV. Select a removed row and choose **Edit → Restore deleted requirement** to restore the row. In a comparison with the last save, this also restores its saved comments. Both actions support Undo.

**File → Save CSV As…** selects a writable destination in supported Chromium contexts. **Save CSV** reuses that destination for the session. Both include the configured `Comments` column by default and download a CSV if the picker is unavailable. **File → Autosave** keeps a local recovery draft where browser storage is available and writes to the selected CSV after a short pause once a writable handle is established. When you reopen the original report, choose **Recover draft** above the table to restore committed edits. The same action is available under File. **Save report copy** creates a resumable self-contained HTML file. Develop copies use names such as `requirements-developed-PN-20260913-085719.html`; Review copies retain the `requirements-reviewed-PN-20260913-085719.html` convention.

## Systems and traceability pilot

Build the pilot from ReqTable's own requirements CSV.

```sh
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  --document-mode develop -o requirements-uat-develop.html
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  -o requirements-uat.html
```

The report opens in **Requirements** with the core writing columns, including Verification Method. Use **Columns** to show more writing fields, or **All fields** to see every CSV record and relationship column. The **System** selector includes all requirements, unallocated requirements, and individual systems. Select **Include subsystems** for a combined view. A requirement shared across systems, such as `REQ-003`, appears once in that view.

Select a record and use **Links** in the workspace bar to see or add relationships. A dot in the ID cell marks records that already have links. Following a link opens the corresponding record view, and **Back to previous record** returns to the starting point. If a target is filtered out within the current grid, **Reveal in grid** shows it alongside that view. The active-filters menu can remove the exception or the system filter. **Trace findings** reports invalid links and cycles. An optional **Name** gives a requirement a short label in link lists and pickers. You can edit it in **All fields**.

In Develop mode, use **Systems** to add subsystems, rename them, move them, and delete them. The delete dialog shows affected subsystems, allocations, and owners and lets you choose how to handle each group. Use **Needs & Sources** to add needs and citations. From a requirement's **Links** panel, use **Allocate to…** to select multiple systems or **Add child requirement…** to create a new row with its parent link filled in. **Rename ID** updates incoming links and comments, and Undo restores a deletion and its links together.

Enable the pilot with `--traceability` or `"traceability": true` in the JSON configuration. The generator adds missing traceability columns. A blank `Type` means `Requirement`, and multi-value link fields use semicolon-separated IDs. Use the same flag when regenerating from a saved CSV. With the default JSON comments format, the exported comments return as annotations. See the [traceability proposal](requirements-traceability-proposal.md) for the schema and model.

### Project glossary

Open **Glossary** in either mode to browse the shared terms for the whole project. Use the **Name** or **Definition** column filter to search. In Develop mode, choose **Add term…**, then edit any of its fields in the grid. To attach a citation, select the term and choose **Links → Link source…**.

Each term is a `Term` record in the same CSV. Enter its **Name** and **Definition** and ReqTable assigns a unique ID when you add it. The Glossary hides IDs by default. Use **Columns** to show them. Separate optional **Aliases** with semicolons, for example `CSV; Delimited Text`. Set **Auto Link** to `Yes` to also link single-word Title Case spellings for that term. The **Trace findings** panel reports incomplete records, duplicate names, and spellings shared by different terms.

The browser underlines registered Title Case phrases and uppercase acronyms in rendered **Requirement**, **Acceptance Criteria**, and **Rationale** text. Matching is case-sensitive, uses whole spellings, and prefers the longest match. For example, a term named `Comma-Separated Values` with alias `CSV` matches either spelling. Code, existing links, URLs, and email addresses are skipped. Matches use continuous rendered text, so a formatting boundary inside a phrase can interrupt a match.

Click an underlined term or focus it and press Enter to read its definition in place. Press Escape to close it and return focus to the term. Links are calculated from the glossary in the open report, so the feature works offline and the prose in the CSV stays plain.

## Review comments

Enter reviewer initials in the report, then select or hover a non-ID cell to reveal its `+` control. A nearby quick-comment popup keeps the latest comment visible, permits its author to edit it, and can open the full comments sidebar. Numbered red indicators mark cells with comments. Reviewer colors are derived consistently from initials. The resizable sidebar supports browsing, searching, inline editing, deleting, and navigating to a cell without closing. Saving or cancelling an inline edit returns to the same browse or single-cell view.

The report distinguishes unsaved requirements, comments, or both. `Save report copy` downloads a new self-contained file. Browsers cannot reliably overwrite the currently open local file. Timestamps are stored as ISO 8601 values with an explicit UTC offset and displayed as `YYYY-MM-DD HH:MM:SS` in the browser's local timezone. Reviewer initials are also retained in browser storage when local-file storage is available, with the saved report's embedded value as the portable fallback.

The toolbar reports visible and total columns, and its **Comments only** control restricts the table to rows with comments. Focusing a filter for a column with two to fifty distinct non-empty values opens a scrollable exact-value checkbox list; this includes typical Category columns. Typing still performs keyword filtering. Clearing an exact-value selection with `×` restores the normal `Filter…` placeholder.

## Keyboard use

Choose **Keyboard help**, or press `?`, for the complete shortcut list. Use the arrow keys or Vim's `h`, `j`, `k`, and `l` to move one cell. Use Home/End or `0`/`$` to reach either end of a row. Press `/` to focus the selected column's filter or, when browsing comments, the comment search field.

Develop reports open in **Spreadsheet** mode. Open **View → Settings** to switch to **Vim**. In Spreadsheet mode, typing on an editable cell starts replacing its value. In Vim mode, `i` edits, `c` opens comments, and `o` / `O` insert a requirement below or above. Use `gg` and Shift+G to reach the first row or the blank entry row.

In both modes, Enter or F2 opens a cell for editing. While editing, Tab and Shift+Tab apply the edit and move to the next or previous visible cell. Ctrl/Cmd+Enter applies in place, and Escape cancels. In Vim mode, Enter inserts a newline. Outside the editor, Ctrl/Cmd+Arrow jumps through filled cells, Ctrl/Cmd+Home and Ctrl/Cmd+End reach the data corners, and Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z undo and redo. Ctrl/Cmd+Y also redoes an edit.

While editing in Spreadsheet mode, Enter commits and moves down, Shift+Enter commits and moves up, and Alt/Option+Enter inserts a newline. Clicking another cell commits the edit and selects that cell. Double-click or press F2 to select the existing value in a categorical field or place the caret at the end of a text field.

Narrow cells open a wider editor anchored to the selected cell. It fits within the grid's visible width and uses the same shortcuts and suggestions as the inline editor.

With a grid cell focused in Spreadsheet mode, Ctrl/Cmd+Shift+Up or Down adds a requirement above or below. Alt/Option+Shift+Up or Down moves the selected requirement. Ctrl/Cmd+Backspace or Delete opens the delete confirmation. The Edit menu shows shortcuts for the active keyboard mode. Press Alt/Option+/ to search available menu commands, then use the arrow keys and Enter to run one.

Committing an edit removes trailing whitespace and blank lines. Columns with up to 50 distinct nonempty values, each a single line of at most 60 characters, suggest existing values as you type. Click a suggestion or use Down Arrow and Enter to select it and commit the edit. You can also enter a new value.

In Develop mode, right-click a cell or press Shift+F10 on a focused cell to open its actions. Drag the grip beside a requirement ID to reorder it in the normal view with source order and no filters. The line shows where the row will land. One Undo reverses the move.

Use Shift+click or Shift+Arrow to extend a cell selection. Ctrl/Cmd+C copies the underlying values as tab-separated text. Ctrl/Cmd+V pastes starting at the active cell, in visible row and column order. The whole paste is rejected if it would touch a protected cell, a removed row, or the edge of the table. One Undo reverses a paste.

Click an ID cell to select the row, then Shift+click another ID or use Shift+Up/Down to select a block. Drag any selected row’s grip to move the whole block in its existing order.

In Develop mode, choose **View → Check requirement quality** to scan all current requirements, including filtered rows. The sidebar shows the flagged wording and a suggestion. Click a finding card or activate its title to focus the relevant cell. **Edit wording** opens the cell editor with the exact match selected. Select the amber warning icon in a cell to jump back to its findings. **Show rows with findings** narrows the grid. Findings refresh after committed edits and are advisory.

Open **Quality settings** in the sidebar to choose the statement column, required fields, obligation keyword and enabled checks. The defaults recognize `Requirement` or `Requirement Text` and use `shall`. A blank keyword turns off obligation checks. Set initial values in the generator configuration with `quality.requirement_column`, `quality.required_columns` and `quality.obligation`.

Use **Dismiss…** to accept a finding with a reason. The exception applies to that exact cell content and finding. **Show dismissed findings** displays the reasons and lets you restore findings. Use **File → Save report copy** to keep quality settings and dismissals with the report. Browser draft recovery can also recover these changes.

In Spreadsheet mode, use Shift+Up/Down from any cell to select consecutive requirements, then Alt/Option+Shift+Up/Down to move them together. Use the normal view in source order with no filters. The selection follows the moved rows, and one Undo reverses each move.

## Use as a Git diff tool

The included `examples/reqtable-git-diff` wrapper generates an offline HTML comparison and opens it with the platform's default browser. Point `REQTABLE_PYZ` at the built zipapp and set the unique ID column if it is not `ID`:

```sh
REQTABLE_PYZ="$PWD/dist/reqtable.pyz" REQTABLE_ID_COLUMN=ID \
  examples/reqtable-git-diff old-requirements.csv new-requirements.csv
```

To register it as a repository-local Git difftool:

```sh
git config diff.tool reqtable
git config difftool.reqtable.cmd \
  'REQTABLE_PYZ="$PWD/dist/reqtable.pyz" REQTABLE_ID_COLUMN=ID examples/reqtable-git-diff "$LOCAL" "$REMOTE"'
git config difftool.prompt false
git difftool --tool=reqtable REVISION_A REVISION_B -- path/to/requirements.csv
```

The wrapper accepts `REQTABLE_CONFIG=/path/to/config.json`. CLI values in the wrapper override matching JSON settings. Git may provide `/dev/null` for a newly added or deleted file; generate a snapshot for that case or compare two commits in which the CSV exists.

## Build and test

```sh
python -m unittest discover -v
python build.py
```

The build writes `dist/reqtable.pyz`.

## Runtime

Python 3.10 or later is required. The HTML report targets current versions of Chrome, Edge, Firefox, and Safari.
