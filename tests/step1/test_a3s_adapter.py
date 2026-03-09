import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from runtime_monitor_lite.storage.jsonl_sink import JsonlSink
from runtime_monitor_lite.supervision.a3s_adapter import (
    A3SAdapter,
    DEFAULT_HOOK_SPECS,
    StreamTimeoutError,
)


class FakeSession:
    def __init__(self, events):
        self.events = list(events)
        self.registered_hooks = []

    async def stream(self, _prompt):
        for item in self.events:
            await asyncio.sleep(0)
            yield item

    def register_hook(self, hook_id, event_type, matcher=None, config=None):
        self.registered_hooks.append((hook_id, event_type, matcher, config))


class SlowFirstEventSession(FakeSession):
    async def stream(self, _prompt):
        await asyncio.sleep(0.05)
        yield {
            "event_type": "start",
            "session_id": "s1",
            "turn_id": 1,
            "ts": "2026-03-09T00:00:00Z",
        }


class SlowSecondEventSession(FakeSession):
    async def stream(self, _prompt):
        yield {
            "event_type": "start",
            "session_id": "s1",
            "turn_id": 1,
            "ts": "2026-03-09T00:00:00Z",
        }
        await asyncio.sleep(0.05)
        yield {
            "event_type": "end",
            "session_id": "s1",
            "turn_id": 1,
            "ts": "2026-03-09T00:00:01Z",
        }


class A3SAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_collect_stream_writes_events_and_stops_on_end(self):
        adapter = A3SAdapter()
        fake_session = FakeSession(
            [
                {"event_type": "start", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:00Z"},
                {"event_type": "tool_start", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:01Z"},
                {"event_type": "end", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:02Z"},
                {"event_type": "text_delta", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:03Z"},
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "events.jsonl"
            sink = JsonlSink(sink_path)
            summary = await adapter.collect_stream(fake_session, "hello", sink)

            lines = sink_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(summary.total_events, 3)
            self.assertEqual(len(lines), 3)
            self.assertIn("SESSION_END", summary.norm_event_counts)

    async def test_collect_stream_respects_max_events(self):
        adapter = A3SAdapter()
        fake_session = FakeSession(
            [
                {"event_type": "turn_start", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:00Z"},
                {"event_type": "tool_start", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:01Z"},
                {"event_type": "tool_end", "session_id": "s1", "turn_id": 1, "ts": "2026-03-09T00:00:02Z"},
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "events.jsonl"
            sink = JsonlSink(sink_path)
            summary = await adapter.collect_stream(fake_session, "hello", sink, max_events=2)
            self.assertEqual(summary.total_events, 2)

    def test_register_default_hooks(self):
        adapter = A3SAdapter()
        fake_session = FakeSession([])
        hook_ids = adapter.register_default_hooks(fake_session, hook_prefix="demo")
        self.assertEqual(len(hook_ids), len(DEFAULT_HOOK_SPECS))
        self.assertEqual(len(fake_session.registered_hooks), len(DEFAULT_HOOK_SPECS))
        self.assertTrue(all(hook_id.startswith("demo_") for hook_id in hook_ids))

    def test_collect_hook_event_writes_single_event(self):
        adapter = A3SAdapter()
        raw_event = {
            "event_type": "post_response",
            "session_id": "s3",
            "turn_id": 2,
            "ts": "2026-03-09T00:00:00Z",
            "text": "ok",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "hook.jsonl"
            sink = JsonlSink(sink_path)
            adapter.collect_hook_event(raw_event, sink)
            payload = json.loads(sink_path.read_text(encoding="utf-8").strip())
            self.assertEqual(payload["event_type_norm"], "MODEL_RESPONSE")
            self.assertEqual(payload["event_quality"], "full")

    async def test_collect_stream_first_event_timeout(self):
        adapter = A3SAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "events.jsonl"
            sink = JsonlSink(sink_path)
            with self.assertRaises(StreamTimeoutError) as ctx:
                await adapter.collect_stream(
                    SlowFirstEventSession([]),
                    "hello",
                    sink,
                    first_event_timeout_seconds=0.01,
                )
            self.assertEqual(ctx.exception.stage, "first_event")
            self.assertEqual(ctx.exception.collected_events, 0)

    async def test_collect_stream_per_event_timeout(self):
        adapter = A3SAdapter()
        with tempfile.TemporaryDirectory() as tmpdir:
            sink_path = Path(tmpdir) / "events.jsonl"
            sink = JsonlSink(sink_path)
            with self.assertRaises(StreamTimeoutError) as ctx:
                await adapter.collect_stream(
                    SlowSecondEventSession([]),
                    "hello",
                    sink,
                    first_event_timeout_seconds=0.2,
                    per_event_timeout_seconds=0.01,
                )
            self.assertEqual(ctx.exception.stage, "next_event")
            self.assertEqual(ctx.exception.collected_events, 1)


if __name__ == "__main__":
    unittest.main()
