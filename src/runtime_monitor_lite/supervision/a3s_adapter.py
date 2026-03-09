from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import Any

from runtime_monitor_lite.supervision.event_normalizer import EventNormalizer
from runtime_monitor_lite.supervision.models import EventRecord


DEFAULT_HOOK_SPECS = (
    ("pre_tool", "pre_tool_use", None, {"priority": 0}),
    ("post_tool", "post_tool_use", None, {"priority": 1, "async_execution": True}),
    ("pre_prompt", "pre_prompt", None, {"priority": 0}),
    ("post_response", "post_response", None, {"priority": 0}),
    ("generate_start", "generate_start", None, {"priority": 5}),
    ("generate_end", "generate_end", None, {"priority": 5}),
    ("on_error", "on_error", None, {"priority": 0, "async_execution": True}),
)


@dataclass(slots=True)
class StreamCollectionSummary:
    total_events: int
    raw_event_counts: dict[str, int]
    norm_event_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "raw_event_counts": self.raw_event_counts,
            "norm_event_counts": self.norm_event_counts,
        }


class StreamTimeoutError(TimeoutError):
    """Raised when stream iteration does not yield within timeout budget."""

    def __init__(self, *, stage: str, timeout_seconds: float, collected_events: int) -> None:
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        self.collected_events = collected_events
        super().__init__(
            f"stream {stage} timeout after {timeout_seconds:.1f}s (collected_events={collected_events})"
        )


class A3SAdapter:
    """Minimal adapter for a3s stream/hook events."""

    def __init__(self, normalizer: EventNormalizer | None = None) -> None:
        self.normalizer = normalizer or EventNormalizer()

    def adapt_event(self, raw_event: Any) -> EventRecord:
        return self.normalizer.normalize(raw_event)

    def register_default_hooks(self, session: Any, hook_prefix: str = "rml") -> list[str]:
        hook_ids: list[str] = []
        for suffix, event_type, matcher, config in DEFAULT_HOOK_SPECS:
            hook_id = f"{hook_prefix}_{suffix}"
            session.register_hook(hook_id, event_type, matcher=matcher, config=config)
            hook_ids.append(hook_id)
        return hook_ids

    async def collect_stream(
        self,
        session: Any,
        prompt: str,
        sink: Any,
        *,
        stop_event_types: set[str] | None = None,
        max_events: int | None = None,
        first_event_timeout_seconds: float | None = None,
        per_event_timeout_seconds: float | None = None,
    ) -> StreamCollectionSummary:
        stop_event_types = stop_event_types or {"end", "error"}
        raw_counter: Counter[str] = Counter()
        norm_counter: Counter[str] = Counter()
        total = 0

        stream = session.stream(prompt)
        stream_iter = stream.__aiter__()
        while True:
            is_first_event = total == 0
            stage = "first_event" if is_first_event else "next_event"
            timeout_seconds: float | None = (
                first_event_timeout_seconds if is_first_event else per_event_timeout_seconds
            )
            try:
                if timeout_seconds is None:
                    raw_event = await stream_iter.__anext__()
                else:
                    raw_event = await asyncio.wait_for(
                        stream_iter.__anext__(),
                        timeout=timeout_seconds,
                    )
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError as exc:
                raise StreamTimeoutError(
                    stage=stage,
                    timeout_seconds=float(timeout_seconds or 0.0),
                    collected_events=total,
                ) from exc

            record = self.adapt_event(raw_event)
            sink.write_event(record)
            raw_counter[record.event_type_raw] += 1
            norm_counter[record.event_type_norm] += 1
            total += 1

            if max_events is not None and total >= max_events:
                break
            if record.event_type_raw in stop_event_types:
                break

        return StreamCollectionSummary(
            total_events=total,
            raw_event_counts=dict(raw_counter),
            norm_event_counts=dict(norm_counter),
        )

    def collect_hook_event(self, raw_event: Any, sink: Any) -> None:
        sink.write_event(self.adapt_event(raw_event))
