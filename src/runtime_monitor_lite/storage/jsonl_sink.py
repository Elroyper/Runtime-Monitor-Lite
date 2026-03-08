from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime_monitor_lite.supervision.models import EventRecord


class JsonlSink:
    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def write_event(self, event: EventRecord) -> None:
        self.write_dict(event.to_dict())

    def write_dict(self, payload: dict[str, Any]) -> None:
        with self.file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
