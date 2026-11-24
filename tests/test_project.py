import unittest

from app.analyzer import _frame_rate


class ProjectTests(unittest.TestCase):
    def test_frame_rate(self):
        self.assertAlmostEqual(_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(_frame_rate("25/1"), 25.0)
        self.assertEqual(_frame_rate("0/0"), 0)


if __name__ == "__main__":
    unittest.main()
