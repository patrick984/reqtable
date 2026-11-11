from __future__ import annotations

from pathlib import Path
from typing import Any

from .baselines import (
    BaselineStore, Manifest, current_user, gate_roles, load_baselines, recompute_hash, resolve,
)
from .core import (
    ConfigError, CsvTable, InputError, build_report_data, extract_report_json, generation_time,
)
from .signoff import (
    DECISIONS, SignOff, approval_status, match_decision, match_role, parse_date,
)


def resolve_baseline(store: BaselineStore, requested: str) -> Manifest:
    return resolve(requested, store.list())


def record_signoff(
    store: BaselineStore,
    config: dict[str, Any],
    manifest: Manifest,
    role: str,
    decision: str,
    user: str,
    note: str = "",
    evidence: str | None = None,
    via: str = "cli",
    date: str | None = None,
) -> tuple[SignOff, str]:
    roles = gate_roles(config, manifest.gate)
    record = SignOff(
        baseline=manifest.name,
        role=match_role(roles, role, manifest.gate),
        user=user.strip(),
        decision=match_decision(decision),
        date=date or generation_time(),
        content_hash=manifest.content_hash,
        note=note,
        evidence=evidence,
        via=via,
        recorded_by=current_user(store.input_path.resolve().parent),
    )
    if not record.user:
        raise ConfigError("the sign-off needs a user name")
    return record, store.add_signoff(manifest, record)


def require_intact(store: BaselineStore, config: dict[str, Any], manifest: Manifest) -> None:
    _, _, digest = recompute_hash(store, config["id_column"], manifest)
    if digest != manifest.content_hash:
        raise InputError(f"baseline {manifest.name} does not match its recorded hash; refusing to record against it")


def sign_off(
    store: BaselineStore, config: dict[str, Any], requested: str, role: str, decision: str,
    user: str | None, note: str, evidence: str | None,
) -> str:
    manifest = resolve_baseline(store, requested)
    require_intact(store, config, manifest)
    who = user or current_user(store.input_path.resolve().parent)
    record, where = record_signoff(store, config, manifest, role, decision, who, note, evidence)
    return f"Recorded {record.decision} by {record.user} as {record.role} for {manifest.name} {where}"


def _first_line(text: str) -> str:
    return text.splitlines()[0] if text else ""


def verify_baseline(store: BaselineStore, config: dict[str, Any], requested: str) -> tuple[list[str], bool]:
    manifest = resolve_baseline(store, requested)
    _, _, digest = recompute_hash(store, config["id_column"], manifest)
    hash_ok = digest == manifest.content_hash
    lines = [
        f"{manifest.name} {manifest.content_hash} "
        + ("content hash matches" if hash_ok else f"content hash DOES NOT MATCH (stored content hashes to {digest})")
    ]
    for waiver in manifest.waivers:
        lines.append(
            f"waived {waiver.check} by {waiver.user} on {waiver.date}: {waiver.reason} ({len(waiver.failing)} records)"
        )
    checked = store.signoffs(manifest)
    for item in checked:
        record = item.record
        verdict = "counts" if item.counts else "does not count"
        explained = item.detail and (not item.counts or item.verification == "recorded")
        why = f" ({_first_line(item.detail)})" if explained else ""
        lines.append(
            f"  {record.role}  {record.user}  {record.decision}  {record.date}  {item.verification}  {verdict}{why}"
        )
    if not checked:
        lines.append("  no sign-offs")
    status = approval_status(gate_roles(config, manifest.gate), checked)
    for entry in status["roles"]:
        have = len(entry["positive"])
        state = "complete" if have >= entry["min"] else "incomplete"
        names = f" ({', '.join(entry['positive'])})" if entry["positive"] else ""
        against = f"; against: {', '.join(entry['negative'])}" if entry["negative"] else ""
        lines.append(f"{entry['role']}: {have} of {entry['min']} needed, {state}{names}{against}")
    if not status["roles"]:
        lines.append(f"gate {manifest.gate} has no sign-off roles configured")
    approved = hash_ok and status["approved"]
    lines.append("approved" if approved else "not approved")
    return lines, approved


def previous_baseline(manifests: list[Manifest], config: dict[str, Any], manifest: Manifest) -> Manifest | None:
    order = [gate["id"] for gate in config["gates"]]
    if manifest.gate not in order:
        return None
    for gate_id in reversed(order[: order.index(manifest.gate)]):
        siblings = [m for m in manifests if m.gate == gate_id and m.system == manifest.system]
        if siblings:
            return max(siblings, key=lambda m: m.number)
    return None


