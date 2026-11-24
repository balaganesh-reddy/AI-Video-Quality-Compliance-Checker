"""Windows USB and video scanning helpers."""

import ctypes
from pathlib import Path

import psutil

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".m4v", ".mpeg", ".mpg", ".webm",
}


def get_removable_drives():
    """Return removable-drive root paths on Windows."""
    drives = []
    for partition in psutil.disk_partitions(all=False):
        path = partition.mountpoint
        if not path:
            continue
        if _drive_type(path) == 2 or "removable" in partition.opts.lower():
            drives.append(path)
    return sorted(set(drives), key=str.lower)


def _drive_type(path):
    """GetDriveTypeW: 2 = removable media."""
    try:
        drive = str(Path(path).anchor or path)
        return ctypes.windll.kernel32.GetDriveTypeW(drive)
    except Exception:
        return 0


def find_videos(folder):
    """Recursively find supported video files below a USB folder."""
    root = Path(folder)
    if not root.exists():
        return []
    return sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS),
        key=lambda p: str(p).lower(),
    )
