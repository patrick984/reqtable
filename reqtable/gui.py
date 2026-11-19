"""Registry of the GUI's workflows and the pure functions that turn form values into commands.

The registry is the single source of truth: the server, the page and the tests all read WORKFLOWS.
Nothing here touches the disk or the network.
"""
from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

FieldKind = Literal["open", "save", "choice", "text", "number", "flag", "column", "table", "sheet"]
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


@dataclass(frozen=True)
class Workflow:
    id: str
    title: str
    summary: str
    when: str
    fields: tuple[Field, ...]


class GuiError(Exception):
    """The form is not ready to become a command; the message is for the user."""


class BadRequest(GuiError):
    """The caller sent a workflow, field or value this registry does not have."""


TABLE_EXTENSIONS = (".csv", ".xlsx")
ON_OFF = (("", "Automatic"), ("on", "Yes"), ("off", "No"))
YES = (("", "No"), ("on", "Yes"))


def _toggle(name: str, label: str, flag: str, help: str, *, both: bool = False) -> Field:
    return Field(name, label, "flag", flag, help, choices=ON_OFF if both else YES, advanced=True)


CONFIG = Field(
    "config", "Settings file", "open", "--config",
    "A JSON file of saved reqtable settings. Leave empty to use the defaults.",
    extensions=(".json",), advanced=True,
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
    "The row of the sheet that holds the column names. Only works together with a sheet; the default is the first non-empty row.",
    xlsx_only=True, advanced=True,
)


def _source(name: str, label: str, flag: str | None, help: str) -> Field:
    return Field(name, label, "open", flag, help, required=True, extensions=TABLE_EXTENSIONS)


def _html_output(help: str) -> Field:
    return Field("output", "Save the report as", "save", "-o", help, required=True, extensions=(".html",))


WORKFLOWS: tuple[Workflow, ...] = (
    Workflow(
        "report", "Make a report from a spreadsheet",
        "Turn a CSV or Excel file into a report you can open in any browser.",
        "Use this when you have a requirements spreadsheet and want to read, filter, review or edit it as a report.",
        (
            _source("input", "Spreadsheet to read", None, "A CSV or Excel (.xlsx) file."),
            _html_output("Where the finished report goes. It is one self-contained file you can email."),
            ID_COLUMN,
            Field(
                "document_mode", "What is the report for?", "choice", "--document-mode",
                "Review reports are for collecting comments. Develop reports let you edit the requirements themselves.",
                choices=(("review", "Review: read it and leave comments"), ("develop", "Develop: edit the requirements")),
                default="review",
            ),
            TABLE, SHEET, HEADER_ROW, TITLE, TRACEABILITY,
            Field(
                "reviewer_initials", "Reviewer initials", "text", "--reviewer-initials",
                "Initials stamped on comments made in the report.", advanced=True,
            ),
            CONFIG, ENCODING, DELIMITER,
        ),
    ),
    Workflow(
        "diff", "Compare two versions",
        "Show what was added, removed or changed between an older and a newer file.",
        "Use this when a requirements file was revised and reviewers need to see exactly what changed.",
        (
            _source("old", "Older version", "--old", "The file to compare against."),
            _source("new", "Newer version", "--new", "The file with the latest changes."),
            _html_output("Where the comparison report goes."),
            ID_COLUMN,
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
            TABLE, SHEET, HEADER_ROW, TITLE, TRACEABILITY, CONFIG, ENCODING, DELIMITER,
        ),
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
            Field("output", "Save the comments as", "save", "-o", "Where the CSV file of comments goes.", required=True, extensions=(".csv",)),
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
    ),
    Workflow(
        "list_tables", "See what's inside an Excel workbook",
        "List the sheets and tables in a workbook, with their column names.",
        "Use this first when you are not sure which table or sheet to use.",
        (
            Field("workbook", "Excel workbook", "open", "--list-tables", "The .xlsx file to look inside.", required=True, extensions=(".xlsx",)),
        ),
    ),
    Workflow(
        "to_csv", "Convert an Excel table to CSV",
        "Save one table or sheet of a workbook as a CSV file.",
        "Use this when you need a plain CSV, for example to keep in version control or compare with an older version.",
        (
            Field("input", "Excel workbook", "open", None, "The .xlsx file to read.", required=True, extensions=(".xlsx",)),
            Field("output", "Save the CSV as", "save", "-o", "Where the CSV file goes. The name must end in .csv.", required=True, extensions=(".csv",)),
            ID_COLUMN, TABLE, SHEET, HEADER_ROW, CONFIG, DELIMITER,
        ),
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


def build_argv(workflow: Workflow, values: Mapping[str, object], workdir: Path | None = None) -> list[str]:
    """Registry-order command line (positional first) for the submitted form values.

    Only checks the form is complete and well formed; the CLI itself validates what the values mean.
    """
    known = {f.name for f in workflow.fields}
    unknown = sorted(set(values) - known)
    if unknown:
        raise BadRequest(f"unknown field {unknown[0]!r} for workflow {workflow.id!r}")
    given = {name: ("" if value is None else str(value)).strip() for name, value in values.items()}
    has_workbook = any(is_workbook_path(given.get(f.name, "")) for f in workflow.fields if f.kind == "open")
    ordered = sorted(workflow.fields, key=lambda f: f.flag is not None)
    argv: list[str] = []
    missing: list[str] = []
    for field in ordered:
        value = given.get(field.name, "")
        if field.xlsx_only and not has_workbook:
            continue
        if not value:
            if field.required:
                missing.append(field.label)
            continue
        if field.kind in ("choice", "flag") and value not in dict(field.choices):
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
    return argv


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
