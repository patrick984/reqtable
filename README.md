# Requirements Table Generator

`reqtable` turns a requirements CSV (or Excel workbook) into an interactive, self-contained HTML report. It can also compare two CSV snapshots and show line- and word-level changes in unified or side-by-side views. Tables support sorting, per-column filters, column visibility, drag resizing, and divider double-click auto-sizing.

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

## Read from Excel

Pass an `.xlsx` workbook wherever you would pass a CSV: the input, `--old`, or `--new`. See which sheets and tables a workbook has:

```sh
python reqtable.pyz --list-tables requirements.xlsx
```

Export a table to CSV (the output must end in `.csv`):

```sh
python reqtable.pyz requirements.xlsx --table Requirements --id-column ID \
  -o requirements.csv
```

Make a report from a table:

```sh
python reqtable.pyz requirements.xlsx --table Requirements --id-column ID \
  -o requirements.html
```

Read a plain sheet whose headers are not on its first row:

```sh
python reqtable.pyz requirements.xlsx --sheet Requirements --header-row 3 \
  --id-column ID -o requirements.html
```

With no `--table` or `--sheet`, a workbook that has exactly one table reads that table. Otherwise reqtable lists the tables and sheets and asks you to choose. Without `--header-row`, a sheet's header is its first non-empty row. The same choice applies to every workbook in a run.

Things to know about the numbers:

- Numbers lose trailing and leading zeros. A version `1.10` becomes `1.1` and `007` becomes `7`, unless the cell is formatted as Text in Excel.
- Formulas read as the value Excel last calculated and saved. Reqtable does not recalculate, so save the workbook in Excel first.
- Date-formatted cells become ISO dates such as `2026-12-01`.
- Only the top-left cell of a merged range has a value.
- `--old git:REV` does not read workbooks yet. Commit a CSV export to compare against a git checkpoint.

Reqtable only reads workbooks; it never writes one.

### Combine tables

Teams often keep requirements in one table and a glossary in another, with their own column names. A saved JSON mapping combines them into the single table reqtable works on, so the same import reruns identically. Start from a template that lists every table and sheet of the workbook, each column mapped to itself:

```sh
python reqtable.pyz --xlsx-mapping-template requirements.xlsx > mapping.json
```

Edit `mapping.json`: delete the sources you do not want and change the output names. Then run it with `-c`:

```sh
python reqtable.pyz requirements.xlsx -c mapping.json --traceability -o requirements.html
```

A mapping for a requirements table with "Req ID" and "Text" columns and a glossary sheet with Term, Meaning and Abbreviation columns:

```json
{
  "id_column": "ID",
  "xlsx": {
    "sources": [
      {
        "table": "Requirements",
        "columns": {"Req ID": "ID", "Text": "Requirement"},
        "exclude": ["Internal"]
      },
      {
        "sheet": "Glossary",
        "header_row": 2,
        "columns": {"Term": "Name", "Meaning": "Definition", "Abbreviation": "Aliases"},
        "type": "Term",
        "id_prefix": "TERM-"
      }
    ]
  }
}
```

- Each source names one `table` or one `sheet` (with an optional `header_row`). `columns` renames headers and `exclude` drops them; other headers pass through. A name that is not a header of that source is an error that lists the real headers.
- `type` sets the `Type` column on that source's rows, so glossary rows become `Term` records. It needs `--traceability` (or `"traceability": true`).
- `id_prefix` gives an ID to rows that have none: the prefix plus the first alias, or the name when there is no alias, in capitals with other characters turned into `-`. `Identifier` with alias `ID` becomes `TERM-ID`. The ID depends only on the row, so it survives a re-import. Two rows that generate the same ID are a duplicate-ID error; give one of them a different alias.
- `set` fills a column with a constant on every row of that source, adding the column when it is missing: `"set": {"Field": "Priority"}`. It runs after `columns` and `exclude`, so name the output header. `type` is the same as `set.Type`; giving both is an error.
- `lists` splits the cells of the named output columns on a separator, trims each part, drops empty ones and joins them with `; `, the separator reqtable uses in `Verified by`, `Aliases` and multi-value columns: `"lists": {"Verified by": ","}`. Use `"newline"` for one value per line. Columns not listed are never split.
- `id_from` names the output columns that build a generated ID (needs `id_prefix`): the prefix plus the slug of each column's value, joined with `-`, empty values skipped. Without it, a `Value` source uses `["Field", "Name"]`, so `Must` in the Priority field becomes `VAL-PRIORITY-MUST`, the same ID `Add value…` creates in the report. Any other source keeps the first-alias-else-Name rule above.
- Columns that share a name across sources line up, and cells a source lacks stay empty.
- The mapping applies to every `.xlsx` input of the run and cannot be combined with `--table`, `--sheet` or `--header-row`. CSV inputs ignore it.
- `-o combined.csv` exports the combined table, so you can edit it as CSV from then on.

