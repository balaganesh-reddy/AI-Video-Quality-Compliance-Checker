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

    def test_rules_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rules.json"
            save_rules(ComplianceRules(minimum_width=1920), path)
            loaded = load_rules(path)
            self.assertEqual(loaded.minimum_width, 1920)
            self.assertEqual(loaded.minimum_height, 720)


if __name__ == "__main__":
    unittest.main()
