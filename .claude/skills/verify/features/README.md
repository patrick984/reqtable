# reqtable verification map

This directory is the maintained source for verifying what reqtable users see. Read this index before driving a report, then use the matching feature file as the recipe.

## Baseline preconditions

- Run `.claude/skills/verify/scripts/launch.sh` from the repo root and note its `RUN_DIR` and `URL`.
- Run `.claude/skills/verify/scripts/doctor.sh "$RUN_DIR"` and require every line to be `ok`.
- Open pages from `URL` in the built-in browser. Never open a report as `file://`.
- Install the harness hooks from SKILL.md after every page load and before any action that downloads or shows a native dialog.
- Never drive an instance that this run did not launch.

## Driving conventions

- Start each recipe from a freshly loaded page. Reloading resets the report to its generated state.
- Find menus and buttons with `find` by accessible name, or by the ids listed in SKILL.md. Do not reuse coordinates after the layout changes.
- Read results from the DOM or the embedded `reqtable-data` JSON, not from a screenshot taken right after an action.
- Stage scenarios only through user actions. Read `state` and `data` to observe, never to set up.

## Proof and skip reporting

- Save one JSON file per feature in `$RUN_DIR/evidence/` with the feature ID, entry point, actions, observed state after each key action, captured downloads and dialogs, and a verdict.
- For a download, prove the content from its embedded JSON and by opening it in the iframe as its recipient would.
- CLI proof includes the command, stdout, stderr, exit code and output file.
- Report an entry point you could not drive with the attempted action and the reason. Do not count it as verified through another path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with the browser pane` (or `the CLI`) starts with `Preconditions:` and pairs each user action with the exact tool action and the observable result.
4. `Gotchas` lists traps that can waste or invalidate a run.

## Features

- [Review export](./review-export.md) covers Export for review and Export changes for review, and the reviewer's comparison toggle. Last proven 2026-11-07 (`snapshot-export`, `changes-export`, `review-toggle`). `removed-row-comment` was proven before this skill existed and has not been rerun with it.
- [Develop editing](./develop-editing.md) covers cell edits, adding, deleting, moving, undo and Save CSV. Last proven 2026-11-07 for `edit-cell`, `add-row`, `delete-row`, `move-row`, `undo` and `save-csv`, as setup for the review export proof.
- [Allowed values](./allowed-values.md) covers editor suggestions with definitions for constrained columns, multi-value segment completion, and the trace finding markers in grid cells. Last proven 2026-11-07 in `uat-develop.html`: Priority suggestions with definitions, Verification Method segment completion, the marker for `Shoud` opening its finding, and the marker clearing on Undo. Phase 3 proven the same day: Glossary → Values listing 12 records, Add value… creating `VAL-PRIORITY-WON-T`, and renaming `Could` to `May` updating REQ-166 with one Undo restoring both. On 2026-11-08 the UAT methods changed to IADT values; the filter and segment steps were rewritten for them and not rerun.
- [Tests traceability](./tests-traceability.md) covers the Tests view, Verified by and Test plan links, Link test…, Add test… and the Verification Method check on tests. Last proven 2026-11-07 in `uat-develop.html`: Tests view with 7 records, TEST-CORE panel with plan and Verifies, REQ-018 Verified by and Link test… adding TEST-VALUES (undone), an undefined method on TEST-CORE flagged, and Add test… creating a test under TP-UAT. `coverage-check` proven 2026-11-08: adding Acceptance to REQ-253 raised the coverage finding and Undo cleared it.
- [Verification tab](./verification-vcrm.md) covers the VCRM tab, its System scope, the Compliance cross-check and Method editing. Last proven 2026-11-08 (`tab`, `scope`, `compliance-check`, `method-edit`), including dark mode. `matrix` and `matrix-export` proven the same day; printed output proven with Chrome print-to-PDF after the print fixes.
- [Review comments](./review-comments.md) covers reviewer initials, adding a comment, Save report copy, and CLI extraction. Not yet proven end to end.
- [Diff report](./diff-report.md) covers the generated old/new comparison, its counts, view toggle and status filters. Not yet proven.
- [Quality check](./quality-check.md) covers Check requirement quality in Develop mode. Not yet proven.
