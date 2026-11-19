# Gate baselines

A gate baseline freezes the requirements approved at a review gate such as SRR, PDR or a subsystem DDR, so later reports can compare against it. The design, including readiness checks and sign-off planned for later phases, is in [requirements-baselines-proposal.md](design/requirements-baselines-proposal.md).

Gates come from the `gates` list in the configuration. The default list is SRR, SFR, PDR, DDR, CDR, TRR, SVR, FCA and PCA, and a project's own list replaces it. Each gate sets:

- `scope`: `table` for the whole table, or `system` for one system and its subsystems, chosen with `--system` when the baseline is created.
- `includes`: the record types the baseline covers, by default `Requirement` and `System`. TRR also includes `Test` and `Test plan`.
- `captures_status`: whether status columns (`baselines.status_columns`, by default Compliance and Result) are part of the baseline. Only SVR, FCA and PCA capture them.

Create, list and compare baselines from the CLI:

```sh
python -m reqtable requirements.csv -c config.json --create-baseline SRR
python -m reqtable requirements.csv -c config.json --create-baseline DDR --system SYS-REPORT
python -m reqtable requirements.csv -c config.json --list-baselines
python -m reqtable requirements.csv -c config.json --document-mode develop --baselines SRR,DDR/SYS-REPORT -o requirements.html
```

Each baseline has a SHA-256 content hash over the rows in its scope, ignoring formatting and, unless the gate captures status, status columns. The same requirements give the same hash whether they came from CSV or XLSX. Holding a gate again creates `SRR-2`, `SRR-3` and so on. `--baselines SRR` means the latest SRR baseline, and `SRR-1` names the first.

Baselines are stored according to `baselines.store`:

- `git` (default): an annotated tag such as `baseline/SRR` or `baseline/DDR/SYS-REPORT` on `HEAD`, with the manifest in the tag message. The input must be committed first. ReqTable never pushes the tag.
- `files`: a folder under `baselines/` beside the input, holding `manifest.json`, the frozen `requirements.csv` and an unchanged copy of the source file. This suits workbooks in a synced SharePoint library. Existing folders are never overwritten.

In the report, **View → Compare with** lists Nothing, Last save, the old file of a diff report, and each embedded baseline. Comparing with a baseline marks added, removed and changed records within its scope and record types, and leaves everything else unchanged. Against a baseline that does not capture status, a changed status shows a muted `was <old value>` note but does not mark the row changed. The line above the grid names the baseline, its date and hash, and warns if the embedded content no longer matches its recorded hash.

## Gate readiness checks

Each gate in the configuration can list `checks`, declarative conditions that say whether the table is ready for that review. A check has an `id`, a `description`, an optional `applies_to` and one condition:

| Condition | Passes when |
|---|---|
| `filled: "Column"` | The cell is not blank. |
| `in: {"Column": ["A", "B"]}` | The cell is not blank and every `;`-separated value is in the list. |
| `linked: "Column"` | At least one listed ID is a record in the table. Add `"leaf": true` to require a System with no subsystems. |
| `no_findings: true` | No record in scope has a trace finding, and the table has no table-level findings. |
| `unchanged_since: true` | No record in scope changed, was added or was removed since its baseline without an approved change request (see Change control). |

`applies_to` selects the records a check covers. It defaults to `{"type": "Requirement"}` (or every record for `no_findings`). `type` takes a record type or a list, and any other key is a column whose value must equal the given text or be one of a list. A check that names a column the table lacks reports an error rather than passing. For a system-scoped gate such as DDR, checks cover only that system's scope.

```json
{"id": "pdr-level", "description": "Every requirement has a verification level",
 "applies_to": {"type": "Requirement", "Priority": ["Must", "Should"]}, "filled": "Verification Level"}
```

The default gates ship with checks. For example, SRR needs requirement text, a verification method and a priority. PDR needs allocation to a leaf system and a verification level. TRR needs every test to have a test plan and a method. SVR, FCA and PCA need Compliant or Waived requirements, and SVR also needs passing tests. Every gate also needs no trace findings. Replace the `gates` list in your configuration to use your own.

The **Gates** view in the report lists each gate as ready or not ready, with each check's result. Results update as you edit in Develop mode. For a system-scoped gate, choose the system in the System picker at the top of the Gates view (it shares the workspace bar's System selector). **Show records** opens the failing records with a removable filter.

In the CLI, `--check-gate` runs the same checks for CI. It prints one line per check and exits 0 when the gate is ready and 1 when it is not:

