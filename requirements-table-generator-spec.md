# Requirements Table Generator — Specification

Status: Implemented through version 2.0  
Target implementation: Python 3 standard library only  
Deliverables after approval: Python source, tests, and deployable `.pyz` zipapp

## 1. Purpose

The Requirements Table Generator converts one requirements CSV file into a single, self-contained HTML document containing an interactive table. It can also compare two historical CSV files and produce a self-contained HTML diff report. Reports are generated explicitly for either comments-only review or editable requirements development.

Both the generator and generated report must work without network access. The generated HTML must not depend on external JavaScript, CSS, fonts, images, or CDNs. Browser storage is used only as a best-effort convenience for reviewer initials; saved reports remain portable without it.

## 2. Goals

- Accept arbitrary CSV schemas based on their header rows.
- Allow optional JSON configuration, with command-line options taking precedence.
- Identify requirements using a named unique-ID column.
- Generate a readable table for a single CSV snapshot.
- Generate a table diff for an old and a new CSV snapshot.
- Provide unified and side-by-side diff views, switchable in the report.
- Highlight changes within cells at line and word level in a VS Code-inspired style.
- Allow columns to be shown or hidden.
- Provide independent keyword filtering for each visible or hidden data column.
- Sort requirements interactively by column.
- Render a safe Markdown subset within cells.
- Allow reviewers to attach timestamped comments and initials to any non-ID table cell.
- Browse and search comments within the report.
- Save a new self-contained HTML copy containing comments.
- Extract a commented HTML report back to CSV with structured comment data.
- In Develop mode, edit cells, add or delete requirements, and explicitly rename requirement IDs.
- Save the edited current requirements to CSV from the browser, including comments by default.
- Show a live diff between the current requirements and the last saved baseline.
- Package and run as a Python zipapp (`.pyz`).

## 3. Non-goals

- Silently overwriting the input CSV without a user gesture or browser permission.
- Parsing spreadsheets such as XLSX.
- Reproducing Git's rename or move detection.
- Executing arbitrary Markdown HTML, JavaScript, or user-supplied templates.
- Pixel-perfect reproduction of the VS Code interface.
- Server-side hosting, search, or collaboration features.

## 4. Terminology

- **Snapshot mode**: generation from one CSV file.
- **Diff mode**: comparison of an old CSV file with a new CSV file.
- **Requirement ID**: the value in the configured unique-ID column.
- **Row status**: `unchanged`, `changed`, `added`, or `removed`.
- **Unified view**: one cell per column, with removed and added fragments shown together.
- **Side-by-side view**: old and new versions of a changed cell shown in adjacent panes.
- **Logical cell**: a cell identified by requirement ID and original CSV column name, independent of the current diff presentation.
- **Comment**: reviewer-authored text attached to a logical cell, with reviewer initials and timestamps.
- **Review mode**: a report in which requirements are immutable and only review comments may change.
- **Develop mode**: a report in which the current requirements may be edited, added, deleted, or explicitly renamed.
- **Saved baseline**: the current requirement and comment revision at report load or after a report/CSV save action.

## 5. Command-line interface

The executable name in examples is `reqtable.pyz`; running the source module directly must expose the same interface.

### 5.1 Snapshot mode

```text
python reqtable.pyz INPUT.csv -o OUTPUT.html [options]
```

### 5.2 Diff mode

```text
python reqtable.pyz --old OLD.csv --new NEW.csv -o OUTPUT.html [options]
```

Snapshot input and the `--old`/`--new` pair are mutually exclusive. Diff mode requires both files.

### 5.3 Comment extraction mode

```text
python reqtable.pyz --extract-comments REPORT.html -o OUTPUT.csv [options]
```

This mode reads a report produced by this application, validates its embedded data format, and reconstructs CSV rows with a comments column. It does not execute the report's JavaScript or parse arbitrary HTML as a requirements report.

For snapshot reports, the reconstructed CSV is based on the original snapshot. For diff reports, the default base is the new/current snapshot.

Relevant options are:

| Option | Meaning |
| --- | --- |
| `--extract-comments PATH` | Read requirements and comments from a generated HTML report. |
| `--comments-column NAME` | Output column name; default `Comments`. |
| `--comments-format {json,text}` | Comment representation; default `json`. |
| `--csv-base {new,old,union}` | Rows used when extracting a diff report; default `new`. |
| `--allow-comment-loss` | Permit an export policy that excludes requirements carrying comments. |

If the selected CSV base would omit any commented requirement, extraction fails with an actionable error unless `--allow-comment-loss` is supplied. With `--csv-base union`, rows from both snapshots are emitted once by ID, current values take precedence, and an additional `_Diff Status` column records `added`, `removed`, `changed`, or `unchanged`.

If the chosen comments-column name already exists in the reconstructed schema, extraction fails rather than overwriting data; the user must select a different name explicitly.

