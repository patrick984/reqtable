# TODO:

- [x] Workflow for easy report generation from (CSV) to previous checkpoints using git history.
- [x] Read requirements from XLSX: `.xlsx` input with `--table`, `--sheet`, `--header-row` and `--list-tables`; CSV export with `-o *.csv`; direct reports and diffs.
- [x] XLSX column mapping: merge a separate glossary table (Name, Definition, Aliases) into Term rows and map differently named columns, via a saved JSON mapping.
- [x] Move undo/redo to top of edit menu, add copy/past/delete.
- [x] Update requirements-uat.csv to add any missing glossary terms.
- [ ] Verification Method and Priority values should be constrained to definitions stored in the table (similar to the glossary).
  - Decisions: allowed values are `Type=Value` records (`Field` names the column, `Name` is the value, `Definition` explains it, optional `Aliases` for replaced spellings and `Reference` for an external link). Per-column rules are `Type=Field` records (`Name` is the column, `Definition` describes it, `Multiple=Yes` allows semicolon-separated values). Undefined values are flagged, never blocked. A column is checked only when it has at least one Value record. Checks need `--traceability`.
  - UAT data: Priority `Must`, `Should`, `Could`. Verification Method keeps `Manual browser test`, `Automated test`, `Automated and manual test`, `Manual UAT`, `Manual accessibility test`, `Performance test`, `Documentation review`; `Manual verification` becomes an alias of `Manual browser test`. Add a Verification Phase column with its own values.
  - [x] Phase 1: Value and Field record types; Trace findings for undefined values, alias spellings, multi-value columns, and invalid Value/Field records; UAT CSV definitions.
  - [ ] Phase 2: editor suggests defined values with definitions (multi-select where `Multiple=Yes`) and marks flagged cells.
  - [ ] Phase 3: Values view in the Glossary, `Add value…` in Develop, renaming a value updates the rows that use it.
  - [ ] Phase 4: `Test` and `Test plan` record types; requirement `Verified by` links to tests; a test's `Part of` links to its plan; its `Reference` is the external link; its Verification Method and Phase are checked against Values.
  - [ ] Phase 5: XLSX mapping support for Value, Field and Test sources (Value IDs include the field, e.g. `VAL-PRIORITY-MUST`).
