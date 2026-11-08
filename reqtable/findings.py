"""Trace findings computed in Python, kept in step with the report's JavaScript.

Each function mirrors one function of TRACE_MODEL_JS, VALUE_MODEL_JS or GLOSSARY_MODEL_JS
so the CLI can report the same findings the report shows. tests/test_findings_parity.py
runs both implementations against the same tables.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

# String.prototype.trim strips this set, which differs from str.strip() (\x1c-\x1f, \x85, \ufeff).
_JS_WHITESPACE = (
    "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)

TRACE_FIELDS: dict[str, tuple[tuple[str, ...], tuple[str, ...], bool]] = {
    "Part of": (("System",), ("System",), True),
    "Allocated to": (("Requirement",), ("System",), False),
    "Owner": (("Requirement",), ("System",), True),
    "Derived from": (("Requirement",), ("Requirement",), False),
    "Source refs": (("Requirement", "Need", "Term"), ("Need", "Source"), False),
    "Verified by": (("Requirement",), ("Test",), False),
    "Test plan": (("Test",), ("Test plan",), True),
}
RECORD_TYPES = ("System", "Requirement", "Need", "Source", "Term", "Value", "Field", "Test", "Test plan")
VERIFICATION_STATES = {"Compliance": ("Requirement", "requirements"), "Result": ("Test", "tests")}
_YES_OR_NO = re.compile(r"(?:yes|no)", re.IGNORECASE | re.ASCII)


@dataclass(frozen=True)
class Finding:
    id: str | None
    field: str
    message: str


@dataclass(eq=False)
class Record:
    id: str
    row: dict[str, str]
    type: str
    outgoing: dict[str, list[Record]] = field(default_factory=dict)


@dataclass(eq=False)
class ValueRule:
    multiple: bool
    values: dict[str, Record] = field(default_factory=dict)
    aliases: dict[str, Record] = field(default_factory=dict)


Issue = Callable[[str | None, str, str], None]


def _trim(value: str) -> str:
    return value.strip(_JS_WHITESPACE)


def _cell(row: dict[str, str], column: str) -> str:
    value = row.get(column)
    return "" if value is None else str(value)


def trace_type(row: dict[str, str]) -> str:
    return _trim(_cell(row, "Type")) or "Requirement"


def trace_ids(value: str | None) -> list[str]:
    return [part for part in (_trim(piece) for piece in ("" if value is None else value).split(";")) if part]


def trace_target_types(field_name: str, record_type: str) -> tuple[str, ...]:
    if field_name == "Source refs" and record_type != "Requirement":
        return ("Source",)
    return TRACE_FIELDS[field_name][1]


def defined_values(rule: ValueRule, cell: str | None) -> list[str]:
    text = _trim("" if cell is None else cell)
    parts = trace_ids(text) if rule.multiple else [text] if text else []
    names = [part if part in rule.values else _trim(_cell(rule.aliases[part].row, "Name")) if part in rule.aliases else part
             for part in parts]
    return list(dict.fromkeys(names))


def verification_state(values: dict[str, ValueRule], column: str, cell: str | None) -> str:
    text = _trim("" if cell is None else cell)
    rule = values.get(column)
    if not rule:
        return text
    found = defined_values(rule, text)
    return found[0] if found else ""


def check_verification(records: dict[str, Record], values: dict[str, ValueRule], issue: Issue) -> None:
    def sentence(parts: list[str]) -> str:
        return f"{', '.join(parts[:-1])} and {parts[-1]}" if len(parts) > 1 else parts[0]

    for record in records.values():
        for column, (applies_to, plural) in VERIFICATION_STATES.items():
            if record.type != applies_to and _trim(_cell(record.row, column)):
                issue(record.id, column, f"{column} applies to {plural}.")
        if record.type != "Requirement" or verification_state(values, "Compliance", record.row.get("Compliance")) != "Compliant":
            continue
        results = [(test.id, verification_state(values, "Result", test.row.get("Result")))
                   for test in record.outgoing.get("Verified by", [])]
        unmet = [(test_id, result) for test_id, result in results if result != "Passed"]
        if unmet:
            described = [f"{test_id} is “{result}”" if result else f"{test_id} has no result" for test_id, result in unmet]
            issue(record.id, "Compliance", f"Compliant, but {sentence(described)}.")


def check_test_coverage(records: dict[str, Record], values: dict[str, ValueRule], issue: Issue) -> None:
    def quote(names: Iterable[str]) -> str:
        return ", ".join(f"“{name}”" for name in names)

    for record in records.values():
        tests = record.outgoing.get("Verified by", [])
        if not tests:
            continue
        for field_name, rule in values.items():
            planned = defined_values(rule, record.row.get(field_name))
            covered = list(dict.fromkeys(name for test in tests for name in defined_values(rule, test.row.get(field_name))))
            missing = [name for name in planned if name not in covered]
            if covered and missing:
                issue(record.id, field_name, f"No test in Verified by covers {quote(missing)}. Its tests have {quote(covered)}.")


def build_glossary(records: Iterable[Record], issue: Issue) -> None:
    names: dict[str, list[Record]] = {}
    spellings: dict[str, dict[str, tuple[Record, str]]] = {}
    for record in records:
        if record.type != "Term":
            continue
        name, definition = _trim(_cell(record.row, "Name")), _trim(_cell(record.row, "Definition"))
        if not name:
            issue(record.id, "Name", "Enter a glossary term name.")
        if not definition:
            issue(record.id, "Definition", "Enter a glossary definition.")
        if name:
            names.setdefault(name.lower(), []).append(record)
        for spelling, field_name in [(name, "Name"), *((alias, "Aliases") for alias in trace_ids(record.row.get("Aliases")))]:
            if spelling:
                spellings.setdefault(spelling, {}).setdefault(record.id, (record, field_name))
    ambiguous_names = set()
    for group in names.values():
        if len(group) < 2:
            continue
        for record in group:
            issue(record.id, "Name", "Another glossary record uses this term name.")
            ambiguous_names.add(_trim(_cell(record.row, "Name")))
    for spelling, entries in spellings.items():
        if len(entries) < 2:
            continue
        for record, field_name in entries.values():
            if field_name != "Name" or spelling not in ambiguous_names:
                issue(record.id, field_name, f"Glossary spelling “{spelling}” is shared by multiple terms.")


def value_column_problem(name: str, headers: set[str], reserved: set[str]) -> str | None:
    if not name:
        return None
    if name in reserved:
        return f"“{name}” is a reserved column and cannot have defined values."
    if name not in headers:
        return f"There is no “{name}” column."
    return None


def value_groups(records: Iterable[Record], key: Callable[[Record], str]) -> dict[str, list[Record]]:
    groups: dict[str, list[Record]] = {}
    for record in records:
        name = key(record)
        if name:
            groups.setdefault(name, []).append(record)
    return groups


def build_value_rules(records: Iterable[Record], headers: list[str], id_column: str, issue: Issue) -> dict[str, ValueRule]:
    header_set, reserved = set(headers), {*TRACE_FIELDS, "Type", "Field", "Multiple", id_column}
    rules: dict[str, ValueRule] = {}
    every = list(records)
    field_records = [record for record in every if record.type == "Field"]

    def column(record: Record) -> str:
        return _trim(_cell(record.row, "Field"))

    def target(record: Record) -> str:
        return _trim(_cell(record.row, "Name"))

    for name, group in value_groups(field_records, target).items():
        problem = value_column_problem(name, header_set, reserved)
        if problem:
            for record in group:
                issue(record.id, "Name", problem)
            continue
        if len(group) > 1:
            for record in group:
                issue(record.id, "Name", f"Another Field record describes {name}.")
        rules[name] = ValueRule(multiple=_trim(_cell(group[0].row, "Multiple")).lower() == "yes")
    for record in field_records:
        multiple = _trim(_cell(record.row, "Multiple"))
        if not target(record):
            issue(record.id, "Name", "Enter the column this record describes.")
        if not _trim(_cell(record.row, "Definition")):
            issue(record.id, "Definition", "Describe this column.")
        if multiple and not _YES_OR_NO.fullmatch(multiple):
            issue(record.id, "Multiple", "Enter Yes or No.")
    value_records = [record for record in every if record.type == "Value"]
    for record in value_records:
        name, field_name = target(record), column(record)
        if not field_name:
            issue(record.id, "Field", "Enter the column this value belongs to.")
        else:
            problem = value_column_problem(field_name, header_set, reserved)
            if problem:
                issue(record.id, "Field", problem)
        if not name:
            issue(record.id, "Name", "Enter the allowed value.")
        if not _trim(_cell(record.row, "Definition")):
            issue(record.id, "Definition", "Explain what this value means.")
    for field_name, group in value_groups(value_records, column).items():
        if value_column_problem(field_name, header_set, reserved):
            continue
        rule = rules.setdefault(field_name, ValueRule(multiple=False))
        claims: dict[str, Record] = {}
        for record in group:
            name = target(record)
            if not name:
                continue
            owner = claims.get(name.lower())
            if owner and owner is not record:
                issue(record.id, "Name", f"Another {field_name} value is named “{name}”.")
                continue
            claims[name.lower()] = record
            rule.values[name] = record
        for record in group:
            if not target(record):
                continue
            for alias in trace_ids(record.row.get("Aliases")):
                owner = claims.get(alias.lower())
                if owner and owner is not record:
                    issue(record.id, "Aliases", f"“{alias}” is already a {field_name} value name or alias.")
                    continue
                if not owner:
                    claims[alias.lower()] = record
                    rule.aliases[alias] = record
    rules = {name: rule for name, rule in rules.items() if rule.values}
    for record in every:
        if record.type in ("Value", "Field"):
            continue
        for field_name, rule in rules.items():
            cell = _trim(_cell(record.row, field_name))
            if not cell:
                continue
            seen = set()
            for part in trace_ids(cell) if rule.multiple else [cell]:
                key = part.lower()
                if key in seen:
                    issue(record.id, field_name, f"“{part}” is listed more than once.")
                seen.add(key)
                if part in rule.values:
                    continue
                replaced = rule.aliases.get(part) or next(
                    (owner for alias, owner in rule.aliases.items() if alias.lower() == key), None)
                canonical = replaced or next((value for value in rule.values.values() if target(value).lower() == key), None)
                if canonical:
                    spelling = "a replaced spelling" if replaced else "spelled differently from the defined value"
                    issue(record.id, field_name, f"“{part}” is {spelling}; use “{target(canonical)}”.")
                else:
                    one = f" {field_name} allows one value." if not rule.multiple and ";" in part else ""
                    issue(record.id, field_name, f"“{part}” is not a defined {field_name} value.{one}")
    return rules


def link_records(records: dict[str, Record], issue: Issue) -> list[Record]:
    systems = []
    for record in records.values():
        record_id, row, record_type = record.id, record.row, record.type
        if ";" in record_id:
            issue(record_id, "ID", "A traceable ID cannot contain a semicolon.")
        if record_type == "System":
            systems.append(record)
        if record_type not in RECORD_TYPES:
            issue(record_id, "Type", f"Unknown record type “{record_type}”.")
        if record_type == "Requirement" and _trim(_cell(row, "Origin")) == "Self-derived" and not _trim(_cell(row, "Rationale")):
            issue(record_id, "Rationale", "Explain why this self-derived requirement is needed.")
        for field_name, (sources, _, single) in TRACE_FIELDS.items():
            ids = trace_ids(row.get(field_name))
            if not ids:
                continue
            if record_type not in sources:
                issue(record_id, field_name, f"{field_name} does not apply to {record_type} records.")
                continue
            if single and len(ids) > 1:
                issue(record_id, field_name, "Select at most one target.")
            seen, targets = set(), []
            for target_id in ids:
                if target_id in seen:
                    issue(record_id, field_name, f"Duplicate reference to {target_id}.")
                    continue
                seen.add(target_id)
                target = records.get(target_id)
                expected = trace_target_types(field_name, record_type)
                if target_id == record_id:
                    issue(record_id, field_name, "A record cannot link to itself.")
                elif not target:
                    issue(record_id, field_name, f"Target {target_id} is missing.")
                elif target.type not in expected:
                    issue(record_id, field_name, f"Target {target_id} has type {target.type}. Expected {' or '.join(expected)}.")
                else:
                    targets.append(target)
            record.outgoing[field_name] = targets
    return systems


def find_cycles(records: dict[str, Record], field_name: str, issue: Issue) -> None:
    done: set[str] = set()
    active: set[str] = set()
    for start in records.values():
        if start.id in done:
            continue
        stack = [(start, iter(start.outgoing.get(field_name, [])))]
        active.add(start.id)
        while stack:
            record, targets = stack[-1]
            target = next(targets, None)
            if target is None:
                active.discard(record.id)
                done.add(record.id)
                stack.pop()
            elif target.id in active:
                cycle = [item.id for item, _ in stack[next(i for i, (item, _) in enumerate(stack) if item is target):]]
                issue(record.id, field_name, f"Cycle: {' → '.join([*cycle, target.id])}.")
            elif target.id not in done:
                active.add(target.id)
                stack.append((target, iter(target.outgoing.get(field_name, []))))


def trace_findings(rows: list[dict[str, str]], headers: list[str], id_column: str) -> list[Finding]:
    """Return the findings buildTraceIndex reports for these rows, in the same order."""
    findings: list[Finding] = []

    def issue(record_id: str | None, field_name: str, message: str) -> None:
        findings.append(Finding(record_id, field_name, message))

    records: dict[str, Record] = {}
    for row in rows:
        record_id = _trim(_cell(row, id_column))
        records[record_id] = Record(record_id, row, trace_type(row))
    systems = link_records(records, issue)
    roots = [system for system in systems if not trace_ids(system.row.get("Part of"))]
    if len(roots) != 1:
        issue(None, "Part of", f"Expected one top-level system. Found {len(roots)}.")
    for field_name in ("Part of", "Derived from"):
        find_cycles(records, field_name, issue)
    build_glossary(records.values(), issue)
    values = build_value_rules(records.values(), headers, id_column, issue)
    check_test_coverage(records, values, issue)
    check_verification(records, values, issue)
    return findings
