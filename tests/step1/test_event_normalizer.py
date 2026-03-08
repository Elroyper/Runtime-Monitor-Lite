from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from runtime_monitor_lite.supervision.event_normalizer import EventNormalizer


class EventNormalizerTest(unittest.TestCase):
    def test_normalize_known_event_maps_to_canonical(self):
        normalizer = EventNormalizer()
        raw_event = {
            "event_id": "evt_001",
            "event_type": "tool_start",
            "session_id": "sess_1",
            "turn_id": 3,
            "ts": "2026-03-09T10:00:00Z",
            "tool_name": "bash",
        }

        record = normalizer.normalize(raw_event)

        self.assertEqual(record.event_type_raw, "tool_start")
        self.assertEqual(record.event_type_norm, "TOOL_EXEC_START")
        self.assertEqual(record.event_quality, "full")
        self.assertEqual(record.session_id, "sess_1")
        self.assertEqual(record.turn_id, 3)

    def test_normalize_unknown_event_goes_to_unknown_raw_event(self):
        normalizer = EventNormalizer()
        raw_event = {
            "event_id": "evt_002",
            "event_type": "foo_bar_baz",
            "session_id": "sess_2",
            "turn_id": 1,
            "ts": "2026-03-09T10:00:01Z",
        }

        record = normalizer.normalize(raw_event)

        self.assertEqual(record.event_type_norm, "UNKNOWN_RAW_EVENT")
        self.assertEqual(record.event_quality, "full")

    def test_missing_required_fields_mark_partial_quality(self):
        normalizer = EventNormalizer()
        raw_event = SimpleNamespace(
            event_id="evt_003",
            event_type="turn_start",
            session_id="sess_3",
            # turn_id missing
            ts="2026-03-09T10:00:02Z",
        )

        record = normalizer.normalize(raw_event)

        self.assertEqual(record.event_type_norm, "TURN_START")
        self.assertIsNone(record.turn_id)
        self.assertEqual(record.event_quality, "partial")
