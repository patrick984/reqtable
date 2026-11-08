# ReqTable gate baselines and sign-off proposal

Status: draft for discussion. Nothing here is implemented.

## Goal

Projects that follow a systems engineering lifecycle freeze their requirements at review gates such as SRR, PDR and CDR. ReqTable should let a project define its own gates, record a frozen baseline at each gate, show what changed since any baseline, check whether the table is ready for a gate, and produce a package that people review and sign. The same workflow must work for a Git repository and for a project whose artefacts are XLSX and PDF files in SharePoint.

Gate checks are advisory at first. A project can make them stricter through configuration later. Formal change control is in scope, but it comes in a later phase.

## Constraints from the existing design

- **Terminology.** The spec already uses *saved baseline* for the state at the last save. This proposal uses **gate baseline** for a frozen, approved snapshot tied to a gate.
- **No server.** Hosting and collaboration services are non-goals, so SharePoint is reached through files on disk, such as a OneDrive-synced library. There is no Microsoft Graph integration.
- **No user code.** The report never runs user templates or scripts (REQ-006). Gate rules are therefore declarative data from a fixed vocabulary.
- **No XLSX writing.** ReqTable reads XLSX but does not write it. Frozen copies are stored as CSV, plus the original file when the project wants it kept.
- **Advisory by default.** Like allowed values and trace findings, gate checks report problems and never block edits unless a project opts in.

## Concepts

| Concept | Meaning |
|---|---|
| **Gate** | A named review in the project's lifecycle, such as SRR, with an order, the baseline it produces, readiness checks and sign-off roles. Defined in configuration. |
| **Gate baseline** | The requirements as approved at a gate, for the whole table or one system's subtree: frozen rows, a scope, a content hash, metadata and sign-offs. |
| **Content hash** | SHA-256 of a canonical serialisation of the table's headers and rows. It identifies a baseline independently of its file format. |
| **Readiness check** | A named, declarative condition over the table, such as "every requirement has a verification method". |
| **Gate package** | The read-only report that reviewers receive: baseline content, changes since the previous gate, readiness results and the VCRM. |
| **Sign-off** | A recorded decision by a person in a role (author, reviewer, approver) about one gate baseline, bound to its content hash. |
| **Change request** | A later-phase record type that authorises changes to baselined requirements. |

The content hash is the keystone. A CSV in Git, an XLSX in SharePoint, an HTML package and a signed PDF of the same baseline all carry the same hash. A signature over any one of them therefore attests the same content.

### Canonical content

The hash covers what the requirements say, not how a file stores them:

- headers and rows after XLSX mapping, in table order
- cell values exactly as read, with line endings normalised to LF
- no formatting, column widths, comments, quality settings or report state

It is computed by the Python generator, embedded in every report, and recomputed by the report's JavaScript when it checks a comparison source.

### Scope

A baseline covers either the whole table or one system and its subsystems. Early gates such as SRR usually cover the whole table. A detailed design review (DDR) usually covers one subsystem in depth.

- A gate declares `"scope": "table"` (the default) or `"scope": "system"`. A system-scoped gate is baselined once per system, for example `--create-baseline DDR --system SYS-REPORT`.
- A system-scoped baseline contains the System records in that subtree and the requirements allocated to any of them, using the same rule as the report's **Include subsystems** scope. Test and Value records are not part of it.
- The scope is part of the canonical content, so the hash covers the scope as well as the rows.
- Comparison, readiness checks and sign-off all work within the scope. Comparing the whole table with a DDR baseline shows changes only for that subtree.
- A requirement can sit in several scoped baselines. That is expected, because a shared requirement is allocated to several systems.

## Configuration

Gates and baseline storage live in the existing JSON configuration. The preset below is shipped and can be replaced or edited per project.

```json
{
  "baselines": {
    "store": "git",
    "git": {"tag_prefix": "baseline/"},
    "files": {"directory": "baselines"},
    "enforcement": "advisory"
  },
  "gates": [
    {
      "id": "SRR",
      "name": "System Requirements Review",
      "produces": "Functional baseline",
      "checks": [
        {"id": "srr-method", "description": "Every requirement has a verification method",
         "applies_to": {"type": "Requirement"}, "filled": "Verification Method"},
        {"id": "srr-no-findings", "description": "No trace findings",
         "no_findings": true}
      ],
      "signoff": [{"role": "Reviewer", "min": 2}, {"role": "Approver", "min": 1}]
    },
    {
      "id": "DDR",
      "name": "Detailed Design Review",
      "produces": "Subsystem design baseline",
      "scope": "system",
      "checks": [
        {"id": "ddr-tests", "description": "Every requirement is linked to a test",
         "applies_to": {"type": "Requirement"}, "linked": "Verified by"}
      ],
      "signoff": [{"role": "Reviewer", "min": 1}, {"role": "Approver", "min": 1}]
    },
    {
      "id": "PDR",
      "name": "Preliminary Design Review",
      "produces": "Allocated baseline",
      "checks": [
        {"id": "pdr-allocated", "description": "Every requirement is allocated to a leaf system",
         "applies_to": {"type": "Requirement"}, "linked": "Allocated to", "leaf": true},
        {"id": "pdr-level", "description": "Every requirement has a verification level",
         "applies_to": {"type": "Requirement"}, "filled": "Verification Level"}
      ],
      "signoff": [{"role": "Reviewer", "min": 2}, {"role": "Approver", "min": 1}]
    }
  ]
}
```

