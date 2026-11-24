"""Persistent cache of successfully analyzed video file signatures."""

import json
import os
from pathlib import Path


APP_NAME = "AI-Video-Quality-Compliance-Checker"


def default_cache_path():
    root = Path(os.getenv("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return root / APP_NAME / "scan_cache.json"


def _volume_identity(root):
    """Use a Windows volume serial so a drive letter change won't invalidate cache."""
    root = Path(root).resolve()
    if os.name == "nt":
        try:
            import ctypes
            volume_root = str(Path(root.anchor))
            serial = ctypes.c_uint32()
            max_component = ctypes.c_uint32()
            flags = ctypes.c_uint32()
            fs_name = ctypes.create_unicode_buffer(261)
            label = ctypes.create_unicode_buffer(261)
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                volume_root, label, len(label), ctypes.byref(serial),
                ctypes.byref(max_component), ctypes.byref(flags), fs_name, len(fs_name),
            )
            if ok:
                return f"volume-{serial.value:08x}"
        except (AttributeError, OSError, TypeError):
            pass
    return str(root)


class ScanCache:
    def __init__(self, path=None):
        self.path = Path(path) if path else default_cache_path()
        try:
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.entries, dict):
                self.entries = {}
        except (OSError, json.JSONDecodeError):
            self.entries = {}

    @staticmethod
    def signature(root, file_path):
        root = Path(root).resolve()
        file_path = Path(file_path).resolve()
        try:
            relative = file_path.relative_to(root).as_posix().casefold()
        except ValueError:
            relative = file_path.as_posix().casefold()
        stat = file_path.stat()
        identity = _volume_identity(root)
        return f"{identity}|{relative}", f"{stat.st_size}:{stat.st_mtime_ns}"

    def is_unchanged(self, root, file_path):
        try:
            key, signature = self.signature(root, file_path)
        except OSError:
            return False
        return self.entries.get(key) == signature

    def mark_processed(self, root, file_path):
        try:
            key, signature = self.signature(root, file_path)
        except OSError:
            return False
        self.entries[key] = signature
        self._save()
        return True

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")
        temporary.replace(self.path)
