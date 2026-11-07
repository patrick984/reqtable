# Quality check

In Develop mode an author scans requirement wording for problems such as a missing obligation keyword or empty required fields. Findings appear in a sidebar and as amber icons on cells, can be dismissed with a reason, and refresh after edits.

## Sub-features

- `scan` lists findings for all current requirements, including filtered rows.
- `jump` focuses the flagged cell from a finding card.
- `edit-wording` opens the cell editor with the match selected.
- `dismiss` accepts a finding with a reason, and `restore` brings it back.
- `settings` changes the statement column, required fields, obligation keyword and enabled checks.

## How to get to it (user POV)

- In a Develop report, **View → Check requirement quality**.
- In the quality sidebar, **Quality settings…**, **Show rows with findings**, **Dismiss…** and **Show dismissed findings**.

## Driving it with the browser pane

Preconditions:

- `<URL>develop.html` is loaded fresh and the harness hooks are installed. Every fixture requirement uses `shall`, so it starts with no obligation findings.

- **Create a finding.** Edit R1's Requirement to `The report opens offline.` and commit. The row has no obligation keyword.
- **Scan.** Choose **View → Check requirement quality** (`#check-quality`). The sidebar lists a finding for R1 and `#quality-count` is non-zero.
- **Jump.** Click the R1 finding card. R1's Requirement cell is selected.
- **Fix.** Edit R1 back to use `shall` and commit. The R1 finding disappears.
- **Dismiss.** Recreate the finding, click **Dismiss…**, enter a reason in `#quality-dismiss-reason`, submit. The finding moves to **Show dismissed findings** with the reason.

## Gotchas

- Findings refresh only after a committed edit, not while the editor is open.
- A dismissal applies to the exact cell content. Editing the cell brings the finding back.
- Quality check is Develop-only, so the menu item is hidden in `snapshot.html` and `diff.html`.