The full preset adds SFR, CDR, TRR and SVR in the usual DoD and INCOSE order. A project renames, removes, reorders or adds gates by editing this list. Gate IDs are free text.

### Check vocabulary

Each check names the records it applies to and one condition. The vocabulary reuses concepts the report already evaluates.

| Key | Condition |
|---|---|
| `applies_to` | Record type and optional field filters, such as `{"type": "Requirement", "Priority": "Must"}`. |
| `filled` | The named column is non-empty. |
| `in` | Every value in the column is in a list, such as Compliance in `["Compliant", "Waived"]`. |
| `linked` | The named link column has at least one target. `leaf: true` requires the target to have no subsystems. |
| `no_findings` | No trace findings, or none of a listed kind. |
| `signoffs_complete` | The gate's sign-off roles have their minimum decisions (phase 3). |
| `unchanged_since` | No baselined requirement changed since the named baseline without an approved change request (phase 4). |

A check that uses an unknown key is a configuration error at generation time, not a silent pass.

## Baseline storage

A gate baseline always resolves to the same result: frozen CSV content, the content hash, and a manifest with metadata and sign-offs. Two stores provide that.

### Git store

- A baseline is an annotated tag on the commit that holds the approved CSV. The name is `baseline/<gate>` for a table baseline, such as `baseline/SRR`, and `baseline/<gate>/<system>` for a scoped one, such as `baseline/DDR/SYS-REPORT`.
- The tag message holds the manifest as JSON: gate, date, the content hash, the source path and who created it.
- `--old git:baseline/SRR` already works, because tags are revisions. The new work is resolving baselines by gate name and checking the hash.
- Tags can be signed, which is the basis for Git sign-off.

### File store (SharePoint and other shared folders)

- A baseline is a folder such as `baselines/SRR/` or `baselines/DDR/SYS-REPORT/` containing:
  - `requirements.csv`, the frozen rows
  - the original source file, for example `requirements.xlsx`, copied unchanged when the project wants it
  - `manifest.json`, with the same fields as the Git tag message plus sign-off entries
  - the gate package, as `package.html` and, once signed, `package.pdf`
- On SharePoint, the folder sits in a synced library. The project can declare it a record or apply a retention label, so SharePoint locks it. The content hash gives integrity independently of SharePoint permissions.
- XLSX input goes through the existing mapping, so formatting changes in the workbook do not change the hash.

### Creating a baseline

- `--create-baseline SRR` validates the gate exists, computes the hash, and then writes the tag (Git store) or the folder (file store).
- Creating a tag is a local, reversible Git operation. Pushing it stays the user's step.
- An existing baseline is never overwritten.
- Re-holding a gate creates a numbered baseline: `SRR-2`, then `SRR-3`. Its manifest records `"gate": "SRR"` and `"supersedes": "SRR"`. The first baseline keeps its plain name. Where a command expects one baseline for a gate, it uses the highest number, so `--baselines SRR` means the latest SRR baseline and `--baselines SRR-1` names the first explicitly. This decision is provisional and can be revisited before phase 1 ships.

## Comparing with baselines

- The generator can embed several baselines, for example `--baselines SRR,PDR`, in addition to today's single `--old` source.
- The report gains a **Compare with** choice: last save, or any embedded baseline. Diff colouring, changes-only, Export changes for review and the VCRM all follow that choice.
- The report shows each baseline's gate, date and content hash, and flags a baseline whose embedded rows no longer match its hash.

## Gate readiness

- A **Gates** view lists the configured gates in order. Each gate shows its checks with pass and fail counts. Clicking a failing check filters the grid to the failing rows through the existing filter and reveal machinery.
- `--check-gate PDR` evaluates the same checks in the CLI. It prints failures and exits 0 when ready and 1 when not, so CI can report readiness on every change.
- `enforcement: "advisory"` is the default. A later `"strict"` setting, globally or per check, would make `--check-gate` failures block `--create-baseline` and would show failing checks as errors in the report. Strictness never prevents editing in Develop mode, because the report cannot stop someone editing the CSV directly.

## Sign-off

Sign-off has three stages that map onto tools the project already uses.

