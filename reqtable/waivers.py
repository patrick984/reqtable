from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from .core import ConfigError

_WAIVER_TYPES: dict[str, Any] = {"check": str, "reason": str, "user": str, "date": str, "failing": list}


@dataclass(frozen=True)
class Waiver:
    check: str
    reason: str
    user: str
    date: str
    failing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "failing": list(self.failing)}

    @classmethod
    def from_dict(cls, data: Any) -> Waiver:
        if not isinstance(data, dict) or set(data) != set(_WAIVER_TYPES):
            raise ValueError("waiver has the wrong keys")
        for key, kind in _WAIVER_TYPES.items():
            if not isinstance(data[key], kind):
                raise ValueError(f"waiver {key} has the wrong type")
        if not data["reason"].strip():
            raise ValueError("waiver reason is empty")
        if not all(isinstance(item, str) for item in data["failing"]):
            raise ValueError("waiver failing must hold strings")
        return cls(data["check"], data["reason"], data["user"], data["date"], tuple(data["failing"]))


def split_ids(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(part.strip() for value in values for part in value.split(",") if part.strip()))


def describe_failure(check: dict[str, Any]) -> str:
    if check["error"]:
        return f"{check['id']} cannot be evaluated ({check['error']}): {check['description']}"
    return f"{check['id']} fails ({len(check['failing'])} of {check['total']}): {check['description']}"


def records(count: int) -> str:
    return f"{count} record" if count == 1 else f"{count} records"


def plan_waivers(
    result: dict[str, Any], ids: Sequence[str], reasons: Sequence[str], user: str, date: str
) -> list[Waiver]:
    """Validate --waive against the evaluation and build the records. Raises ConfigError naming the first problem."""
    if not ids:
        return []
    if not reasons or any(not reason.strip() for reason in reasons):
        raise ConfigError("--waive needs --reason with the grounds for the waiver")
    if len(reasons) not in (1, len(ids)):
        raise ConfigError(
            f"give one --reason for all waived checks, or one per check in the order they are named "
            f"({len(ids)} checks, {len(reasons)} reasons)"
        )
    checks = {check["id"]: check for check in result["checks"]}
    for check_id in ids:
        check = checks.get(check_id)
        if check is None:
            raise ConfigError(f"cannot waive {check_id!r}: gate {result['gate']} has no such check")
        if check["enforcement"] != "strict":
            raise ConfigError(f"cannot waive {check_id}: it is advisory and does not block")
        if not check["error"] and not check["failing"]:
            raise ConfigError(f"cannot waive {check_id}: it is not failing")
    paired = list(reasons) if len(reasons) == len(ids) else [reasons[0]] * len(ids)
    return [
        Waiver(check_id, reason.strip(), user, date, tuple(checks[check_id]["failing"]))
        for check_id, reason in zip(ids, paired)
    ]
