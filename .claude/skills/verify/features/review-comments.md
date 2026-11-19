# Review comments

A reviewer enters initials, adds comments to cells in a Review report, saves an annotated report copy, and the author extracts those comments back to CSV with the CLI. Comments show as numbered red indicators on cells and in the comments sidebar.

## Sub-features

- `initials` records reviewer initials used on every new comment.
- `quick-comment` adds a comment to a cell from its `+` control.
- `browse-comments` lists, searches and opens comments in the sidebar.
- `save-copy` downloads a `-reviewed-<initials>-` report copy that keeps the comments.
- `extract-cli` writes the comments to a CSV column with `--extract-comments`.

## How to get to it (user POV)

- Open `<URL>snapshot.html` and use **Set initials** in the header.
- Hover or select a non-ID cell and click its `+`, or press `C` in Vim mode.
- **View → Browse comments**, or **Filter → Comments only**.
- **File → Save report copy**.
- `python3 dist/reqtable.pyz --extract-comments <report.html> --id-column ID -o <out.csv>`.

## Driving it with the browser pane

Preconditions:

- `<URL>snapshot.html` is loaded fresh and the harness hooks are installed.

- **Set initials.** Fill `#reviewer-initials` with `PN` and dispatch `input` and `change`. The header shows `PN`.
- **Add a comment.** Click `button[data-comment-row="R2"][data-comment-column="Requirement"]`, type into `#quick-comment-text`, click **Add comment**. R2's Requirement cell shows a red `1`.
- **Browse.** Choose **View → Browse comments**. The sidebar lists the comment with `PN`.
- **Save copy.** Choose **File → Save report copy**. The captured download is named `snapshot-reviewed-PN-<timestamp>.html` and its `reqtable-data.comments` holds the comment with `requirementId` `R2`, `column` `Requirement` and an ISO timestamp with an offset.
- **Reopen.** Load the download in the iframe. The red indicator is on R2's Requirement cell.

## Driving it with the CLI

Preconditions:

- A report with comments exists on disk. Browser downloads cannot reach disk, so use a report generated from a CSV that already has a `Comments` column in JSON form.

- **Extract.** Run `python3 dist/reqtable.pyz --extract-comments <report.html> --id-column ID -o "$RUN_DIR/evidence/extracted.csv"`. Exit code `0`, and the `Comments` column holds the JSON comments.

## Gotchas

- The ID column never offers a comment control.
- Initials are kept in browser storage per origin, so a second page in the same run starts with them filled in.
- The browser-to-CLI round trip cannot be driven by this harness. Report it as not covered instead of substituting a generated report for the browser copy.

## Driving Excel comment import with the CLI

Preconditions:

- A workbook with Excel notes or threaded comments on a sheet, such as the one `commented_workbook` in `tests/test_xlsx_import.py` writes, and a config with `xlsx.sources` and a `headings` entry.

- **Import.** Run `python3 dist/reqtable.pyz <workbook.xlsx> -c <config.json> -o "$RUN_DIR/xlsx.html"`. Exit code `0`, `warning:` lines on stderr for missing IDs, duplicate IDs and dropped comments.
- **Browse.** Open the report and choose **View → Browse comments**. Imported comments list with the author's initials. A cell with an imported comment shows its red count.
