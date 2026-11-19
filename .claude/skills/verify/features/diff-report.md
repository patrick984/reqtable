# Diff report

The CLI compares an old and a new CSV and writes a Review report that marks each requirement added, removed, changed or unchanged, with line and word highlights in unified or side-by-side views.

## Sub-features

- `diff-counts` reports the number of added, removed, changed and unchanged requirements.
- `diff-views` switches between unified and side-by-side views.
- `status-filters` narrows rows with **Changes only** and the per-status checkboxes.
- `word-highlights` marks changed words and lines, including multiline cells.

## How to get to it (user POV)

- Run `python3 dist/reqtable.pyz --old <old.csv> --new <new.csv> --id-column ID -o <out.html>` and open the result.
- In the report, **View → Diff view** toggles the view.
- **Filter → Changes only**, and the `Added`, `Removed`, `Changed` and `Unchanged` checkboxes in the Filter menu.

## Driving it with the browser pane

Preconditions:

- `<URL>diff.html` is loaded fresh. It compares `examples/requirements-old.csv` with `examples/requirements-new.csv`.

- **Counts.** Read `JSON.parse(document.getElementById('reqtable-data').textContent).meta.counts`. It reports three changed, one added, one removed and zero unchanged, matching docs/uat/UAT-CHECKLIST.md.
- **Row statuses.** Read row classes. Each row carries one of `row-added`, `row-removed`, `row-changed` or `row-unchanged`.
- **Switch view.** Choose **View → Diff view** (`#view-toggle`). The layout switches between unified and side-by-side. Record the button text before and after.
- **Filter.** Open **Filter**, untick `input[data-status="removed"]`. The removed row leaves the grid. Tick it again and it returns.
- **Highlights.** Inspect SYS-002's Requirement cell. It contains inserted and deleted word markup across its lines.

## Gotchas

- The diff is computed at generation time. Regenerate (relaunch) after changing `reqtable/core.py`, or the page proves the old code.
- A removed row sorts by its old value.
