import tempfile
import unittest
from pathlib import Path

from app.scan_cache import ScanCache


class ScanCacheTests(unittest.TestCase):
    def test_processed_file_is_skipped_when_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "usb"
            root.mkdir()
            video = root / "clip.mp4"
            video.write_bytes(b"video-data")
            cache = ScanCache(Path(directory) / "cache.json")
            self.assertFalse(cache.is_unchanged(root, video))
            self.assertTrue(cache.mark_processed(root, video))
            self.assertTrue(cache.is_unchanged(root, video))

    def test_modified_file_is_scanned_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "usb"
            root.mkdir()
            video = root / "clip.mp4"
            video.write_bytes(b"first")
            cache = ScanCache(Path(directory) / "cache.json")
            cache.mark_processed(root, video)
            video.write_bytes(b"updated-content")
            self.assertFalse(cache.is_unchanged(root, video))


if __name__ == "__main__":
    unittest.main()