### 5.4 Required and common options

| Option | Meaning |
| --- | --- |
| `-o`, `--output PATH` | Output HTML path. Required. |
| `--old PATH` | Old/baseline CSV in diff mode. |
| `--new PATH` | New/current CSV in diff mode. |
| `--id-column NAME` | Exact header name used as the unique ID. Required unless supplied by configuration. |
| `-c`, `--config PATH` | Optional JSON configuration file. |
| `--title TEXT` | Report title. |
| `--document-mode {review,develop}` | Generate a comments-only Review report or editable Develop report; default `review`. |
| `--encoding NAME` | CSV encoding; default `utf-8-sig`. |
| `--delimiter CHAR` | Explicit one-character delimiter; default is comma. |
| `--initial-diff-view {unified,side-by-side}` | Initial diff presentation; default `unified`. |
| `--include-unchanged` | Include unchanged rows in diff output; enabled by default. |
| `--changes-only` | Initially show only changed, added, and removed rows. |
| `--reviewer-initials TEXT` | Optional initial value for the reviewer-initials field. |

Boolean options may have explicit positive and negative forms where needed, for example `--include-unchanged` and `--no-include-unchanged`.

### 5.5 Other commands

```text
python reqtable.pyz --help
python reqtable.pyz --version
python reqtable.pyz --print-default-config
```

`--print-default-config` writes a documented default JSON configuration to standard output.

### 5.6 Configuration precedence

Values are resolved in this order, highest precedence first:

1. Explicit command-line options
2. JSON configuration
3. Built-in defaults

There will be no implicit discovery of a configuration file in the working directory, keeping invocations reproducible.

## 6. JSON configuration

The configuration is a UTF-8 JSON object. Unknown keys are errors by default so spelling mistakes do not silently change behavior.

Proposed structure:

```json
{
  "id_column": "ID",
  "title": "System requirements",
  "document_mode": "review",
  "csv": {
    "encoding": "utf-8-sig",
    "delimiter": ",",
    "strict_columns": true
  },
  "columns": {
    "hidden": ["Internal Notes"],
    "order": ["ID", "Title", "Requirement", "Rationale", "Status"],
    "labels": {
      "Requirement": "Requirement text"
    },
    "widths": {
      "ID": "9rem",
      "Requirement": "32rem"
    },
    "markdown": ["Requirement", "Rationale", "Notes"]
  },
  "diff": {
    "initial_view": "unified",
    "initial_changes_only": false,
    "ignore_columns": [],
    "ignore_trailing_whitespace": false
  },
  "comments": {
    "enabled": true,
    "reviewer_initials": null,
    "csv_column": "Comments",
    "csv_format": "json"
  }
}
```

Column names in configuration refer to original CSV header names, not display labels.

### 6.1 Generic schema behavior

- All CSV columns are included unless hidden or omitted by configuration.
- `columns.order` places listed columns first in the given order. Unlisted columns follow in CSV order.
- In diff mode, the effective schema is the union of old and new headers: columns from the new file first, followed by old-only columns in old-file order.
- The ID column cannot be omitted from the report, but it may be initially hidden if explicitly configured. A warning will be emitted because hiding it reduces clarity.
- Markdown is enabled for all columns by default. `columns.markdown`, when present, limits Markdown rendering to the listed columns; other cells render as plain text with line breaks preserved.

## 7. CSV input rules

- CSV is parsed using Python's `csv` module with RFC 4180-compatible quoting behavior.
- The first record is the header.
- Quoted delimiters, quoted newlines, and escaped quote characters are supported.
- Default encoding is `utf-8-sig`, accepting UTF-8 files both with and without a byte-order mark.
- Header names are preserved for display and matching.
- Empty header names are rejected.
- Duplicate header names are rejected.
- With `strict_columns: true`, every data record must contain exactly the header's field count.
- Blank physical lines are ignored according to the behavior of the standard CSV parser.
- A file containing a header but no data rows is valid.

### 7.1 Requirement identity

- `id_column` matching against the header is case-sensitive and exact.
- Each requirement ID must be non-empty after trimming leading and trailing whitespace.
- IDs are compared as strings after trimming their outer whitespace; their displayed value otherwise remains as supplied.
- Duplicate IDs within either input file are fatal validation errors, with the duplicate ID and record numbers reported.
- IDs define identity only. A change to an ID is represented as one removed requirement and one added requirement.

### 7.2 Cell comparison

- By default, cell values are compared exactly after CSV decoding.
- Line endings are normalized from CRLF or CR to LF before comparison and rendering.
- Leading whitespace and trailing whitespace are significant unless a specific ignore option is enabled.
- An absent column in one snapshot is treated as an empty cell for row comparison, while the header itself is still reported as old-only or new-only in metadata.
- Columns named by `diff.ignore_columns` remain displayable but do not cause a row to receive `changed` status. If another column changes, ignored columns are still rendered without change highlighting.

