"""Registry of the GUI's workflows and the pure functions that turn form values into commands.

The registry is the single source of truth: the server, the page and the tests all read WORKFLOWS.
Nothing here touches the disk or the network.
"""
from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Mapping, Sequence

from .signoff import DECISIONS

FieldKind = Literal[
    "open", "save", "choice", "radio", "text", "number", "flag", "column", "table", "sheet",
    "gate", "baseline", "baselines", "role", "system", "waivers",
]
Panel = Literal["form", "mapping"]
Shell = Literal["sh", "powershell"]


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: FieldKind
    flag: str | None
    help: str
    required: bool = False
    choices: tuple[tuple[str, str], ...] = ()
    default: str = ""
    extensions: tuple[str, ...] = ()
    advanced: bool = False
    xlsx_only: bool = False
    requires: str = ""
    pair_flag: str | None = None


@dataclass(frozen=True)
class Workflow:
    """One task card. `fixed` argv is always emitted. `outcomes` give exit codes a plain label, and a code other than 0
    answers the question rather than failing. `table` names the tab-separated columns of stdout, and `recorded` says what
    a successful run leaves behind."""

    id: str
    title: str
    summary: str
    when: str
    fields: tuple[Field, ...]
    group: str = ""
    fixed: tuple[str, ...] = ()
    panel: Panel = "form"
    outcomes: tuple[tuple[int, str], ...] = ()
    table: tuple[str, ...] = ()
    recorded: str = ""


class GuiError(Exception):
    """The form is not ready to become a command; the message is for the user."""


class BadRequest(GuiError):
    """The caller sent a workflow, field or value this registry does not have."""


TABLE_EXTENSIONS = (".csv", ".xlsx")
ANY_FILE = ("*",)
ON_OFF = (("", "Automatic"), ("on", "Yes"), ("off", "No"))
YES = (("", "No"), ("on", "Yes"))
MAKE, COMPARE, EXCEL, GATES = "Make reports", "Compare and review", "Excel workbooks", "Gates and sign-off"
GROUPS = (MAKE, COMPARE, EXCEL, GATES)


def _toggle(name: str, label: str, flag: str, help: str, *, both: bool = False) -> Field:
    return Field(name, label, "flag", flag, help, choices=ON_OFF if both else YES, advanced=True)


CONFIG = Field(
    "config", "Settings file", "open", "--config",
    "A JSON file of saved reqtable settings. Leave empty to use the defaults.",
    extensions=(".json",), advanced=True,
)
GATE_CONFIG = replace(
    CONFIG, advanced=False,
    help="A JSON file of saved reqtable settings. It can list your own review gates and choose where baselines are stored. Leave empty to use the defaults.",
)
ENCODING = Field(
    "encoding", "Text encoding", "text", "--encoding",
    "Only change this if accented letters look wrong. The default handles most files, including ones saved by Excel.",
    advanced=True,
)
DELIMITER = Field(
    "delimiter", "Column separator", "text", "--delimiter",
    "The character between columns in a CSV file. The default is a comma.",
    advanced=True,
)
ID_COLUMN = Field(
    "id_column", "ID column", "column", "--id-column",
    "The column that holds each requirement's unique ID. Required unless your settings file names one.",
)
TITLE = Field("title", "Report title", "text", "--title", "Shown at the top of the report. Leave empty for the default.", advanced=True)
TRACEABILITY = _toggle(
    "traceability", "Systems and traceability document", "--traceability",
    "Treat the file as a systems and traceability document. Automatic lets reqtable decide.", both=True,
)
TABLE = Field(
    "table", "Excel table", "table", "--table",
    "Which table in the workbook to read. A workbook with exactly one table needs no choice.", xlsx_only=True,
)
SHEET = Field(
    "sheet", "Excel sheet", "sheet", "--sheet",
    "Read a whole sheet instead of a table. Use this when the workbook has no tables.", xlsx_only=True,
)
HEADER_ROW = Field(
    "header_row", "Header row number", "number", "--header-row",
    "The row of the sheet that holds the column names. The default is the first non-empty row.",
    xlsx_only=True, requires="sheet",
)
WHICH_BLOCK = (TABLE, SHEET, HEADER_ROW, ID_COLUMN)
DOCUMENT_MODE = Field(
    "document_mode", "What is the report for?", "radio", "--document-mode",
    "Review reports are for collecting comments. Develop reports let you edit the requirements themselves.",
    choices=(("review", "Review: read it and leave comments"), ("develop", "Develop: edit the requirements")),
    default="review",
)
BASELINES = Field(
    "baselines", "Compare against baselines", "baselines", "--baselines",
    "Embed frozen gate baselines so the report can show what changed since each one. Needs baselines to exist already.",
    advanced=True,
)


