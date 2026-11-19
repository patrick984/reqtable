# Read from Excel

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

## Real-world workbooks

CSV inputs stay strict. A workbook is repaired while it is imported, so a report or a diff of two workbooks does not stop on a few untidy rows. Each repair prints a `warning:` line on stderr and is listed in the report's warnings.

- A row with no cells at all is skipped without a warning.
- A row with content but no ID is named `ROW-<worksheet row>`, such as `ROW-12`, and one warning per source lists them. This includes rows where `id_prefix` has nothing to build an ID from.
- A repeated ID keeps its first row. The later ones become `REQ-010~2`, `REQ-010~3` and so on, skipping any value already in use, with one warning per ID that gives the worksheet rows. Two workbooks with the same repeats line up in a diff, because the same rows get the same names.

## Heading rows

Some workbooks use rows without an ID as headings, marked in a type column such as `Req Type`. A source's `headings` key names them:

```json
{
  "sheet": "Requirements",
  "columns": {"Req ID": "ID"},
  "exclude": ["Req Type"],
  "headings": {"column": "Req Type", "values": ["Heading"], "text": "Requirement", "into": "Category"}
}
```

- `column`, `values` and `text` use the workbook's own header names, before `columns` and `exclude` apply, so the type column can still be excluded.
- A row is a heading when its `column` cell equals one of `values`, ignoring case and surrounding spaces. `text` names the cell that holds the heading text. Without it, the first non-empty cell of the row other than `column` is used.
- Heading rows are removed. Each row after one gets its text in the `into` column, which is created when missing, unless that row already has a value there. A later heading replaces an earlier one.

## Excel comments

Notes and threaded comments on the imported sheet become review comments, so they show in the report's comments sidebar and on the cells. Threaded replies are separate comments in date order, and the placeholder note Excel keeps beside a thread is ignored. A comment lands on the final ID of its row and on the output column name after `columns` renaming.

- The initials are the first letter of each word of the author's name (`Patrick Norman` becomes `PN`), the first two letters of a single word, or `XL` when the author is unknown.
- A threaded comment keeps its own date. A note has none, so it takes the workbook's last-modified date.
- A comment on the ID column moves to the row's first other column and starts with `[on ID] `, because the report cannot attach comments to IDs.
- Comments on heading rows, excluded columns or cells outside the imported table or sheet range are dropped, and one warning gives the count.
- Set `"comments": {"enabled": false}` to import none. Exporting to CSV does not carry comments.

## Combine tables

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
- `id_prefix` gives an ID to rows that have none: the prefix plus the first alias, or the name when there is no alias, in capitals with other characters turned into `-`. `Identifier` with alias `ID` becomes `TERM-ID`. The ID depends only on the row, so it survives a re-import. Rows that generate the same ID get `~2`, `~3` suffixes and a warning, like any repeated ID; give one of them a different alias to avoid that. A row with nothing to build an ID from is named `ROW-<worksheet row>` with a warning.
- `set` fills a column with a constant on every row of that source, adding the column when it is missing: `"set": {"Field": "Priority"}`. It runs after `columns` and `exclude`, so name the output header. `type` is the same as `set.Type`; giving both is an error.
- `lists` splits the cells of the named output columns on a separator, trims each part, drops empty ones and joins them with `; `, the separator reqtable uses in `Verified by`, `Aliases` and multi-value columns: `"lists": {"Verified by": ","}`. Use `"newline"` for one value per line. Columns not listed are never split.
- `id_from` names the output columns that build a generated ID (needs `id_prefix`): the prefix plus the slug of each column's value, joined with `-`, empty values skipped. Without it, a `Value` source uses `["Field", "Name"]`, so `Must` in the Priority field becomes `VAL-PRIORITY-MUST`, the same ID `Add value…` creates in the report. Any other source keeps the first-alias-else-Name rule above.
- Columns that share a name across sources line up, and cells a source lacks stay empty.
- The mapping applies to every `.xlsx` input of the run and cannot be combined with `--table`, `--sheet` or `--header-row`. CSV inputs ignore it.
- `-o combined.csv` exports the combined table, so you can edit it as CSV from then on.

### Fill in requirements from another table

Workbooks often keep a requirement's Verification Level and Verified by outside the requirements table: a verification matrix sheet with one row per requirement and test, and a tests table whose `Verifies` cells read `R-1, R-3`. A source with `"merge": true` fills in the records the other sources add, by ID, instead of adding rows:

```json
{
  "id_column": "ID",
  "traceability": true,
  "xlsx": {
    "sources": [
      {"table": "Reqs", "columns": {"Req ID": "ID", "Text": "Requirement"}},
      {"sheet": "Matrix", "merge": true,
       "columns": {"Requirement": "ID", "Level": "Verification Level", "Test": "Verified by"}},
      {"table": "Tests", "type": "Test", "columns": {"Test ID": "ID", "Title": "Name"}, "exclude": ["Verifies"]},
      {"table": "Tests", "merge": true, "columns": {"Verifies": "ID", "Test ID": "Verified by"},
       "exclude": ["Title"], "lists": {"ID": ","}}
    ]
  }
}
```

The `Tests` table is mapped twice: once to add the tests as `Test` records, once to link each requirement it verifies back to the test.

- Merge sources run after the other sources, in mapping order, and after their IDs are repaired. A merge source needs the `id_column` header after `columns` and `exclude`, and it cannot give `type`, `id_prefix`, `id_from`, `headings` or `set.Type`. At least one source must not be a merge source.
- Each row fills in the record whose ID is in its ID cell. With the ID column in `lists`, each listed ID fills in its record. Rows with an empty ID are skipped. A repeated ID is not renamed `~2`; every row for it fills in the same record.
- IDs match the records' final IDs, so a record renamed `R-1~2` is filled in only by a row that reads `R-1~2`.
- `Verified by`, `Allocated to`, `Derived from`, `Source refs`, `Affects`, `Aliases` and the source's `lists` columns collect distinct values after the record's own, joined with `; `. Other columns fill an empty cell; a different value keeps the record's and is reported.
- Headers a merge source adds follow the other sources' headers.
- One warning per source lists the IDs that match no record, and one lists the conflicting values: `R-2 Verification Level: kept 'Unit', ignored 'Subsystem'`.
- An Excel comment on a merge row lands on the first record that row fills in, in the cell's output column.

### Lookup lists and tests

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