## 8. Safe Markdown subset

Cells support the following syntax:

- Paragraphs and line breaks
- Unordered and ordered lists
- Emphasis and strong emphasis
- Inline code and fenced code blocks
- Links using `[label](target)` syntax
- Headings, rendered with levels constrained to fit safely inside a table cell
- Blockquotes

The following are not supported:

- Raw HTML
- Images
- Embedded media
- Tables inside cells
- Footnotes
- Task-list controls
- Any scriptable or extension-specific syntax

All source text and generated attributes are HTML-escaped before markup is introduced. Link targets are limited to `http`, `https`, and `mailto` schemes; other schemes are rendered as non-clickable text. Links open normally in the current browsing context unless a future configuration option explicitly changes this.

Markdown parsing will be implemented internally using only the Python standard library. The supported subset is intentionally documented and need not exactly match CommonMark in ambiguous cases.

Diff tokenization operates on the original Markdown source. Diff spans must then be combined with safe Markdown rendering without producing invalid nested HTML. The implementation may conservatively fall back to escaped text with diff spans for a changed block when Markdown boundaries make safe composition ambiguous.

## 9. Diff model

Rows are matched by normalized requirement ID.

| Condition | Status |
| --- | --- |
| ID occurs only in old CSV | Removed |
| ID occurs only in new CSV | Added |
| ID occurs in both and at least one compared cell differs | Changed |
| ID occurs in both and all compared cells are equal | Unchanged |

### 9.1 Row ordering

The report uses the new CSV's row order. Removed rows are inserted near their former neighbors where a stable insertion point can be determined; otherwise they appear in a final “Removed requirements” section. This preserves current-document readability without implying that row reordering is a content change.

Pure row movement is not treated as a requirement change.

### 9.2 Cell-level diff algorithm

For each changed cell:

1. Split normalized text into lines while retaining line boundaries.
2. Use `difflib.SequenceMatcher` to align unchanged, removed, added, and replaced line blocks.
3. Within paired replacement lines, tokenize into words, whitespace, and punctuation.
4. Apply `SequenceMatcher` again to highlight changed word-level fragments.
5. Treat very large or pathologically repetitive cells defensively, with a documented size threshold and whole-line fallback to avoid excessive generation time or report size.

Whitespace remains visible through normal browser wrapping and preserved line breaks. Changed whitespace may receive a subtle marker so it is not completely invisible.

### 9.3 Unified view

- A changed cell contains old/removal blocks followed by new/addition blocks where applicable.
- Removed lines/fragments use a muted red background and strike-through only where it remains legible.
- Added lines/fragments use a muted green background.
- Unchanged context within a changed cell remains neutral.
- Added and removed rows receive a status-colored edge and badge.

### 9.4 Side-by-side view

- The table retains one logical column per CSV field.
- Within each changed cell, an old pane and a new pane are shown side-by-side.
- On narrow screens, panes stack vertically and are explicitly labelled `Old` and `New`.
- Unchanged cells may render as a single full-width value to reduce visual noise.
- Added and removed rows show an empty counterpart pane.

Switching views occurs entirely in the browser and does not reload or regenerate the report.

## 10. Generated HTML report

### 10.1 Self-contained output

The report is one HTML5 file containing:

- Embedded CSS
- Embedded vanilla JavaScript
- Embedded report data
- No external resource references
- No network requests

Report data will be serialized safely so cell content cannot terminate a `<script>` element or inject executable markup. A restrictive Content Security Policy meta tag should be included where compatible with the inline implementation.

### 10.2 Header and summary

The report header contains:

- Report title
- Mode: snapshot or diff
- Document mode: a prominent `Review mode` or `Develop mode` badge
- Input filenames, not full paths
- Generation timestamp, expressed in local time with UTC offset
- Requirement count
- In diff mode: counts for added, removed, changed, and unchanged rows
- A clear indication when configuration caused columns to be ignored for change detection

For reproducible output, a future `--timestamp` or `SOURCE_DATE_EPOCH` mechanism may override the current generation time. The initial implementation should support `SOURCE_DATE_EPOCH`.

### 10.3 Table controls

The report provides:

- A column chooser with checkboxes and a visible `shown of total columns` count
- Show all and reset-to-default column actions
- One keyword filter input per column, with exact-value checkboxes for columns having two to fifty non-empty values
- A clear-all-filters action
- A global result count showing visible and total rows
- In diff mode, status filters for added, removed, changed, and unchanged
- In diff mode, a unified/side-by-side view toggle
- A changes-only shortcut
- A reset-view action
- Sort controls on column headers
- Draggable column dividers and double-click auto-sizing for the column to the divider's left
- A resizable comments/review panel and a `Comments only` row filter
- A keyboard-shortcut help page
- Save commented copy and comment-export guidance
- In Develop mode: add, rename, delete, undo, redo, CSV save, and saved-baseline diff actions

