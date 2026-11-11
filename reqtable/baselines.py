from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .core import (
    ConfigError,
    ReqtableError,
    CsvSource,
    CsvTable,
    InputError,
    OutputError,
    atomic_write_text,
    generation_time,
    prepare_trace_table,
    read_csv_source,
)
from .signoff import CheckedSignOff, SignOff, approval_status, slug
from .waivers import Waiver
from .xlsx import block_to_csv, is_xlsx

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


def links(cell: str) -> list[str]:
    return [part.strip() for part in cell.split(";") if part.strip()]


def record_type(row: dict[str, str]) -> str:
    return row.get("Type", "").strip() or "Requirement"


def _subtree(rows: Sequence[dict[str, str]], id_column: str, system: str) -> set[str]:
    children: dict[str, list[str]] = {}
    for row in rows:
        if record_type(row) == "System":
            for parent in links(row.get("Part of", "")):
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
    included = [row for row in rows if record_type(row) in wanted]
    if system is None:
        return included
    subtree = _subtree(rows, id_column, system)
    requirements = [
        row for row in included
        if record_type(row) == "Requirement" and subtree.intersection(links(row.get("Allocated to", "")))
    ]
    tests = {test for row in requirements for test in links(row.get("Verified by", ""))}
    chosen_tests = [row for row in included if record_type(row) == "Test" and row[id_column].strip() in tests]
    plans = {plan for row in chosen_tests for plan in links(row.get("Test plan", ""))}
    kept = {id(row) for row in requirements + chosen_tests}

    def keep(row: dict[str, str]) -> bool:
        kind = record_type(row)
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


def find_gate(config: dict[str, Any], gate_id: str) -> Gate:
    for gate in config["gates"]:
        if gate["id"] == gate_id:
            return Gate.from_config(gate)
    known = ", ".join(gate["id"] for gate in config["gates"]) or "none"
    raise ConfigError(f"unknown gate {gate_id!r}; configured gates: {known}")


@dataclass(frozen=True)
class BaselineName:
    """number None means 'the latest' and only occurs in a requested name."""

    gate: str
    number: int | None = 1
    system: str | None = None

    @classmethod
    def parse(cls, text: str) -> BaselineName:
        head, _, system = text.partition("/")
        match = re.fullmatch(r"(.+?)(?:-(\d+))?", head)
        if not match:
            raise InputError(f"invalid baseline name {text!r}")
        number = int(match.group(2)) if match.group(2) else None
        return cls(match.group(1), number, system or None)

    def __str__(self) -> str:
        assert self.number is not None
        gate = self.gate if self.number == 1 else f"{self.gate}-{self.number}"
        return f"{gate}/{self.system}" if self.system else gate


_MANIFEST_TYPES: dict[str, Any] = {
    "format": str, "name": str, "gate": str, "supersedes": (str, type(None)), "system": (str, type(None)),
    "includes": list, "captures_status": bool, "status_columns": list, "content_hash": str,
    "source": str, "created": str, "created_by": str,
}


@dataclass(frozen=True)
class Manifest:
    name: str
    gate: str
    supersedes: str | None
    system: str | None
    includes: list[str]
    captures_status: bool
    status_columns: list[str]
    content_hash: str
    source: str
    created: str
    created_by: str
    waivers: tuple[Waiver, ...] = ()
    format: str = HASH_FORMAT

    @property
    def number(self) -> int:
        parsed = BaselineName.parse(self.name).number
        return 1 if parsed is None else parsed

    def to_dict(self) -> dict[str, Any]:
        fields = asdict(self)
        return {**{key: fields[key] for key in _MANIFEST_TYPES}, "waivers": [waiver.to_dict() for waiver in self.waivers]}

    @classmethod
    def from_dict(cls, data: Any) -> Manifest:
        if not isinstance(data, dict) or set(data) - {"waivers"} != set(_MANIFEST_TYPES):
            raise ValueError("manifest has the wrong keys")
        waivers = data.get("waivers", [])
        if not isinstance(waivers, list):
            raise ValueError("manifest waivers must be a list")
        for key, kind in _MANIFEST_TYPES.items():
            if not isinstance(data[key], kind):
                raise ValueError(f"manifest {key} has the wrong type")
        if data["format"] != HASH_FORMAT:
            raise ValueError(f"unsupported manifest format {data['format']!r}")
        for key in ("includes", "status_columns"):
            if not all(isinstance(item, str) for item in data[key]):
                raise ValueError(f"manifest {key} must hold strings")
        parsed = BaselineName.parse(data["name"])
        if parsed.gate != data["gate"] or parsed.system != data["system"] or parsed.number == 0:
            raise ValueError("manifest name does not match its gate and system")
        return cls(**{key: data[key] for key in _MANIFEST_TYPES}, waivers=tuple(Waiver.from_dict(item) for item in waivers))


