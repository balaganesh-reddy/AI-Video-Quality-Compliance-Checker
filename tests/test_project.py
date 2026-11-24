import tempfile
import unittest
from pathlib import Path

from app.analyzer import _frame_rate
from app.usb import VIDEO_EXTENSIONS, find_videos


class ProjectTests(unittest.TestCase):
    def test_frame_rate(self):
        self.assertAlmostEqual(_frame_rate("30000/1001"), 29.97, places=2)
        self.assertEqual(_frame_rate("25/1"), 25.0)
        self.assertEqual(_frame_rate("0/0"), 0)

    def test_mcap_is_supported(self):
        self.assertIn(".mcap", VIDEO_EXTENSIONS)

    def test_find_mcap_recursively(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            mcap = nested / "recording.mcap"
            mcap.write_bytes(b"mcap")
            found = find_videos(root)
            self.assertEqual(found, [mcap])


if __name__ == "__main__":
    unittest.main()
