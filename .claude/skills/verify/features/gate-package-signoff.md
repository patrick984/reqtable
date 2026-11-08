# Gate package and sign-off

`--gate-package BASELINE` builds a Review report of a baseline with a cover (gate, baseline, scope, hash, sign-offs, approval badge) and a **Record decision** form. Decisions persist with Save report copy and are imported with `--import-decisions`. `--sign-off` records decisions directly, as signed Git tags or `manifest.json` entries, and `--verify-baseline` checks the hash, signatures and approval status.

## Sub-features

- `package-cover` cover facts, sign-off table and approval badge; the package compares with the previous gate's baseline and shows every row.
- `record-decision` the form adds decisions, marks the report unsaved, and Save report copy embeds them.
- `import-decisions` imports a saved copy's decisions as sign-offs and skips them on re-import.
- `git-signoff` `--sign-off` creates SSH- or GPG-signed tags that `--verify-baseline` reports as good.
- `file-signoff` `--sign-off` appends to `manifest.json`; latest decision per person wins.
- `package-print` landscape PDF, cover first, baseline name and hash in every page's bottom margin.

## How to get to it (user POV)

- CLI commands in the README's Gate packages and sign-off section.
- Open the package HTML, fill in **Record decision**, then File → **Save report copy**.

## Driving it with the CLI

Preconditions:

- A scratch repo with an SSH signing key: `ssh-keygen -t ed25519 -N "" -f keys/cm`, then `git config gpg.format ssh`, `user.signingkey keys/cm.pub`, and `gpg.ssh.allowedSignersFile` pointing at a file holding `<email> <public key>`. Copy `requirements-uat.csv`, write `{"id_column":"ID","traceability":true}` to `config.json`, commit. Use `P(){ PYTHONPATH=<repo> python3 -m reqtable "$@"; }`.

- **Git flow.** Create SRR, change one requirement and commit, create PDR. `--gate-package PDR -o pdr-package.html`. `--sign-off PDR --role Approver --decision Approved` prints `as tag signoff/PDR/approver/<user>`. `--verify-baseline PDR` lists it as `good counts`, reports Reviewer 0 of 2, ends `not approved`, exit 1.
- **Import.** Inject two Reviewer decisions into the package's `data.decisions` (as Save report copy does) and run `--import-decisions <copy>`: two `imported ... as tag signoff/PDR/reviewer/...` lines. Running it again prints `skipped ... already recorded`. `--verify-baseline PDR` ends `approved`, exit 0. `git cat-file -p signoff/PDR/reviewer/<user>` shows `via: package` and `recorded_by`.
- **File flow.** Copy `tests/fixtures/excel-sample.xlsx` with a config using `"baselines": {"store": "files"}` and the fixture `xlsx.sources`. Create SRR, write the package into `baselines/SRR/`, copy a PDF there, record two Reviewer sign-offs and an Approver `Rejected`: verify says `against: <name>` and exits 1. A later `Approved` by the same person makes it exit 0.

## Driving it with the browser pane

Preconditions:

- The PDR package from the Git flow is served on localhost and loaded fresh, with harness hooks that capture `URL.createObjectURL` and stub `alert`/`confirm`.

- **Cover.** `#package-cover` shows the facts, `Compared with SRR`, and `#package-signoff-table` rows per role. The approver row shows `Signature good` with the note. `#package-approval` reads `Not approved` until the reviewers are in. The grid compares with SRR and shows every row, with the reworded requirement `row-changed`.
- **Record decision.** Type a name in `#package-decision-user`, click `#package-decision-submit`. The Reviewer row's last cell lists the decision with a Remove button, and `state.dirty` is true. The cover grows, so take a new screenshot before clicking the form again.
- **Save copy.** Set reviewer initials first (Save report copy refuses without them and only alerts). File → Save report copy downloads `<name>-reviewed-<initials>-<time>.html`; its embedded JSON has `decisions` with both entries, and the rendered cover is not duplicated.

## Gotchas

- The pane cannot write its download to disk. Prove import by injecting the captured decisions into the generated package with Python.
- Prove print with headless Chrome `--print-to-pdf` and a PDFKit render. Expect page 1 to be the cover alone, landscape pages, every requirement row, and `<baseline> · sha256:<hash>` at the foot of each page.
- A package with an undefined value in its cover script shows a blank page: check `read_console_messages` first if the cover is missing.