def next_name(existing: Iterable[Manifest], gate: str, system: str | None) -> tuple[BaselineName, str | None]:
    siblings = [m for m in existing if m.gate == gate and m.system == system]
    if not siblings:
        return BaselineName(gate, 1, system), None
    latest = max(siblings, key=lambda m: m.number)
    return BaselineName(gate, latest.number + 1, system), latest.name


def resolve(requested: str, manifests: Sequence[Manifest]) -> Manifest:
    wanted = BaselineName.parse(requested)
    candidates = [m for m in manifests if m.gate == wanted.gate and m.system == wanted.system]
    if wanted.number is not None:
        candidates = [m for m in candidates if m.number == wanted.number]
    if not candidates:
        known = ", ".join(m.name for m in manifests) or "none"
        raise InputError(f"unknown baseline {requested!r}; existing baselines: {known}")
    return max(candidates, key=lambda m: m.number)


def sort_manifests(manifests: Iterable[Manifest], config: dict[str, Any]) -> list[Manifest]:
    order = {gate["id"]: index for index, gate in enumerate(config["gates"])}
    return sorted(
        manifests,
        key=lambda m: (order.get(m.gate, len(order)), m.gate, m.system or "", m.number),
    )


def run_git(directory: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(["git", "-C", str(directory), *args], capture_output=True)
    except OSError as exc:
        raise InputError(f"cannot run git: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise InputError(f"git {args[0]} failed: {detail}")
    return completed.stdout


def current_user(directory: Path) -> str:
    try:
        name = run_git(directory, "config", "user.name").decode("utf-8", "replace").strip()
    except InputError:
        name = ""
    return name or getpass.getuser()


def _print_warning(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


TableReader = Callable[[Path], CsvTable]

SIGNOFF_PREFIX = "signoff/"


def _tag_number(ref: str) -> int:
    match = re.search(r"-(\d+)$", ref)
    return int(match.group(1)) if match else 1


def classify_verification(returncode: int, output: str) -> str:
    if returncode == 0:
        return "good"
    text = output.lower()
    if "no signature" in text:
        return "unsigned"
    if re.search(r"bad signature|incorrect signature|invalid signature", text):
        return "bad"
    return "unverifiable"


class BaselineStore(ABC):
    """Where gate baselines live. Both stores keep the same manifest and the same frozen table."""

    source: str

    def __init__(self, input_path: Path, config: dict[str, Any], read_file: TableReader, warn: Callable[[str], None]):
        self.input_path = input_path
        self.config = config
        self.read_file = read_file
        self.warn = warn

    @abstractmethod
    def current(self) -> CsvTable:
        """The table a new baseline would freeze."""

    @abstractmethod
    def list(self) -> list[Manifest]: ...

    @abstractmethod
    def write(self, manifest: Manifest, table: CsvTable) -> None: ...

    @abstractmethod
    def read(self, manifest: Manifest) -> CsvTable: ...

    @abstractmethod
    def where(self, manifest: Manifest) -> str:
        """Phrase for the creation message, such as 'as tag baseline/SRR'."""

    @abstractmethod
    def add_signoff(self, manifest: Manifest, record: SignOff) -> str:
        """Record a sign-off beside the baseline and return the phrase for where it went."""

    @abstractmethod
    def signoffs(self, manifest: Manifest) -> list[CheckedSignOff]:
        """The baseline's sign-offs, oldest first, each checked the way this store can check it."""


class GitStore(BaselineStore):
    def __init__(self, input_path: Path, config: dict[str, Any], read_file: TableReader, warn: Callable[[str], None]):
        super().__init__(input_path, config, read_file, warn)
        self.prefix = config["baselines"]["git"]["tag_prefix"]

    @cached_property
    def root(self) -> Path:
        directory = self.input_path.resolve().parent
        try:
            return Path(run_git(directory, "rev-parse", "--show-toplevel").decode("utf-8").strip())
        except InputError as exc:
            raise InputError(f"{self.input_path} is not inside a git work tree: {exc}") from exc

    @cached_property
    def source(self) -> str:  # type: ignore[override]
        tracked = run_git(self.root, "ls-files", "--full-name", "--", str(self.input_path.resolve())).decode("utf-8")
        paths = [line for line in tracked.splitlines() if line]
        if not paths:
            raise InputError(f"{self.input_path} is not tracked by git; commit it before creating a baseline")
        return paths[0]

    def current(self) -> CsvTable:
        if run_git(self.root, "status", "--porcelain", "--", self.source).strip():
            raise InputError(f"{self.input_path} has uncommitted changes; commit them before creating a baseline")
        return self._read_at("HEAD", self.source)

    def _read_at(self, rev: str, source: str) -> CsvTable:
        name = Path(source).name
        spec = f"{rev}:{source}"
        if is_xlsx(name):
            blob = run_git(self.root, "cat-file", "blob", spec)
            with tempfile.TemporaryDirectory() as folder:
                copy = Path(folder) / name
                copy.write_bytes(blob)
                return self.read_file(copy)
        encoding = self.config["csv"]["encoding"]
        label = f"{name} @ {rev}"
        try:
            text = run_git(self.root, "cat-file", "--filters", spec).decode(encoding)
        except (UnicodeError, LookupError) as exc:
            raise InputError(f"{label}: cannot decode as {encoding}: {exc}") from exc
        return read_csv_source(CsvSource(label, text, Path(source)), self.config)

    def _ref(self, manifest: Manifest) -> str:
        return f"{self.prefix}{manifest.name}"

    def list(self) -> list[Manifest]:
        listing = run_git(
            self.root, "for-each-ref", "--format=%(refname)%00%(objecttype)%00%(contents)%01", f"refs/tags/{self.prefix}"
        ).decode("utf-8", "replace")
        found = []
        for record in listing.split("\x01"):
            if not record.strip():
                continue
            ref, kind, contents = record.lstrip("\n").split("\x00", 2)
            try:
                if kind != "tag":
                    raise ValueError("not an annotated tag")
                _, _, body = contents.partition("\n\n")
                manifest = Manifest.from_dict(json.JSONDecoder().raw_decode(body.lstrip())[0])
                if ref != f"refs/tags/{self._ref(manifest)}":
                    raise ValueError("tag name does not match its manifest")
            except (ValueError, InputError) as exc:
                self.warn(f"ignoring tag {ref.removeprefix('refs/tags/')}: {exc}")
                continue
            found.append(manifest)
        return found

    def write(self, manifest: Manifest, table: CsvTable) -> None:
        message = f"ReqTable baseline {manifest.name}\n\n{json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False)}\n"
        with tempfile.TemporaryDirectory() as folder:
            message_file = Path(folder) / "message"
            message_file.write_text(message, encoding="utf-8")
            run_git(self.root, "tag", "-a", self._ref(manifest), "-F", str(message_file), "HEAD")

    def read(self, manifest: Manifest) -> CsvTable:
        return self._read_at(f"refs/tags/{self._ref(manifest)}^{{commit}}", manifest.source)

    def where(self, manifest: Manifest) -> str:
        return f"as tag {self._ref(manifest)}"

    def add_signoff(self, manifest: Manifest, record: SignOff) -> str:
        stem = f"{SIGNOFF_PREFIX}{manifest.name}/{slug(record.role)}/"
        if not slug(record.role) or not slug(record.user):
            raise InputError("a sign-off needs a role and a user that contain letters or digits")
        taken = set(
            run_git(self.root, "for-each-ref", "--format=%(refname:short)", f"refs/tags/{stem}").decode().split()
        )
        base = f"{stem}{slug(record.user)}"
        name, number = base, 1
        while name in taken:
            number += 1
            name = f"{base}-{number}"
        commit = run_git(self.root, "rev-parse", f"refs/tags/{self._ref(manifest)}^{{commit}}").decode().strip()
        message = (
            f"ReqTable sign-off {record.baseline} {record.role} {record.decision}\n\n"
            f"{json.dumps(record.to_dict(), indent=2, ensure_ascii=False)}\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            message_file = Path(folder) / "message"
            message_file.write_text(message, encoding="utf-8")
            try:
                run_git(self.root, "tag", "-s", name, "-F", str(message_file), commit)
            except InputError as exc:
                raise InputError(
                    f"{exc}\nSign-off tags must be signed. Configure a signing key for git, either GPG "
                    "(user.signingkey) or SSH (gpg.format ssh and user.signingkey), then try again."
                ) from exc
        return f"as tag {name}"

    def signoffs(self, manifest: Manifest) -> list[CheckedSignOff]:
        commit = run_git(self.root, "rev-parse", f"refs/tags/{self._ref(manifest)}^{{commit}}").decode().strip()
        listing = run_git(
            self.root, "for-each-ref", "--format=%(refname)%00%(objecttype)%00%(*objectname)%00%(contents)%01",
            f"refs/tags/{SIGNOFF_PREFIX}{manifest.name}/",
        ).decode("utf-8", "replace")
        found = []
        for entry in listing.split("\x01"):
            if not entry.strip():
                continue
            ref, kind, target, contents = entry.lstrip("\n").split("\x00", 3)
            try:
                if kind != "tag":
                    raise ValueError("not an annotated tag")
                _, _, body = contents.partition("\n\n")
                record = SignOff.from_dict(json.JSONDecoder().raw_decode(body.lstrip())[0])
            except ValueError as exc:
                self.warn(f"ignoring tag {ref.removeprefix('refs/tags/')}: {exc}")
                continue
            if record.baseline != manifest.name:
                continue
            verification, detail = self._verify_tag(ref)
            problems = []
            if target != commit:
                problems.append("the tag does not point at the baseline commit")
            if record.content_hash != manifest.content_hash:
                problems.append("its content hash differs from the baseline's")
            counts = verification == "good" and not problems
            reason = "; ".join(problems)
            found.append((record, ref, CheckedSignOff(record, verification, "; ".join(filter(None, (reason, detail))), counts)))
        found.sort(key=lambda item: (item[0].moment, _tag_number(item[1]), item[1]))
        return [checked for _, _, checked in found]

    def _verify_tag(self, ref: str) -> tuple[str, str]:
        try:
            completed = subprocess.run(["git", "-C", str(self.root), "verify-tag", ref], capture_output=True)
        except OSError as exc:
            raise InputError(f"cannot run git: {exc}") from exc
        detail = completed.stderr.decode("utf-8", "replace").strip()
        return classify_verification(completed.returncode, detail), detail


class FileStore(BaselineStore):
    def __init__(self, input_path: Path, config: dict[str, Any], read_file: TableReader, warn: Callable[[str], None]):
        super().__init__(input_path, config, read_file, warn)
        self.directory = input_path.parent / config["baselines"]["files"]["directory"]
        self.source = input_path.name

    def current(self) -> CsvTable:
        return self.read_file(self.input_path)

    def _folder(self, manifest: Manifest) -> Path:
        return self.directory / manifest.name

    def list(self) -> list[Manifest]:
        found = []
        if not self.directory.is_dir():
            return found
        for path in sorted(self.directory.rglob("manifest.json")):
            relative = path.parent.relative_to(self.directory)
            if any(part.startswith(".") for part in relative.parts):
                continue
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    stored.pop("signoffs", None)
                manifest = Manifest.from_dict(stored)
                if manifest.name != relative.as_posix():
                    raise ValueError("folder name does not match its manifest")
            except (OSError, ValueError, InputError) as exc:
                self.warn(f"ignoring {path}: {exc}")
                continue
            found.append(manifest)
        return found

    def write(self, manifest: Manifest, table: CsvTable) -> None:
        target = self._folder(manifest)
        if not target.resolve().is_relative_to(self.directory.resolve()):
            raise InputError(f"baseline name {manifest.name!r} would leave {self.directory}")
        if target.exists():
            raise InputError(f"baseline folder {target} already exists; baselines are never overwritten")
        staging = target.parent / f".{target.name}.staging"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir()
            records = [table.headers, *([row[header] for header in table.headers] for row in table.rows)]
            csv_text = block_to_csv(records, self.config["csv"]["delimiter"])
            (staging / "requirements.csv").write_bytes(("\ufeff" + csv_text).encode("utf-8"))
            shutil.copy2(self.input_path, staging / f"source{self.input_path.suffix}")
            (staging / "manifest.json").write_text(
                json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            os.rename(staging, target)
        except OSError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise OutputError(f"cannot write baseline folder {target}: {exc}") from exc

    def read(self, manifest: Manifest) -> CsvTable:
        path = self._folder(manifest) / "requirements.csv"
        config = {**self.config, "csv": {**self.config["csv"], "encoding": "utf-8-sig"}}
        return read_csv_source(CsvSource(f"{manifest.name} requirements.csv", None, path), config)

    def where(self, manifest: Manifest) -> str:
        return f"in {self._folder(manifest)}"

    def _manifest_path(self, manifest: Manifest) -> Path:
        return self._folder(manifest) / "manifest.json"

    def add_signoff(self, manifest: Manifest, record: SignOff) -> str:
        path = self._manifest_path(manifest)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InputError(f"cannot read {path}: {exc}") from exc
        data["signoffs"] = [*data.get("signoffs", []), record.to_dict()]
        atomic_write_text(str(path), json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return f"in {path}"

    def signoffs(self, manifest: Manifest) -> list[CheckedSignOff]:
        path = self._manifest_path(manifest)
        try:
            entries = json.loads(path.read_text(encoding="utf-8")).get("signoffs", [])
        except (OSError, ValueError) as exc:
            raise InputError(f"cannot read {path}: {exc}") from exc
        found = []
        for index, entry in enumerate(entries):
            try:
                record = SignOff.from_dict(entry)
            except ValueError as exc:
                self.warn(f"ignoring sign-off {index + 1} in {path}: {exc}")
                continue
            found.append(CheckedSignOff(record, "recorded", self._evidence_detail(manifest, record), True))
        return found

    def _evidence_detail(self, manifest: Manifest, record: SignOff) -> str:
        evidence = record.evidence
        if not evidence or "://" in evidence or Path(evidence).is_absolute():
            return ""
        found = (self._folder(manifest) / evidence).exists()
        return f"evidence {evidence} {'found' if found else 'not found'} in the baseline folder"


def open_store(
    input_path: str | Path,
    config: dict[str, Any],
    read_file: TableReader,
    warn: Callable[[str], None] = _print_warning,
) -> BaselineStore:
    store = GitStore if config["baselines"]["store"] == "git" else FileStore
    return store(Path(input_path), config, read_file, warn)


def require_scope_args(gate: Gate, system: str | None, config: dict[str, Any]) -> None:
    if gate.scope == "system":
        if not system:
            raise ConfigError(f"gate {gate.id} is system-scoped; give --system with a System ID")
        if not config["traceability"]:
            raise ConfigError("system-scoped baselines need --traceability")
    elif system:
        raise ConfigError(f"gate {gate.id} covers the whole table; --system applies only to system-scoped gates")


def require_system_record(table: CsvTable, system: str | None) -> None:
    if system is None:
        return
    record = table.by_id.get(system)
    if record is None or record_type(record) != "System":
        raise InputError(f"{system!r} is not a System record in {table.label}")


def create_baseline(
    store: BaselineStore, config: dict[str, Any], gate_id: str, system: str | None, waivers: Sequence[Waiver] = ()
) -> Manifest:
    gate = find_gate(config, gate_id)
    require_scope_args(gate, system, config)
    table = store.current()
    id_column = config["id_column"]
    require_system_record(table, system)
    status_columns = config["baselines"]["status_columns"]
    digest = content_hash(
        table.headers, select_scope(table.rows, id_column, system, gate.includes),
        system, gate.includes, gate.captures_status, status_columns,
    )
    name, supersedes = next_name(store.list(), gate.id, system)
    manifest = Manifest(
        name=str(name), gate=gate.id, supersedes=supersedes, system=system, includes=list(gate.includes),
        captures_status=gate.captures_status, status_columns=list(status_columns), content_hash=digest,
        source=store.source, created=generation_time(), created_by=current_user(store.input_path.resolve().parent),
        waivers=tuple(waivers),
    )
    store.write(manifest, table)
    return manifest


def gate_roles(config: dict[str, Any], gate_id: str) -> list[dict[str, Any]]:
    for gate in config["gates"]:
        if gate["id"] == gate_id:
            return list(gate.get("signoff", []))
    return []


def recompute_hash(store: BaselineStore, id_column: str, manifest: Manifest) -> tuple[CsvTable, list[dict[str, str]], str]:
    table = store.read(manifest)
    rows = select_scope(table.rows, id_column, manifest.system, manifest.includes)
    digest = content_hash(
        table.headers, rows, manifest.system, manifest.includes, manifest.captures_status, manifest.status_columns
    )
    return table, rows, digest


def load_baselines(
    store: BaselineStore, config: dict[str, Any], requested: Iterable[str], warn: Callable[[str], None] = _print_warning
) -> list[dict[str, Any]]:
    manifests = store.list()
    gates = {gate["id"]: Gate.from_config(gate) for gate in config["gates"]}
    id_column = config["id_column"]
    chosen: dict[str, Manifest] = {}
    for name in requested:
        found = resolve(name, manifests)
        chosen.setdefault(found.name, found)
    entries = []
    for found in chosen.values():
        table, rows, digest = recompute_hash(store, id_column, found)
        hash_ok = digest == found.content_hash
        if not hash_ok:
            warn(f"baseline {found.name} does not match its recorded hash")
        gate = gates.get(found.gate)
        checked = store.signoffs(found)
        entries.append({
            "name": found.name,
            "gate": found.gate,
            "gateName": gate.name if gate else found.gate,
            "produces": gate.produces if gate else "",
            "system": found.system,
            "created": found.created,
            "createdBy": found.created_by,
            "hash": found.content_hash,
            "hashOk": hash_ok,
            "includes": found.includes,
            "capturesStatus": found.captures_status,
            "statusColumns": found.status_columns,
            "source": found.source,
            "headers": table.headers,
            "rows": rows,
            "signoffs": [item.to_dict() for item in checked],
            "approval": approval_status(gate_roles(config, found.gate), checked),
            "waivers": [waiver.to_dict() for waiver in found.waivers],
        })
    return entries


def build_controls(store: BaselineStore, config: dict[str, Any]) -> dict[str, Any] | None:
    """The controlling baseline row of every baselined record, or None when there is nothing to control.

    A record's controlling baseline is the latest created one whose scope holds it. Among baselines created at
    the same moment the later gate, then the higher number, controls, and the list puts it first because the
    report's checkChanges keeps the first of equal creation times.
    """
    if not config["baselines"]["change_control"]:
        return None
    try:
        manifests = store.list()
    except ReqtableError:
        return None
    if not manifests:
        return None
    order = {gate["id"]: index for index, gate in enumerate(config["gates"])}
    manifests.sort(key=lambda m: (m.created, -order.get(m.gate, len(order)), -m.number, m.name))
    id_column = config["id_column"]
    records: dict[str, dict[str, Any]] = {}
    created: dict[str, str] = {}
    try:
        for manifest in manifests:
            table = store.read(manifest)
            if config["traceability"]:
                table, _ = prepare_trace_table(table, config)
            for row in select_scope(table.rows, id_column, manifest.system, manifest.includes):
                record_id = row[id_column].strip()
                if record_id not in records or manifest.created > created[record_id]:
                    records[record_id] = {"baseline": manifest.name, "row": row}
                    created[record_id] = manifest.created
    except ReqtableError as exc:
        store.warn(f"change control is off: {exc}")
        return None
    return {
        "baselines": [
            {"name": m.name, "created": m.created, "system": m.system, "includes": m.includes,
             "capturesStatus": m.captures_status, "statusColumns": m.status_columns}
            for m in manifests
        ],
        "records": records,
    }
