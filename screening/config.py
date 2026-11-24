import json
from pathlib import Path


DEFAULT_CONFIG = {
    "extraction": {
        "sample_fps": 2.0,
        "timestamp_source": "log_time",
        "skip_depth_topics": True,
        "image_topics": "auto",
    },
    "usb": {
        "poll_seconds": 3,
        "settle_seconds": 5,
        "drive_types": [2],
        "exclude_drives": ["C:\\"],
        "only_drives": [],
        "process_present_at_start": True,
        "pattern": "*.mcap",
    },
    "paths": {
        "output_dir": "output",
        "results_dir": "output/results",
        "pending_dir": "output/pending",
        "backup_dir": "output/backups",
        "audit_log": "output/audit.log",
        "log_file": "output/screening.log",
    },
    "privacy": {
        "save_review_frames": False,
        "review_frames_dir": "output/review_frames",
        "retention_days": 14,
        "max_saved_fail_frames": 50,
        "max_saved_review_frames": 20,
    },
    "quality": {
        "min_side_px": 160,
        "blur_min": 15.0,
        "dark_mean_max": 12.0,
        "bright_mean_min": 245.0,
        "flat_std_min": 3.0,
    },
}


def load_config(path="config.json"):
    config_path = Path(path)
    if not config_path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_merge(merged, config)
    return merged


def _deep_merge(target, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
