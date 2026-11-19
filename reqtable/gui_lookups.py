"""Read-only questions the GUI page asks while a form is being filled in: columns, tables, gates, baselines and systems.

Every function takes the form's query values, honours the same settings the CLI would, and reports a problem as an
``error`` string instead of raising, so the page can show it beside the field it belongs to.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

from .baselines import find_gate, record_type, sort_manifests
from .cli import input_source, table_store
from .core import ReqtableError, load_config, prepare_trace_table, read_csv_source, resolve_gate_enforcement
from .gui import guess_id_column, is_workbook_path
from .xlsx import Workbook, XlsxSelection, read_selection

PREVIEW_ROWS = 3
READ_ERRORS = (ReqtableError, OSError, UnicodeError, LookupError, csv.Error, ValueError)
TOGGLES = {"on": True, "off": False}


def resolve(workdir: Path, path: str) -> Path:
    return workdir / path if path else workdir


def selection_of(query: Mapping[str, str]) -> XlsxSelection:
    header_row = query.get("header_row", "")
    return XlsxSelection(query.get("table") or None, query.get("sheet") or None, int(header_row) if header_row else None)


def config_of(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    return load_config(
        str(resolve(workdir, query["config"])) if query.get("config") else None,
        {
            "id_column": query.get("id_column") or None,
            "traceability": TOGGLES.get(query.get("traceability", "")),
            "csv.encoding": query.get("encoding") or None,
            "csv.delimiter": query.get("delimiter") or None,
        },
    )


def _preview(rows: list[list[str]]) -> dict[str, Any]:
    data = [row for row in rows[1:] if any(cell.strip() for cell in row)]
    return {"columns": rows[0], "row_count": len(data), "rows": data[:PREVIEW_ROWS], "id_guess": guess_id_column(rows[0])}


def columns(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    path = resolve(workdir, query.get("path", ""))
    try:
        if is_workbook_path(str(path)):
            return _preview(read_selection(path, selection_of(query)).rows)
        config = config_of(workdir, {k: v for k, v in query.items() if k != "id_column"})
        with path.open("r", encoding=config["csv"]["encoding"], newline="") as handle:
            reader = csv.reader(handle, delimiter=config["csv"]["delimiter"])
            header = next(reader, [])
            counted = [row for row in reader if any(cell.strip() for cell in row)]
        return {**_preview([header, *counted]), "row_count": len(counted)}
    except READ_ERRORS as exc:
        return {"columns": [], "row_count": 0, "rows": [], "id_guess": "", "error": str(exc)}


def config_maps_workbook(workdir: Path, config: str) -> bool:
    """Whether the settings file decides which tables are read, through xlsx.sources. A broken file decides nothing."""
    if not config:
        return False
    try:
        return bool(load_config(str(resolve(workdir, config)))["xlsx"]["sources"])
    except ReqtableError:
        return False


def tables(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    maps = config_maps_workbook(workdir, query.get("config", ""))
    try:
        with Workbook.open(resolve(workdir, query.get("path", ""))) as workbook:
            return {
                "tables": [{"name": t.name, "sheet": t.sheet} for t in workbook.tables],
                "sheets": [{"name": s.name, "state": s.state} for s in workbook.sheets],
                "config_maps_workbook": maps,
            }
    except ReqtableError as exc:
        return {"tables": [], "sheets": [], "config_maps_workbook": maps, "error": str(exc)}


def gates(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    try:
        config = config_of(workdir, query)
    except ReqtableError as exc:
        return {"gates": [], "error": str(exc)}
    result = []
    for gate in config["gates"]:
        resolved = resolve_gate_enforcement(gate, config["baselines"]["enforcement"])
        result.append({
            "id": gate["id"],
            "name": gate.get("name", gate["id"]),
            "scope": find_gate(config, gate["id"]).scope,
            "roles": [{"role": entry["role"], "min": entry["min"]} for entry in gate.get("signoff", [])],
            "checks": [
                {"id": check["id"], "description": check["description"], "enforcement": check["enforcement"]}
                for check in resolved["checks"]
            ],
        })
    return {"gates": result, "store": config["baselines"]["store"]}


def baselines(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    path = query.get("path", "")
    if not path:
        return {"baselines": []}
    try:
        config = config_of(workdir, query)
        store = table_store(str(resolve(workdir, path)), selection_of(query), config)
        found = sort_manifests(store.list(), config)
    except READ_ERRORS as exc:
        return {"baselines": [], "error": str(exc)}
    return {
        "baselines": [
            {"name": m.name, "gate": m.gate, "system": m.system or "", "created": m.created, "created_by": m.created_by}
            for m in found
        ],
        "store": config["baselines"]["store"],
    }


def systems(workdir: Path, query: Mapping[str, str]) -> dict[str, Any]:
    path = query.get("path", "")
    if not path:
        return {"systems": []}
    try:
        config = config_of(workdir, query)
        table = read_csv_source(input_source(str(resolve(workdir, path)), selection_of(query), config), config)
        if config["traceability"]:
            table, _ = prepare_trace_table(table, config)
    except READ_ERRORS as exc:
        return {"systems": [], "error": str(exc)}
    id_column = config["id_column"]
    return {
        "systems": [
            {"id": row[id_column], "name": row.get("Name", "")} for row in table.rows if record_type(row) == "System"
        ]
    }