Controls are usable without a mouse and have accessible labels.

### 10.4 Filtering semantics

- Each column filter is a case-insensitive literal substring search by default.
- Multiple active column filters are combined with logical AND.
- A row matches a column filter when the searchable plain-text value for that column contains the query.
- In diff mode, changed cells search both old and new values; added or removed cells search the available value.
- Markdown syntax is not part of searchable content where it can be removed reliably; visible link labels and code text are searchable.
- Filtering updates immediately, with a short debounce for large tables.
- Columns with two to fifty distinct non-empty values offer a scrollable exact-value checkbox chooser. Higher-cardinality columns retain keyword filtering only.
- Clearing an exact-value filter with its adjacent `×` control clears the selected-value set and restores the normal `Filter…` placeholder.
- Hidden columns may remain filtered. The interface must visibly indicate any active filter on a hidden column.
- Regular-expression search is not part of the initial version.

### 10.5 Table behavior

- The header remains visible while scrolling where browser support permits.
- Long content wraps; line breaks are preserved.
- Column widths are sensible by default and may be overridden in configuration.
- Initial widths are estimated from representative header and cell content without allowing a single outlier to make a column excessively wide.
- A reviewer may drag a header divider to resize a column. Double-clicking a divider auto-sizes the column to its left from representative visible content.
- The table supports horizontal scrolling rather than shrinking text to unreadable sizes.
- Requirement IDs and status remain visually easy to locate.
- Empty values are distinguished from missing old/new counterparts in diff mode.
- Clicking a column header cycles through ascending, descending, and original CSV order.
- Sorting is stable. Equal values retain their prior source order.
- Text sorting is case-insensitive and uses the browser's built-in locale-aware comparison with numeric segments enabled.
- Empty values sort after non-empty values in both directions.
- In diff mode, sorting uses the new value when available and otherwise the old value.
- Filtering and sorting compose: filters determine which rows are visible, while sorting determines their displayed order.
- The initial version supports one active sort column at a time.

### 10.6 State persistence

Column visibility, filters, sorting, and selected diff view persist only for the lifetime of the open page. They are view state and are not written into saved copies. Reviewer initials are the sole exception: the report attempts to retain them in `localStorage` for the current browser profile and falls back silently to the initials embedded in the report when local-file storage is unavailable.

Comments and requirement edits are document data rather than view state. They persist in a saved report copy and, in Develop mode, in browser-generated CSV output.

### 10.7 Comments and review workflow

- Comments are enabled by default and may be disabled through configuration.
- A non-ID logical cell may contain zero or more comments. The configured ID column never offers comment controls.
- Comments attach to `requirement ID + original column name`, not to the current row number or visual diff pane. They therefore remain attached when rows are sorted or filtered and when the diff view changes.
- In diff mode, a comment applies to the logical cell as a whole. The reviewer may refer to old or new content in the comment text, but old and new panes do not have separate comment threads in the initial version.
- Each comment contains a stable generated comment ID, reviewer initials, creation timestamp, optional modification timestamp, and text. Stored timestamps use ISO 8601 with an explicit UTC offset; the interface displays them in the browser's local timezone as `YYYY-MM-DD HH:MM:SS`.
- Reviewer initials are required before adding a comment. They must contain 1–16 non-control characters after trimming.
- Timestamps use ISO 8601 with seconds and the reviewer's local UTC offset, for example `2026-09-13T15:42:18+10:00`.
- Initials identify the entered reviewer only; the offline file provides no authentication or identity verification.
- Comment text supports the same safe Markdown subset as requirement cells.
- Reviewers can add, edit, and delete comments. Deletion requires confirmation.
- Editing preserves the creation timestamp and records a modification timestamp.
- A cell with comments displays a clear, keyboard-accessible red indicator and comment count. Empty blue add controls appear only for the selected cell and the cell under the pointer.
- Hovering or focusing a comment-count indicator displays a nearby read-only preview of its comments.
- Activating any cell comment indicator opens a nearby quick-comment popup without losing the user's table position. The popup shows the most recent existing comment, summarizes any earlier comments, and includes a `Show sidebar` action for that cell.
- Comments receive a deterministic reviewer color based on initials. The quick popup provides an `Edit` action for the latest comment when its initials match the active reviewer.
- Completing or cancelling sidebar comment editing restores focus within the prior sidebar view.
- Added, edited, and deleted comments update the report's in-memory comment model immediately.

### 10.8 Comment browser and search

The review panel provides:

- A chronological or table-order list of all comments
- Search across comment text, reviewer initials, requirement ID, column name, and displayed timestamp
- Filters for reviewer initials, column, and row status in diff reports
- Navigation from a comment to its table cell, temporarily revealing the column and row if hidden by current view settings, while keeping the sidebar open
- Counts for total comments and commented cells
- An empty state when no comments exist or no comments match the search

