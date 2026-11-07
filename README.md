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

## Review comments

Enter reviewer initials in the report, then select or hover a non-ID cell to reveal its `+` control. A nearby quick-comment popup keeps the latest comment visible, permits its author to edit it, and can open the full comments sidebar. Numbered red indicators mark cells with comments. Reviewer colors are derived consistently from initials. The resizable sidebar supports browsing, searching, inline editing, deleting, and navigating to a cell without closing. Saving or cancelling an inline edit returns to the same browse or single-cell view.

The report distinguishes unsaved requirements, comments, or both. `Save report copy` downloads a new self-contained file. Browsers cannot reliably overwrite the currently open local file. Timestamps are stored as ISO 8601 values with an explicit UTC offset and displayed as `YYYY-MM-DD HH:MM:SS` in the browser's local timezone. Reviewer initials are also retained in browser storage when local-file storage is available, with the saved report's embedded value as the portable fallback.

The toolbar reports visible and total columns, and its **Comments only** control restricts the table to rows with comments. Focusing a filter for a column with two to fifty distinct non-empty values opens a scrollable exact-value checkbox list; this includes typical Category columns. Typing still performs keyword filtering. Clearing an exact-value selection with `×` restores the normal `Filter…` placeholder.

## Keyboard use

Choose **Keyboard help**, or press `?`, for the complete shortcut list. Use the arrow keys or Vim's `h`, `j`, `k`, and `l` to move one cell. Use Home/End or `0`/`$` to reach either end of a row. Press `/` to focus the selected column's filter or, when browsing comments, the comment search field.

Develop reports open in **Spreadsheet** mode. Open **View → Settings** to switch to **Vim**. In Spreadsheet mode, typing on an editable cell starts replacing its value. In Vim mode, `i` edits, `c` opens comments, and `o` / `O` insert a requirement below or above. Use `gg` and Shift+G to reach the first row or the blank entry row.

In both modes, Enter or F2 opens a cell for editing. While editing, Tab and Shift+Tab apply the edit and move to the next or previous visible cell. Ctrl/Cmd+Enter applies in place, and Escape cancels. In Vim mode, Enter inserts a newline. Outside the editor, Ctrl/Cmd+Arrow jumps through filled cells, Ctrl/Cmd+Home and Ctrl/Cmd+End reach the data corners, and Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z undo and redo. Ctrl/Cmd+Y also redoes an edit.

While editing in Spreadsheet mode, Enter commits and moves down, Shift+Enter commits and moves up, and Alt/Option+Enter inserts a newline. Clicking another cell commits the edit and selects that cell. F2 opens the existing value with the caret at the end.

With a grid cell focused in Spreadsheet mode, Ctrl/Cmd+Shift+Up or Down adds a requirement above or below. Alt/Option+Shift+Up or Down moves the selected requirement. Ctrl/Cmd+Backspace or Delete opens the delete confirmation. The Edit menu shows shortcuts for the active keyboard mode. Press Alt/Option+/ to search available menu commands, then use the arrow keys and Enter to run one.

Committing an edit removes trailing whitespace and blank lines. Columns with up to 50 distinct nonempty values, each a single line of at most 60 characters, suggest existing values as you type. Click a suggestion or use Down Arrow and Enter to select it and commit the edit. You can also enter a new value.

In Develop mode, right-click a cell or press Shift+F10 on a focused cell to open its actions. Drag the grip beside a requirement ID to reorder it in the normal view with source order and no filters. The line shows where the row will land. One Undo reverses the move.

Use Shift+click or Shift+Arrow to extend a cell selection. Ctrl/Cmd+C copies the underlying values as tab-separated text. Ctrl/Cmd+V pastes starting at the active cell, in visible row and column order. The whole paste is rejected if it would touch a protected cell, a removed row, or the edge of the table. One Undo reverses a paste.

Click an ID cell to select the row, then Shift+click another ID or use Shift+Up/Down to select a block. Drag any selected row’s grip to move the whole block in its existing order.

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
