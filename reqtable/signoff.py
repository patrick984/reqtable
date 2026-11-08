from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable, Sequence

from .core import ConfigError, InputError

SIGNOFF_FORMAT = "reqtable-signoff/1"
DECISIONS = ("Reviewed", "Changes requested", "Approved", "Rejected")
POSITIVE = frozenset({"Reviewed", "Approved"})
VIAS = ("cli", "package")
VERIFICATIONS = ("good", "unsigned", "bad", "unverifiable", "recorded")

_RECORD_TYPES: dict[str, Any] = {
    "format": str, "baseline": str, "role": str, "user": str, "decision": str, "date": str,
    "content_hash": str, "note": str, "evidence": (str, type(None)), "via": str, "recorded_by": str,
}


def validate_roles(roles: Any, where: str) -> None:
    if not isinstance(roles, list):
        raise ConfigError(f"{where}.signoff must be an array")
    seen: set[str] = set()
    for index, entry in enumerate(roles):
        spot = f"{where}.signoff[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"role", "min"}:
            raise ConfigError(f"{spot} must be an object with 'role' and 'min'")
        role, minimum = entry["role"], entry["min"]
        if not isinstance(role, str) or not role.strip():
            raise ConfigError(f"{spot}.role must be a non-empty string")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise ConfigError(f"{spot}.min must be a whole number of at least 1")
        if role.strip().casefold() in seen:
            raise ConfigError(f"{spot}: duplicate role {role!r}")
        seen.add(role.strip().casefold())


def parse_date(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError(f"invalid sign-off date {text!r}: expected an ISO date with offset") from exc
    return moment if moment.tzinfo else moment.astimezone()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass(frozen=True)
class SignOff:
    baseline: str
    role: str
    user: str
    decision: str
    date: str
    content_hash: str
    note: str = ""
    evidence: str | None = None
    via: str = "cli"
    recorded_by: str = ""
    format: str = SIGNOFF_FORMAT

    def to_dict(self) -> dict[str, Any]:
        fields = asdict(self)
        return {key: fields[key] for key in _RECORD_TYPES}

    @classmethod
    def from_dict(cls, data: Any) -> SignOff:
        if not isinstance(data, dict) or set(data) != set(_RECORD_TYPES):
            raise ValueError("sign-off has the wrong keys")
        for key, kind in _RECORD_TYPES.items():
            if not isinstance(data[key], kind):
                raise ValueError(f"sign-off {key} has the wrong type")
        if data["format"] != SIGNOFF_FORMAT:
            raise ValueError(f"unsupported sign-off format {data['format']!r}")
        if data["decision"] not in DECISIONS:
            raise ValueError(f"unknown decision {data['decision']!r}")
        if data["via"] not in VIAS:
            raise ValueError(f"unknown via {data['via']!r}")
        if not data["role"].strip() or not data["user"].strip():
            raise ValueError("sign-off needs a role and a user")
        try:
            parse_date(data["date"])
        except InputError as exc:
            raise ValueError(str(exc)) from exc
        return cls(**data)

    @property
    def moment(self) -> datetime:
        return parse_date(self.date)

    def key(self) -> tuple[str, str, str, str, str]:
        return (self.baseline, self.role.casefold(), self.user.casefold(), self.decision, self.moment.isoformat())


@dataclass(frozen=True)
class CheckedSignOff:
    """A sign-off with what its store could establish about it. Only counting ones feed approval."""

    record: SignOff
    verification: str
    detail: str
    counts: bool

    def to_dict(self) -> dict[str, Any]:
        return {**self.record.to_dict(), "verification": self.verification, "detail": self.detail, "counts": self.counts}


def approval_status(roles: Sequence[dict[str, Any]], signoffs: Iterable[CheckedSignOff]) -> dict[str, Any]:
    """Each user's latest counting decision decides; a role is complete at `min` distinct positive users."""
    latest: dict[str, dict[str, SignOff]] = {}
    ordered = sorted(enumerate(s for s in signoffs if s.counts), key=lambda pair: (pair[1].record.moment, pair[0]))
    for _, checked in ordered:
        record = checked.record
        latest.setdefault(record.role.casefold(), {})[record.user.casefold()] = record
    statuses = []
    for entry in roles:
        decided = latest.get(entry["role"].casefold(), {}).values()
        statuses.append({
            "role": entry["role"],
            "min": entry["min"],
            "positive": [r.user for r in decided if r.decision in POSITIVE],
            "negative": [r.user for r in decided if r.decision not in POSITIVE],
        })
    approved = bool(statuses) and all(len(status["positive"]) >= status["min"] for status in statuses)
    return {"approved": approved, "roles": statuses}


def match_role(roles: Sequence[dict[str, Any]], requested: str, gate: str) -> str:
    for entry in roles:
        if entry["role"].casefold() == requested.strip().casefold():
            return entry["role"]
    known = ", ".join(entry["role"] for entry in roles) or "none"
    raise InputError(f"gate {gate} has no sign-off role {requested!r}; its roles: {known}")
