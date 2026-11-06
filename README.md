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

In Develop mode, double-click a non-ID cell or press Enter/F2 to edit its Markdown source. The ID column is renamed only through **Rename ID**, which checks uniqueness and migrates attached comments. Use **Edit** to undo, redo, insert above or below, and move requirements. CSV row order records the manual position independently of the ID. The bottom entry row creates a requirement with the next ID when a non-empty field is committed. **View → Show changes since save** opens a diff with unchanged rows hidden by default. Diff cells retain safe Markdown formatting.

**File → Save CSV As…** selects a writable destination in supported Chromium contexts. **Save CSV** reuses that destination for the session. Both include the configured `Comments` column by default and download a CSV if the picker is unavailable. **File → Autosave** keeps a local recovery draft where browser storage is available and writes to the selected CSV after a short pause once a writable handle is established. Use **Recover autosaved draft** in File when reopening the original report. **Save report copy** creates a resumable self-contained HTML file. Develop copies use names such as `requirements-developed-PN-20260913-085719.html`; Review copies retain the `requirements-reviewed-PN-20260913-085719.html` convention.

## Review comments

Enter reviewer initials in the report, then select or hover a non-ID cell to reveal its `+` control. A nearby quick-comment popup keeps the latest comment visible, permits its author to edit it, and can open the full comments sidebar. Numbered red indicators mark cells with comments. Reviewer colors are derived consistently from initials. The resizable sidebar supports browsing, searching, inline editing, deleting, and navigating to a cell without closing. Saving or cancelling an inline edit returns to the same browse or single-cell view.

The report distinguishes unsaved requirements, comments, or both. `Save report copy` downloads a new self-contained file. Browsers cannot reliably overwrite the currently open local file. Timestamps are stored as ISO 8601 values with an explicit UTC offset and displayed as `YYYY-MM-DD HH:MM:SS` in the browser's local timezone. Reviewer initials are also retained in browser storage when local-file storage is available, with the saved report's embedded value as the portable fallback.

The toolbar reports visible and total columns, and its **Comments only** control restricts the table to rows with comments. Focusing a filter for a column with two to fifty distinct non-empty values opens a scrollable exact-value checkbox list; this includes typical Category columns. Typing still performs keyword filtering. Clearing an exact-value selection with `×` restores the normal `Filter…` placeholder.

## Keyboard use

Choose **Keyboard help**, or press `?`, for the complete shortcut list. Use the arrow keys or Vim's `h`, `j`, `k`, and `l` to move one cell. Use Home/End or `0`/`$` to reach either end of a row. Press `/` to focus the selected column's filter or, when browsing comments, the comment search field.

In Develop mode, Tab and Shift+Tab move across visible cells and wrap between rows. At the outer edges they leave the grid. Ctrl/Cmd+Arrow jumps to the end of a block of filled cells, across a gap to the next filled cell, or to the grid edge. Ctrl/Cmd+Home and Ctrl/Cmd+End reach the first and last corners of the visible data. Press `gg` for the first row and Shift+G for the bottom, including the blank entry row. Press Enter, F2, or `i` to edit a non-ID cell, and `c` to open its comments. Ctrl/Cmd+Z undoes an edit and Ctrl/Cmd+Y or Ctrl/Cmd+Shift+Z redoes it. The textarea keeps its normal text editing shortcuts.

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