Comment search is case-insensitive literal substring matching. Search and browsing run entirely in the browser.

The Browse comments control toggles the sidebar open and closed. The sidebar defaults to a compact width, can be resized from its left edge, and stays open after navigation, addition, and editing. Existing comments edit inline within their cards, identified directly by comment ID. Saving or cancelling an edit returns to the exact prior sidebar view rather than changing between browse and single-cell modes. A Back action returns from one cell's thread to the searchable browse view. Opening one header popup closes any other open header popup. The Columns popup closes after Show all or Defaults is selected.

### 10.9 Keyboard navigation and help

- A visible Keyboard help action and the `?` shortcut open an offline help dialog listing every shortcut.
- Table cells use roving focus and retain a clearly shaded selected-cell state that does not depend on the browser's focus outline.
- Arrow keys and Vim-style `H`, `J`, `K`, and `L` move one cell. Home/End and `0`/`$` move to the first/last visible column. Ctrl+Home/Ctrl+End and `G`/Shift+`G` move to the first/last table row. Page Up/Page Down move ten rows.
- Keyboard movement scrolls both axes as needed so the entire selected cell remains inside the table viewport below the sticky headers.
- In Review mode, Enter or `C` opens the comment popup for the focused cell when comments are enabled.
- In Develop mode, Enter or F2 edits a focused non-ID cell; `C` opens its comment popup. Ctrl/Cmd+Z and Ctrl/Cmd+Y perform requirement undo and redo.
- `/` focuses and selects the filter for the selected cell's column, or the comment-search field when the browse-comments view is open.
- Each filter has an adjacent clear button. Down Arrow or Enter from a filter moves focus to the same column in the first matching row.
- Escape closes open header menus, comment popups, hover previews, and the comments sidebar.

The following saving section is numbered 10.10, and the CSV comment representation section is numbered 10.11.

### 10.10 Saving a report copy

- A prominent `Save report copy` action serializes the current document model and downloads a new, fully self-contained HTML file.
- The downloaded copy retains all original report data, rendering code, and comments, and remains fully functional offline.
- Review reports use `-reviewed-<initials>-YYYYMMDD-HHMMSS.html`. Develop reports use `-developed-<initials>-YYYYMMDD-HHMMSS.html`.
- Saving requires non-empty reviewer initials even when the report contains no new comments, because the initials identify who produced that reviewed copy.
- For filename safety, runs of characters outside ASCII letters, digits, hyphens, and underscores in the initials are replaced with a single hyphen, and leading or trailing separators are removed. The initials stored inside comments remain unchanged. If normalization produces an empty filename component, saving is blocked and the reviewer is asked to enter filename-safe initials.
- The timestamp suffix reduces accidental replacement across repeated saves; the browser may still add a numeric suffix on collision.
- The baseline mechanism uses an in-browser `Blob` and a temporary download link. It does not require a server or third-party library.
- Develop reports use the File System Access API for `Save CSV…` where available and fall back to a browser download when it is unavailable or disallowed.
- The report must never claim to have overwritten its currently opened file.

The report tracks a clean comment revision and a current comment revision:

- Any add, edit, or delete operation marks the report as having unsaved comment changes.
- A persistent, high-visibility indicator shows `Unsaved comments` while revisions differ.
- The page registers a `beforeunload` warning while comments are unsaved, subject to browser limitations.
- Initiating a successful client-side download marks that comment revision as saved and records the download time in the interface. Browsers do not reliably report whether the user later cancelled or removed the download, so the UI must state `Download initiated` rather than claiming a file was durably written.
- Reopening a saved commented copy starts in a clean state.

### 10.11 CSV comment representation

The default `json` representation stores a JSON array in each requirement row's comments field. Only comments attached to that requirement are included. Items are ordered by creation time and use original column names:

```json
[
  {
    "column": "Requirement",
    "initials": "PN",
    "created": "2026-09-13T15:42:18+10:00",
    "modified": null,
    "text": "Clarify the tolerance at low supply voltage."
  }
]
```

The CSV writer performs normal quoting, so embedded commas, quotes, and newlines remain valid CSV. Comment IDs are internal report details and are omitted from CSV unless later needed for round-trip comment synchronization.

The optional `text` representation emits human-readable comment blocks containing the column, initials, timestamp, and text. It is intended for reading and import into less structured systems; JSON is the normative lossless representation.

### 10.12 Develop-mode editing

