from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime_monitor_lite.supervision.models import EventRecord


RAW_EVENT_TO_CANONICAL = {
    "pre_tool_use": "TOOL_PRECHECK",
    "tool_start": "TOOL_EXEC_START",
    "tool_end": "TOOL_EXEC_END",
    "post_response": "MODEL_RESPONSE",
    "on_error": "RUNTIME_ERROR",
    "error": "RUNTIME_ERROR",
    "session_start": "SESSION_START",
    "start": "SESSION_START",
    "turn_start": "TURN_START",
    "turn_end": "TURN_END",
    "session_end": "SESSION_END",
    "end": "SESSION_END",
    "external_task_pending": "EXTERNAL_TASK_PENDING",
    "external_task_completed": "EXTERNAL_TASK_COMPLETED",
    "confirmation_timeout": "CONFIRMATION_TIMEOUT",
}


class EventNormalizer:
    def normalize(self, raw_event: Any) -> EventRecord:
        event_type_raw = self._read(raw_event, "event_type") or self._read(raw_event, "type") or "UNKNOWN"
        event_type_norm = RAW_EVENT_TO_CANONICAL.get(event_type_raw, "UNKNOWN_RAW_EVENT")

        session_id = self._read(raw_event, "session_id")
        turn_id = self._read(raw_event, "turn_id")
        if turn_id is None:
            turn_id = self._read(raw_event, "turn")

        ts = self._read(raw_event, "ts")
        if ts is None:
            ts = self._read(raw_event, "timestamp")
        if ts is None:
            ts = datetime.now(timezone.utc).isoformat()

        event_id = self._read(raw_event, "event_id")
        if event_id is None:
            event_id = f"evt_{uuid4().hex}"

        payload = self._to_payload(raw_event)
        required = (session_id, turn_id, ts)
        event_quality = "full" if all(v is not None for v in required) else "partial"

        return EventRecord(
            event_id=str(event_id),
            framework="a3s",
            session_id=session_id,
            turn_id=self._to_int_or_none(turn_id),
            event_type_raw=str(event_type_raw),
            event_type_norm=event_type_norm,
            ts=str(ts) if ts is not None else None,
            payload=payload,
            event_quality=event_quality,
        )

    @staticmethod
    def _read(raw_event: Any, key: str) -> Any:
        if isinstance(raw_event, Mapping):
            return raw_event.get(key)
        return getattr(raw_event, key, None)

    @staticmethod
    def _to_payload(raw_event: Any) -> dict[str, Any]:
        if isinstance(raw_event, Mapping):
            return dict(raw_event)

        raw_dict = getattr(raw_event, "__dict__", None)
        if isinstance(raw_dict, dict):
            return dict(raw_dict)

        return {}

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
