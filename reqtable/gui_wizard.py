"""How the GUI walks someone through a task: the pages of each task's wizard, what usually follows a task, and the typical jobs.

Pages are derived from the registry's field kinds, so a new field lands on a page without a hand-kept list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .gui import Field, Workflow, table_inputs


@dataclass(frozen=True)
class WizardPage:
    id: str
    title: str
    help: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class NextStep:
    """A task that usually follows another. `carry` pairs a field of the finished task with the field of this task it fills."""

    workflow: str
    label: str
    why: str
    carry: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class JourneyStep:
    workflow: str
    why: str


@dataclass(frozen=True)
class Journey:
    id: str
    title: str
    summary: str
    steps: tuple[JourneyStep, ...]


GATE_KINDS = frozenset({"gate", "baseline", "role", "system", "waivers"})

FILES_HELP = "Pick the file this task reads."
GATE_HELP = "Say which review gate or baseline this is about."
OPTIONS_HELP = "Where the result goes, and anything else worth setting. The defaults suit most people."

MAPPING_PAGES = (
    WizardPage(
        "workbook",
        "Choose the workbook",
        "Pick the .xlsx file that holds your tables. If you saved a mapping earlier, you can load it to change it.",
        ("input",),
    ),
    WizardPage(
        "tables",
        "Say what each table holds",
        "Say what each table or sheet holds. Leave the ones you do not need on “Don't import”.",
        (),
    ),
    WizardPage(
        "save",
        "Check the preview and save",
        "Check what would be imported, then save the mapping.",
        (),
    ),
    WizardPage(
        "report",
        "Make the report",
        "The mapping is saved. Make a report that uses it.",
        (),
    ),
)


def _on_files_page(field: Field, tables: set[str]) -> bool:
    return (
        field.name in tables
        or field.xlsx_only
        or field.kind == "column"
        or (field.kind == "open" and (field.required or not field.advanced))
    )


def _on_gate_page(field: Field) -> bool:
    return field.kind in GATE_KINDS or (field.kind == "choice" and field.required)


def _gate_title(fields: list[Field]) -> str:
    subject = "Gate" if any(f.kind == "gate" for f in fields) else "Baseline"
    return subject + (
        " and decision" if any(f.kind == "choice" for f in fields) else ""
    )


def wizard_pages(workflow: Workflow) -> tuple[WizardPage, ...]:
    """The pages before the final check-and-run page, which every form task has and which holds no fields.

    A trailing page of only advanced fields would be a step that shows nothing but a collapsed section,
    so those fields join the page before it."""
    if workflow.panel != "form":
        return MAPPING_PAGES
    tables = {f.name for f in table_inputs(workflow)}
    files = [f for f in workflow.fields if _on_files_page(f, tables)]
    rest = [f for f in workflow.fields if f not in files]
    gate = [f for f in rest if _on_gate_page(f)]
    options = [f for f in rest if f not in gate]
    groups = [
        ("files", "Choose files", FILES_HELP, files),
        ("gate", _gate_title(gate) if gate else "", GATE_HELP, gate),
        ("options", "Options", OPTIONS_HELP, options),
    ]
    groups = [group for group in groups if group[3]]
    if len(groups) > 1 and all(f.advanced for f in groups[-1][3]):
        *kept, (_, _, _, folded) = groups
        kept[-1] = (*kept[-1][:3], [*kept[-1][3], *folded])
        groups = kept
    return tuple(
        WizardPage(i, t, h, tuple(f.name for f in fs)) for i, t, h, fs in groups
    )


def _same(*names: str) -> tuple[tuple[str, str], ...]:
    return tuple((name, name) for name in names)


SOURCE = ("input", "table", "sheet", "header_row", "id_column", "config")

NEXT: Mapping[str, tuple[NextStep, ...]] = {
    "report": (
        NextStep(
            "comments",
            "Collect review comments",
            "When reviewers send their copy back",
            (("output", "report"),),
        ),
    ),
    "develop": (
        NextStep(
            "diff",
            "Compare your edits with the original",
            "After you save your edited table as a CSV from the report",
            (("input", "old"),),
        ),
    ),
    "diff": (
        NextStep(
            "comments",
            "Collect review comments",
            "When reviewers send their copy back",
            (("output", "report"),),
        ),
    ),
    "to_csv": (
        NextStep(
            "report",
            "Make a report from this CSV",
            "To read, filter or review the table",
            (("output", "input"),),
        ),
        NextStep(
            "diff",
            "Compare this CSV with an older version",
            "To see what changed since the last revision",
            (("output", "new"),),
        ),
    ),
    "list_tables": (
        NextStep(
            "mapping",
            "Import several tables from this workbook",
            "When requirements, glossary terms or tests sit on different sheets",
            (("workbook", "input"),),
        ),
        NextStep(
            "report",
            "Make a report from one table",
            "When one table holds the requirements",
            (("workbook", "input"),),
        ),
        NextStep(
            "to_csv",
            "Convert one table to CSV",
            "When you need a plain CSV file",
            (("workbook", "input"),),
        ),
    ),
    "mapping": (
        NextStep(
            "report",
            "Make a report with this mapping",
            "Now that the mapping is saved",
            (("input", "input"),),
        ),
    ),
    "check_gate": (
        NextStep(
            "create_baseline",
            "Freeze a baseline at this gate",
            "When you hold the review and want a permanent record",
            _same(*SOURCE, "gate", "system"),
        ),
    ),
    "create_baseline": (
        NextStep(
            "gate_package",
            "Make a gate review package",
            "To send reviewers the frozen baseline",
            _same(*SOURCE),
        ),
        NextStep(
            "sign_off",
            "Record a sign-off",
            "When a reviewer has already decided",
            _same(*SOURCE),
        ),
    ),
    "gate_package": (
        NextStep(
            "import_decisions",
            "Import the returned decisions",
            "When reviewers send their saved copies back",
            (*_same(*SOURCE), ("output", "package")),
        ),
    ),
    "sign_off": (
        NextStep(
            "verify_baseline",
            "Verify the baseline",
            "To see whether it has the sign-offs it needs",
            _same(*SOURCE, "baseline"),
        ),
    ),
    "import_decisions": (
        NextStep(
            "verify_baseline",
            "Verify the baseline",
            "To see whether it has the sign-offs it needs",
            _same(*SOURCE),
        ),
    ),
}

JOURNEYS: tuple[Journey, ...] = (
    Journey(
        "share",
        "Share requirements for review",
        "Make a report your reviewers can comment on, then pull their comments back into a spreadsheet.",
        (
            JourneyStep(
                "report",
                "Make the report. Keep it on Review so reviewers can leave comments.",
            ),
            JourneyStep(
                "comments",
                "When reviewers send their copy back, collect their comments.",
            ),
        ),
    ),
    Journey(
        "edit",
        "Edit requirements in the browser",
        "Open your requirements in a report where you add, edit and delete them, then save the table as a CSV.",
        (
            JourneyStep(
                "develop", "Make a Develop report and edit your requirements in it."
            ),
        ),
    ),
    Journey(
        "changes",
        "See what changed between two versions",
        "Compare an older and a newer file, then collect reviewers' comments on the changes.",
        (
            JourneyStep("diff", "Choose the two versions and make the comparison."),
            JourneyStep(
                "comments",
                "When reviewers send their copy back, collect their comments.",
            ),
        ),
    ),
    Journey(
        "excel",
        "Bring in an Excel workbook",
        "Look inside a workbook, say what each table holds, and make a report from it.",
        (
            JourneyStep("list_tables", "See which sheets and tables the workbook has."),
            JourneyStep("mapping", "Say what each table holds and save the mapping."),
            JourneyStep("report", "Make a report with the saved mapping."),
        ),
    ),
    Journey(
        "gate",
        "Hold a gate review",
        "Check a gate, freeze a baseline, send reviewers a package, record their decisions and verify the result.",
        (
            JourneyStep("check_gate", "See what still needs fixing before the review."),
            JourneyStep(
                "create_baseline", "Freeze the requirements as reviewed at the gate."
            ),
            JourneyStep(
                "gate_package", "Write the package reviewers will read and decide in."
            ),
            JourneyStep(
                "import_decisions", "Record the decisions from the returned packages."
            ),
            JourneyStep(
                "verify_baseline", "Check that the baseline has the sign-offs it needs."
            ),
        ),
    ),
)
