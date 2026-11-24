from __future__ import annotations

import ctypes
import time
from pathlib import Path

import psutil


def _windows_drive_type(mount: Path, partition_opts: str) -> int:
    """Return a Windows drive type, preferring psutil's reliable mount flags."""
    options = partition_opts.lower().split(",")
    if "removable" in options:
        return 2  # DRIVE_REMOVABLE
    if "fixed" in options:
        return 3  # DRIVE_FIXED

    try:
        # mount.anchor already includes the trailing backslash (e.g. E:\\).
        root = mount.anchor or str(mount)
        return int(ctypes.windll.kernel32.GetDriveTypeW(root))
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def get_removable_drives(allowed_types=(2, 3), exclude=("C:\\",), only=()):
    found = []
    normalized_only = {str(item).rstrip("\\").lower() for item in only}
    normalized_exclude = {str(item).rstrip("\\").lower() for item in exclude}

    for partition in psutil.disk_partitions(all=False):
        mount = Path(partition.mountpoint)
        if not mount.exists():
            continue
        normalized = str(mount).rstrip("\\").lower()
        if normalized in normalized_exclude:
            continue
        if normalized_only and normalized not in normalized_only:
            continue

        drive_type = _windows_drive_type(mount, partition.opts)
        if drive_type in allowed_types:
            found.append(mount)
    return sorted(set(found), key=lambda item: str(item).lower())


def watch(config, callback):
    """Poll Windows drives and call callback(drive) after insertion settles."""
    usb = config
    settle_seconds = float(usb.get("settle_seconds", 5))
    exclude = tuple(usb.get("exclude_drives", ["C:\\"]))
    allowed_types = tuple(usb.get("drive_types", [2, 3]))
    only = tuple(usb.get("only_drives", []))

    # Keep this empty so drives already mounted when watch starts are processed.
    known = set()
    pending = {}
    while True:
        drives = get_removable_drives(allowed_types, exclude, only)
        current = {str(drive): drive for drive in drives}

        for drive_name, drive in current.items():
            if drive_name not in known and drive_name not in pending:
                print(f"Detected drive {drive} - waiting {settle_seconds:g}s for it to settle")
                pending[drive_name] = time.monotonic()
            if drive_name in pending and time.monotonic() - pending[drive_name] >= settle_seconds:
                print(f"Processing card drive {drive}")
                callback(drive)
                known.add(drive_name)
                pending.pop(drive_name, None)

        known.intersection_update(current)
        for drive_name in list(pending):
            if drive_name not in current:
                pending.pop(drive_name, None)

        time.sleep(float(usb.get("poll_seconds", 3)))
