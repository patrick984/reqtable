"""The GUI's workbook mapping builder: what each kind of table can fill in, and the pure code that turns a form into
the ``xlsx.sources`` mapping documented in the README. Only ``preview_mapping`` and ``save_mapping`` touch the disk."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .core import ConfigError, ReqtableError, atomic_write_text, validate_xlsx_sources
from .gui import BadRequest, GuiError, guess_id_column
from .xlsx import XlsxSelection, import_workbook

ID_COLUMN = "ID"
FIELD_COLUMN = "Field"
SEPARATORS = ((",", "Comma"), (";", "Semicolon"), ("newline", "New line"))
LIST_SEPARATOR = ","
KEEP, MAP, EXCLUDE = "keep", "map", "exclude"
FIELD_CHOICES = (
    ("Priority", "Priority"),
    ("Verification Method", "Verification Method"),
    ("Verification Level", "Verification Level (verification stages)"),
    ("Execution", "Execution (manual or automated)"),
    ("Compliance", "Compliance"),
    ("Result", "Result"),
)


@dataclass(frozen=True)
class Target:
    """An output column a role offers. `hints` are other header names that should be matched to it automatically."""

    column: str
    label: str
    list_separator: bool = False
    hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class Role:
    id: str
    label: str
    help: str
    type: str | None
    targets: tuple[Target, ...]
    id_prefix: str = ""
    needs_field: bool = False
    merge: bool = False


def _id(label: str = "ID") -> Target:
    return Target(ID_COLUMN, label, hints=("id",))


NAME = Target("Name", "Name", hints=("title",))
REFERENCE = Target("Reference", "Link or citation", hints=("url", "link"))
METHOD = Target("Verification Method", "Verification Method", True, ("method",))
LEVEL = Target("Verification Level", "Verification Level (verification stages)", True, ("level", "stage"))

ROLES: tuple[Role, ...] = (
    Role(
        "requirements", "Requirements", "The requirements themselves. Each row keeps its own Type.", None,
        (
            _id("ID"), Target("Name", "Short title", hints=("title",)),
            Target("Requirement", "Requirement text", hints=("text", "description", "shall")),
            Target("Priority", "Priority"), METHOD, LEVEL,
            Target("Verified by", "Tests that verify it", True, ("tests",)),
            Target("Allocated to", "Systems it is allocated to", True),
            Target("Derived from", "Parent requirements", True, ("parent",)),
            Target("Source refs", "Needs and sources", True, ("sources",)),
            Target("Owner", "Owning system"), Target("Rationale", "Rationale"),
            Target("Compliance", "Compliance (is it met?)"), Target("Type", "Record type", hints=("kind",)),
        ),
    ),
    Role(
        "glossary", "Glossary terms", "Words and abbreviations the project defines. Each row becomes a Term.", "Term",
        (
            _id("ID"), Target("Name", "Term", hints=("name", "word")),
            Target("Definition", "Meaning", hints=("meaning", "description")),
            Target("Aliases", "Other spellings", True, ("abbreviation", "synonyms", "alias")),
            Target("Auto Link", "Link automatically in text", hints=("autolink",)), REFERENCE,
        ),
        id_prefix="TERM-",
    ),
    Role(
        "values", "Allowed values",
        "The values a column may hold, such as Must and Should for Priority, or Unit and System for Verification Level.", "Value",
        (
            _id("ID"), Target(FIELD_COLUMN, "Column the value belongs to", hints=("column",)),
            Target("Name", "Allowed value", hints=("value",)),
            Target("Definition", "Meaning", hints=("meaning", "description")),
            Target("Aliases", "Old spellings", True, ("synonyms", "alias")), REFERENCE,
        ),
        id_prefix="VAL-", needs_field=True,
    ),
    Role(
        "tests", "Tests", "Tests, scripts or checklists that verify requirements. The description lands in the Requirement column.",
        "Test",
        (
            _id("ID"), Target("Name", "Test title", hints=("title", "name")),
            Target("Requirement", "Description", hints=("description", "text", "steps")),
            Target("Test plan", "Test plan", hints=("plan",)), METHOD, LEVEL,
            Target("Execution", "How it is run (Manual or Automated)"), Target("Result", "Result", hints=("status",)),
            Target("Reference", "Link to the test", hints=("url", "link")),
        ),
        id_prefix="TEST-",
    ),
    Role(
        "plans", "Test plans", "Groups of tests. The description lands in the Requirement column.", "Test plan",
        (
            _id("ID"), Target("Name", "Plan title", hints=("title",)),
            Target("Requirement", "Description", hints=("description", "text")), REFERENCE,
        ),
        id_prefix="PLAN-",
    ),
    Role(
        "systems", "Systems", "The systems and subsystems the requirements are allocated to.", "System",
        (_id("ID"), NAME, Target("Part of", "Parent system", hints=("parent",)), REFERENCE),
        id_prefix="SYS-",
    ),
    Role(
        "needs", "Needs", "Stakeholder needs that requirements trace back to. The description lands in the Requirement column.",
        "Need",
        (
            _id("ID"), NAME, Target("Requirement", "Description", hints=("description", "text")),
            Target("Source refs", "Sources", True, ("sources",)), REFERENCE,
        ),
        id_prefix="NEED-",
    ),
    Role(
        "sources", "Sources", "Documents, standards or people that needs and requirements cite.", "Source",
        (_id("ID"), NAME, REFERENCE), id_prefix="SRC-",
    ),
)
ROLES += (
    Role(
        "merge", "Details for existing requirements (matched by ID)",
        "Fills in cells of requirements that are already imported, matching each row by ID. Use it for a verification "
        "matrix sheet, or add a tests table a second time here to link its tests to the requirements they verify.",
        None,
        (
            Target(ID_COLUMN, "Requirement ID (which requirement this row is about)", True, ("id", "requirement id", "verifies")),
            LEVEL, METHOD, Target("Verified by", "Tests that verify it", True, ("tests",)), Target("Priority", "Priority"),
            Target("Rationale", "Rationale"),
        ),
        merge=True,
    ),
)
ROLES_BY_ID = {role.id: role for role in ROLES}


def role_named(role_id: str) -> Role:
    try:
        return ROLES_BY_ID[role_id]
    except KeyError:
        raise BadRequest(f"unknown role {role_id!r}") from None


def role_for_type(record_type: str | None) -> Role | None:
    return next((role for role in ROLES if role.type == record_type), None)


def mapping_json() -> dict[str, Any]:
    return {
        "roles": [asdict(role) for role in ROLES],
        "separators": [{"value": value, "label": label} for value, label in SEPARATORS],
        "fields": [{"value": value, "label": label} for value, label in FIELD_CHOICES],
        "id_column": ID_COLUMN,
    }


def suggest_columns(role: Role, headers: list[str]) -> dict[str, Any]:
    """Prefill: each header goes to the role target it is named after, else it is kept as it is."""
    guessed_id = guess_id_column(headers)
    taken: set[str] = set()
    columns = []
    for header in headers:
        name = header.strip().casefold()
        target = None
        for candidate in role.targets:
            if candidate.column in taken:
                continue
            if candidate.column == ID_COLUMN:
                hit = header == guessed_id and bool(guessed_id)
            else:
                hit = name in {candidate.column.casefold(), candidate.label.casefold(), *candidate.hints}
            if hit:
                target = candidate
                break
        if target is None:
            columns.append({"header": header, "action": KEEP, "to": "", "separator": ""})
            continue
        taken.add(target.column)
        columns.append({
            "header": header, "action": MAP, "to": target.column, "separator": LIST_SEPARATOR if target.list_separator else "",
        })
    has_id = ID_COLUMN in taken
    return {"columns": columns, "id_prefix": "" if has_id or role.merge else role.id_prefix}


@dataclass(frozen=True)
class ColumnDraft:
    header: str
    action: str
    to: str
    separator: str

    @property
    def output(self) -> str:
        return self.to if self.action == MAP else self.header


@dataclass(frozen=True)
class SourceDraft:
    kind: str
    name: str
    header_row: int | None
    role: Role | None
    field: str
    id_prefix: str
    columns: tuple[ColumnDraft, ...]
    extra: Mapping[str, Any]
    raw: Mapping[str, Any] | None = None

    @property
    def where(self) -> str:
        return f"{self.kind} {self.name!r}"


def _text(value: object, where: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise BadRequest(f"{where} must be text")
    return value.strip()


def _parse_column(item: object, where: str) -> ColumnDraft:
    if not isinstance(item, Mapping):
        raise BadRequest(f"{where} must be an object")
    action = _text(item.get("action", KEEP), f"{where}.action")
    if action not in (KEEP, MAP, EXCLUDE):
        raise BadRequest(f"{where}.action must be keep, map or exclude")
    return ColumnDraft(
        _text(item.get("header"), f"{where}.header"), action, _text(item.get("to"), f"{where}.to"),
        _text(item.get("separator"), f"{where}.separator"),
    )


def _parse_source(item: object, index: int) -> SourceDraft:
    where = f"sources[{index}]"
    if not isinstance(item, Mapping):
        raise BadRequest(f"{where} must be an object")
    kind = _text(item.get("kind"), f"{where}.kind")
    if kind not in ("table", "sheet"):
        raise BadRequest(f"{where}.kind must be table or sheet")
    name = _text(item.get("name"), f"{where}.name")
    if not name:
        raise BadRequest(f"{where}.name is required")
    if isinstance(item.get("raw"), Mapping):
        return SourceDraft(kind, name, None, None, "", "", (), {}, item["raw"])
    row = item.get("header_row")
    header_row = None if row in (None, "") else row
    if header_row is not None and (isinstance(header_row, bool) or not isinstance(header_row, int)):
        try:
            header_row = int(str(header_row))
        except ValueError:
            raise BadRequest(f"{where}.header_row must be a number") from None
    role_id = _text(item.get("role"), f"{where}.role")
    columns = item.get("columns", [])
    extra = item.get("extra", {})
    if not isinstance(columns, list) or not isinstance(extra, Mapping):
        raise BadRequest(f"{where} has columns or extra of the wrong shape")
    return SourceDraft(
        kind, name, header_row, role_named(role_id) if role_id else None, _text(item.get("field"), f"{where}.field"),
        _text(item.get("id_prefix"), f"{where}.id_prefix"),
        tuple(_parse_column(column, f"{where}.columns[{i}]") for i, column in enumerate(columns)), extra,
    )


def build_source(draft: SourceDraft, id_column: str) -> dict[str, Any]:
    if draft.raw is not None:
        return dict(draft.raw)
    assert draft.role is not None
    role = draft.role
    source: dict[str, Any] = {draft.kind: draft.name}
    if draft.kind == "sheet" and draft.header_row is not None:
        source["header_row"] = draft.header_row
    if role.type:
        source["type"] = role.type
    if role.merge:
        source["merge"] = True
        if not any(c.action == MAP and c.to == ID_COLUMN for c in draft.columns):
            raise GuiError(f"{draft.where}: choose which column holds the requirement ID, so each row finds its requirement")
    empty = [c.header for c in draft.columns if c.action == MAP and not c.to]
    if empty:
        raise GuiError(f"{draft.where}: choose where {empty[0]!r} goes, keep it as it is, or leave it out")
    columns = {
        c.header: out for c in draft.columns
        if c.action == MAP and (out := id_column if c.to == ID_COLUMN else c.to) != c.header
    }
    outputs = [c.output for c in draft.columns if c.action != EXCLUDE]
    for output, count in Counter(outputs).items():
        if count > 1:
            raise GuiError(f"{draft.where}: more than one column goes to {output!r}")
    if columns:
        source["columns"] = columns
    exclude = [c.header for c in draft.columns if c.action == EXCLUDE]
    if exclude:
        source["exclude"] = exclude
    lists = {
        (id_column if c.output == ID_COLUMN else c.output): c.separator
        for c in draft.columns if c.action != EXCLUDE and c.separator
    }
    if lists:
        source["lists"] = lists
    constants = dict(draft.extra.get("set", {}))
    if role.needs_field and FIELD_COLUMN not in outputs:
        if not draft.field:
            raise GuiError(f"{draft.where}: say which column these values are for, or map a column to {FIELD_COLUMN!r}")
        constants[FIELD_COLUMN] = draft.field
    if constants:
        source["set"] = constants
    if draft.id_prefix and not role.merge:
        source["id_prefix"] = draft.id_prefix
    return {**source, **{k: v for k, v in draft.extra.items() if k not in source and k != "set"}}


def build_mapping(form: Mapping[str, Any]) -> dict[str, Any]:
    """The JSON configuration a form describes, validated the way the importer validates it."""
    if not isinstance(form, Mapping) or not isinstance(form.get("sources"), list):
        raise BadRequest("expected {sources: [...]}")
    id_column = _text(form.get("id_column"), "id_column") or ID_COLUMN
    extra = form.get("extra", {})
    xlsx_extra = form.get("xlsx_extra", {})
    if not isinstance(extra, Mapping) or not isinstance(xlsx_extra, Mapping):
        raise BadRequest("extra must be an object")
    drafts = [_parse_source(item, i) for i, item in enumerate(form["sources"])]
    chosen = [d for d in drafts if d.raw is not None or d.role is not None]
    if not chosen:
        raise GuiError("Choose at least one table or sheet to import, and say what it holds.")
    sources = [build_source(draft, id_column) for draft in chosen]
    mapping = {
        "id_column": id_column, "traceability": True, **{k: v for k, v in extra.items() if k not in ("id_column", "traceability", "xlsx")},
        "xlsx": {**{k: v for k, v in xlsx_extra.items() if k != "sources"}, "sources": sources},
    }
    try:
        validate_xlsx_sources(sources)
    except ConfigError as exc:
        raise GuiError(str(exc)) from exc
    return mapping


def form_from_mapping(mapping: object) -> tuple[dict[str, Any], list[str]]:
    """Best effort inverse of build_mapping. Anything the form cannot show is kept untouched and listed in the notes."""
    if not isinstance(mapping, Mapping):
        raise GuiError("That file is not a reqtable settings file: its top level must be a JSON object.")
    xlsx = mapping.get("xlsx")
    sources = xlsx.get("sources") if isinstance(xlsx, Mapping) else None
    if not isinstance(sources, list) or not sources:
        raise GuiError("That settings file has no xlsx.sources, so there is no workbook mapping to edit.")
    notes: list[str] = []
    extra = {k: v for k, v in mapping.items() if k not in ("id_column", "traceability", "xlsx")}
    xlsx_extra = {k: v for k, v in xlsx.items() if k != "sources"}  # type: ignore[union-attr]
    for key in extra:
        notes.append(f"Kept as it is, not editable here: {key}")
    for key in xlsx_extra:
        notes.append(f"Kept as it is, not editable here: xlsx.{key}")
    if mapping.get("traceability") is False:
        notes.append("The file turns traceability off. Sources with a record type need it, so it is switched on.")
    id_column = mapping.get("id_column") or ID_COLUMN
    form_sources = [_source_form(source, index, notes, id_column) for index, source in enumerate(sources)]
    return {
        "id_column": mapping.get("id_column") or ID_COLUMN, "sources": form_sources, "extra": extra, "xlsx_extra": xlsx_extra,
    }, notes


def _source_form(source: object, index: int, notes: list[str], id_column: str) -> dict[str, Any]:
    if not isinstance(source, Mapping) or ("table" in source) == ("sheet" in source):
        raise GuiError(f"xlsx.sources[{index}] needs exactly one of 'table' or 'sheet'.")
    kind = "table" if "table" in source else "sheet"
    name = str(source[kind])
    constants = dict(source.get("set", {})) if isinstance(source.get("set"), Mapping) else {}
    type_name = source.get("type") or constants.get("Type")
    role = role_for_type(type_name) if type_name != "Requirement" else ROLES_BY_ID["requirements"]
    if source.get("merge") is True:
        role = ROLES_BY_ID["merge"] if not type_name else None
    if role is None or ("type" in source and "Type" in constants):
        notes.append(f"{kind.capitalize()} {name!r} has a record type this form cannot edit, so it is kept exactly as it is.")
        return {"kind": kind, "name": name, "raw": dict(source)}
    handled = {kind, "header_row", "columns", "exclude", "lists", "id_prefix", "set", "type", "merge"}
    extra = {k: v for k, v in source.items() if k not in handled}
    if type_name == "Requirement":
        extra["type"] = "Requirement"
    constants.pop("Type", None)
    field = constants.pop(FIELD_COLUMN, "") if role.needs_field else ""
    if constants:
        extra["set"] = {**extra.get("set", {}), **constants}
    for key in extra:
        notes.append(f"{kind.capitalize()} {name!r}: kept as it is, not editable here: {key}")
    columns: dict[str, dict[str, Any]] = {}
    for header, to in (source.get("columns") or {}).items():
        columns[header] = {"header": header, "action": MAP, "to": ID_COLUMN if to == id_column else to, "separator": ""}
    for header in source.get("exclude") or []:
        columns[header] = {"header": header, "action": EXCLUDE, "to": "", "separator": ""}
    for output, separator in ((ID_COLUMN if k == id_column else k, v) for k, v in (source.get("lists") or {}).items()):
        match = next((c for c in columns.values() if c["action"] == MAP and c["to"] == output), None) or columns.setdefault(
            output, {"header": output, "action": KEEP, "to": "", "separator": ""}
        )
        match["separator"] = separator
    if role.needs_field and not field and FIELD_COLUMN not in {c["to"] if c["action"] == MAP else c["header"] for c in columns.values()}:
        columns[FIELD_COLUMN] = {"header": FIELD_COLUMN, "action": KEEP, "to": "", "separator": ""}
    return {
        "kind": kind, "name": name, "header_row": source.get("header_row"), "role": role.id, "field": field,
        "id_prefix": source.get("id_prefix", ""), "columns": list(columns.values()), "extra": extra,
    }


def preview_mapping(workbook: Path, mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Run the importer on the draft: rows per source, record types and warnings, or the error the CLI would give."""
    sources = mapping["xlsx"]["sources"]
    id_column = mapping["id_column"]
    try:
        imported = import_workbook(workbook, XlsxSelection(), sources, id_column, True, False)
        counts = []
        for source in sources:
            name = source.get("table") or source["sheet"]
            if source.get("merge"):
                counts.append({"name": name, "rows": None})
                continue
            alone = import_workbook(workbook, XlsxSelection(), [source], id_column, True, False)
            counts.append({"name": name, "rows": len(alone.block.rows) - 1})
    except (ReqtableError, OSError) as exc:
        return {"error": str(exc)}
    rows = imported.block.rows
    type_at = rows[0].index("Type") if "Type" in rows[0] else None
    types = Counter((row[type_at].strip() if type_at is not None else "") or "Requirement" for row in rows[1:])
    return {"sources": counts, "types": dict(types), "total": len(rows) - 1, "warnings": list(imported.warnings)}


def save_mapping(workdir: Path, path: str, mapping: Mapping[str, Any], overwrite: bool) -> dict[str, Any]:
    if not path.strip():
        raise GuiError("Choose where to save the mapping.")
    target = workdir / path
    if target.suffix.lower() != ".json":
        raise GuiError("The mapping file name must end in .json.")
    if target.exists() and not overwrite:
        return {"exists": True, "path": str(target)}
    atomic_write_text(str(target), json.dumps(mapping, indent=2) + "\n")
    return {"saved": str(target)}


def load_mapping(workdir: Path, path: str) -> dict[str, Any]:
    if not path.strip():
        raise GuiError("Choose a mapping file to load.")
    try:
        mapping = json.loads((workdir / path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise GuiError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    except ValueError as exc:
        raise GuiError(f"{path} is not valid JSON: {exc}") from exc
    form, notes = form_from_mapping(mapping)
    return {"form": form, "notes": notes}