1. **Develop.** Authors edit the table in Develop mode or the source spreadsheet. In Git, this happens on a branch.
2. **Review.** Reviewers receive the gate package or an Export for review report. Their comments are captured as today. The review ends with a recorded decision, *Reviewed* or *Changes requested*, per reviewer.
3. **Approve.** After readiness checks pass and review actions close, approvers record *Approved* against the baseline's content hash. The baseline is then frozen.

ReqTable records decisions and checks them. It does not create cryptographic signatures itself, because a static HTML file has no trustworthy identity. Signatures come from tools that hold the signer's key.

### Where the evidence lives

Sign-offs live outside the baselined table, in the tag or the manifest. If they lived inside, adding a sign-off would change the table and therefore its hash.

| | Git | SharePoint and files |
|---|---|---|
| **Review evidence** | Pull request approvals on the baseline branch, plus review comments in the package. | Review comments in the package, saved as a report copy next to the baseline. |
| **Approval evidence** | One signed tag per approver and decision, named `signoff/<baseline>/<role>/<user>`, such as `signoff/SRR/approver/pnorman` or `signoff/DDR/SYS-REPORT/reviewer/jsmith`. It points at the baseline commit and carries the role, decision and content hash in its message. GPG, SSH and Sigstore (`gitsign`) signing all work. | A PAdES digital signature on `package.pdf`, applied in Acrobat, DocuSign or SharePoint eSignature. The manifest lists each signer, role, decision and date. |
| **Binding to content** | The tag signs the commit, which contains the CSV. Its message repeats the content hash. | The PDF shows the content hash on its cover page and footer, so the signature covers the hash. |
| **Verification** | `--verify-baseline SRR` runs `git verify-tag` for each sign-off tag and compares hashes. | `--verify-baseline SRR` checks the manifest and the CSV hash. ReqTable does not validate PDF signatures. Acrobat and other viewers validate them when the file is opened, so that check stays with them. |

### Producing the PDF

- **Phase 3 default.** Print the gate package to PDF from the browser. The matrix print styles already produce a clean landscape document, and the cover page and footer carry the gate, date and content hash.
- **Optional.** If Chrome or Edge is installed, `--package-pdf` could drive its headless print-to-PDF. This adds no Python dependency, but it is an external program the project must have.
- **Not proposed.** A built-in PDF writer. It is a large, fragile piece of work for little gain over browser printing.

### Sign-off roles and readiness

The gate's `signoff` list sets the required roles and counts. The `signoffs_complete` check reads decisions from the tag messages or the manifest, so the Gates view shows sign-off progress next to the content checks.

## Change control (later phase)

- A `Change request` record type with status values, such as Proposed, Approved, Rejected and Implemented, defined through Value records like other constrained columns.
- A requirement changed since a baseline links to the change request that authorised it, through a new `Changed by` link column.
- A trace finding flags a baselined requirement that differs from the baseline without an approved change request. The `unchanged_since` check turns that into gate readiness.
- Approving a change request can reuse the same sign-off mechanism, bound to the content hash of the change.

## Phases

| Phase | Delivers | Proves |
|---|---|---|
| 1. Baseline identity | Canonical content hash, table and system scopes, Git and file stores, manifest, numbered re-baselines, `--create-baseline`, `--baselines` and **Compare with** in the report. | A baseline from Git or from an XLSX folder compares identically, and a scoped baseline covers exactly its subtree. |
| 2. Gate readiness | Gate configuration, check vocabulary, shipped preset, Gates view, `--check-gate`. | A project can change the gate list and checks without code changes. |
| 3. Package and sign-off | Gate package with cover page and hash, review decisions, sign-off roles, Git signed-tag verification, manifest sign-offs, `--verify-baseline`. | A signed tag or signed PDF can be traced to exactly one baseline. |
| 4. Change control | Change request records, `Changed by` links, the unapproved-change finding, `unchanged_since`. | A post-baseline edit without a change request is flagged. |
| 5. Strict mode | `enforcement: "strict"` per gate or check. | Strict gates block baseline creation in the CLI and CI. |

## Decisions

Recorded on 2026-11-08 from the first review of this proposal.

1. **Git approvals** use one signed tag per approver and decision, not a single tag with Git notes. Each tag can be listed and verified on its own.
2. **PDF signatures** are not validated by ReqTable. The content hash printed in the signed PDF is enough to tie it to a baseline, and viewers such as Acrobat validate the signature on open.
3. **Re-baselining** creates `SRR-2`, `SRR-3` and so on, because explicit names are clearer than replacing `SRR`. This is provisional.
4. **Scope** can be the whole table or one system's subtree, so that subsystem gates such as DDR can be baselined per system.

## Open questions

1. **SharePoint locking.** It is not yet known whether target tenants offer retention labels or record declaration. Until then, the content hash and the signed PDF are the integrity controls, and locking is an optional extra the project applies in SharePoint.
2. **Scope boundary.** Should a system-scoped baseline also include the tests that verify its requirements, so a DDR package carries its test evidence? The current proposal leaves tests out of the hash and shows them only in the package.