def _source(name: str, label: str, flag: str | None, help: str) -> Field:
    return Field(name, label, "open", flag, help, required=True, extensions=TABLE_EXTENSIONS)


def _html_output(name: str, help: str) -> Field:
    return Field("output", "Save the report as", "save", "-o", help, required=True, extensions=(".html",), default=name)


def _report_fields(*, mode: bool) -> tuple[Field, ...]:
    return (
        _source("input", "Spreadsheet to read", None, "A CSV or Excel (.xlsx) file."),
        *WHICH_BLOCK,
        _html_output("requirements-report.html", "Where the finished report goes. It is one self-contained file you can email."),
        *((DOCUMENT_MODE,) if mode else ()),
        TITLE, TRACEABILITY,
        Field(
            "reviewer_initials", "Reviewer initials", "text", "--reviewer-initials",
            "Initials stamped on comments made in the report.", advanced=True,
        ),
        BASELINES, CONFIG, ENCODING, DELIMITER,
    )


def _table_input(help: str) -> Field:
    return _source("input", "Requirements file", None, help)


def _gate(flag: str, help: str) -> Field:
    return Field("gate", "Review gate", "gate", flag, help, required=True)


def _baseline(flag: str, help: str) -> Field:
    return Field("baseline", "Baseline", "baseline", flag, help, required=True)


SYSTEM = Field(
    "system", "System", "system", "--system",
    "Which system the gate covers. Only gates that cover one system and its subsystems ask for this.",
)
USER = Field(
    "user", "Who is doing this", "text", "--user",
    "Recorded with the entry. Leave empty to use your git user name or your login name.",
)
GATE_TAIL = (TRACEABILITY, ENCODING, DELIMITER)

