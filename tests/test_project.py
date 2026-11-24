import json
import tempfile
import unittest
from pathlib import Path

from app.analyzer import _frame_rate
from app.config import ComplianceRules, load_rules, save_rules


class ProjectTests(unittest.TestCase):
    def test_frame_rate(self):
        self.assertAlmostEqual(_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(_frame_rate("25/1"), 25.0)
        self.assertEqual(_frame_rate("0/0"), 0)

    def test_visual_rules_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            rules = ComplianceRules(maximum_hand_absence_seconds=45, minimum_average_brightness=70)
            save_rules(rules, path)
            loaded = load_rules(path)
            self.assertEqual(loaded.maximum_hand_absence_seconds, 45)
            self.assertEqual(loaded.minimum_average_brightness, 70)

    def test_legacy_duration_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps({"minimum_width": 1920, "maximum_duration_seconds": 10}), encoding="utf-8")
            rules = load_rules(path)
            self.assertEqual(rules.maximum_hand_absence_seconds, 60)
            self.assertFalse(hasattr(rules, "maximum_duration_seconds"))


if __name__ == "__main__":
    unittest.main()
