# Point-and-click GUI

If you would rather not type commands, start the GUI:

```sh
python reqtable.pyz --gui
```

It prints an address and opens it in your browser. The home page has two parts:

- **Typical jobs.** Pick one and the GUI walks you through it task by task: share requirements for review, edit requirements in the browser, see what changed between two versions, bring in an Excel workbook, or hold a gate review. After each task it offers the next one, with your files already filled in.
- **All tasks.** Every task as a card, grouped as below. Choose one to do it on its own.

Each task is a short wizard: **Choose files**, then **Options** (some tasks also have a **Gate** page), then **Check and run**. **Next** waits, and says why, until the page has what it needs. **Back** and the step list at the top return to an earlier page, and **← All tasks** returns to the home page without losing what you entered. The browser's Back button works too.

- **Make reports.** Make a report, or open **Edit requirements (Develop report)** to edit requirements in the browser. The report and comparison options show Review and Develop as two cards.
- **Compare and review.** Compare two versions, or collect comments from a reviewed report.
- **Excel workbooks.** Look inside a workbook, convert a table to CSV, or **Import several tables from one workbook**. Choose the table or sheet before the ID column; the form picks an ID-like column for you and previews the first rows so you can confirm the table. The import has four pages: choose the workbook, say what each table holds, check the preview and save, then make the report. It lists every table and sheet with a role (requirements, glossary terms, allowed values such as Verification Level, tests, test plans, systems, needs, sources, or details that fill in existing requirements by ID), prefills each column from its header, previews the result, and saves the `mapping.json` described under [Combine tables](excel.md#combine-tables). Add the same table twice to give it two roles. The last page, **Make a report with this mapping**, opens the report task with `-c mapping.json --traceability`.
- **Gates and sign-off.** Check whether a gate is ready, freeze a baseline (with waivers for blocked strict checks), list baselines, record a sign-off, verify a baseline, make a gate review package and import returned decisions. A "not ready" or "not approved" answer is shown as an answer, not a failure. Pick a settings file to use your own gates, or one with `"baselines": {"store": "files"}` when the file is not in a git repository. These tasks record things, so nothing runs until you press Run.

The GUI runs only on your own computer: it listens on `127.0.0.1` and needs the secret token in the printed address, so other computers and other web pages cannot use it. Press Ctrl+C in the terminal to stop it. Use `--no-browser` to print the address without opening a browser.

The last page of every task shows the exact command it runs, for macOS/Linux (`sh`) or Windows (PowerShell), with a Copy button. Steps you run or add collect under **Your workflow** in the header, where you can reorder them, then copy or save them as a script (`reqtable-workflow.sh` or `reqtable-workflow.ps1`) to repeat the same work later without the GUI. A run that records something permanent (a baseline, a sign-off, imported decisions) is not added by itself, because running the script again would record it again; add it by hand if you mean that.