WORKFLOWS: tuple[Workflow, ...] = (
    Workflow(
        "report", "Make a report from a spreadsheet",
        "Turn a CSV or Excel file into a report you can open in any browser.",
        "Use this when you have a requirements spreadsheet and want to read, filter, review or edit it as a report. If your Excel table has heading rows that name categories, use “Import several tables from one workbook” instead. One table is fine there.",
        _report_fields(mode=True), group=MAKE,
    ),
    Workflow(
        "develop", "Edit requirements (Develop report)",
        "Turn a CSV or Excel file into a Develop report, where you add, edit and delete requirements right in the browser.",
        "Use this when you want to change the requirements themselves, not only comment on them. Save the edited table back as a CSV from the report.",
        _report_fields(mode=False), group=MAKE, fixed=("--document-mode", "develop"),
    ),
    Workflow(
        "diff", "Compare two versions",
        "Show what was added, removed or changed between an older and a newer file.",
        "Use this when a requirements file was revised and reviewers need to see exactly what changed.",
        (
            _source("old", "Older version", "--old", "The file to compare against."),
            _source("new", "Newer version", "--new", "The file with the latest changes."),
            *WHICH_BLOCK,
            _html_output("requirements-diff.html", "Where the comparison report goes."),
            DOCUMENT_MODE,
            Field(
                "initial_diff_view", "How to show changes", "choice", "--initial-diff-view",
                "Unified shows changes in one column. Side by side shows old and new next to each other.",
                choices=(("unified", "Unified"), ("side-by-side", "Side by side")), advanced=True,
            ),
            _toggle("changes_only", "Start with changed rows only", "--changes-only", "Hide rows that did not change when the report opens."),
            _toggle(
                "include_unchanged", "Include unchanged rows", "--include-unchanged",
                "Keep rows that did not change in the report. Automatic uses your settings.", both=True,
            ),
            TITLE, TRACEABILITY, BASELINES, CONFIG, ENCODING, DELIMITER,
        ),
        group=COMPARE,
    ),
    Workflow(
        "comments", "Collect review comments from a reviewed report",
        "Pull the comments reviewers made in a report back out into a CSV file.",
        "Use this when reviewers have sent back their copy of a report and you want their comments in a spreadsheet.",
        (
            Field(
                "report", "Reviewed report", "open", "--extract-comments",
                "The report file a reviewer saved, with their comments in it.", required=True, extensions=(".html",),
            ),
            Field("output", "Save the comments as", "save", "-o", "Where the CSV file of comments goes.", required=True, extensions=(".csv",), default="review-comments.csv"),
            Field(
                "csv_base", "Which rows to include", "choice", "--csv-base",
                "For a comparison report. New keeps rows in the newer version, old the older one, union both.",
                choices=(("new", "Rows in the newer version"), ("old", "Rows in the older version"), ("union", "Rows from both versions")),
                default="new", advanced=True,
            ),
            Field(
                "comments_format", "Comment format in the CSV", "choice", "--comments-format",
                "Text is easiest to read in a spreadsheet. JSON keeps every detail of each comment.",
                choices=(("text", "Plain text"), ("json", "JSON")), advanced=True,
            ),
            Field("comments_column", "Comments column name", "text", "--comments-column", "The CSV column that receives the comments.", advanced=True),
            _toggle(
                "allow_comment_loss", "Allow losing some comments", "--allow-comment-loss",
                "Carry on even if some comments cannot be placed on a row. Without this, reqtable stops and tells you.",
            ),
            CONFIG, DELIMITER,
        ),
        group=COMPARE,
    ),
    Workflow(
        "list_tables", "See what's inside an Excel workbook",
        "List the sheets and tables in a workbook, with their column names.",
        "Use this first when you are not sure which table or sheet to use.",
        (
            Field("workbook", "Excel workbook", "open", "--list-tables", "The .xlsx file to look inside.", required=True, extensions=(".xlsx",)),
        ),
        group=EXCEL,
    ),
    Workflow(
        "to_csv", "Convert an Excel table to CSV",
        "Save one table or sheet of a workbook as a CSV file.",
        "Use this when you need a plain CSV, for example to keep in version control or compare with an older version.",
        (
            Field("input", "Excel workbook", "open", None, "The .xlsx file to read.", required=True, extensions=(".xlsx",)),
            *WHICH_BLOCK,
            Field("output", "Save the CSV as", "save", "-o", "Where the CSV file goes. The name must end in .csv.", required=True, extensions=(".csv",), default="workbook-table.csv"),
            CONFIG, DELIMITER,
        ),
        group=EXCEL,
    ),
    Workflow(
        "mapping", "Import several tables from one workbook (requirements, glossary, tests…)",
        "Choose which tables of a workbook are requirements, glossary terms, allowed values, tests or test plans, and save the mapping.",
        "Use this when one workbook holds your requirements and also your glossary, lookup lists or tests on other sheets. It also handles a single requirements table whose heading rows name the category of the rows below them.",
        (
            Field("input", "Excel workbook", "open", None, "The .xlsx file that holds the tables.", required=True, extensions=(".xlsx",)),
        ),
        group=EXCEL, panel="mapping",
    ),
    Workflow(
        "check_gate", "Check whether a gate is ready",
        "Run a review gate's readiness checks on your requirements and see which pass.",
        "Use this before a review such as SRR or PDR, to see what still needs fixing. It changes nothing.",
        (
            _table_input("The CSV or Excel (.xlsx) file to check."), *WHICH_BLOCK, GATE_CONFIG,
            _gate("--check-gate", "The review gate to check, such as SRR or PDR."), SYSTEM, *GATE_TAIL,
        ),
        group=GATES, outcomes=((0, "This gate is ready"), (1, "Not ready yet")),
    ),
    Workflow(
        "create_baseline", "Freeze a baseline at a gate",
        "Freeze the requirements as approved at a review gate, so later reports can compare against them.",
        "Use this when a gate review is held and you want a permanent record of exactly what was reviewed.",
        (
            _table_input("The CSV or Excel (.xlsx) file to freeze."), *WHICH_BLOCK, GATE_CONFIG,
            _gate("--create-baseline", "The review gate you are holding."), SYSTEM,
            Field(
                "waivers", "Waive a failing check", "waivers", "--waive",
                "A strict gate refuses to freeze while a required check fails. Waive a check with a reason, and the waiver is recorded in the baseline.",
                pair_flag="--reason",
            ),
            replace(USER, advanced=True), *GATE_TAIL,
        ),
        group=GATES, outcomes=((1, "Blocked by a required check"),),
        recorded="A permanent baseline was recorded where the result below says. Freezing this gate again makes a new numbered baseline and never changes this one.",
    ),
    Workflow(
        "list_baselines", "List baselines",
        "See every baseline that was frozen for this requirements file.",
        "Use this to find a baseline's name before you sign it off or verify it.",
        (_table_input("The CSV or Excel (.xlsx) file whose baselines to list."), *WHICH_BLOCK, GATE_CONFIG, *GATE_TAIL),
        group=GATES, fixed=("--list-baselines",), table=("Baseline", "Gate", "System", "Frozen", "By", "Hash"),
    ),
    Workflow(
        "sign_off", "Record a sign-off",
        "Record a reviewer's decision on a frozen baseline.",
        "Use this when a reviewer or approver has decided on a baseline and you want it on the record.",
        (
            _table_input("The CSV or Excel (.xlsx) file the baseline was frozen from."), *WHICH_BLOCK, GATE_CONFIG,
            _baseline("--sign-off", "The baseline the decision is about."),
            Field("role", "Role", "role", "--role", "The sign-off role the decision is made in. The roles come from the baseline's gate.", required=True),
            Field(
                "decision", "Decision", "choice", "--decision", "What was decided.", required=True,
                choices=tuple((d, d) for d in DECISIONS),
            ),
            USER,
            Field("note", "Note", "text", "--note", "Anything worth keeping with the decision, such as the board meeting.", advanced=True),
            Field("evidence", "Evidence file", "open", "--evidence", "A file that backs the decision, such as a signed PDF.", extensions=ANY_FILE, advanced=True),
            *GATE_TAIL,
        ),
        group=GATES,
        recorded="Your decision was recorded where the result below says. Use Verify a baseline to see where the sign-offs stand.",
    ),
    Workflow(
        "verify_baseline", "Verify a baseline",
        "Recheck that a baseline's content is unchanged and see whether it has the sign-offs it needs.",
        "Use this to find out whether a gate is approved, or to prove a frozen baseline was not altered.",
        (
            _table_input("The CSV or Excel (.xlsx) file the baseline was frozen from."), *WHICH_BLOCK, GATE_CONFIG,
            _baseline("--verify-baseline", "The baseline to check."), *GATE_TAIL,
        ),
        group=GATES, outcomes=((0, "Approved and unchanged"), (1, "Not approved yet, or the content changed")),
    ),
    Workflow(
        "gate_package", "Make a gate review package",
        "Write the report reviewers receive for a baseline, with a cover for recording their decisions.",
        "Use this when you want reviewers to read a frozen baseline and record their decisions in one file.",
        (
            _table_input("The CSV or Excel (.xlsx) file the baseline was frozen from."), *WHICH_BLOCK, GATE_CONFIG,
            _baseline("--gate-package", "The baseline reviewers will look at."),
            Field("output", "Save the package as", "save", "-o", "Where the package goes. It is one self-contained file you can email.", required=True, extensions=(".html",), default="gate-package.html"),
            *GATE_TAIL,
        ),
        group=GATES,
    ),
    Workflow(
        "import_decisions", "Import decisions from a returned package",
        "Record the decisions reviewers saved in their copy of a gate package as sign-offs.",
        "Use this when reviewers have sent back their saved copies of a gate package.",
        (
            _table_input("The CSV or Excel (.xlsx) file the package was made from."), *WHICH_BLOCK, GATE_CONFIG,
            Field(
                "package", "Returned package", "open", "--import-decisions",
                "The package file a reviewer saved, with their decision in it.", required=True, extensions=(".html",),
            ),
            *GATE_TAIL,
        ),
        group=GATES,
        recorded="Each decision in the package was recorded as a sign-off, as the result below says.",
    ),
)