def build_package(store: BaselineStore, config: dict[str, Any], requested: str, output_name: str) -> dict[str, Any]:
    manifests = store.list()
    manifest = resolve(requested, manifests)
    id_column = config["id_column"]
    table, rows, digest = recompute_hash(store, id_column, manifest)
    hash_ok = digest == manifest.content_hash
    if not hash_ok:
        store.warn(f"baseline {manifest.name} does not match its recorded hash")
    gate = next((entry for entry in config["gates"] if entry["id"] == manifest.gate), None)
    if gate is None:
        raise ConfigError(f"gate {manifest.gate} of baseline {manifest.name} is not configured")
    frozen = CsvTable(
        f"{manifest.name} (frozen)", manifest.source, table.headers, rows,
        [row[id_column].strip() for row in rows], {row[id_column].strip(): row for row in rows},
    )
    checks = {check["id"]: check["description"] for check in gate.get("checks", [])}
    previous = previous_baseline(manifests, config, manifest)
    embedded = load_baselines(store, config, [previous.name], store.warn) if previous else []
    gate_name = gate.get("name", gate["id"])
    package_config = {
        **config, "title": f"{gate_name} gate package: {manifest.name}", "document_mode": "review", "gates": [gate],
    }
    data = build_report_data(frozen, package_config, output_name, baselines=embedded)
    checked = store.signoffs(manifest)
    roles = gate_roles(config, manifest.gate)
    if previous:
        data["options"]["initialCompareWith"] = f"baseline:{previous.name}"
    data["decisions"] = []
    data["package"] = {
        "gate": {"id": gate["id"], "name": gate_name, "produces": gate.get("produces", ""), "scope": gate.get("scope", "table")},
        "baseline": {
            "name": manifest.name, "gate": manifest.gate, "system": manifest.system, "created": manifest.created,
            "createdBy": manifest.created_by, "hash": manifest.content_hash, "hashOk": hash_ok, "source": manifest.source,
        },
        "previous": previous.name if previous else None,
        "roles": roles,
        "signoffs": [item.to_dict() for item in checked],
        "approval": approval_status(roles, checked),
        "waivers": [
            {**waiver.to_dict(), "description": checks.get(waiver.check)} for waiver in manifest.waivers
        ],
        "decisionOptions": list(DECISIONS),
    }
    return data


def _package_decisions(path: str, data: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    package = data.get("package")
    baseline = package.get("baseline") if isinstance(package, dict) else None
    if not isinstance(baseline, dict) or not isinstance(baseline.get("name"), str) or not isinstance(baseline.get("hash"), str):
        raise InputError(f"{path}: not a gate package; generate one with --gate-package")
    decisions = data.get("decisions", [])
    if not isinstance(decisions, list):
        raise InputError(f"{path}: decisions must be a list")
    return baseline["name"], baseline["hash"], decisions


def import_decisions(store: BaselineStore, config: dict[str, Any], path: str) -> list[str]:
    data = extract_report_json(path)
    name, digest, decisions = _package_decisions(path, data)
    manifest = next((m for m in store.list() if m.name == name), None)
    if manifest is None:
        raise InputError(f"{path}: baseline {name!r} does not exist in this store")
    if manifest.content_hash != digest:
        raise InputError(f"{path}: package was made for a different {name} (hash {digest}); this store has {manifest.content_hash}")
    require_intact(store, config, manifest)
    roles = gate_roles(config, manifest.gate)
    pending = []
    for index, entry in enumerate(decisions, start=1):
        where = f"{path}: decision {index}"
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in ("role", "user", "decision", "date")):
            raise InputError(f"{where} needs role, user, decision and date")
        note = entry.get("note", "")
        if not isinstance(note, str):
            raise InputError(f"{where}: note must be text")
        try:
            pending.append((match_role(roles, entry["role"], manifest.gate), match_decision(entry["decision"]), entry, note))
        except ConfigError as exc:
            raise InputError(f"{where}: {exc}") from exc
        parse_date(entry["date"])
    seen = {item.record.key() for item in store.signoffs(manifest)}
    lines = []
    for role, decision, entry, note in pending:
        user, date = entry["user"].strip(), parse_date(entry["date"]).isoformat()
        label = f"{decision} by {user} as {role} on {date}"
        probe = SignOff(manifest.name, role, user, decision, date, manifest.content_hash)
        if probe.key() in seen:
            lines.append(f"skipped {label}: already recorded")
            continue
        _, where = record_signoff(
            store, config, manifest, role, decision, user, note, Path(path).name, via="package", date=date
        )
        seen.add(probe.key())
        lines.append(f"imported {label} {where}")
    return lines or [f"no decisions in {path}"]