#### Lookup lists and tests

A workbook can also hold the allowed values for columns such as Priority and Verification Method, and a table of tests. This mapping imports a requirements table whose `Tests` cells read `T-1, T-2`, a `Priorities` sheet (Value, Meaning), a `Lists` sheet (Field, Value, Meaning, Old spellings), a `TestCases` table and a `Plans` table:

```json
{
  "id_column": "ID",
  "traceability": true,
  "xlsx": {
    "sources": [
      {"table": "Reqs", "columns": {"Req ID": "ID", "Text": "Requirement", "Tests": "Verified by"},
       "lists": {"Verified by": ","}},
      {"sheet": "Priorities", "type": "Value", "set": {"Field": "Priority"},
       "columns": {"Value": "Name", "Meaning": "Definition"}, "id_prefix": "VAL-"},
      {"sheet": "Lists", "type": "Value",
       "columns": {"Value": "Name", "Meaning": "Definition", "Old spellings": "Aliases"},
       "lists": {"Aliases": ","}, "id_prefix": "VAL-"},
      {"table": "TestCases", "type": "Test",
       "columns": {"Test ID": "ID", "Title": "Name", "Plan": "Test plan", "Method": "Verification Method"}},
      {"table": "Plans", "type": "Test plan", "columns": {"Plan ID": "ID", "Title": "Name"}}
    ]
  }
}
```

The value rows get IDs such as `VAL-PRIORITY-MUST` and `VAL-VERIFICATION-METHOD-MANUAL-BROWSER-TEST`, requirements link to their tests with `T-1; T-2`, and each test links to its plan. A `Type=Field` source (`"type": "Field"`, `"set": {"Multiple": "Yes"}`, `Column` mapped to `Name`) marks a column as multi-value.

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

To hand off requirements from Develop mode, finish the active edit and choose **File → Export for review**. The browser downloads a self-contained `-for-review-…html` snapshot with the current rows, traceability, glossary, and comments on those rows. Export works from a comparison view and shares the current snapshot. The author can keep editing and save their working file separately. Send the exported HTML to the reviewer. They can open it offline, enter their initials, and return their comments using **File → Save report copy**.

For a review against an established baseline, choose **File → Export changes for review** before saving the new edits. This copy includes the last saved rows and opens with the changes visible, including additions, removals, edits, and changes to row order. Saving the working report, including CSV autosave, advances that baseline. In Review mode, use **View → Show current requirements** to see the full current table and **View → Show changes since last save** to return to the comparison. The annotated report copy carries the comparison back to the author.

## Systems and traceability pilot

Build the pilot from ReqTable's own requirements CSV.

```sh
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  --document-mode develop -o requirements-uat-develop.html
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  -o requirements-uat.html
```

The report opens in **Requirements** with the core writing columns, including Verification Method. Use **Columns** to show more writing fields such as Rationale, or **All fields** to see every CSV record and relationship column. The **System** selector includes all requirements, unallocated requirements, and individual systems. Select **Include subsystems** for a combined view. A requirement shared across systems, such as `REQ-003`, appears once in that view.

Select a record and use **Links** in the workspace bar to see or add relationships. A dot in the ID cell marks records that already have links. Following a link opens the corresponding record view, and **Back to previous record** returns to the starting point. If a target is filtered out within the current grid, **Reveal in grid** shows it alongside that view. The active-filters menu can remove the exception or the system filter. **Trace findings** reports invalid links and cycles. An optional **Name** gives a requirement a short label in link lists and pickers. You can edit it in **All fields**.

In Develop mode, use **Systems** to add subsystems, rename them, move them, and delete them. The delete dialog shows affected subsystems, allocations, and owners and lets you choose how to handle each group. Use **Needs & Sources** to add needs and citations. From a requirement's **Links** panel, use **Allocate to…** to select multiple systems or **Add child requirement…** to create a new row with its parent link filled in. **Rename ID** updates incoming links and comments, and Undo restores a deletion and its links together.

Enable the pilot with `--traceability` or `"traceability": true` in the JSON configuration. The generator adds missing traceability columns. A blank `Type` means `Requirement`, and multi-value link fields use semicolon-separated IDs. Use the same flag when regenerating from a saved CSV. With the default JSON comments format, the exported comments return as annotations. See the [traceability proposal](requirements-traceability-proposal.md) for the schema and model.

