from __future__ import annotations

from typing import Any

from runtime_monitor_lite.supervision.event_normalizer import EventNormalizer
from runtime_monitor_lite.supervision.models import EventRecord


class A3SAdapter:
    """Minimal adapter for a3s stream/hook events."""

    def __init__(self, normalizer: EventNormalizer | None = None) -> None:
        self.normalizer = normalizer or EventNormalizer()

    def adapt_event(self, raw_event: Any) -> EventRecord:
        return self.normalizer.normalize(raw_event)

    async def collect_stream(self, session: Any, prompt: str, sink: Any) -> None:
        async for raw_event in session.stream(prompt):
            sink.write_event(self.adapt_event(raw_event))

    def collect_hook_event(self, raw_event: Any, sink: Any) -> None:
        sink.write_event(self.adapt_event(raw_event))
