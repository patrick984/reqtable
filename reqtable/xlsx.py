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

from .core import DEFAULT_CONFIG, ConfigError, InputError, valid_initials

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_DC_MODIFIED = "{http://purl.org/dc/terms/}modified"
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
    """The selected cells: `name` is the table or sheet they came from, row 0 is the header.

    `rows[i]` is worksheet row `first_row + i` of `sheet`, and its first column is worksheet column `first_col`.
    """

    name: str
    rows: list[list[str]]
    first_row: int = 1
    first_col: int = 1
    sheet: str = ""


@dataclass(frozen=True)
class Imported:
    """What an .xlsx input yields: the combined table as a block, repair warnings, and Excel comments as review comments."""

    block: Block
    warnings: tuple[str, ...] = ()
    comments: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class RawComment:
    row: int
    col: int
    author: str
    created: str
    text: str


@dataclass
class Part:
    """One source's rows on their way to the combined table, with the worksheet position of each."""

    name: str
    sheet: str
    headers: list[str]
    rows: list[list[str]]
    numbers: list[int]
    columns: dict[int, str | None]


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

    def raw_comments(self, sheet: Sheet) -> list[RawComment]:
        """Comments of a sheet: threaded ones with each reply on its own, else the legacy note on that cell."""
        names = set(self._zip.namelist())
        links = [(kind, target) for _, kind, target in _typed_relationships(self._zip, sheet.part) if target in names]
        threaded: list[RawComment] = []
        for _, target in (l for l in links if l[0].endswith("/threadedComment")):
            people = self._people()
            for node in ET.fromstring(self._zip.read(target)).findall("{*}threadedComment"):
                text = node.find("{*}text")
                row, col = split_ref(node.get("ref", ""))
                threaded.append(RawComment(
                    row, col, people.get(node.get("personId", ""), ""), node.get("dT", ""),
                    (text.text or "").strip() if text is not None else "",
                ))
        threaded.sort(key=lambda c: (c.row, c.col, c.created))
        threaded_cells = {(c.row, c.col) for c in threaded}
        notes: list[RawComment] = []
        for _, target in (l for l in links if l[0].endswith("/comments")):
            root = ET.fromstring(self._zip.read(target))
            authors = [(a.text or "").strip() for a in root.findall("m:authors/m:author", NS)]
            for node in root.findall("m:commentList/m:comment", NS):
                row, col = split_ref(node.get("ref", ""))
                text_node = node.find("m:text", NS)
                text = _text_of(text_node) if text_node is not None else ""
                if (row, col) in threaded_cells and text.startswith("[Threaded comment]"):
                    continue
                index = int(node.get("authorId") or -1)
                author = authors[index] if 0 <= index < len(authors) else ""
                if author and text.startswith(author + ":\n"):
                    text = text[len(author) + 2:]
                notes.append(RawComment(row, col, author, self._modified(), text.strip()))
        notes.sort(key=lambda c: (c.row, c.col))
        return [*notes, *threaded]

    def _people(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for _, kind, target in _typed_relationships(self._zip, "xl/workbook.xml"):
            if kind.endswith("/person") and target in self._zip.namelist():
                for person in ET.fromstring(self._zip.read(target)).findall("{*}person"):
                    result[person.get("id", "")] = (person.get("displayName") or "").strip()
        return result

    def _modified(self) -> str:
        if "docProps/core.xml" not in self._zip.namelist():
            return ""
        node = ET.fromstring(self._zip.read("docProps/core.xml")).find(_DC_MODIFIED)
        return (node.text or "").strip() if node is not None else ""

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


def _typed_relationships(archive: zipfile.ZipFile, part: str) -> list[tuple[str, str, str]]:
    """(id, type, target part) for each relationship of a part."""
    folder, name = posixpath.split(part)
    path = posixpath.join(folder, "_rels", name + ".rels")
    if path not in archive.namelist():
        return []
    result = []
    for rel in ET.fromstring(archive.read(path)).findall("rel:Relationship", NS):
        target = rel.get("Target", "")
        result.append((
            rel.get("Id", ""),
            rel.get("Type", ""),
            target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target)),
        ))
    return result


def _relationships(archive: zipfile.ZipFile, part: str) -> dict[str, str]:
    return {rid: target for rid, _, target in _typed_relationships(archive, part)}


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
    return Block(table.name, _trim_empty_tail(rows), r1, c1, table.sheet)


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
    return Block(sheet.name, wb.read_block(sheet, header_row, c1, last, c2), header_row, c1, sheet.name)


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


