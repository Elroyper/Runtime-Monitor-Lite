from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ACTION_CANONICALIZATION = {
    "allow": "ALLOW",
    "alert": "ALERT",
    "recommend_block": "RECOMMEND_BLOCK",
    "recommend_external_approval": "RECOMMEND_EXTERNAL_APPROVAL",
    "block": "BLOCK",
    "external_approval": "EXTERNAL_APPROVAL",
}


def canonicalize_action(action: str) -> str:
    """Convert config enum to canonical storage enum."""
    if not isinstance(action, str):
        raise ValueError("Unknown action: non-string")

    normalized = action.strip()
    if not normalized:
        raise ValueError("Unknown action: empty")

    if normalized in ACTION_CANONICALIZATION.values():
        return normalized

    key = normalized.lower()
    if key in ACTION_CANONICALIZATION:
        return ACTION_CANONICALIZATION[key]

    raise ValueError(f"Unknown action: {action}")


@dataclass(slots=True)
class EventRecord:
    event_id: str
    framework: str
    session_id: str | None
    turn_id: int | None
    event_type_raw: str
    event_type_norm: str
    ts: str | None
    payload: dict[str, Any] = field(default_factory=dict)
    event_quality: str = "full"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