### Project glossary

Open **Glossary** in either mode to browse the shared terms for the whole project. Use the **Name** or **Definition** column filter to search. In Develop mode, choose **Add term…**, then edit any of its fields in the grid. To attach a citation, select the term and choose **Links → Link source…**.

Each term is a `Term` record in the same CSV. Enter its **Name** and **Definition** and ReqTable assigns a unique ID when you add it. The Glossary hides IDs by default. Use **Columns** to show them. Separate optional **Aliases** with semicolons, for example `CSV; Delimited Text`. Set **Auto Link** to `Yes` to also link single-word Title Case spellings for that term. The **Trace findings** panel reports incomplete records, duplicate names, and spellings shared by different terms.

The browser underlines registered Title Case phrases and uppercase acronyms in rendered **Requirement**, **Acceptance Criteria**, and **Rationale** text. Matching is case-sensitive, uses whole spellings, and prefers the longest match. For example, a term named `Comma-Separated Values` with alias `CSV` matches either spelling. Code, existing links, URLs, and email addresses are skipped. Matches use continuous rendered text, so a formatting boundary inside a phrase can interrupt a match.

Click an underlined term or focus it and press Enter to read its definition in place. Press Escape to close it and return focus to the term. Links are calculated from the glossary in the open report, so the feature works offline and the prose in the CSV stays plain.

### Allowed values

A column such as **Priority** or **Verification Method** can be limited to values defined in the same table, the way glossary terms are. Add a `Value` record for each allowed value and, optionally, a `Field` record that describes the column. This needs `--traceability` and is advisory. ReqTable still accepts any cell, and **Trace findings** reports each one that is not defined.

A `Value` record uses **Field** for the column it belongs to, **Name** for the allowed value, and **Definition** to explain it. Optional **Aliases** (semicolon-separated) list replaced spellings, and **Reference** can link to an external explanation. A `Field` record uses **Name** for the column, **Definition** to describe it, and **Multiple** (`Yes` or blank) to allow several semicolon-separated values in one cell.

```csv
ID,Type,Name,Field,Multiple,Aliases,Definition,Priority,Verification Method
FIELD-VM,Field,Verification Method,,Yes,,How the requirement is shown to be met.,,
VAL-PRIORITY-MUST,Value,Must,Priority,,,Required for the release.,,
VAL-PRIORITY-SHOULD,Value,Should,Priority,,,Expected but not blocking.,,
VAL-VM-BROWSER,Value,Manual browser test,Verification Method,,Manual verification,A person checks the report in a browser.,,
REQ-1,,,,,,,Shoud,Manual verification; Automated test
```

A column is checked only when it has at least one `Value` record. Trace findings then report, on any other record with a non-empty cell:

- a value that is not defined, such as `Shoud`
- a replaced spelling, with the defined value to use instead
- a spelling that differs from a defined value only in case
- a duplicate value in a `Multiple` cell
- more than one value in a column that allows one

Findings also report invalid `Value` and `Field` records: a missing or unknown **Field**, a reserved column (the ID column, `Type`, `Field`, `Multiple` or a link column), a missing **Name** or **Definition**, duplicate names or clashing aliases within one field, two `Field` records for one column, and a **Multiple** other than `Yes` or `No`. Value and Field records appear in **All fields** and stay out of the Requirements view.

In Develop mode, editing a column that has `Value` records suggests exactly the defined values, each with its definition, in table order. Aliases are not suggested. Typing narrows the list to values that start with the text, then values that contain it. In a `Multiple` column the editor works on the semicolon-separated segment under the caret, hides values already in the cell, and replaces only that segment when you choose one. The editor stays open so you can type `; ` and add another value. A cell with any trace finding shows a flag button. Click it to open the finding in **Trace findings**.

**Glossary → Values** lists every `Value` and `Field` record in table order, with ID (hidden by default), Type, Field, Name, Definition, Multiple, Aliases and Reference columns. **Terms** and **Values** are a two-button toggle inside the Glossary view, and the choice is remembered for the session. In Develop mode, **Add value…** asks for a Field, Name, Definition and optional Aliases. The Field list offers columns that may have values, and columns that already have values come first. The new record gets the ID `VAL-<FIELD>-<NAME>` (uppercase, other characters become `-`, for example `VAL-PRIORITY-WON-T`), with `-2`, `-3` and so on when the ID is taken. Add `Field` records (column descriptions and **Multiple**) in **All fields**.