WORKFLOWS_BY_ID = {workflow.id: workflow for workflow in WORKFLOWS}


def workflow_named(workflow_id: str) -> Workflow:
    try:
        return WORKFLOWS_BY_ID[workflow_id]
    except KeyError:
        raise BadRequest(f"unknown workflow {workflow_id!r}") from None


def column_source(workflow: Workflow) -> Field | None:
    """The field whose file supplies the ID-column choices."""
    return next((f for f in workflow.fields if f.kind == "open" and ".csv" in f.extensions), None) or next(
        (f for f in workflow.fields if f.kind == "open" and ".xlsx" in f.extensions), None
    )


def is_workbook_path(path: str) -> bool:
    return path.lower().endswith(".xlsx")


def _shown_path(value: str, workdir: Path | None) -> str:
    path = Path(value)
    if workdir is not None and path.is_absolute():
        try:
            return path.relative_to(workdir).as_posix()
        except ValueError:
            pass
    return value


def lookup_source(workflow: Workflow) -> Field | None:
    """The field whose file the gate, baseline and system lists are read from: the table being worked on."""
    return next((f for f in workflow.fields if f.name in ("input", "new") and f.kind == "open"), None)


def guess_id_column(columns: Sequence[str]) -> str:
    """The header that most likely holds each record's ID, or an empty string when none looks like one."""
    names = [c for c in columns if c.strip()]
    exact = next((c for c in names if c.strip().casefold() == "id"), None)
    if exact is not None:
        return exact
    return next((c for c in names if c.strip().casefold().endswith((" id", "_id")) or c.strip().endswith("Id")), "")