```sh
python -m reqtable requirements.csv -c config.json --check-gate PDR
python -m reqtable requirements.csv -c config.json --check-gate DDR --system SYS-REPORT
```

The CLI evaluates trace findings with a Python port of the report's rules, so it needs only the standard library. Parity tests run both implementations on the same tables and require identical findings.

## Strict gates and waivers

Gate checks are advisory unless configured otherwise. Set `enforcement` to `"strict"` in `baselines` for every check, on a gate, or on a single check; the most specific setting wins:

```json
{"id": "PDR", "name": "Preliminary Design Review", "enforcement": "strict", "checks": [
  {"id": "pdr-no-findings", "description": "There are no trace findings", "no_findings": true, "enforcement": "advisory"}]}
```

A failing strict check blocks `--create-baseline` for that gate. Advisory failures are printed as warnings and do not block. To proceed anyway, waive the blocking checks with a reason for each, in the order they are named, or one reason for all:

```sh
python -m reqtable requirements.csv -c config.json --create-baseline PDR \
  --waive pdr-allocated-leaf --reason "Leaf allocation completes at DDR" \
  --waive pdr-level --reason "REQ-178 is a documentation requirement"
```

Only failing strict checks can be waived. Each waiver records the check, reason, user (`--user` to override), date and failing records in the baseline, and appears in `--verify-baseline` and on the gate package cover. Waivers do not affect approval. `--check-gate` marks failures `FAIL (strict)` or `FAIL (advisory)` and still exits 1 when any check fails. The Gates view shows strict failures as blocking and the gate as **Blocked**. Strictness never prevents editing in Develop mode.

## Gate packages and sign-off

A gate package is the report reviewers receive for a baseline:

```sh
python -m reqtable requirements.csv -c config.json --gate-package PDR -o pdr-package.html
```

It opens in Review mode on the baseline's frozen rows, compared with the previous gate's baseline so changes since that gate are marked. A cover at the top names the gate, baseline, scope, creator and full content hash, and lists the sign-offs for each role in the gate's `signoff` list with an Approved or Not approved badge. Printing gives a landscape PDF that starts with the cover and repeats the baseline name and hash at the foot of every page, ready to sign in Acrobat or another PDF tool.

Reviewers record a decision (Reviewed, Changes requested, Approved or Rejected) in the cover's **Record decision** form and keep it with **Save report copy**, like a comment. The configuration manager then imports the saved copies:

```sh
python -m reqtable requirements.csv -c config.json --import-decisions pdr-package-reviewed-AL.html
```

Decisions can also be recorded directly:

```sh
python -m reqtable requirements.csv -c config.json --sign-off PDR --role Approver --decision Approved --note "PDR board" --evidence package.pdf
```

In the Git store each decision becomes a signed annotated tag such as `signoff/PDR/approver/casey-manager`, created with `git tag -s` and the user's configured GPG or SSH key, pointing at the baseline commit and carrying the role, decision and content hash. Signing must be configured; reqtable never creates unsigned sign-offs and never pushes. In the file store each decision is appended to the baseline's `manifest.json`, and `--evidence` usually names the signed PDF in the baseline folder.

`--verify-baseline PDR` recomputes the content hash, checks every sign-off (Git signatures with `git verify-tag`), and prints each role's progress. A baseline is approved when every role has at least its minimum number of people whose latest decision is Reviewed or Approved. The command exits 0 only when the hash matches and the baseline is approved. Reports that embed baselines with `--baselines` also carry their sign-offs and approval status.

## Change control

Once a requirement is baselined, changes to it need an approved change request. A `Change request` record lists the IDs it covers in **Affects** and records its decision in **Change status** (Proposed, Approved, Rejected or Implemented). Every traceability report has both columns.

Each record is controlled by the most recently created baseline that contained it: a subsystem requirement by its DDR once one exists, otherwise by the latest table-wide baseline. Reports find the baselines in the store automatically (set `baselines.change_control` to `false` to turn this off). Then **Trace findings** flags, unless an Approved or Implemented change request lists the ID in Affects:

- a record that differs from its controlling baseline, naming the changed columns (status columns do not count unless that baseline captured them)
- a new record inside a baselined scope
- a record removed since its baseline

In Develop mode, the **Change requests** view lists change requests, with **Add change request…** to create one. Use **Link affected record…** in its Links panel, which also offers removed records. A requirement's Links panel lists the change requests that affect it. Every gate after SRR includes an `unchanged_since` check, so `--check-gate` and the Gates view report unauthorised changes.