- Document mode is fixed at generation time. A Review report cannot enable requirement editing from inside the HTML file.
- Double-click, Enter, or F2 starts inline editing for a selected non-ID cell. The editor operates on Markdown source, provides Apply and Cancel actions, and never accepts raw rendered HTML.
- The ID cell is read-only during ordinary cell editing. `Rename ID` is a separate operation that trims and validates the replacement ID, refuses duplicates, and migrates comments to the replacement ID.
- `Add requirement` requires a unique non-empty ID and creates the remaining fields empty. `Delete requirement` requires confirmation; if the requirement has comments, the confirmation states that those comments will also be deleted.
- Requirement edits, additions, deletions, renames, and comments migrated or removed by those operations participate in an undo/redo history of up to 100 states.
- Filtering and sorting operate on current values. Editing is committed before a table rerender, and focus returns to the edited logical cell where possible.
- In a historical diff report, the old input remains immutable and edits affect only the new/current dataset.

### 10.13 Changes-since-save diff

- Develop mode provides a `Show changes since save` toggle.
- At initial load, the saved baseline is the embedded current dataset. Saving a report copy or successfully writing/initiating a CSV download advances the saved baseline to the current revision.
- When enabled, the table compares the saved baseline with the current in-memory dataset using added, removed, changed, and unchanged statuses and the existing unified/side-by-side cell presentation.
- Editing a row marks it changed; adding a row marks it added; deleting a saved row marks it removed; restoring values to their saved form makes the row unchanged.
- The toggle is view state. It neither mutates the dataset nor marks the document dirty.

### 10.14 Browser CSV saving

- CSV output contains the current Develop-mode dataset in its current row order and original current-schema column order. Deleted requirements are omitted.
- Comments are included by default in the configured comments column using the configured JSON or text representation. The export refuses to overwrite an existing input column of the same name.
- Serialization uses the configured one-character delimiter, RFC 4180-compatible quoting, doubled embedded quotes, CRLF records, preserved multiline values, and a UTF-8 byte-order mark.
- When `showSaveFilePicker` and writable file handles are available, `Save CSV…` asks the user for a destination and writes it directly. Otherwise it creates an offline Blob download using the current input filename as the suggestion.
- Cancelling a file picker does not advance the saved baseline. A successful direct write or initiated fallback download does.
- Browsers cannot silently overwrite the input path or prove that a fallback download remains on disk. The interface distinguishes `CSV saved` from `CSV download initiated`.

## 11. Accessibility and presentation

- Use semantic HTML elements and a real `<table>` structure.
- Associate header cells with data cells using appropriate table semantics.
- All controls have visible labels or accessible names.
- Comment indicators expose their comment count and associated requirement/column to assistive technology.
- The comment editor supports keyboard submission and cancellation without trapping focus.
- Status is conveyed by text and icons/shapes as well as color.
- Color choices aim for WCAG 2.1 AA contrast.
- Keyboard focus is clearly visible.
- Reduced-motion preferences are respected; no animation is required.
- Printing produces a readable table and hides interactive controls that have no print value.
- Default styling supports light mode. A self-contained dark-mode palette may follow the browser's `prefers-color-scheme` setting.
- Filter inputs explicitly set readable foreground, background, placeholder, and caret colors in both palettes.
- Added or removed content in unified diff view does not render a highlighted empty counterpart.

## 12. Performance targets

The initial design target is:

- Up to 10,000 requirements
- Up to 50 columns
- Up to 10 MiB combined decoded CSV content
- Typical changed cells below 100 KiB each
- Up to 10,000 comments per report, subject to practical browser memory and output-file size

Generation should avoid holding unnecessary duplicate representations, but may load both CSV files into memory to validate IDs and compute the diff. The browser implementation should debounce filtering and minimize full DOM reconstruction. If these targets prove too slow with a conventional table DOM, the implementation may render rows incrementally, provided search results and accessibility remain correct.

Limits that prevent resource exhaustion must produce clear errors or documented diff fallbacks rather than silently truncating content.

## 13. Diagnostics and error handling

Errors are written to standard error and return a non-zero exit status. Messages include the input filename and record/column context where available.

Suggested exit codes:

| Code | Meaning |
| ---: | --- |
| 0 | Success |
| 2 | Command-line usage or configuration error |
| 3 | Input file or CSV validation error |
| 4 | Output write error |
| 5 | Unexpected internal error |

The output file should be written atomically where practical: generate into a temporary file in the destination directory, flush and close it, then replace the destination. A failed generation must not leave a partial HTML report.

Warnings, such as configured columns not found in one snapshot, are written to standard error. Missing required configured columns are errors.

## 14. Packaging

The project will use a package layout compatible with Python's `zipapp` module and contain a `__main__.py` entry point.

Example build command:

```text
python -m zipapp src -m "reqtable.cli:main" -p "/usr/bin/env python3" -o reqtable.pyz
```

The resulting archive must run on supported Python installations without installation or third-party packages.

Proposed supported runtime: Python 3.10 and later. This is a review decision; Python 3.9 support can be included if required.

### 14.1 Git difftool integration