def _map_source(block: Block, source: dict[str, Any], id_column: str | None, traceability: bool) -> Part:
    """Apply one configured source to its block: headings, exclude, rename, set, lists, then Type and generated IDs."""
    where = f"xlsx source {_source_name(source)!r}"
    headers = list(block.rows[0])
    if "" in headers:
        raise InputError(f"{where}: empty column name in header")
    duplicates = sorted({h for h in headers if headers.count(h) > 1})
    if duplicates:
        raise InputError(f"{where}: duplicate column name(s): {', '.join(duplicates)}")
    columns, exclude = source.get("columns", {}), source.get("exclude", [])
    headings = source.get("headings")
    heading_columns = [headings[k] for k in ("column", "text") if k in headings] if headings else []
    for name in (*columns, *exclude, *heading_columns):
        if name not in headers:
            raise ConfigError(f"{where} has no column {name!r}; columns: {_names(iter(headers))}")
    live = [
        (block.first_row + 1 + i, row) for i, row in enumerate(block.rows[1:]) if any(cell.strip() for cell in row)
    ]
    under: list[str] = [""] * len(live)
    if headings:
        type_at = headers.index(headings["column"])
        text_at = headers.index(headings["text"]) if "text" in headings else None
        values = {v.strip().casefold() for v in headings["values"]}
        kept, under, current = [], [], ""
        for number, row in live:
            if row[type_at].strip().casefold() in values:
                if text_at is not None:
                    current = row[text_at].strip()
                else:
                    current = next((c.strip() for i, c in enumerate(row) if i != type_at and c.strip()), "")
            else:
                kept.append((number, row))
                under.append(current)
        live = kept
    keep = [i for i, h in enumerate(headers) if h not in exclude]
    out_headers = [columns.get(headers[i], headers[i]) for i in keep]
    clashes = sorted({h for h in out_headers if out_headers.count(h) > 1})
    if clashes:
        raise ConfigError(f"{where}: columns map to the same output header: {', '.join(clashes)}")
    numbers = [number for number, _ in live]
    rows = [[row[i] for i in keep] for _, row in live]

    def column(name: str) -> int:
        if name not in out_headers:
            out_headers.append(name)
            for row in rows:
                row.append("")
        return out_headers.index(name)

    def need(name: str, key: str) -> int:
        if name not in out_headers:
            raise ConfigError(f"{where}: {key} names {name!r}, which is not a mapped column; columns: {_names(iter(out_headers))}")
        return out_headers.index(name)

    constants = dict(source.get("set", {}))
    if "type" in source:
        constants["Type"] = source["type"]
    if "Type" in constants and not traceability:
        raise ConfigError(
            f"{where} sets 'type', which needs traceability: use --traceability or set \"traceability\": true"
        )
    for name, constant in constants.items():
        at = column(name)
        for row in rows:
            row[at] = constant
    if headings:
        at = column(headings["into"])
        for row, heading in zip(rows, under):
            if heading and not row[at].strip():
                row[at] = heading
    for name, separator in source.get("lists", {}).items():
        at = need(name, "lists")
        pattern = r"\r?\n" if separator == "newline" else re.escape(separator)
        for row in rows:
            row[at] = "; ".join(p for p in (part.strip() for part in re.split(pattern, row[at])) if p)
    if "id_prefix" in source:
        if not id_column:
            raise ConfigError(f"{where} sets 'id_prefix', which needs an ID column: use --id-column or set id_column")
        at = column(id_column)
        id_from = source.get("id_from") or (["Field", "Name"] if constants.get("Type") == "Value" else None)
        parts_at = [need(name, "id_from") for name in id_from] if id_from else []
        names = out_headers.index("Name") if "Name" in out_headers else None
        aliases = out_headers.index("Aliases") if "Aliases" in out_headers else None
        for row in rows:
            if row[at].strip():
                continue
            if id_from:
                slug = "-".join(filter(None, (_slug(row[i]) for i in parts_at)))
            else:
                alias = next((a.strip() for a in row[aliases].split(";") if a.strip()), "") if aliases is not None else ""
                slug = _slug(alias) or (_slug(row[names]) if names is not None else "")
            if slug:
                row[at] = source["id_prefix"] + slug
    elif id_column and id_column not in out_headers:
        raise ConfigError(
            f"{where} has no {id_column!r} column: map one of its columns to {id_column!r}, "
            f"set id_prefix to generate IDs, or remove the source"
        )
    sheet_columns = {
        block.first_col + i: None if h in exclude else columns.get(h, h) for i, h in enumerate(headers)
    }
    return Part(block.name, block.sheet, out_headers, rows, numbers, sheet_columns)


def _plain_part(block: Block) -> Part:
    headers = list(block.rows[0])
    body = [(block.first_row + 1 + i, row) for i, row in enumerate(block.rows[1:]) if any(c.strip() for c in row)]
    return Part(
        block.name, block.sheet, headers, [row for _, row in body], [n for n, _ in body],
        {block.first_col + i: h for i, h in enumerate(headers)},
    )


