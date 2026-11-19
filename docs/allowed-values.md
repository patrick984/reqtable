# Allowed values

A column such as **Priority** or **Verification Method** can be limited to values defined in the same table, the way glossary terms are. Add a `Value` record for each allowed value and, optionally, a `Field` record that describes the column. This needs `--traceability` and is advisory. ReqTable still accepts any cell, and **Trace findings** reports each one that is not defined.

A `Value` record uses **Field** for the column it belongs to, **Name** for the allowed value, and **Definition** to explain it. Optional **Aliases** (semicolon-separated) list replaced spellings, and **Reference** can link to an external explanation. A `Field` record uses **Name** for the column, **Definition** to describe it, and **Multiple** (`Yes` or blank) to allow several semicolon-separated values in one cell. **Multiple** is a checkbox cell like **Auto Link**. It is read-only in Review mode.

```csv
ID,Type,Name,Field,Multiple,Aliases,Definition,Priority,Verification Method
FIELD-VM,Field,Verification Method,,Yes,,How the requirement is shown to be met.,,
VAL-PRIORITY-MUST,Value,Must,Priority,,,Required for the release.,,
VAL-PRIORITY-SHOULD,Value,Should,Priority,,,Expected but not blocking.,,
VAL-VM-DEMO,Value,Demonstration,Verification Method,,Manual check,Operate it and observe the result.,,
VAL-VM-TEST,Value,Test,Verification Method,,,Run it under controlled conditions and record results.,,
REQ-1,,,,,,,Shoud,Manual check; Test
```

A column is checked only when it has at least one `Value` record. Trace findings then report, on any other record with a non-empty cell:

- a value that is not defined, such as `Shoud`
- a replaced spelling, with the defined value to use instead
- a spelling that differs from a defined value only in case
- a duplicate value in a `Multiple` cell
- more than one value in a column that allows one

Findings also report invalid `Value` and `Field` records: a missing or unknown **Field**, a reserved column (the ID column, `Type`, `Field`, `Multiple` or a link column), a missing **Name** or **Definition**, duplicate names or clashing aliases within one field, two `Field` records for one column, and a **Multiple** other than `Yes` or `No`. Value and Field records appear in **All fields** and stay out of the Requirements view.

In Develop mode, editing a column that has `Value` records suggests exactly the defined values, each with its definition, in table order. Aliases are not suggested. Typing narrows the list to values that start with the text, then values that contain it. In a `Multiple` column the editor works on the semicolon-separated segment under the caret, hides values already in the cell, and replaces only that segment when you choose one. The editor stays open so you can type `; ` and add another value. A cell with any trace finding shows a flag button. Click it to open the finding in **Trace findings**.

**Glossary → Values** lists every `Value` and `Field` record in table order, with ID (hidden by default), Type, Field, Name, Definition, Multiple, Aliases and Reference columns. **Terms** and **Values** are a two-button toggle inside the Glossary view, and the choice is remembered for the session. In Develop mode, **Add value…** asks for a Field, Name, Definition and optional Aliases. The Field list offers columns that may have values, and columns that already have values come first. The new record gets the ID `VAL-<FIELD>-<NAME>` (uppercase, other characters become `-`, for example `VAL-PRIORITY-WON-T`), with `-2`, `-3` and so on when the ID is taken. Add `Field` records (column descriptions and **Multiple**) in **All fields**.

Renaming a value in its **Name** cell asks `Rename “Should” to “Recommended” in 39 rows that use it?`. Choose OK to rewrite those cells in the same step, so one **Undo** restores the name and the rows. Choose Cancel to change only the name, and the rows then show findings. Matching is exact and case-sensitive on the whole cell, or on each semicolon-separated segment in a `Multiple` column. Value and Field records are never rewritten. Renaming a `Field` record, or changing a value's **Field**, does not update any rows.

A column with `Value` records shows by default in the Requirements and Tests views when that view's records use it, so a project's own column names need no configuration.

The pilot's `requirements-uat.csv` follows the V-model with three constrained columns:

- **Verification Method** says how a requirement is shown to be met: `Inspection`, `Analysis`, `Demonstration` or `Test`. Several are allowed per cell.
- **Verification Level** says where on the V it is verified: `Unit`, `Integration`, `System` or `Acceptance` (alias `UAT`). Several are allowed per cell. Unit, Integration and System verify the product against its specification. Acceptance validates it against user needs.
- **Execution** says how a test is run: `Manual` or `Automated`. It belongs on Test records, not requirements, because one requirement can be checked both ways by two tests.

Priority uses `Must`, `Should` and `Could`.
