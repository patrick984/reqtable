from __future__ import annotations

import csv
import difflib
import html
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .markdown import render_markdown
from .traceability import TRACE_COLUMNS


class ReqtableError(Exception):
    """Base class for actionable application errors."""


class ConfigError(ReqtableError):
    pass


class InputError(ReqtableError):
    pass


class OutputError(ReqtableError):
    pass


RECORD_TYPES = ("System", "Requirement", "Need", "Source", "Term", "Value", "Field", "Test", "Test plan")


def _preset_gate(id: str, name: str, produces: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": id, "name": name, "produces": produces, "scope": "table",
        "includes": ["Requirement", "System"], "captures_status": False, **extra,
    }


PRESET_GATES = [
    _preset_gate("SRR", "System Requirements Review", "Functional baseline"),
    _preset_gate("SFR", "System Functional Review", "Functional baseline"),
    _preset_gate("PDR", "Preliminary Design Review", "Allocated baseline"),
    _preset_gate("DDR", "Detailed Design Review", "Subsystem design baseline", scope="system"),
    _preset_gate("CDR", "Critical Design Review", "Product baseline"),
    _preset_gate(
        "TRR", "Test Readiness Review", "Test baseline",
        includes=["Requirement", "System", "Test", "Test plan"],
    ),
    _preset_gate("SVR", "System Verification Review", "Verified baseline", captures_status=True),
    _preset_gate("FCA", "Functional Configuration Audit", "Functional audit baseline", captures_status=True),
    _preset_gate("PCA", "Physical Configuration Audit", "As-built product baseline", captures_status=True),
]

DEFAULT_CONFIG: dict[str, Any] = {
    "id_column": None,
    "title": "Requirements",
    "document_mode": "review",
    "traceability": False,
    "csv": {"encoding": "utf-8-sig", "delimiter": ",", "strict_columns": True},
    "columns": {"hidden": [], "order": [], "labels": {}, "widths": {}, "markdown": None},
    "diff": {
        "initial_view": "unified",
        "initial_changes_only": False,
        "include_unchanged": True,
        "ignore_columns": [],
        "ignore_trailing_whitespace": False,
    },
    "comments": {
        "enabled": True,
        "reviewer_initials": None,
        "csv_column": "Comments",
        "csv_format": "json",
    },
    "quality": {"requirement_column": None, "required_columns": [], "obligation": "shall"},
    "xlsx": {"sources": []},
    "baselines": {
        "store": "git",
        "git": {"tag_prefix": "baseline/"},
        "files": {"directory": "baselines"},
        "enforcement": "advisory",
        "status_columns": ["Compliance", "Result"],
    },
    "gates": PRESET_GATES,
}


@dataclass(frozen=True)
class CsvSource:
    """A CSV to read: a file on disk (text is None) or already-read text with a display label."""

    label: str
    text: str | None
    path: Path

    @property
    def filename(self) -> str:
        return self.path.name if self.text is None else self.label


@dataclass
class CsvTable:
    label: str
    filename: str
    headers: list[str]
    rows: list[dict[str, str]]
    ids: list[str]
    by_id: dict[str, dict[str, str]]