def blocked_checks(stderr: str) -> list[str]:
    """The check IDs a blocked --create-baseline suggests waiving, in the order the CLI names them."""
    found = re.search(r"--waive (\S+) --reason", stderr)
    return [part for part in found.group(1).split(",") if part] if found else []


def _waiver_args(field: Field, rows: object) -> list[str]:
    if rows in (None, "", []):
        return []
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise BadRequest(f"{field.name!r} must be a list of {{check, reason}} rows")
    assert field.flag is not None and field.pair_flag is not None
    argv: list[str] = []
    for row in rows:
        check, reason = (str(row.get(key) or "").strip() for key in ("check", "reason"))
        if not check and not reason:
            continue
        if not check or not reason:
            raise GuiError("Each waiver needs both the check and the reason")
        if "," in check or check.startswith("-"):
            raise GuiError(f"{check!r} is not a check ID")
        argv += [field.flag, check, f"{field.pair_flag}={reason}" if reason.startswith("-") else field.pair_flag]
        if not reason.startswith("-"):
            argv.append(reason)
    return argv


def build_argv(workflow: Workflow, values: Mapping[str, object], workdir: Path | None = None) -> list[str]:
    """Registry-order command line (positional first) for the submitted form values.

    Only checks the form is complete and well formed; the CLI itself validates what the values mean.
    """
    if workflow.panel != "form":
        raise BadRequest(f"{workflow.id!r} builds a mapping file, not a command")
    known = {f.name for f in workflow.fields}
    unknown = sorted(set(values) - known)
    if unknown:
        raise BadRequest(f"unknown field {unknown[0]!r} for workflow {workflow.id!r}")
    waivers = {f.name for f in workflow.fields if f.kind == "waivers"}
    given = {
        name: value if name in waivers else ("" if value is None else str(value)).strip() for name, value in values.items()
    }
    has_workbook = any(is_workbook_path(str(given.get(f.name, ""))) for f in workflow.fields if f.kind == "open")
    ordered = sorted(workflow.fields, key=lambda f: f.flag is not None)
    argv: list[str] = []
    missing: list[str] = []
    for field in ordered:
        if field.kind == "waivers":
            argv += _waiver_args(field, given.get(field.name))
            continue
        value = str(given.get(field.name, ""))
        if field.xlsx_only and not has_workbook:
            continue
        if field.requires and not given.get(field.requires):
            continue
        if not value:
            if field.required:
                missing.append(field.label)
            continue
        if field.kind in ("choice", "radio", "flag") and value not in dict(field.choices):
            raise BadRequest(f"{value!r} is not a choice for {field.name!r}")
        if field.kind in ("open", "save"):
            if value.startswith("-"):
                raise GuiError(f"{field.label}: a file name cannot start with '-'")
            value = _shown_path(value, workdir)
        if field.kind == "flag":
            assert field.flag is not None
            argv.append(field.flag if value == "on" else "--no-" + field.flag[2:])
        elif field.flag is None:
            argv.append(value)
        elif value.startswith("-"):
            argv.append(f"{field.flag}={value}")
        else:
            argv += [field.flag, value]
    if missing:
        raise GuiError("Please fill in: " + ", ".join(missing))
    return [*argv, *workflow.fixed]


