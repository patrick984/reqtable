from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

HASH_FORMAT = "reqtable-baseline/1"


@dataclass(frozen=True)
class Gate:
    id: str
    name: str
    produces: str
    scope: str
    includes: tuple[str, ...]
    captures_status: bool

    @classmethod
    def from_config(cls, gate: dict[str, Any]) -> Gate:
        return cls(
            id=gate["id"],
            name=gate.get("name", gate["id"]),
            produces=gate.get("produces", ""),
            scope=gate.get("scope", "table"),
            includes=tuple(gate.get("includes", ("Requirement", "System"))),
            captures_status=gate.get("captures_status", False),
        )


def _links(cell: str) -> list[str]:
    return [part.strip() for part in cell.split(";") if part.strip()]


def _record_type(row: dict[str, str]) -> str:
    return row.get("Type", "").strip() or "Requirement"


def _subtree(rows: Sequence[dict[str, str]], id_column: str, system: str) -> set[str]:
    children: dict[str, list[str]] = {}
    for row in rows:
        if _record_type(row) == "System":
            for parent in _links(row.get("Part of", "")):
                children.setdefault(parent, []).append(row[id_column].strip())
    found, pending = {system}, [system]
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def select_scope(
    rows: Sequence[dict[str, str]], id_column: str, system: str | None, includes: Iterable[str]
) -> list[dict[str, str]]:
    wanted = set(includes)
    included = [row for row in rows if _record_type(row) in wanted]
    if system is None:
        return included
    subtree = _subtree(rows, id_column, system)
    requirements = [
        row for row in included
        if _record_type(row) == "Requirement" and subtree.intersection(_links(row.get("Allocated to", "")))
    ]
    tests = {test for row in requirements for test in _links(row.get("Verified by", ""))}
    chosen_tests = [row for row in included if _record_type(row) == "Test" and row[id_column].strip() in tests]
    plans = {plan for row in chosen_tests for plan in _links(row.get("Test plan", ""))}
    kept = {id(row) for row in requirements + chosen_tests}

    def keep(row: dict[str, str]) -> bool:
        kind = _record_type(row)
        if kind == "System":
            return row[id_column].strip() in subtree
        if kind == "Test plan":
            return row[id_column].strip() in plans
        if kind in {"Requirement", "Test"}:
            return id(row) in kept
        return True

    return [row for row in included if keep(row)]


def content_hash(
    headers: Sequence[str],
    rows_in_scope: Iterable[dict[str, str]],
    system: str | None,
    includes: Iterable[str],
    captures_status: bool,
    status_columns: Iterable[str],
) -> str:
    skipped = set() if captures_status else set(status_columns)
    hashed = [header for header in headers if header not in skipped]
    payload = [
        HASH_FORMAT,
        {"system": system or None, "includes": sorted(includes), "status": captures_status},
        hashed,
        [[row.get(header, "").replace("\r\n", "\n").replace("\r", "\n") for header in hashed] for row in rows_in_scope],
    ]
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
