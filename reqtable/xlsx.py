"""Read requirements from an .xlsx workbook with the standard library only.

Reading only: the workbook is never written. Cell values come out as the text
Excel displays for the stored value, so a block of cells can be fed to the CSV
pipeline unchanged. Merged cells keep their value in the top-left cell only.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET

from .core import DEFAULT_CONFIG, ConfigError, InputError

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
NS = {"m": _MAIN, "rel": _REL}

# Built-in number formats that Excel displays as dates or times (including the CJK locale ones).
_BUILTIN_DATE_FORMATS = frozenset({14, 15, 16, 17, 18, 19, 20, 21, 22, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
                                   45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58})


@dataclass(frozen=True)
class Sheet:
    name: str
    part: str
    state: str


@dataclass(frozen=True)
class Table:
    name: str
    sheet: str
    ref: str
    header_rows: int = 1
    totals_rows: int = 0


@dataclass(frozen=True)
class XlsxSelection:
    """Which block of a workbook to read, shared by every .xlsx input of one run."""

    table: str | None = None
    sheet: str | None = None
    header_row: int | None = None

    def __post_init__(self) -> None:
        if self.table and self.sheet:
            raise ConfigError("--table and --sheet cannot be combined; a table already belongs to one sheet")
        if self.header_row is not None:
            if not self.sheet:
                raise ConfigError("--header-row needs --sheet")
            if self.header_row < 1:
                raise ConfigError("--header-row must be 1 or greater")

    @property
    def given(self) -> bool:
        return bool(self.table or self.sheet or self.header_row is not None)


@dataclass(frozen=True)
class Block:
    """The selected cells: `name` is the table or sheet they came from, row 0 is the header."""

    name: str
    rows: list[list[str]]


def is_xlsx(path: str) -> bool:
    return path.lower().endswith(".xlsx")


def split_ref(ref: str) -> tuple[int, int]:
    match = re.fullmatch(r"\$?([A-Za-z]+)\$?(\d+)", ref)
    if not match:
        raise InputError(f"invalid cell reference {ref!r}")
    col = 0
    for ch in match.group(1).upper():
        col = col * 26 + ord(ch) - 64
    return int(match.group(2)), col


def column_name(col: int) -> str:
    out = ""
    while col:
        col, rem = divmod(col - 1, 26)
        out = chr(65 + rem) + out
    return out


def _range(ref: str) -> tuple[int, int, int, int]:
    start, _, end = ref.partition(":")
    (r1, c1), (r2, c2) = split_ref(start), split_ref(end or start)
    return r1, c1, r2, c2


def _text_of(node: ET.Element) -> str:
    """Text of an <si> or <is>: plain <t> or rich-text <r> runs; phonetic <rPh> hints are not content."""
    parts = []
    for child in node:
        if child.tag == f"{{{_MAIN}}}t":
            parts.append(child.text or "")
        elif child.tag == f"{{{_MAIN}}}r":
            parts.extend(t.text or "" for t in child.findall("m:t", NS))
    # Excel writes control characters as _xHHHH_, such as the CR in a line break typed on Windows.
    return re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), "".join(parts))


def _excel_date(serial: float, date1904: bool) -> str:
    if date1904:
        base = dt.datetime(1904, 1, 1)
    else:
        # Excel treats 1900 as a leap year, so serials before its fake Feb 29 count from a day later.
        base = dt.datetime(1899, 12, 31) if serial < 60 else dt.datetime(1899, 12, 30)
    stamp = base + dt.timedelta(seconds=round(serial * 86400))
    if serial < 1:
        return stamp.time().isoformat(timespec="seconds")
    if stamp.time() == dt.time(0):
        return stamp.date().isoformat()
    return stamp.isoformat(timespec="seconds")


def _number(raw: str) -> str:
    number = float(raw)
    if number.is_integer() and abs(number) < 1e16:
        return str(int(number))
    return repr(number)


def _is_date_format(format_id: int, code: str) -> bool:
    if format_id in _BUILTIN_DATE_FORMATS:
        return True
    visible = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.|_.|\*.', "", code)
    return bool(re.search(r"[dmyhs]", visible, re.I))


@dataclass
class Workbook:
    path: Path
    sheets: list[Sheet]
    tables: list[Table]
    shared: list[str]
    date_styles: frozenset[int]
    date1904: bool
    _zip: zipfile.ZipFile = field(repr=False)
    _grids: dict[str, dict[tuple[int, int], str]] = field(default_factory=dict, repr=False)

    def __enter__(self) -> "Workbook":
        return self

    def __exit__(self, *exc: object) -> None:
        self._zip.close()

    @classmethod
    def open(cls, path: str | Path) -> "Workbook":
        path = Path(path)
        try:
            archive = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise InputError(f"cannot open {path} as an .xlsx workbook: {exc}") from exc
        try:
            return cls._load(path, archive)
        except (KeyError, ET.ParseError, ValueError, zipfile.BadZipFile) as exc:
            archive.close()
            raise InputError(f"{path} is not a readable .xlsx workbook: {exc}") from exc
        except Exception:
            archive.close()
            raise

    @classmethod
    def _load(cls, path: Path, archive: zipfile.ZipFile) -> "Workbook":
        names = set(archive.namelist())
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = _relationships(archive, "xl/workbook.xml")
        properties = root.find("m:workbookPr", NS)
        sheets = [
            Sheet(s.get("name", ""), relations[s.get(_R_ID)], s.get("state", "visible"))
            for s in root.findall("m:sheets/m:sheet", NS)
        ]
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared = [_text_of(si) for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        tables = []
        for sheet in sheets:
            for target in _relationships(archive, sheet.part).values():
                if "/tables/" not in target or target not in names:
                    continue
                table = ET.fromstring(archive.read(target))
                tables.append(Table(
                    table.get("displayName") or table.get("name") or "",
                    sheet.name,
                    table.get("ref", ""),
                    int(table.get("headerRowCount", "1")),
                    int(table.get("totalsRowCount", "0")),
                ))
        return cls(
            path, sheets, tables, shared, _date_styles(archive, names),
            properties is not None and properties.get("date1904") in ("1", "true"), archive,
        )

    def sheet_named(self, name: str) -> Sheet:
        found = next((s for s in self.sheets if s.name.casefold() == name.casefold()), None)
        if found is None:
            raise InputError(f"{self.path.name} has no sheet {name!r}; sheets: {_names(s.name for s in self.sheets)}")
        return found

    def table_named(self, name: str) -> Table:
        found = next((t for t in self.tables if t.name.casefold() == name.casefold()), None)
        if found is None:
            raise InputError(f"{self.path.name} has no table {name!r}; tables: {_names(t.name for t in self.tables)}")
        return found

    def cells(self, sheet: Sheet) -> dict[tuple[int, int], str]:
        """Non-empty cells of a sheet keyed by (row, column), both 1-based."""
        if sheet.name not in self._grids:
            try:
                self._grids[sheet.name] = dict(self._parse_cells(sheet))
            except (KeyError, ET.ParseError, ValueError, zipfile.BadZipFile) as exc:
                raise InputError(f"{self.path.name}: cannot read sheet {sheet.name!r}: {exc}") from exc
        return self._grids[sheet.name]

    def read_block(self, sheet: Sheet, r1: int, c1: int, r2: int, c2: int) -> list[list[str]]:
        grid = self.cells(sheet)
        return [[grid.get((r, c), "") for c in range(c1, c2 + 1)] for r in range(r1, r2 + 1)]

    def _parse_cells(self, sheet: Sheet) -> Iterator[tuple[tuple[int, int], str]]:
        row_number = col_number = 0
        row_tag, cell_tag = f"{{{_MAIN}}}row", f"{{{_MAIN}}}c"
        with self._zip.open(sheet.part) as handle:
            for event, element in ET.iterparse(handle, events=("start", "end")):
                if element.tag == row_tag and event == "start":
                    row_number = int(element.get("r") or row_number + 1)
                    col_number = 0
                elif element.tag == cell_tag and event == "end":
                    if element.get("r"):
                        row_number, col_number = split_ref(element.get("r", ""))
                    else:
                        col_number += 1
                    value = self._value(element)
                    if value != "":
                        yield (row_number, col_number), value
                    element.clear()

    def _value(self, cell: ET.Element) -> str:
        kind = cell.get("t", "n")
        v = cell.find("m:v", NS)
        raw = v.text if v is not None and v.text is not None else ""
        if kind == "s":
            return self.shared[int(raw)] if raw else ""
        if kind == "inlineStr":
            node = cell.find("m:is", NS)
            return _text_of(node) if node is not None else ""
        if kind in ("str", "e", "d"):
            return raw
        if kind == "b":
            return "TRUE" if raw == "1" else "FALSE"
        if raw == "":
            return ""
        if int(cell.get("s", "0")) in self.date_styles:
            try:
                return _excel_date(float(raw), self.date1904)
            except (OverflowError, ValueError):
                pass
        return _number(raw)


def _names(names: Iterator[str]) -> str:
    return ", ".join(names) or "(none)"


def _relationships(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    folder, name = posixpath.split(part)
    path = posixpath.join(folder, "_rels", name + ".rels")
    if path not in archive.namelist():
        return {}
    result = {}
    for rel in ET.fromstring(archive.read(path)).findall("rel:Relationship", NS):
        target = rel.get("Target", "")
        result[rel.get("Id", "")] = (
            target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
        )
    return result


def _date_styles(archive: zipfile.ZipFile, names: set[str]) -> frozenset[int]:
    if "xl/styles.xml" not in names:
        return frozenset()
    root = ET.fromstring(archive.read("xl/styles.xml"))
    custom = {int(f.get("numFmtId", "0")): f.get("formatCode", "") for f in root.findall("m:numFmts/m:numFmt", NS)}
    result = set()
    for index, xf in enumerate(root.findall("m:cellXfs/m:xf", NS)):
        format_id = int(xf.get("numFmtId", "0"))
        if _is_date_format(format_id, custom.get(format_id, "")):
            result.add(index)
    return frozenset(result)


def _trim_empty_tail(rows: list[list[str]]) -> list[list[str]]:
    while rows and not any(rows[-1]):
        rows.pop()
    return rows


def _table_block(wb: Workbook, table: Table) -> Block:
    if table.header_rows < 1:
        raise InputError(f"{wb.path.name}: table {table.name!r} has no header row")
    r1, c1, r2, c2 = _range(table.ref)
    rows = wb.read_block(wb.sheet_named(table.sheet), r1, c1, r2 - table.totals_rows, c2)
    return Block(table.name, _trim_empty_tail(rows))


def _sheet_block(wb: Workbook, sheet: Sheet, header_row: int | None) -> Block:
    grid = wb.cells(sheet)
    if header_row is None:
        if not grid:
            raise InputError(f"{wb.path.name}: sheet {sheet.name!r} is empty")
        header_row = min(r for r, _ in grid)
    header_cols = [c for r, c in grid if r == header_row]
    if not header_cols:
        raise InputError(f"{wb.path.name}: sheet {sheet.name!r} has no header cells in row {header_row}")
    c1, c2 = min(header_cols), max(header_cols)
    last = max((r for r, c in grid if c1 <= c <= c2), default=header_row)
    return Block(sheet.name, wb.read_block(sheet, header_row, c1, last, c2))


def select_block(wb: Workbook, selection: XlsxSelection) -> Block:
    if selection.table:
        return _table_block(wb, wb.table_named(selection.table))
    if selection.sheet:
        return _sheet_block(wb, wb.sheet_named(selection.sheet), selection.header_row)
    if len(wb.tables) == 1:
        return _table_block(wb, wb.tables[0])
    raise InputError(
        f"{wb.path.name} has {len(wb.tables)} tables; choose one with --table or a sheet with --sheet "
        f"(tables: {_names(t.name for t in wb.tables)}; sheets: {_names(s.name for s in wb.sheets)})"
    )


def read_selection(path: str | Path, selection: XlsxSelection) -> Block:
    with Workbook.open(path) as wb:
        return select_block(wb, selection)


def _source_name(source: dict[str, Any]) -> str:
    return source.get("table") or source["sheet"]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", text.upper()).strip("-")


def _map_source(block: Block, source: dict[str, Any], id_column: str | None, traceability: bool) -> Block:
    """Apply one configured source to its block: exclude, rename, then Type and generated IDs."""
    where = f"xlsx source {_source_name(source)!r}"
    headers, body = list(block.rows[0]), block.rows[1:]
    if "" in headers:
        raise InputError(f"{where}: empty column name in header")
    duplicates = sorted({h for h in headers if headers.count(h) > 1})
    if duplicates:
        raise InputError(f"{where}: duplicate column name(s): {', '.join(duplicates)}")
    columns, exclude = source.get("columns", {}), source.get("exclude", [])
    for name in (*columns, *exclude):
        if name not in headers:
            raise ConfigError(f"{where} has no column {name!r}; columns: {_names(iter(headers))}")
    keep = [i for i, h in enumerate(headers) if h not in exclude]
    out_headers = [columns.get(headers[i], headers[i]) for i in keep]
    clashes = sorted({h for h in out_headers if out_headers.count(h) > 1})
    if clashes:
        raise ConfigError(f"{where}: columns map to the same output header: {', '.join(clashes)}")
    rows = [[row[i] for i in keep] for row in body]

    def column(name: str) -> int:
        if name not in out_headers:
            out_headers.append(name)
            for row in rows:
                row.append("")
        return out_headers.index(name)

    if "type" in source:
        if not traceability:
            raise ConfigError(
                f"{where} sets 'type', which needs traceability: use --traceability or set \"traceability\": true"
            )
        at = column("Type")
        for row in rows:
            row[at] = source["type"]
    if "id_prefix" in source:
        if not id_column:
            raise ConfigError(f"{where} sets 'id_prefix', which needs an ID column: use --id-column or set id_column")
        at = column(id_column)
        names = out_headers.index("Name") if "Name" in out_headers else None
        aliases = out_headers.index("Aliases") if "Aliases" in out_headers else None
        for number, row in enumerate(rows, start=2):
            if row[at].strip():
                continue
            alias = next((a.strip() for a in row[aliases].split(";") if a.strip()), "") if aliases is not None else ""
            slug = _slug(alias) or (_slug(row[names]) if names is not None else "")
            if not slug:
                raise InputError(
                    f"{where}: row {number} has no ID and no Aliases or Name to build one from for id_prefix"
                )
            row[at] = source["id_prefix"] + slug
    elif id_column and id_column not in out_headers:
        raise ConfigError(
            f"{where} has no {id_column!r} column: map one of its columns to {id_column!r}, "
            f"set id_prefix to generate IDs, or remove the source"
        )
    return Block(block.name, [out_headers, *rows])


def combine_sources(wb: Workbook, sources: list[dict[str, Any]], id_column: str | None, traceability: bool) -> Block:
    """One block from several configured sources: shared headers line up, missing cells are empty."""
    mapped = []
    for source in sources:
        selection = XlsxSelection(source.get("table"), source.get("sheet"), source.get("header_row"))
        mapped.append(_map_source(select_block(wb, selection), source, id_column, traceability))
    headers: list[str] = [id_column] if id_column and any(id_column in b.rows[0] for b in mapped) else []
    for block in mapped:
        headers += [h for h in block.rows[0] if h not in headers]
    rows = [headers]
    for block in mapped:
        head = block.rows[0]
        rows += [[row[head.index(h)] if h in head else "" for h in headers] for row in block.rows[1:]]
    return Block(" + ".join(b.name for b in mapped), rows)


def read_mapped(path: str | Path, sources: list[dict[str, Any]], id_column: str | None, traceability: bool) -> Block:
    with Workbook.open(path) as wb:
        return combine_sources(wb, sources, id_column, traceability)


def mapping_template(path: str | Path) -> dict[str, Any]:
    """A complete config for a workbook: every table, and every sheet without one, mapped to itself."""
    sources: list[dict[str, Any]] = []
    with Workbook.open(path) as wb:
        for table in wb.tables:
            if table.header_rows >= 1:
                sources.append({"table": table.name, "block": _table_block(wb, table)})
        for sheet in wb.sheets:
            if any(t.sheet == sheet.name for t in wb.tables) or not wb.cells(sheet):
                continue
            first = min(r for r, _ in wb.cells(sheet))
            sources.append({"sheet": sheet.name, "header_row": first, "block": _sheet_block(wb, sheet, first)})
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    id_headers = []
    for source in sources:
        headers = source.pop("block").rows[0]
        source["columns"] = {h: h for h in headers}
        id_headers += [h for h in headers if h.casefold() == "id"]
    config["id_column"] = id_headers[0] if id_headers else None
    config["xlsx"]["sources"] = sources
    return config


def block_to_csv(rows: list[list[str]], delimiter: str) -> str:
    """CRLF records, like the browser's Save CSV, without its byte-order mark."""
    buffer = io.StringIO(newline="")
    csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n").writerows(rows)
    return buffer.getvalue()


def describe(path: str | Path) -> str:
    with Workbook.open(path) as wb:
        lines = ["Sheets:"]
        lines += [f"  {s.name}" + ("" if s.state == "visible" else f" ({s.state})") for s in wb.sheets]
        lines.append("Tables:")
        if not wb.tables:
            lines.append("  (none)")
        for table in wb.tables:
            headers = ""
            if table.header_rows >= 1:
                r1, c1, _, c2 = _range(table.ref)
                row = wb.read_block(wb.sheet_named(table.sheet), r1, c1, r1, c2)[0]
                headers = "  headers: " + ", ".join(row)
            lines.append(f"  {table.name}  sheet: {table.sheet}  ref: {table.ref}{headers}")
        return "\n".join(lines)