PS_BARE = re.compile(r"[A-Za-z0-9_./\\:=+-]+")


def quote_powershell(token: str) -> str:
    if PS_BARE.fullmatch(token):
        return token
    return "'" + token.replace("'", "''") + "'"


_SHELLS = {
    "sh": ("python3", shlex.quote, " \\"),
    "powershell": ("python", quote_powershell, " `"),
}
WIDTH = 78


def _is_flag(token: str) -> bool:
    return token.startswith("-") and len(token) > 1


def _command(argv: Sequence[str], program: Sequence[str], shell: Shell) -> str:
    interpreter, quote, continuation = _SHELLS[shell]
    tokens = [quote(t) for t in argv]
    start = next((i for i, t in enumerate(argv) if _is_flag(t)), len(argv))
    head = " ".join([interpreter, *(quote(t) for t in program), *tokens[:start]])
    groups: list[list[str]] = []
    for original, token in zip(argv[start:], tokens[start:]):
        if _is_flag(original) or not groups:
            groups.append([token])
        else:
            groups[-1].append(token)
    flat = " ".join([head, *(" ".join(g) for g in groups)])
    if len(flat) <= WIDTH:
        return flat
    return (continuation + "\n").join([head, *("  " + " ".join(g) for g in groups)])


def posix_command(argv: Sequence[str], program: Sequence[str] = ("reqtable.pyz",)) -> str:
    return _command(argv, program, "sh")


def powershell_command(argv: Sequence[str], program: Sequence[str] = ("reqtable.pyz",)) -> str:
    return _command(argv, program, "powershell")


Step = tuple[str, Sequence[str]]


def script(steps: Sequence[Step], shell: Shell, workdir: Path, program: Sequence[str] = ("reqtable.pyz",)) -> str:
    """A runnable script for (title, argv) steps. Titles become comments."""
    if shell == "sh":
        lines = ["#!/bin/sh", "set -e", f"cd {shlex.quote(str(workdir))}"]
        after: list[str] = []
    else:
        lines = ["$ErrorActionPreference = 'Stop'", f"Set-Location -LiteralPath {quote_powershell(str(workdir))}"]
        # Native commands do not throw on failure, so stop on a non-zero exit code.
        after = ["if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"]
    for title, argv in steps:
        lines += ["", "# " + " ".join(title.split()), _command(argv, program, shell), *after]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Launcher:
    """How to start reqtable: the argv to run, its environment, and the tokens to show a user."""

    run: tuple[str, ...]
    shown: tuple[str, ...]
    env: Mapping[str, str]


def launcher(workdir: Path, module_file: str | None = None) -> Launcher:
    here = Path(module_file or __file__).resolve()
    archive = next((p for p in here.parents if p.is_file()), None)
    if archive is not None:
        return Launcher((sys.executable, str(archive)), (_shown_path(str(archive), workdir),), {})
    return Launcher((sys.executable, "-m", "reqtable"), ("-m", "reqtable"), {"PYTHONPATH": str(here.parent.parent)})
