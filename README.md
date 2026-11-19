# Requirements Table Generator

`reqtable` turns a requirements CSV (or Excel workbook) into an interactive, self-contained HTML report. It can also compare two CSV snapshots and show line- and word-level changes in unified or side-by-side views. Tables support sorting, per-column filters, column visibility, drag resizing, and divider double-click auto-sizing.

The generator uses only the Python standard library. Generated reports contain all CSS, JavaScript, data, and review comments in one file and work offline.

## Install

Python 3.10 or later is required. The HTML report targets current versions of Chrome, Edge, Firefox, and Safari.

Build the single-file program from a checkout:

```sh
python build.py
```

The build writes `dist/reqtable.pyz`. The examples here and in [docs/](docs/) write `reqtable.pyz` for short; use `dist/reqtable.pyz`, or copy it next to your CSV.

## Quick start

If you would rather not type commands, start the [point-and-click GUI](docs/gui.md):

```sh
python reqtable.pyz --gui
```

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

## Documentation

- [Point-and-click GUI](docs/gui.md): run every task from a browser form instead of the command line.
- [Review and Develop modes](docs/review-and-develop.md): the two report modes, saving, handing off for review, and review comments.
- [Read from Excel](docs/excel.md): import workbooks, repair untidy rows, and combine several tables with a saved mapping.
- [Configuration](docs/configuration.md): the JSON settings file.
- [Keyboard use](docs/keyboard.md): shortcuts, editing, selection, and requirement quality checks.
- [Use as a Git diff tool](docs/git.md): compare reports in `git difftool`, or against a git tag or commit.
- Traceability:
  - [Systems and traceability pilot](docs/traceability.md): systems, links, needs and sources.
  - [Project glossary](docs/glossary.md)
  - [Allowed values](docs/allowed-values.md)
  - [Tests and verification](docs/tests-and-verification.md)
- [Gates, baselines and sign-off](docs/gates.md): freeze baselines, check gate readiness, waivers, review packages, sign-off and change control.
- [Build and test](docs/development.md): for contributors.
- Design and planning: the [generator spec](docs/design/requirements-table-generator-spec.md), the [baselines](docs/design/requirements-baselines-proposal.md) and [traceability](docs/design/requirements-traceability-proposal.md) proposals, the [UAT checklist](docs/uat/UAT-CHECKLIST.md) and the [TODO list](docs/planning/TODO.md).
