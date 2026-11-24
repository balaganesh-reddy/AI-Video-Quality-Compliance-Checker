import json
import tempfile
import unittest
from pathlib import Path

from app.analyzer import _frame_rate, evaluate_visual_metrics
from app.config import ComplianceRules, load_rules, save_rules


class ProjectTests(unittest.TestCase):
    def test_frame_rate(self):
        self.assertAlmostEqual(_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(_frame_rate("25/1"), 25.0)
        self.assertEqual(_frame_rate("0/0"), 0)

    def test_rules_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            rules = ComplianceRules(maximum_phone_use_seconds=90, minimum_wrist_visible_frame_ratio=0.95)
            save_rules(rules, path)
            loaded = load_rules(path)
            self.assertEqual(loaded.maximum_phone_use_seconds, 90)
            self.assertEqual(loaded.minimum_wrist_visible_frame_ratio, 0.95)

    def test_phone_use_over_two_minutes_fails(self):
        result = evaluate_visual_metrics(
            wrist_visible_ratio=1.0, phone_use_seconds=121,
            well_lit_ratio=1.0, rules=ComplianceRules(),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("phone use lasted" in issue for issue in result["issues"]))

    def test_phone_use_at_two_minutes_does_not_fail_by_duration_alone(self):
        result = evaluate_visual_metrics(
            wrist_visible_ratio=1.0, phone_use_seconds=120,
            well_lit_ratio=1.0, rules=ComplianceRules(),
        )
        self.assertEqual(result["status"], "PASS")

    def test_missing_wrist_visibility_fails(self):
        result = evaluate_visual_metrics(
            wrist_visible_ratio=0.89, phone_use_seconds=0,
            well_lit_ratio=1.0, rules=ComplianceRules(),
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("both wrists" in issue for issue in result["issues"]))

    def test_old_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            path.write_text(json.dumps({"minimum_width": 1920, "maximum_duration_seconds": 10}), encoding="utf-8")
            rules = load_rules(path)
            self.assertEqual(rules.maximum_phone_use_seconds, 120)
            self.assertFalse(hasattr(rules, "maximum_duration_seconds"))


if __name__ == "__main__":
    unittest.main()
