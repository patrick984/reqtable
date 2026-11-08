# Gate baselines

The CLI freezes a gate baseline (`--create-baseline GATE [--system ID]`) as a Git tag or a `baselines/` folder, lists them (`--list-baselines`), and embeds them in a report (`--baselines NAME,...`). In the report, **View → Compare with** compares the table with an embedded baseline within its scope and record types, and a line above the grid names the baseline and its hash.

## Sub-features

- `git-store` creates `baseline/<name>` tags with the manifest in the message, refuses uncommitted input, and numbers re-baselines.
- `file-store` writes `manifest.json`, `requirements.csv` and `source.<ext>` under `baselines/<name>/` beside an XLSX or CSV input.
- `cross-store-hash` the same rows hash identically from an XLSX file store and a CSV Git store.
- `compare-baseline` the report marks in-scope changes, keeps out-of-scope rows unchanged, and follows live allocation edits.
- `status-progress` against a baseline without status, a status change shows `was <old>` and leaves the row unchanged.
- `hash-warning` a baseline whose content no longer matches its hash shows a warning in the comparison line.

## How to get to it (user POV)

- Run the CLI commands in the README's Gate baselines section.
- In a report generated with `--baselines`, open **View** and choose a baseline under **Compare with**.

## Driving it with the CLI

Preconditions:

- A scratch folder outside the repo. Call the CLI through a shell function, `P(){ PYTHONPATH=<repo> python3 -m reqtable "$@"; }`, because zsh does not split a command stored in a variable.

- **Git store.** `git init`, set a local user, copy `requirements-uat.csv`, write `{"id_column":"ID","traceability":true}` to `config.json`, commit. `P requirements-uat.csv -c config.json --create-baseline SRR` prints `Created baseline SRR (sha256:…) as tag baseline/SRR`. Edit a cell without committing: `--create-baseline PDR` exits 3 with `has uncommitted changes`. After committing, `--create-baseline DDR --system SYS-EXTRACT` creates `baseline/DDR/SYS-EXTRACT`, a second SRR creates `SRR-2`, and `--list-baselines` prints three tab-separated lines. `git cat-file -p baseline/DDR/SYS-EXTRACT` shows the manifest JSON after the first blank line.
- **File store.** Copy `tests/fixtures/excel-sample.xlsx` to `Requirements.xlsx` with a config setting `"traceability": true`, `"baselines": {"store": "files"}` and the `xlsx.sources` of `FIXTURE_SOURCES` in `tests/test_xlsx_mapping.py`. `--create-baseline SRR` creates `baselines/SRR/` with the three files, and `source.xlsx` is byte-identical to the input.
- **Cross-store hash.** Export the workbook with `-o requirements.csv`, commit it in a new repo, and create SRR there. The hash equals the file-store SRR hash.

## Driving it with the browser pane

Preconditions:

- The Git-store report generated with `--document-mode develop --baselines SRR-1,DDR/SYS-EXTRACT` is served on localhost and loaded fresh, with REQ-099 reworded and REQ-001 Compliance set to Compliant after SRR.

- **Compare.** Open **View**: the Compare with group lists Nothing, Last save and the two baselines. Click `[data-compare="baseline:SRR"]`. `#comparison-line` reads `Comparing with SRR (Functional baseline, …) · sha256:<12 hex>`, and only REQ-099 is `row-changed`.
- **Status progress.** Show unchanged rows. REQ-001's Compliance cell reads `Compliant` with `was Not verified`, and the row is `row-unchanged`.
- **Scope.** Click `[data-compare="baseline:DDR/SYS-EXTRACT"]`. No row is changed, because REQ-099 is outside SYS-EXTRACT.
- **Live scope.** In All fields, allocate an unallocated requirement into a scoped baseline's subtree. It becomes `row-added` against that baseline.

- **Gates view.** In a Develop report of `requirements-uat.csv` built with `--traceability`, open `#view=gates`. SRR and SFR show `✓ Ready`. PDR shows `✗ Not ready` with `pdr-allocated-leaf` 31 of 267 failing and `pdr-level` 1 of 267 failing (REQ-178). Click the first `button[data-gate-show]`: the Requirements view shows 31 rows and the chip `Gate check pdr-allocated-leaf: 31 records`. Browser Back returns to Gates.
- **System gate.** In Gates, set `#trace-system` to `system:SYS-EXTRACT`. `section.gate[data-gate="DDR"]` shows `ddr-verified` 13 of 13 failing.
- **Live update.** Give REQ-178 a Verification Level and return to Gates: `pdr-level` passes.
- **CLI parity.** `python3 -m reqtable requirements-uat.csv --id-column ID --traceability --check-gate PDR` prints the same counts and exits 1. `--check-gate DDR --system SYS-EXTRACT` lists 13 failing records.

## Gotchas

- Comparing starts with unchanged rows hidden, like Last save. A change to a System record shows only in Systems or All fields.
- A hash mismatch needs a tampered baseline. Edit `baselines/<name>/requirements.csv` in a file store, regenerate, and the comparison line ends `content does not match its recorded hash`.
- The pane may serve a cached report after regeneration. Add a query string such as `?v=2`.