def _merge_known(base: dict[str, Any], override: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        where = f"{prefix}.{key}" if prefix else key
        if key not in base:
            raise ConfigError(f"unknown configuration key: {where}")
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise ConfigError(f"configuration value {where} must be an object")
            result[key] = dict(value) if not base[key] else _merge_known(base[key], value, where)
        else:
            result[key] = value
    return result


def load_config(path: str | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    supplied: dict[str, Any] = {}
    if path:
        try:
            supplied = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"cannot read configuration {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON configuration {path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
        if not isinstance(supplied, dict):
            raise ConfigError("configuration root must be a JSON object")
    config = _merge_known(DEFAULT_CONFIG, supplied)
    for dotted, value in (overrides or {}).items():
        if value is None:
            continue
        parts = dotted.split(".")
        cursor = config
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor[parts[-1]] = value
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config["traceability"], bool):
        raise ConfigError("traceability must be true or false")
    if config["traceability"] and config["id_column"] in TRACE_COLUMNS:
        raise ConfigError("the ID column cannot be a reserved traceability column")
    quality = config["quality"]
    for field in ("requirement_column", "obligation"):
        value = quality[field]
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ConfigError(f"quality.{field} must be null or a non-empty string")
    if not isinstance(quality["required_columns"], list) or not all(
        isinstance(column, str) and column.strip() for column in quality["required_columns"]
    ):
        raise ConfigError("quality.required_columns must be an array of non-empty column names")
    if config["id_column"] is not None and not isinstance(config["id_column"], str):
        raise ConfigError("id_column must be null or a string")
    if not isinstance(config["title"], str):
        raise ConfigError("title must be a string")
    if config["document_mode"] not in {"review", "develop"}:
        raise ConfigError("document_mode must be 'review' or 'develop'")
    if not isinstance(config["csv"]["encoding"], str) or not config["csv"]["encoding"]:
        raise ConfigError("csv.encoding must be a non-empty string")
    delimiter = config["csv"]["delimiter"]
    if not isinstance(delimiter, str) or len(delimiter) != 1 or ord(delimiter) < 32 or ord(delimiter) == 127:
        raise ConfigError("csv.delimiter must be one printable character")
    if not isinstance(config["csv"]["strict_columns"], bool):
        raise ConfigError("csv.strict_columns must be true or false")
    for field in ("hidden", "order"):
        value = config["columns"][field]
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ConfigError(f"columns.{field} must be an array of strings")
    markdown = config["columns"]["markdown"]
    if markdown is not None and (not isinstance(markdown, list) or not all(isinstance(x, str) for x in markdown)):
        raise ConfigError("columns.markdown must be null or an array of strings")
    for field in ("labels", "widths"):
        value = config["columns"][field]
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise ConfigError(f"columns.{field} must be an object of string values")
    width_pattern = re.compile(r"^(?:[1-9]\d*(?:\.\d+)?)(?:px|rem|em|ch|%)$")
    for column, width in config["columns"]["widths"].items():
        if not width_pattern.fullmatch(width):
            raise ConfigError(f"unsafe or invalid width for column {column!r}: {width!r}")
    if config["diff"]["initial_view"] not in {"unified", "side-by-side"}:
        raise ConfigError("diff.initial_view must be 'unified' or 'side-by-side'")
    for field in ("initial_changes_only", "include_unchanged", "ignore_trailing_whitespace"):
        if not isinstance(config["diff"][field], bool):
            raise ConfigError(f"diff.{field} must be true or false")
    ignored = config["diff"]["ignore_columns"]
    if not isinstance(ignored, list) or not all(isinstance(x, str) for x in ignored):
        raise ConfigError("diff.ignore_columns must be an array of strings")
    if config["comments"]["csv_format"] not in {"json", "text"}:
        raise ConfigError("comments.csv_format must be 'json' or 'text'")
    if not isinstance(config["comments"]["enabled"], bool):
        raise ConfigError("comments.enabled must be true or false")
    if not isinstance(config["comments"]["csv_column"], str) or not config["comments"]["csv_column"]:
        raise ConfigError("comments.csv_column must be a non-empty string")
    initials = config["comments"]["reviewer_initials"]
    if initials is not None and not valid_initials(initials):
        raise ConfigError("comments.reviewer_initials must contain 1-16 non-control characters")
    validate_xlsx_sources(config["xlsx"]["sources"])
    validate_baselines(config["baselines"])
    validate_gates(config["gates"])


def validate_baselines(baselines: dict[str, Any]) -> None:
    if baselines["store"] not in {"git", "files"}:
        raise ConfigError("baselines.store must be 'git' or 'files'")
    prefix = baselines["git"]["tag_prefix"]
    if not isinstance(prefix, str) or not prefix.endswith("/") or prefix == "/":
        raise ConfigError("baselines.git.tag_prefix must be a non-empty string that ends with '/'")
    directory = baselines["files"]["directory"]
    if not isinstance(directory, str) or not directory.strip():
        raise ConfigError("baselines.files.directory must be a non-empty string")
    if baselines["enforcement"] != "advisory":
        raise ConfigError("baselines.enforcement must be 'advisory'")
    columns = baselines["status_columns"]
    if not isinstance(columns, list) or not all(isinstance(x, str) for x in columns):
        raise ConfigError("baselines.status_columns must be an array of strings")


_GATE_KEYS = {"id", "name", "produces", "scope", "includes", "captures_status", "checks", "signoff"}


def validate_gates(gates: Any) -> None:
    if not isinstance(gates, list) or not all(isinstance(g, dict) for g in gates):
        raise ConfigError("gates must be an array of objects")
    seen: set[str] = set()
    for index, gate in enumerate(gates):
        where = f"gates[{index}]"
        unknown = sorted(set(gate) - _GATE_KEYS)
        if unknown:
            raise ConfigError(f"unknown configuration key: {where}.{unknown[0]}")
        gate_id = gate.get("id")
        if not isinstance(gate_id, str) or not gate_id.strip():
            raise ConfigError(f"{where}.id must be a non-empty string")
        where = f"gates[{index}] ({gate_id})"
        if "/" in gate_id:
            raise ConfigError(f"{where}: gate ID cannot contain '/'")
        if re.search(r"-\d+$", gate_id):
            raise ConfigError(f"{where}: gate ID cannot end in '-' and a number; numbers are reserved for re-baselines")
        if gate_id in seen:
            raise ConfigError(f"{where}: duplicate gate ID")
        seen.add(gate_id)
        for key in ("name", "produces"):
            if key in gate and not isinstance(gate[key], str):
                raise ConfigError(f"{where}.{key} must be a string")
        if gate.get("scope", "table") not in {"table", "system"}:
            raise ConfigError(f"{where}.scope must be 'table' or 'system'")
        includes = gate.get("includes", ["Requirement", "System"])
        if not isinstance(includes, list) or not includes or not all(x in RECORD_TYPES for x in includes):
            raise ConfigError(f"{where}.includes must be a non-empty array of: {', '.join(RECORD_TYPES)}")
        if not isinstance(gate.get("captures_status", False), bool):
            raise ConfigError(f"{where}.captures_status must be true or false")
        for key in ("checks", "signoff"):
            if key in gate and not isinstance(gate[key], list):
                raise ConfigError(f"{where}.{key} must be an array")


_XLSX_SOURCE_KEYS = {"table", "sheet", "header_row", "columns", "exclude", "type", "id_prefix", "set", "id_from", "lists"}


def validate_xlsx_sources(sources: Any) -> None:
    if not isinstance(sources, list) or not all(isinstance(s, dict) for s in sources):
        raise ConfigError("xlsx.sources must be an array of objects")
    for index, source in enumerate(sources):
        where = f"xlsx.sources[{index}]"
        unknown = sorted(set(source) - _XLSX_SOURCE_KEYS)
        if unknown:
            raise ConfigError(f"unknown configuration key: {where}.{unknown[0]}")
        has_table, has_sheet = "table" in source, "sheet" in source
        if has_table == has_sheet:
            raise ConfigError(f"{where} needs exactly one of 'table' or 'sheet'")
        for key in ("table", "sheet", "type", "id_prefix"):
            if key in source and (not isinstance(source[key], str) or not source[key].strip()):
                raise ConfigError(f"{where}.{key} must be a non-empty string")
        if "header_row" in source:
            row = source["header_row"]
            if not has_sheet:
                raise ConfigError(f"{where}.header_row applies only with 'sheet'")
            if isinstance(row, bool) or not isinstance(row, int) or row < 1:
                raise ConfigError(f"{where}.header_row must be a whole number of 1 or greater")
        columns = source.get("columns", {})
        if not isinstance(columns, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in columns.items()
        ):
            raise ConfigError(f"{where}.columns must be an object of source header to output header strings")
        exclude = source.get("exclude", [])
        if not isinstance(exclude, list) or not all(isinstance(x, str) for x in exclude):
            raise ConfigError(f"{where}.exclude must be an array of strings")
        constants = source.get("set", {})
        if not isinstance(constants, dict) or not all(
            isinstance(k, str) and k.strip() and isinstance(v, str) for k, v in constants.items()
        ):
            raise ConfigError(f"{where}.set must be an object of output header to constant string")
        if "type" in source and "Type" in constants:
            raise ConfigError(f"{where} gives both 'type' and set.Type; use one")
        if "id_from" in source:
            id_from = source["id_from"]
            if not isinstance(id_from, list) or not id_from or not all(isinstance(x, str) and x.strip() for x in id_from):
                raise ConfigError(f"{where}.id_from must be a non-empty array of column names")
            if "id_prefix" not in source:
                raise ConfigError(f"{where}.id_from needs id_prefix")
        lists = source.get("lists", {})
        if not isinstance(lists, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v for k, v in lists.items()
        ):
            raise ConfigError(f"{where}.lists must be an object of output header to separator string (or \"newline\")")


def valid_initials(value: Any) -> bool:
    return isinstance(value, str) and 1 <= len(value.strip()) <= 16 and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def read_csv_table(path: str, config: dict[str, Any]) -> CsvTable:
    return read_csv_source(CsvSource(str(Path(path)), None, Path(path)), config)


def read_csv_source(csv_source: CsvSource, config: dict[str, Any]) -> CsvTable:
    source = csv_source.label
    encoding = config["csv"]["encoding"]
    delimiter = config["csv"]["delimiter"]
    if csv_source.text is not None:
        handle: Any = io.StringIO(csv_source.text, newline="")
    else:
        try:
            handle = csv_source.path.open("r", encoding=encoding, newline="")
        except (OSError, LookupError) as exc:
            raise InputError(f"cannot open {source}: {exc}") from exc
    with handle:
        reader = csv.reader(handle, delimiter=delimiter, strict=True)
        try:
            headers = next(reader)
        except StopIteration as exc:
            raise InputError(f"{source}: CSV file is empty") from exc
        except csv.Error as exc:
            raise InputError(f"{source}: invalid CSV header: {exc}") from exc
        if not headers:
            raise InputError(f"{source}: CSV header is empty")
        if any(h == "" for h in headers):
            raise InputError(f"{source}: empty column name in header")
        duplicates = sorted({h for h in headers if headers.count(h) > 1})
        if duplicates:
            raise InputError(f"{source}: duplicate column name(s): {', '.join(duplicates)}")
        id_column = config.get("id_column")
        if not id_column:
            raise ConfigError("an ID column is required; use --id-column or set id_column in the config")
        if id_column not in headers:
            raise InputError(f"{source}: ID column {id_column!r} is not present")
        rows: list[dict[str, str]] = []
        ids: list[str] = []
        by_id: dict[str, dict[str, str]] = {}
        record_by_id: dict[str, int] = {}
        try:
            for record_number, values in enumerate(reader, start=2):
                if values == []:
                    continue
                if config["csv"]["strict_columns"] and len(values) != len(headers):
                    raise InputError(
                        f"{source}: record {record_number} has {len(values)} fields; expected {len(headers)}"
                    )
                if len(values) < len(headers):
                    values += [""] * (len(headers) - len(values))
                elif len(values) > len(headers):
                    values = values[: len(headers)]
                row = {header: value.replace("\r\n", "\n").replace("\r", "\n") for header, value in zip(headers, values)}
                normalized_id = row[id_column].strip()
                if not normalized_id:
                    raise InputError(f"{source}: record {record_number} has an empty ID in {id_column!r}")
                if normalized_id in by_id:
                    raise InputError(
                        f"{source}: duplicate ID {normalized_id!r} at records "
                        f"{record_by_id[normalized_id]} and {record_number}"
                    )
                rows.append(row)
                ids.append(normalized_id)
                by_id[normalized_id] = row
                record_by_id[normalized_id] = record_number
        except (csv.Error, UnicodeError) as exc:
            raise InputError(f"{source}: invalid CSV near record {reader.line_num}: {exc}") from exc
    return CsvTable(source, csv_source.filename, headers, rows, ids, by_id)


def effective_columns(old: CsvTable | None, new: CsvTable, config: dict[str, Any]) -> list[str]:
    headers = list(new.headers)
    if old:
        headers.extend(h for h in old.headers if h not in headers)
    configured = config["columns"]["order"]
    missing = [h for h in configured if h not in headers]
    if missing:
        raise ConfigError(f"configured ordered column(s) not found: {', '.join(missing)}")
    return configured + [h for h in headers if h not in configured]


def _comparison_value(value: str, config: dict[str, Any]) -> str:
    if config["diff"]["ignore_trailing_whitespace"]:
        return "\n".join(line.rstrip() for line in value.split("\n"))
    return value


def _tokens(line: str) -> list[str]:
    return re.findall(r"\s+|\w+|[^\w\s]", line, flags=re.UNICODE)


def _word_pair(old: str, new: str) -> tuple[str, str]:
    a, b = _tokens(old), _tokens(new)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    old_parts: list[str] = []
    new_parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        left = html.escape("".join(a[i1:i2]))
        right = html.escape("".join(b[j1:j2]))
        if tag == "equal":
            old_parts.append(left)
            new_parts.append(right)
        else:
            if left:
                old_parts.append(f'<span class="diff-word removed-word">{left}</span>')
            if right:
                new_parts.append(f'<span class="diff-word added-word">{right}</span>')
    return "".join(old_parts), "".join(new_parts)


def render_diff(old: str, new: str) -> dict[str, str]:
    # Do not manufacture a highlighted blank line for a genuinely empty side.
    # This is especially important for added and removed rows in unified view.
    if old == "" and new != "":
        new_html = "".join(
            f'<div class="diff-line added-line">{html.escape(line) or "&nbsp;"}</div>'
            for line in new.splitlines()
        )
        return {"oldHtml": "", "newHtml": new_html, "unifiedHtml": new_html}
    if new == "" and old != "":
        old_html = "".join(
            f'<div class="diff-line removed-line">{html.escape(line) or "&nbsp;"}</div>'
            for line in old.splitlines()
        )
        return {"oldHtml": old_html, "newHtml": "", "unifiedHtml": old_html}
    if max(len(old), len(new)) > 100_000:
        old_html = html.escape(old)
        new_html = html.escape(new)
        return {
            "oldHtml": f'<div class="diff-line removed-line">{old_html}</div>',
            "newHtml": f'<div class="diff-line added-line">{new_html}</div>',
            "unifiedHtml": (
                f'<div class="diff-line removed-line">{old_html}</div>'
                f'<div class="diff-line added-line">{new_html}</div>'
            ),
        }
    a = old.splitlines() or ([""] if old == "" else [])
    b = new.splitlines() or ([""] if new == "" else [])
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    old_out: list[str] = []
    new_out: list[str] = []
    unified: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in a[i1:i2]:
                escaped = html.escape(line) or "&nbsp;"
                block = f'<div class="diff-line context-line">{escaped}</div>'
                old_out.append(block); new_out.append(block); unified.append(block)
        elif tag == "delete":
            for line in a[i1:i2]:
                block = f'<div class="diff-line removed-line">{html.escape(line) or "&nbsp;"}</div>'
                old_out.append(block); unified.append(block)
        elif tag == "insert":
            for line in b[j1:j2]:
                block = f'<div class="diff-line added-line">{html.escape(line) or "&nbsp;"}</div>'
                new_out.append(block); unified.append(block)
        else:
            old_lines, new_lines = a[i1:i2], b[j1:j2]
            count = max(len(old_lines), len(new_lines))
            for index in range(count):
                left = old_lines[index] if index < len(old_lines) else None
                right = new_lines[index] if index < len(new_lines) else None
                if left is not None and right is not None:
                    left_html, right_html = _word_pair(left, right)
                    old_block = f'<div class="diff-line removed-line">{left_html or "&nbsp;"}</div>'
                    new_block = f'<div class="diff-line added-line">{right_html or "&nbsp;"}</div>'
                    old_out.append(old_block); new_out.append(new_block); unified.extend((old_block, new_block))
                elif left is not None:
                    block = f'<div class="diff-line removed-line">{html.escape(left) or "&nbsp;"}</div>'
                    old_out.append(block); unified.append(block)
                elif right is not None:
                    block = f'<div class="diff-line added-line">{html.escape(right) or "&nbsp;"}</div>'
                    new_out.append(block); unified.append(block)
    return {"oldHtml": "".join(old_out), "newHtml": "".join(new_out), "unifiedHtml": "".join(unified)}


def _estimated_column_width(name: str, rows: list[dict[str, Any]]) -> int:
    """Estimate a compact initial pixel width without letting outliers dominate."""
    lengths = [len(name)]
    multiline = False
    for row in rows[:1000]:
        cell = row["cells"][name]
        for value in (cell.get("old"), cell.get("new")):
            if value is None:
                continue
            text = str(value)
            multiline = multiline or "\n" in text
            lengths.extend(len(line) for line in text.splitlines() or [""])
    lengths.sort()
    percentile = lengths[min(len(lengths) - 1, int((len(lengths) - 1) * 0.90))]
    useful_chars = max(len(name) + 2, percentile)
    cap = 44 if multiline or useful_chars > 36 else 32
    return max(82, min(460, 30 + min(useful_chars, cap) * 7))


def _ordered_diff_ids(old: CsvTable, new: CsvTable) -> list[str]:
    result = list(new.ids)
    old_positions = {value: index for index, value in enumerate(old.ids)}
    removed = [value for value in old.ids if value not in new.by_id]
    for removed_id in removed:
        following = next((value for value in old.ids[old_positions[removed_id] + 1 :] if value in result), None)
        if following is None:
            result.append(removed_id)
        else:
            result.insert(result.index(following), removed_id)
    return result


def _cell(column: str, old_value: str | None, new_value: str | None, changed: bool, markdown: bool) -> dict[str, Any]:
    old_text = "" if old_value is None else old_value
    new_text = "" if new_value is None else new_value
    result: dict[str, Any] = {
        "column": column,
        "old": old_value,
        "new": new_value,
        "changed": changed,
        "search": f"{old_text}\n{new_text}".casefold(),
    }
    if changed:
        result.update(render_diff(old_text, new_text))
    else:
        display = new_text if new_value is not None else old_text
        rendered = render_markdown(display) if markdown else html.escape(display).replace("\n", "<br>")
        result.update({"oldHtml": rendered, "newHtml": rendered, "unifiedHtml": rendered})
    return result


def generation_time() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None:
        try:
            return datetime.fromtimestamp(int(epoch), timezone.utc).astimezone().isoformat(timespec="seconds")
        except (ValueError, OverflowError, OSError) as exc:
            raise ConfigError("SOURCE_DATE_EPOCH must be a valid integer timestamp") from exc
    return datetime.now().astimezone().isoformat(timespec="seconds")


def prepare_trace_table(
    table: CsvTable, config: dict[str, Any]
) -> tuple[CsvTable, list[dict[str, Any]]]:
    comments_config = config["comments"]
    comment_column = comments_config["csv_column"]
    if comments_config["enabled"] and comment_column in (*TRACE_COLUMNS, config["id_column"]):
        raise ConfigError("the comments column cannot also store traceability data")
    managed_comments = (
        comments_config["enabled"] and comments_config["csv_format"] == "json"
        and comment_column in table.headers
    )
    headers = [name for name in table.headers if not managed_comments or name != comment_column]
    headers.extend(name for name in TRACE_COLUMNS if name not in headers)
    rows = [{name: row.get(name, "") for name in headers} for row in table.rows]
    comments = []
    if managed_comments:
        for rid, row in zip(table.ids, table.rows):
            message = f"{table.label}: expected exported JSON comments in {comment_column!r} for {rid!r}"
            try:
                records = json.loads(row[comment_column] or "[]")
            except ValueError as exc:
                raise InputError(message) from exc
            if not isinstance(records, list):
                raise InputError(message)
            for record in records:
                if (
                    not isinstance(record, dict)
                    or record.get("column") not in headers
                    or record["column"] == config["id_column"]
                    or not valid_initials(record.get("initials"))
                    or not all(isinstance(record.get(key), str) for key in ("created", "text"))
                    or (record.get("modified") is not None and not isinstance(record["modified"], str))
                ):
                    raise InputError(message)
                comments.append({
                    "id": f"imported-{len(comments)}",
                    "requirementId": rid,
                    **{key: record.get(key) for key in ("column", "initials", "created", "modified", "text")},
                })
    return CsvTable(table.label, table.filename, headers, rows, table.ids, dict(zip(table.ids, rows))), comments


def build_report_data(
    new: CsvTable,
    config: dict[str, Any],
    output_name: str,
    old: CsvTable | None = None,
) -> dict[str, Any]:
    comments = []
    traceability = config["traceability"]
    if traceability:
        new, comments = prepare_trace_table(new, config)
        if old:
            old, old_comments = prepare_trace_table(old, config)
            comments.extend({**comment, "id": f"old-{comment['id']}"} for comment in old_comments
                            if comment["requirementId"] not in new.by_id)
    columns = effective_columns(old, new, config)
    quality = config["quality"]
    quality_columns = set(quality["required_columns"])
    if quality["requirement_column"] is not None:
        quality_columns.add(quality["requirement_column"])
    invalid_quality_columns = quality_columns.difference(set(new.headers) - {config["id_column"]})
    if invalid_quality_columns:
        names = ", ".join(sorted(invalid_quality_columns))
        raise ConfigError(f"quality columns must be non-ID columns in the current CSV: {names}")
    markdown_columns = config["columns"]["markdown"]
    markdown_set = set(columns if markdown_columns is None else markdown_columns)
    for name in markdown_set:
        if name not in columns:
            raise ConfigError(f"configured Markdown column not found: {name}")
    ignored = set(config["diff"]["ignore_columns"])
    unknown_ignored = ignored.difference(columns)
    if unknown_ignored:
        raise ConfigError(f"ignored diff column(s) not found: {', '.join(sorted(unknown_ignored))}")
    rows: list[dict[str, Any]] = []
    if old is None:
        ids = new.ids
    else:
        ids = _ordered_diff_ids(old, new)
    counts = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for requirement_id in ids:
        old_row = old.by_id.get(requirement_id) if old else None
        new_row = new.by_id.get(requirement_id)
        if old is None:
            status = "unchanged"
        elif old_row is None:
            status = "added"
        elif new_row is None:
            status = "removed"
        else:
            changed_columns = [
                column for column in columns
                if column not in ignored
                and _comparison_value(old_row.get(column, ""), config) != _comparison_value(new_row.get(column, ""), config)
            ]
            status = "changed" if changed_columns else "unchanged"
        counts[status] += 1
        cells: dict[str, dict[str, Any]] = {}
        for column in columns:
            old_value = old_row.get(column, "") if old_row is not None and column in old_row else None
            new_value = new_row.get(column, "") if new_row is not None and column in new_row else None
            changed = (
                old is not None
                and column not in ignored
                and _comparison_value("" if old_value is None else old_value, config)
                != _comparison_value("" if new_value is None else new_value, config)
            )
            cells[column] = _cell(column, old_value, new_value, changed, column in markdown_set)
        rows.append({"id": requirement_id, "status": status, "sourceOrder": len(rows), "cells": cells})
    if old is not None and not config["diff"]["include_unchanged"]:
        rows = [row for row in rows if row["status"] != "unchanged"]
    labels = config["columns"]["labels"]
    trace_widths = {"Name": 150, "Definition": 320, "Aliases": 140, "Rationale": 260} if traceability else {}
    column_data = [
        {
            "name": name,
            "label": labels.get(name, name),
            "hidden": name in config["columns"]["hidden"],
            "width": config["columns"]["widths"].get(name),
            "estimatedWidth": max(_estimated_column_width(name, rows), trace_widths.get(name, 0)),
            "oldOnly": bool(old and name in old.headers and name not in new.headers),
            "newOnly": bool(old and name in new.headers and name not in old.headers),
            "markdown": name in markdown_set,
        }
        for name in columns
    ]
    warnings: list[str] = []
    optional_names = set(config["columns"]["hidden"])
    optional_names.update(config["columns"]["labels"])
    optional_names.update(config["columns"]["widths"])
    unknown_optional = sorted(optional_names.difference(columns))
    if unknown_optional:
        warnings.append("configured optional column(s) not found: " + ", ".join(unknown_optional))
    if config["id_column"] in config["columns"]["hidden"]:
        warnings.append("the requirement ID column is initially hidden")
    stem = Path(output_name).stem
    stem = re.sub(r"-reviewed-[A-Za-z0-9_-]+(?:-\d{8}T\d{6})?$", "", stem)
    return {
        "format": "reqtable-report",
        "formatVersion": 1,
        "meta": {
            "title": config["title"],
            "mode": "diff" if old else "snapshot",
            "documentMode": config["document_mode"],
            "generated": generation_time(),
            "newFilename": new.filename,
            "oldFilename": old.filename if old else None,
            "baseFilename": stem,
            "idColumn": config["id_column"],
            "counts": counts,
            "ignoredColumns": sorted(ignored),
            "warnings": warnings,
        },
        "options": {
            "initialView": config["diff"]["initial_view"],
            "initialChangesOnly": config["diff"]["initial_changes_only"],
            "commentsEnabled": config["comments"]["enabled"],
            "reviewerInitials": config["comments"]["reviewer_initials"] or "",
            "includeUnchanged": config["diff"]["include_unchanged"],
            "ignoreTrailingWhitespace": config["diff"]["ignore_trailing_whitespace"],
            "commentsColumn": config["comments"]["csv_column"],
            "commentsFormat": config["comments"]["csv_format"],
            "csvDelimiter": config["csv"]["delimiter"],
            "quality": quality,
            "traceability": traceability,
        },
        "columns": column_data,
        "rows": rows,
        "source": {
            "new": {"headers": new.headers, "rows": new.rows},
            "old": {"headers": old.headers, "rows": old.rows} if old else None,
        },
        "comments": comments,
    }


def atomic_write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    destination = Path(path)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise OutputError(f"cannot write {destination}: {exc}") from exc


def comments_as_text(comments: Iterable[dict[str, Any]]) -> str:
    blocks = []
    for comment in comments:
        timestamp = comment.get("modified") or comment.get("created", "")
        blocks.append(
            f"[{timestamp}] [{comment.get('initials', '')}] [{comment.get('column', '')}]\n"
            f"{comment.get('text', '')}"
        )
    return "\n\n---\n\n".join(blocks)


def extract_report_json(report_path: str) -> dict[str, Any]:
    path = Path(report_path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"cannot read report {path}: {exc}") from exc
    match = re.search(
        r'<script\s+id="reqtable-data"\s+type="application/json">(.*?)</script>',
        source,
        flags=re.DOTALL,
    )
    if not match:
        raise InputError(f"{path}: reqtable data block was not found")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid embedded report data: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != "reqtable-report" or data.get("formatVersion") not in (1, 2):
        raise InputError(f"{path}: unsupported or invalid reqtable report format")
    if not isinstance(data.get("comments"), list) or not isinstance(data.get("source"), dict):
        raise InputError(f"{path}: malformed report data")
    for index, comment in enumerate(data["comments"]):
        required = {"id", "requirementId", "column", "initials", "created", "text"}
        if not isinstance(comment, dict) or not required.issubset(comment):
            raise InputError(f"{path}: malformed comment at index {index}")
        if not valid_initials(comment["initials"]):
            raise InputError(f"{path}: invalid reviewer initials in comment {index}")
        if not all(isinstance(comment[key], str) for key in required):
            raise InputError(f"{path}: invalid field type in comment {index}")
        if len(comment["text"]) > 1_000_000:
            raise InputError(f"{path}: comment {index} exceeds the size limit")
    return data


def extract_comments_csv(
    report_path: str,
    output_path: str,
    comments_column: str,
    comments_format: str,
    csv_base: str,
    allow_comment_loss: bool,
    delimiter: str = ",",
) -> None:
    data = extract_report_json(report_path)
    source = data["source"]
    mode = data["meta"].get("mode")
    if mode == "snapshot":
        selected = source["new"]
        allowed_ids = {str(row.get(data["meta"]["idColumn"], "")).strip() for row in selected["rows"]}
        add_status = False
    else:
        if csv_base not in {"new", "old", "union"}:
            raise ConfigError("--csv-base must be new, old, or union")
        if csv_base in {"new", "old"}:
            selected = source[csv_base]
            if selected is None:
                raise InputError(f"report does not contain a {csv_base} snapshot")
            allowed_ids = {str(row.get(data["meta"]["idColumn"], "")).strip() for row in selected["rows"]}
            add_status = False
        else:
            id_column = data["meta"]["idColumn"]
            old_rows = {str(row.get(id_column, "")).strip(): row for row in source["old"]["rows"]}
            new_rows = {str(row.get(id_column, "")).strip(): row for row in source["new"]["rows"]}
            order = [str(row.get(id_column, "")).strip() for row in source["new"]["rows"]]
            order += [str(row.get(id_column, "")).strip() for row in source["old"]["rows"] if str(row.get(id_column, "")).strip() not in new_rows]
            headers = list(source["new"]["headers"]) + [h for h in source["old"]["headers"] if h not in source["new"]["headers"]]
            if "_Diff Status" in headers:
                raise InputError("cannot use union CSV base because '_Diff Status' already exists")
            if data["formatVersion"] == 1:
                status_by_id = {row["id"]: row["status"] for row in data["rows"]}
            else:
                status_by_id = data.get("diffStatus")
                if not isinstance(status_by_id, dict):
                    raise InputError(f"{report_path}: malformed diff status map")
            selected = {
                "headers": headers + ["_Diff Status"],
                "rows": [{**old_rows.get(rid, {}), **new_rows.get(rid, {}), "_Diff Status": status_by_id.get(rid, "")} for rid in order],
            }
            allowed_ids = set(order)
            add_status = True
    excluded = [c for c in data["comments"] if c["requirementId"] not in allowed_ids]
    if excluded and not allow_comment_loss:
        excluded_ids = sorted({c["requirementId"] for c in excluded})
        raise InputError(
            "selected CSV base would omit comments for requirement(s): " + ", ".join(excluded_ids)
            + "; select another --csv-base or pass --allow-comment-loss"
        )
    headers = list(selected["headers"])
    if comments_column in headers:
        raise InputError(f"comments column {comments_column!r} already exists; choose another name")
    headers.append(comments_column)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for comment in data["comments"]:
        if comment["requirementId"] in allowed_ids:
            exported = {key: comment.get(key) for key in ("column", "initials", "created", "modified", "text")}
            grouped.setdefault(comment["requirementId"], []).append(exported)
    id_column = data["meta"]["idColumn"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=delimiter, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for source_row in selected["rows"]:
        row = dict(source_row)
        rid = str(row.get(id_column, "")).strip()
        comments = sorted(grouped.get(rid, []), key=lambda item: item.get("created") or "")
        row[comments_column] = (
            json.dumps(comments, ensure_ascii=False, separators=(",", ":"))
            if comments_format == "json"
            else comments_as_text(comments)
        )
        writer.writerow(row)
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8-sig")
