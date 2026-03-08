from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from runtime_monitor_lite.supervision.models import canonicalize_action


class ActionCanonicalizationTest(unittest.TestCase):
    def test_action_canonicalization_maps_config_enum_to_storage_enum(self):
        self.assertEqual(canonicalize_action("allow"), "ALLOW")
        self.assertEqual(canonicalize_action("alert"), "ALERT")
        self.assertEqual(canonicalize_action("recommend_block"), "RECOMMEND_BLOCK")
        self.assertEqual(
            canonicalize_action("recommend_external_approval"),
            "RECOMMEND_EXTERNAL_APPROVAL",
        )
        self.assertEqual(canonicalize_action("block"), "BLOCK")
        self.assertEqual(canonicalize_action("external_approval"), "EXTERNAL_APPROVAL")

    def test_action_canonicalization_accepts_canonical_input(self):
        self.assertEqual(canonicalize_action("ALLOW"), "ALLOW")
        self.assertEqual(canonicalize_action("RECOMMEND_BLOCK"), "RECOMMEND_BLOCK")

    def test_action_canonicalization_rejects_unknown_action(self):
        with self.assertRaisesRegex(ValueError, "Unknown action"):
            canonicalize_action("drop_database")