The distribution includes a POSIX wrapper that accepts old and new CSV paths, invokes the zipapp in diff mode, writes a temporary self-contained HTML report, and opens it in the platform browser when `open` or `xdg-open` is available. Documentation provides repository-local `git difftool` configuration using Git's `$LOCAL` and `$REMOTE` paths. The wrapper accepts environment variables for the zipapp path, unique-ID column, and optional JSON configuration. Added or deleted files represented by `/dev/null` are a documented limitation and should be rendered as snapshot reports instead.

## 15. Security requirements

- Treat CSV and JSON content as untrusted.
- Escape all user-controlled text inserted into HTML, CSS, JavaScript, and attributes according to its destination context.
- Never render raw HTML from Markdown.
- Reject dangerous link schemes.
- Do not use `eval`, dynamic script loading, or dynamically compiled JavaScript.
- Do not initiate network requests.
- Do not expose absolute source file paths in the report by default.
- Protect embedded JSON against script-element termination and Unicode line-separator issues.
- Configuration-provided CSS widths must be validated against a narrow allowlist of safe length values rather than inserted verbatim.
- Apply the same escaping and safe-Markdown rules to reviewer initials and comment text as to CSV content.
- Treat a commented HTML report as untrusted input during CSV extraction.
- Extract data only from the application's versioned, explicitly identified embedded data block; do not execute JavaScript or accept external references.
- Validate the embedded schema, report-format version, requirement IDs, comment fields, and reasonable size limits before writing CSV.

## 16. Test strategy

Tests will use only `unittest` and other standard-library modules.

### 16.1 Unit tests

- CSV parsing, quoting, multiline cells, BOM handling, and validation
- Configuration parsing, validation, defaults, and CLI precedence
- Unique-ID normalization and duplicate detection
- Schema union and configured column order
- Row classification and ordering
- Line- and word-level diff generation
- Markdown subset rendering and unsafe-input escaping
- Safe data embedding into HTML
- Filtering helper logic where testable outside the browser
- Stable sorting, empty-value handling, and diff old/new sort-key selection
- Comment creation, editing, deletion, attachment keys, timestamps, and dirty-state transitions
- Reviewer-initial filename normalization and save validation
- Comment searching and reviewer/column/status filters where testable outside the browser
- Comment JSON and text CSV serialization
- Commented-report extraction, schema validation, collision handling, and loss prevention
- Reproducible timestamp behavior

### 16.2 Integration tests

- Generate a snapshot report from representative CSV input
- Generate a diff report covering all four row statuses
- Run from source and from the built `.pyz`
- Confirm output contains no external resource URLs or imports
- Confirm malformed inputs fail with the intended exit code and no partial output
- Verify deterministic output with a fixed `SOURCE_DATE_EPOCH`
- Generate a correctly named commented-copy fixture and extract it back to snapshot CSV
- Extract comments from diff reports using `new`, `old`, and `union` bases
- Confirm export refuses to discard comments unless explicitly allowed
- Confirm comment text cannot inject HTML or script content into a saved copy

### 16.3 Browser-oriented verification

Without third-party browser automation, interactive behavior will be verified using:

- JavaScript structured to expose small pure functions testable with an optional locally available JS runtime, without making that runtime a project dependency
- Static assertions over generated HTML and embedded data
- A documented manual verification checklist covering column visibility, filters, sorting, status filters, view switching, comment editing/search/navigation, unsaved-change warnings, saving/reopening, keyboard use, narrow layouts, and printing

## 17. Acceptance criteria

The implementation is accepted when:

1. A single valid CSV produces one standalone HTML file showing every requirement and configured column.
2. Two valid CSV files produce one standalone diff report with correct added, removed, changed, and unchanged classifications.
3. Changed cells show line- and word-level additions/removals.
4. The report can switch between unified and side-by-side presentations without regeneration.
5. Each column can be independently filtered and shown or hidden.
6. Rows can be sorted ascending or descending by any column and restored to source order.
7. Reviewers can add, edit, delete, browse, search, and navigate to timestamped cell comments carrying their initials.
8. Unsaved comment or requirement changes are clearly indicated and protected by a best-effort unload warning.
9. Saving produces a correctly named `-reviewed-<initials>-YYYYMMDD-HHMMSS.html` standalone report that retains comments, reopens cleanly, and works offline.
10. A commented snapshot or diff report can be converted to valid CSV with comments in the configured comments column and without silent comment loss.
11. Safe supported Markdown renders correctly, while raw HTML and unsafe links cannot inject active content.
12. The report works with networking disabled and contains no external dependencies.
13. The generator runs using only the supported Python standard library.
14. The packaged `.pyz` exposes the same behavior as running from source.
15. Invalid schemas, missing ID columns, empty IDs, duplicate IDs, malformed reports, and comment-column collisions produce actionable errors.
16. A Develop report can edit non-ID fields, add and delete requirements, explicitly rename unique IDs, and undo or redo requirement mutations.
17. A Develop report can compare the current dataset with its saved baseline using the normal diff views.
18. Browser CSV output round-trips edited multiline and quoted fields and contains structured comments by default.
19. Review reports do not expose or enable requirement mutation actions.