def _listed(items: list[str], limit: int = 12) -> str:
    return ", ".join(items[:limit]) + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _repair_ids(parts: list[Part], id_column: str | None, file: str) -> list[str]:
    """Name rows that have no ID ROW-<worksheet row> and suffix repeated IDs with ~2, ~3, ...; one warning per case."""
    warnings: list[str] = []
    if not id_column:
        return warnings
    usable = [(part, part.headers.index(id_column)) for part in parts if id_column in part.headers]
    for part, at in usable:
        named = []
        for number, row in zip(part.numbers, part.rows):
            if not row[at].strip():
                row[at] = f"ROW-{number}"
                named.append(row[at])
        if named:
            noun = "row has" if len(named) == 1 else "rows have"
            warnings.append(
                f"{file} [{part.name}]: {len(named)} {noun} no ID in {id_column!r}; "
                f"named {'it' if len(named) == 1 else 'them'} {_listed(named)}"
            )
    seen: dict[str, list[tuple[int, list[str], int]]] = {}
    for part, at in usable:
        for number, row in zip(part.numbers, part.rows):
            seen.setdefault(row[at].strip(), []).append((number, row, at))
    taken = set(seen)
    for rid, found in seen.items():
        if len(found) < 2:
            continue
        renamed = []
        for _, row, at in found[1:]:
            n = 2
            while f"{rid}~{n}" in taken:
                n += 1
            taken.add(f"{rid}~{n}")
            row[at] = f"{rid}~{n}"
            renamed.append(row[at])
        warnings.append(
            f"{file} [{' + '.join(p.name for p in parts)}]: duplicate ID {rid!r} at rows {', '.join(str(n) for n, _, _ in found)}; "
            f"renamed the later {'one' if len(renamed) == 1 else 'ones'} {', '.join(renamed)}"
        )
    return warnings


def _combine(parts: list[Part], id_column: str | None) -> Block:
    """One block from several parts: shared headers line up, missing cells are empty."""
    headers: list[str] = [id_column] if id_column and any(id_column in p.headers for p in parts) else []
    for part in parts:
        headers += [h for h in part.headers if h not in headers]
    rows = [headers]
    for part in parts:
        rows += [[row[part.headers.index(h)] if h in part.headers else "" for h in headers] for row in part.rows]
    return Block(" + ".join(p.name for p in parts), rows)


def _initials(author: str) -> str:
    words = re.sub(r"[\x00-\x1f\x7f]", " ", author).split()
    if not words:
        return "XL"
    value = (words[0][:2] if len(words) == 1 else "".join(w[0] for w in words)).upper()[:16]
    return value if valid_initials(value) else "XL"


def _place(part: Part, id_column: str | None, comment: RawComment) -> tuple[str, str, str] | None:
    """The (requirement ID, output column, text) a comment lands on in this part, or None if it falls outside it."""
    column = part.columns.get(comment.col)
    if not id_column or id_column not in part.headers or column is None or comment.row not in part.numbers:
        return None
    row = part.rows[part.numbers.index(comment.row)]
    rid = row[part.headers.index(id_column)].strip()
    if column != id_column:
        return rid, column, comment.text
    others = [h for h in part.headers if h != id_column]
    return (rid, others[0], f"[on ID] {comment.text}") if others else None


def _review_comments(wb: Workbook, parts: list[Part], id_column: str | None, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    comments: list[dict[str, Any]] = []
    dropped = 0
    for sheet_name in dict.fromkeys(part.sheet for part in parts):
        try:
            found = wb.raw_comments(wb.sheet_named(sheet_name))
        except (KeyError, ET.ParseError, ValueError, zipfile.BadZipFile) as exc:
            raise InputError(f"{wb.path.name}: cannot read comments of sheet {sheet_name!r}: {exc}") from exc
        for raw in found:
            placed = next(
                (hit for part in parts if part.sheet == sheet_name and (hit := _place(part, id_column, raw))), None
            )
            if placed is None:
                dropped += 1
                continue
            rid, column, text = placed
            comments.append({
                "id": f"xlsx-{len(comments) + 1}", "requirementId": rid, "column": column,
                "initials": _initials(raw.author), "created": raw.created, "modified": None, "text": text,
            })
    warnings = []
    if dropped:
        noun = "comment" if dropped == 1 else "comments"
        warnings.append(
            f"{label}: dropped {dropped} Excel {noun} on heading rows, excluded columns or cells outside the imported block"
        )
    return comments, warnings


def import_workbook(
    path: str | Path,
    selection: XlsxSelection,
    sources: list[dict[str, Any]],
    id_column: str | None,
    traceability: bool,
    comments: bool,
) -> Imported:
    """Read one workbook the lenient way: configured sources or the selected block, IDs repaired, comments mapped."""
    with Workbook.open(path) as wb:
        if sources:
            parts = [
                _map_source(
                    select_block(wb, XlsxSelection(s.get("table"), s.get("sheet"), s.get("header_row"))),
                    s, id_column, traceability,
                )
                for s in sources
            ]
        else:
            parts = [_plain_part(select_block(wb, selection))]
        warnings = _repair_ids(parts, id_column, Path(path).name)
        block = _combine(parts, id_column)
        label = f"{Path(path).name} [{block.name}]"
        found: list[dict[str, Any]] = []
        if comments:
            found, extra = _review_comments(wb, parts, id_column, label)
            warnings += extra
        return Imported(block, tuple(warnings), tuple(found))


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
