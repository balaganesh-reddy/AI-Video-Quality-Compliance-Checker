from __future__ import annotations

import ctypes
import time
from pathlib import Path

import psutil


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

        try:
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(str(mount.anchor or mount) + "\\")
        except Exception:
            options = partition.opts.lower()
            drive_type = 2 if "removable" in options else 3

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

    known = set()

    if not usb.get("process_present_at_start", True):
        known.update(str(drive) for drive in get_removable_drives(allowed_types, exclude, only))

    pending = {}
    while True:
        current = {
            str(drive): drive
            for drive in get_removable_drives(allowed_types, exclude, only)
        }

        for drive_name, drive in current.items():
            if drive_name not in known and drive_name not in pending:
                pending[drive_name] = time.monotonic()
            if drive_name in pending and time.monotonic() - pending[drive_name] >= settle_seconds:
                callback(drive)
                known.add(drive_name)
                pending.pop(drive_name, None)

        known.intersection_update(current)
        for drive_name in list(pending):
            if drive_name not in current:
                pending.pop(drive_name, None)

        time.sleep(float(usb.get("poll_seconds", 3)))
