from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Sequence

from .baselines import links, record_type, select_scope
from .core import RECORD_TYPES, ConfigError, validate_enforcement
from .findings import trace_findings

Finding = tuple["str | None", str, str]

MAX_LISTED = 10
CHANGE_FINDING = re.compile(
    r"(?:Changed|Added|Removed) since .+ without an approved change request\."
)


@dataclass
class Table:
    rows: list[dict[str, str]]
    all_rows: list[dict[str, str]]
    id_column: str
    findings: Sequence[Finding]

    def rid(self, row: dict[str, str]) -> str:
        return row[self.id_column].strip()

    @cached_property
    def record_ids(self) -> set[str]:
        return {self.rid(row) for row in self.all_rows}

    @cached_property
    def leaf_systems(self) -> set[str]:
        systems = [row for row in self.all_rows if record_type(row) == "System"]
        parents = {
            parent for row in systems for parent in links(row.get("Part of", ""))
        }
        return {self.rid(row) for row in systems} - parents


@dataclass(frozen=True)
class Outcome:
    failing: list[str]
    total: int
    global_messages: list[str]


@dataclass(frozen=True)
class Condition:
    """One entry of the check vocabulary: its config rules, the columns it reads, and its per-record test."""

    key: str
    validate: Callable[[Any, str], None]
    columns: Callable[[Any], list[str]]
    passes: Callable[[Any, dict[str, Any], dict[str, str], Table], bool]


