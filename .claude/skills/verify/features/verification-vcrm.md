# Verification tab (VCRM)

In a traceability report, the **Verification** tab lists requirements with ID, Requirement, Verification Method, Verification Level, Verified by and Compliance. Method cells show one slot per defined method (I A D T). Verified by cells show each test's name and Result badge. A summary strip counts rows per Compliance value plus No compliance, No method and No linked tests. Trace findings flag a requirement marked `Compliant` while a linked test has not `Passed`.

## Sub-features

- `tab` shows the VCRM columns, the method slots, the result badges and the strip.
- `scope` keeps the tab when the System selector changes and scopes the strip.
- `compliance-check` flags Compliant with an unpassed linked test, and stays quiet when every linked test passed.
- `method-edit` opens the normal editor on the raw Verification Method text.

## How to get to it (user POV)

- Click **Verification** in the view bar (after Tests).
- Pick a system in the **System** selector while on the tab.
- Edit a Compliance or Verification Method cell with `Return`, `F2` or a double-click.

## Driving it with the browser pane

Preconditions:

- `<URL>uat-develop.html` is loaded fresh and the harness hooks are installed.

- **Tab.** Click `[data-trace-view="verification"]`. It has `aria-pressed="true"`. Header cells read ID, Requirement, Verification Method, Verification Level, Verified by, Compliance. `#trace-verification-summary` reads `Not verified 267 … No linked tests 254`. `tr[data-row-id="REQ-253"] td[data-column="Verified by"]` reads `Traceability tests Passed` and `Systems and traceability browser checks Not run`.
- **Scope.** Set `#trace-system` to `system:SYS-EXTRACT` with `form_input`. The tab stays pressed, `#result-count` reads `13 requirements`, and the strip reads `Not verified 13 … No linked tests 13`.
- **Compliance check.** Select REQ-252's Compliance cell, press `Return`, `cmd+a`, `Delete`, type `Compliant`, press `Return`. No `.trace-marker` appears and the strip shows `Compliant 1`. The selection moves down a row after commit, so press `Escape` and `Up` before editing REQ-253 the same way. Its cell carries a `.trace-marker` titled `Compliant, but TEST-UAT-TRACEABILITY is “Not run”.`
- **Method edit.** Select a Verification Method cell and press `Return`. The focused textarea holds the raw text, such as `Test`, not the slots.

## Gotchas

- `cmd+a` then typing can append instead of replace in a cell editor that already had text typed into it. Press `Delete` after `cmd+a`.
- `Pass` is an alias of the test Result `Passed`, not of Compliance. Typed into Compliance it is an undefined value.
- Changed cells in a diff report show their diff markup, not the slots or badges.
