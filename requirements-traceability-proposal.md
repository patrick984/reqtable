# ReqTable systems and traceability proposal

**Status:** Implemented as an opt-in pilot. See the [README](README.md#systems-and-traceability-pilot) for generation commands and the [UAT checklist](UAT-CHECKLIST.md#systems-and-traceability-pilot) for trial scenarios.

ReqTable should support system breakdown, requirement allocation, and traceability in a single CSV. The generated report should derive its navigation, reverse links, and findings from that CSV and run offline. The pilot will use ReqTable itself as the system, with the Python generator and Browser report as subsystems.

## Model

| Relationship | Meaning | Cardinality |
| --- | --- | --- |
| **Part of** | A subsystem belongs to a parent system element. | One parent per subsystem, with one top-level system in the pilot. |
| **Allocated to** | A requirement applies to a system element and appears in its view. | One or more allocations when known. |
| **Owner** | One system element is accountable for the requirement as a whole. | At most one. It may be the common parent of the allocated subsystems. |
| **Derived from** | A lower-level requirement carries forward an obligation from an upstream requirement. | Zero or more upstream requirements. Derivation forms a directed acyclic graph. |
| **Source refs** | A requirement traces to an embedded need or a source record, such as a standard or contract clause. A need may also cite a source record. | Zero or more origins. |

The system hierarchy is a tree for the pilot. A shared requirement has one ID, statement, and set of comments. It appears in every allocated subsystem view, and edits in any of those views update the same row. Create distinct child requirements when the subsystems have distinct obligations to verify. One requirement can contribute to more than one upstream obligation, and one upstream requirement can flow down into several child requirements.

Store each relationship once. The report computes the reverse links so reviewers can follow a trace in either direction. A trace records the relationship for review. Reviewers still determine whether the child requirements collectively cover the parent obligation.

Keep rationale on the child requirement. If projects later need a reason or approval status for each individual link, optional link records could carry that metadata in the same CSV. Keep requirement and system IDs independent of their paths so moving a subsystem leaves references intact.

## Proposed CSV representation

Traceability is opt-in so existing flat reports, including files with a project-specific `Type` column, retain their current interpretation. An opt-in file uses globally unique IDs across all row types. A blank `Type` on an ordinary requirement row defaults to `Requirement`.

| Column | Use |
| --- | --- |
| `ID` | Stable record identifier using the configured ID column. |
| `Type` | `System`, `Requirement`, `Need`, or `Source`. A subsystem uses the same type as a top-level system. |
| `Name` | Display label for a system, need, or source record. |
| `Requirement` | Requirement statement. A need can use the same column for its wording. |
| `Part of` | Parent system ID for a subsystem. |
| `Allocated to` | System IDs on a requirement row. |
| `Owner` | Optional accountable system ID on a requirement row. |
| `Derived from` | Parent requirement IDs on a requirement row. |
| `Source refs` | IDs of in-file origin records. |
| `Reference` | External document, revision, and clause or section on a source record. The report can display this citation offline. |
| `Origin` | Optional `Self-derived` marker for a requirement whose source is a design decision. |
| `Rationale` | Explanation on the child, including why a self-derived requirement is needed. |

Use semicolon-separated ID lists in the multi-value fields and trim whitespace around each ID. Traceable IDs therefore cannot contain semicolons. Use normal CSV quoting when a field contains the configured CSV delimiter. A top-level requirement can cite a user requirement, stakeholder need, or standard through embedded records. For a small project, include the relevant wording in the file. For an external document, keep a named source record with its precise citation and any locally available context.

Keep existing requirement columns such as Category, Priority, Acceptance Criteria, Verification Method, and Source Section. The pilot can add structured links alongside the existing Source Section citations.

## ReqTable pilot

Keep existing requirement wording and IDs. The pilot adds a small set of system records, allocations, and clearly labelled proposals to demonstrate a complete trace from an embedded need to distinct subsystem obligations.

| ID | Type | Example | Part of | Owner | Allocated to | Derived from | Source refs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SYS-REQTABLE` | System | ReqTable | | | | | |
| `SYS-GENERATOR` | System | Python generator | `SYS-REQTABLE` | | | | |
| `SYS-REPORT` | System | Browser report | `SYS-REQTABLE` | | | | |
| `PILOT-NEED-001` | Need | **Proposed:** Authors and reviewers need to generate and use reports without network access. | | | | | |
| `REQ-003` | Requirement | Existing offline operation requirement. | | `SYS-REQTABLE` | `SYS-GENERATOR; SYS-REPORT` | | `PILOT-NEED-001` *(proposed trace)* |
| `PILOT-REQ-001` | Requirement | **Proposed:** The generator shall produce a report from a local requirements CSV while networking is disabled. | | `SYS-GENERATOR` | `SYS-GENERATOR` | `REQ-003` | |
| `PILOT-REQ-002` | Requirement | **Proposed:** The browser report shall open a generated local HTML report and support review and saving a report copy while networking is disabled. | | `SYS-REPORT` | `SYS-REPORT` | `REQ-003` | |
| `REQ-124` | Requirement | Existing Python standard-library constraint. | | `SYS-GENERATOR` | `SYS-GENERATOR` | | |
| `REQ-145` | Requirement | Existing keyboard navigation and offline shortcut help requirement. | | `SYS-REPORT` | `SYS-REPORT` | | |

The proposed children have separate verification activities. Run the generator against a local fixture with networking disabled, then open the resulting HTML with networking disabled and exercise the review and save-copy workflows. Retain end-to-end ownership of `REQ-003` at the ReqTable level. The existing source statements are in [requirements-uat.csv](requirements-uat.csv).

## Report and editing workflow

- Keep the requirements grid as the main editing surface. Add a system tree with a selected-system view and an option to include its descendants. Show a shared requirement once in a combined view.
- For a selected requirement, show its owner, allocations, sources, upstream requirements, and downstream requirements in a trace panel. Allow users to navigate to linked records and explicitly reveal a target hidden by the current view.
- In Develop mode, provide a system editor for names and containment and a relationship picker that searches targets by ID or name. Restrict picker choices to valid target types. Keep the equivalent CSV fields available for direct editing.
- Keep report generation, the browser UI, and saved HTML copies self-contained. Save CSV with the canonical rows and reference fields. Derive indexes, tree views, and trace findings when opening a report or after a committed edit.

## Pilot validation

- Report missing IDs, wrong target types, self-links, duplicate references, and cycles in containment or derivation. Reject new invalid links from the picker. Preserve invalid links imported from a CSV so the author can see and fix them.
- Distinguish intentionally self-derived requirements from rows awaiting a source. A missing allocation, owner, or origin can be a review finding where the project expects one.
- Update incoming references atomically on rename. Before deleting a referenced row, show the affected relationships and require a decision about those links.
- Exercise the pilot by opening `REQ-003` from both subsystem views, editing it once, navigating upstream to the proposed need and downstream to both proposed children, and saving and reopening the single CSV. Confirm existing flat CSVs still open and edit normally.