## 18. Review decisions and proposed defaults

Please confirm or revise these points before implementation:

| Decision | Proposed default |
| --- | --- |
| Minimum Python version | Python 3.10 |
| CSV delimiter | Comma, configurable explicitly; no automatic sniffing |
| ID normalization | Trim outer whitespace; otherwise case-sensitive |
| Markdown scope | Enabled for every column unless configuration restricts it |
| Unchanged rows in diff | Included, with changes-only control |
| Row reordering | Reported in the Develop saved-baseline diff |
| Removed-row placement | Near former neighbors where possible; otherwise final removed section |
| Initial diff view | Unified |
| Search behavior | Case-insensitive literal substring, AND across columns |
| Sorting | Included; single-column, stable, with source-order reset |
| Browser-state persistence | Best-effort reviewer initials and Develop recovery drafts |
| Comments per cell | Multiple on non-ID cells; attached to requirement ID and original column name |
| Comment formatting | Safe Markdown subset |
| Save behavior | Download a new self-contained `-reviewed-<initials>-YYYYMMDD-HHMMSS.html` copy |
| Unsaved state after save | Clear after download is initiated, with an explicit browser-limitation notice |
| CSV comment representation | JSON array in `Comments` by default; optional text format |
| Document mode | Review by default; Develop must be selected explicitly |
| Requirement ID edits | Read-only in cell editing; change only through validated `Rename ID` |
| Develop CSV export | Current dataset with comments included by default |
| Changes-since-save baseline | Report load, last saved report copy, or last successful/initiated CSV save |
| Diff report CSV base | New/current snapshot; refuse silent loss of comments on excluded rows |
| Dark mode | Follow browser preference |
| Reproducible builds | Honor `SOURCE_DATE_EPOCH` |

## 19. Potential later enhancements

These are explicitly deferred:

- Multi-column sorting
- Regex filters
- Saved view presets
- Exporting the filtered view
- Deep links to individual requirement IDs
- Configurable status or enum styling
- A second configuration format such as TOML
- Virtualized rendering for substantially larger datasets
- Authenticated reviewer identity or cryptographic signatures
- Live multi-user collaboration or comment merging
- Direct overwrite of the currently opened HTML file

## 20. Develop editor and save workflow (2.1)

- Group report controls into File, Edit, View, Filter, and Columns menus. Keep Browse comments directly accessible. Review reports hide the Edit menu and Develop-only save controls.
- Tab reaches the menus. Left and Right move between menu headings. Up and Down open a menu and move between enabled items. Home and End jump within a menu, Enter activates an action, Space toggles a checkbox, and Escape closes the menu and returns focus to its heading.
- Use compact green Apply and red Cancel buttons with accessible labels. Enter activates the focused button, Ctrl/Cmd+Enter applies from the textarea, and Escape cancels. Inside the editor, double-click selects a word and triple-click selects the full field. Place the modified-cell indicator in the left padding.
- Ctrl/Cmd+Z undoes changes. Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y redoes them. A focused text field retains its native editing shortcuts.
- Store manual row position as CSV row order. Rename ID preserves that position. Add Above/Below inserts next to the selected current requirement, and Move Up/Down shifts its position by one. Adding or moving returns the view to source order. Undo and redo cover both operations.
- Keep a blank entry row at the bottom of Develop reports. Committing a non-empty non-ID field creates a requirement. Use the most common numeric ID prefix and its existing digit width, advancing beyond the highest known number in that family. Use `REQ-001` when there is no numeric ID family. Blank or cancelled edits leave the dataset unchanged.
- Changes since save starts with unchanged rows hidden. The Filter menu can show them again. Changes to the relative order of shared requirements are shown in the saved-baseline comparison. The historical CSV comparison retains its existing content-based status rules.
- Render safe Markdown in both sides of a diff for Markdown-enabled columns. Apply word highlighting to rendered text and preserve block structure. Formatting-only changes still show the old and new rendered sides. Plain-text columns retain their line and word diff.
- Save CSV reuses the writable handle selected in this page session. Save CSV As requests a destination. Where the file picker is unavailable, both use a CSV download. Cancelling the picker leaves the saved baseline intact. A native write advances the baseline only after its stream closes successfully.
- Autosave is enabled by default in Develop mode and can be paused in File. Committed changes are saved as a browser-local recovery draft where local storage is available. Reopening the same source report offers recovery in File. Drafts are scoped to that report and browser, and do not depend on keeping the original tab open.
- After a successful native CSV save, autosave also writes committed changes to the selected handle after a short pause. Successful writes advance the saved baseline. An autosave write failure leaves the local recovery draft available and stops automatic writes to that handle. An active cell edit must be applied or cancelled before a manual save.