Renaming a value in its **Name** cell asks `Rename “Should” to “Recommended” in 39 rows that use it?`. Choose OK to rewrite those cells in the same step, so one **Undo** restores the name and the rows. Choose Cancel to change only the name, and the rows then show findings. Matching is exact and case-sensitive on the whole cell, or on each semicolon-separated segment in a `Multiple` column. Value and Field records are never rewritten. Renaming a `Field` record, or changing a value's **Field**, does not update any rows.

### Tests

Requirements can point at the tests that verify them. A `Test plan` record groups tests, and a `Test` record is one test, script or checklist. Both are rows in the same CSV, with a **Name**, an optional description in **Requirement** and a **Reference** for the external link, for example a test-management tool URL. Only HTTP, HTTPS and mailto links render as links, so write a repository path as code, such as `` `tests/test_core.py` ``.

Open **Tests** to list every `Test plan` and `Test` record in table order, with ID, Type, Name, Test plan, Verification Method, Reference and Requirement columns. In Develop mode, **Add test plan…** and **Add test…** take an ID, Name and description, and **Add test…** offers the existing plans. Edit the other fields in the grid.

A requirement's **Verified by** column lists `Test` IDs. In its **Links** panel, choose **Link test…** to pick tests. A test's **Test plan** column holds at most one `Test plan` ID, set with **Set test plan…**. The panel shows the reverse links as **Verifies** on a test and **Tests** on a plan. The dedicated **Test plan** column keeps **Part of** for the Systems tree. Deleting a test or plan clears the links that point at it, and the confirmation lists them.

The tests' **Verification Method** is checked against the table's `Value` records like any other row, so an undefined method shows a trace finding. **Trace findings** also reports links to missing or wrongly typed records.

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

With a grid cell focused in Spreadsheet mode, Ctrl/Cmd+Shift+Up or Down adds a requirement above or below. Alt/Option+Shift+Up or Down moves the selected requirement. Ctrl/Cmd+Backspace or Delete opens the delete confirmation. Plain Delete or Backspace clears the selected cells; the ID column, protected columns and removed rows are skipped, and one Undo restores them. The Edit menu shows shortcuts for the active keyboard mode. Press Alt/Option+/ to search available menu commands, then use the arrow keys and Enter to run one.

Committing an edit removes trailing whitespace and blank lines. Columns with up to 50 distinct nonempty values, each a single line of at most 60 characters, suggest existing values as you type. Click a suggestion or use Down Arrow and Enter to select it and commit the edit. Columns with defined values suggest those values instead, with their definitions, and a `Multiple` column keeps the editor open after you choose one. You can also enter a new value.

In Develop mode, right-click a cell or press Shift+F10 on a focused cell to open its actions. Drag the grip beside a requirement ID to reorder it in the normal view with source order and no filters. The line shows where the row will land. One Undo reverses the move.

Use Shift+click or Shift+Arrow to extend a cell selection. Ctrl/Cmd+C copies the underlying values as tab-separated text. Ctrl/Cmd+V pastes starting at the active cell, in visible row and column order. The whole paste is rejected if it would touch a protected cell, a removed row, or the edge of the table. One Undo reverses a paste. The **Edit** menu lists Undo and Redo first, then **Copy**, **Paste** and **Clear cells**, which act on the selected cells. Menu **Paste** reads the system clipboard, so the browser may ask for permission. If it is refused, the status line says so and Ctrl/Cmd+V still works. **Clear cells** is separate from **Delete requirement**, which removes the whole row.

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

### Compare against a git checkpoint

Skip the manual export: `--old` also accepts `git:REV`, where `REV` is any tag, branch, or commit. The old file is read from git, so the working-tree `--new` CSV is compared with its own committed version at that revision:

```sh
python -m reqtable --old git:v1.0 --new requirements.csv --id-column ID -o changes-since-v1.0.html
```

If the file lived elsewhere at that revision, name the path with `git:REV:PATH`:

```sh
python -m reqtable --old git:v1.0:docs/old-requirements.csv --new requirements.csv --id-column ID -o changes.html
```

The report labels the old side like `requirements.csv @ v1.0 (abc1234)`. This form runs `git` as an external command, so `git` must be on `PATH`, and the CSV must be inside a git repository. Git's line-ending and attribute filters apply, so the result matches a checkout of that revision. It works with `--document-mode develop` too.

## Build and test

```sh
python -m unittest discover -v
python build.py
```

The build writes `dist/reqtable.pyz`.

## Runtime

Python 3.10 or later is required. The HTML report targets current versions of Chrome, Edge, Firefox, and Safari.