def _validate_column(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: must name a column")


def _validate_in(value: Any, where: str) -> None:
    ok = isinstance(value, dict) and len(value) == 1
    if ok:
        ((column, allowed),) = value.items()
        ok = (
            bool(column.strip())
            and isinstance(allowed, list)
            and bool(allowed)
            and all(isinstance(item, str) and item.strip() for item in allowed)
        )
    if not ok:
        raise ConfigError(
            f"{where}: must be an object with one column and a non-empty array of allowed values"
        )


def _validate_true(value: Any, where: str) -> None:
    if value is not True:
        raise ConfigError(f"{where}: must be true")


def _filled(
    column: str, check: dict[str, Any], row: dict[str, str], table: Table
) -> bool:
    return bool(row.get(column, "").strip())


def _in(
    value: dict[str, list[str]],
    check: dict[str, Any],
    row: dict[str, str],
    table: Table,
) -> bool:
    ((column, allowed),) = value.items()
    cell = links(row.get(column, ""))
    return bool(cell) and all(part in allowed for part in cell)


def _linked(
    column: str, check: dict[str, Any], row: dict[str, str], table: Table
) -> bool:
    valid = table.leaf_systems if check.get("leaf") else table.record_ids
    return any(target in valid for target in links(row.get(column, "")))


CONDITIONS: dict[str, Condition] = {
    condition.key: condition
    for condition in (
        Condition("filled", _validate_column, lambda v: [v], _filled),
        Condition("in", _validate_in, lambda v: list(v), _in),
        Condition("linked", _validate_column, lambda v: [v], _linked),
        Condition(
            "no_findings", _validate_true, lambda v: [], lambda v, c, row, t: True
        ),
        Condition(
            "unchanged_since", _validate_true, lambda v: [], lambda v, c, row, t: True
        ),
    )
}
WHOLE_RECORD_CONDITIONS = ("no_findings", "unchanged_since")

CHECK_KEYS = {"id", "description", "applies_to", "leaf", "enforcement", *CONDITIONS}


def _validate_applies_to(applies: Any, where: str) -> None:
    if not isinstance(applies, dict):
        raise ConfigError(f"{where}.applies_to must be an object")
    for key, value in applies.items():
        values = value if isinstance(value, list) else [value]
        if not key.strip() or not values or not all(isinstance(v, str) for v in values):
            raise ConfigError(
                f"{where}.applies_to.{key} must be a string or a non-empty array of strings"
            )
        unknown = [v for v in values if key == "type" and v not in RECORD_TYPES]
        if unknown:
            raise ConfigError(
                f"{where}.applies_to.type: unknown record type {unknown[0]!r}"
            )


def validate_checks(checks: Any, gate_where: str) -> None:
    if not isinstance(checks, list):
        raise ConfigError(f"{gate_where}.checks must be an array")
    seen: set[str] = set()
    for index, check in enumerate(checks):
        name = check.get("id") if isinstance(check, dict) else None
        where = (
            f"{gate_where}.checks[{name if isinstance(name, str) and name else index}]"
        )
        if not isinstance(check, dict):
            raise ConfigError(f"{where} must be an object")
        for key in ("id", "description"):
            if not isinstance(check.get(key), str) or not check[key].strip():
                raise ConfigError(f"{where}.{key} must be a non-empty string")
        if check["id"] in seen:
            raise ConfigError(f"{where}: duplicate check ID")
        seen.add(check["id"])
        unknown = sorted(set(check) - CHECK_KEYS)
        if unknown:
            raise ConfigError(f"unknown configuration key: {where}.{unknown[0]}")
        used = [key for key in CONDITIONS if key in check]
        if len(used) != 1:
            raise ConfigError(
                f"{where} needs exactly one condition: {', '.join(CONDITIONS)}"
            )
        if "leaf" in check and (
            used[0] != "linked" or not isinstance(check["leaf"], bool)
        ):
            raise ConfigError(
                f"{where}: 'leaf' must be true or false and applies only to 'linked'"
            )
        CONDITIONS[used[0]].validate(check[used[0]], f"{where}.{used[0]}")
        if "applies_to" in check:
            _validate_applies_to(check["applies_to"], where)
        if "enforcement" in check:
            validate_enforcement(check["enforcement"], f"{where}.enforcement")


def _applies(check: dict[str, Any], row: dict[str, str]) -> bool:
    default = (
        {}
        if any(key in check for key in WHOLE_RECORD_CONDITIONS)
        else {"type": "Requirement"}
    )
    for key, wanted in check.get("applies_to", default).items():
        allowed = wanted if isinstance(wanted, list) else [wanted]
        if (
            record_type(row) if key == "type" else row.get(key, "").strip()
        ) not in allowed:
            return False
    return True


def _no_findings(records: list[dict[str, str]], table: Table) -> Outcome:
    flagged = {finding[0] for finding in table.findings if finding[0] is not None}
    failing = [table.rid(row) for row in records if table.rid(row) in flagged]
    messages = [finding[2] for finding in table.findings if finding[0] is None]
    return Outcome(
        failing + ([""] if messages else []), len(records) + bool(messages), messages
    )


def _unchanged_since(
    records: list[dict[str, str]],
    table: Table,
    controls: dict[str, Any] | None,
    system: str | None,
    id_column: str,
) -> Outcome:
    removed = [
        record_id
        for record_id in (controls["records"] if controls else {})
        if record_id not in table.record_ids
    ]
    if system and removed:
        gone = [controls["records"][record_id]["row"] for record_id in removed]
        in_scope = {
            table.rid(row)
            for row in select_scope(
                [*table.all_rows, *gone], id_column, system, RECORD_TYPES
            )
        }
        removed = [record_id for record_id in removed if record_id in in_scope]
    counted = {*map(table.rid, records), *removed}
    changed = dict.fromkeys(
        finding[0] for finding in table.findings if CHANGE_FINDING.fullmatch(finding[2])
    )
    return Outcome(
        [record_id for record_id in changed if record_id in counted],
        len(records) + len(removed),
        [],
    )


def evaluate_check(
    check: dict[str, Any],
    rows: Sequence[dict[str, str]],
    headers: Sequence[str],
    id_column: str,
    system: str | None,
    findings: Sequence[Finding],
    controls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": check["id"],
        "description": check["description"],
        "enforcement": check.get("enforcement", "advisory"),
        "error": None,
    }
    key = next(key for key in CONDITIONS if key in check)
    condition = CONDITIONS[key]
    columns = [
        *(k for k in check.get("applies_to", {}) if k != "type"),
        *condition.columns(check[key]),
    ]
    for column in columns:
        if column not in headers:
            return {**result, "error": f"The table has no “{column}” column."}
    scoped = (
        select_scope(rows, id_column, system, RECORD_TYPES) if system else list(rows)
    )
    table = Table(scoped, list(rows), id_column, findings)
    records = [row for row in scoped if _applies(check, row)]
    if key == "no_findings":
        outcome = _no_findings(records, table)
    elif key == "unchanged_since":
        outcome = _unchanged_since(records, table, controls, system, id_column)
    else:
        failing = [
            table.rid(row)
            for row in records
            if not condition.passes(check[key], check, row, table)
        ]
        outcome = Outcome(failing, len(records), [])
    return {
        **result,
        "total": outcome.total,
        "failing": outcome.failing,
        "global": outcome.global_messages,
    }


def evaluate_gate(
    gate: dict[str, Any],
    rows: Sequence[dict[str, str]],
    headers: Sequence[str],
    id_column: str,
    system: str | None,
    findings: Sequence[Finding],
    controls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = [
        evaluate_check(check, rows, headers, id_column, system, findings, controls)
        for check in gate.get("checks", [])
    ]
    failed = [
        check for check in checks if check["error"] is not None or check["failing"]
    ]
    blocking = [check["id"] for check in failed if check["enforcement"] == "strict"]
    return {
        "gate": gate["id"],
        "name": gate.get("name", gate["id"]),
        "system": system,
        "ready": not failed,
        "blocking": blocking,
        "blocked": bool(blocking),
        "checks": checks,
    }


def table_findings(
    rows: Sequence[dict[str, str]],
    headers: Sequence[str],
    id_column: str,
    controls: dict[str, Any] | None = None,
) -> list[Finding]:
    return [
        (f.id, f.field, f.message)
        for f in trace_findings(list(rows), list(headers), id_column, controls)
    ]


def format_result(result: dict[str, Any]) -> list[str]:
    scope = f" for {result['system']}" if result["system"] else ""
    blocked = ", blocked" if result["blocked"] else ""
    lines = [
        f"{result['gate']} {result['name']}{scope}: {'ready' if result['ready'] else 'not ready'}{blocked}"
    ]
    for check in result["checks"]:
        level = f"({check['enforcement']})"
        if check["error"]:
            lines.append(f"  ERROR {level} {check['id']}  {check['error']}")
        elif check["failing"]:
            shown = ", ".join(
                found or "(table)" for found in check["failing"][:MAX_LISTED]
            )
            more = ", …" if len(check["failing"]) > MAX_LISTED else ""
            lines.append(
                f"  FAIL {level} {check['id']}  {check['description']}: "
                f"{len(check['failing'])} of {check['total']} records: {shown}{more}"
            )
        else:
            lines.append(f"  pass {check['id']}  {check['description']}")
    return lines
