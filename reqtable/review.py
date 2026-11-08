from __future__ import annotations

from pathlib import Path
from typing import Any

from .baselines import BaselineStore, Manifest, current_user, recompute_hash, resolve
from .core import ConfigError, InputError, generation_time
from .signoff import CheckedSignOff, SignOff, approval_status, match_decision, match_role


def gate_roles(config: dict[str, Any], gate_id: str) -> list[dict[str, Any]]:
    for gate in config["gates"]:
        if gate["id"] == gate_id:
            return list(gate.get("signoff", []))
    return []


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
