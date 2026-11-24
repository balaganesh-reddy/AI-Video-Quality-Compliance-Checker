from __future__ import annotations

import csv
import hashlib
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from screening.extractor import extract_mcap_to_images


class Screener:
    def __init__(self, config):
        self.config = config
        self.paths = config["paths"]
        for key in ("output_dir", "results_dir", "pending_dir", "backup_dir"):
            Path(self.paths[key]).mkdir(parents=True, exist_ok=True)

    def check(self):
        try:
            import rosbags
            mcap_available = True
        except ImportError:
            mcap_available = False
        return {
            "mcap": "AVAILABLE" if mcap_available else "UNAVAILABLE",
            "detectors": {
                "person": "NOT CONFIGURED",
                "possible_minor": "NOT CONFIGURED",
                "nsfw": "NOT CONFIGURED",
            },
            "privacy": self.config["privacy"],
        }

    def process_path(self, path, card_ids=None, force=False, pattern="*.mcap"):
        source = Path(path)
        if source.is_file():
            files = [source] if source.suffix.lower() == ".mcap" else []
        elif source.is_dir():
            files = sorted(source.rglob(pattern))
        else:
            return []

        results = []
        for mcap in files:
            results.append(self.process_one(mcap, card_ids or []))
        return results

    def process_drive(self, drive):
        pattern = self.config["usb"].get("pattern", "*.mcap")
        return self.process_path(drive, [], False, pattern)

    def process_one(self, mcap: Path, card_ids):
        mcap = Path(mcap)
        sha256 = hashlib.sha256(mcap.read_bytes()).hexdigest()
        output_name = mcap.stem
        frame_dir = Path(self.paths["results_dir"]) / output_name / "extracted_frames"

        try:
            frames = extract_mcap_to_images(
                mcap,
                frame_dir,
                fps=float(self.config["extraction"]["sample_fps"]),
            )
            status = "REVIEW"
            reasons = ["Unconfigured detectors: automatic detector review required"]
        except Exception as exc:
            frames = []
            status = "ERROR"
            reasons = [str(exc)]

        record = {
            "video_name": mcap.name,
            "status": status,
            "reasons": "; ".join(reasons),
            "flagged_timestamps": [],
            "review_timestamps": [frame["timestamp_ns"] for frame in frames],
            "frames_received": len(frames),
            "frames_processed": len(frames),
            "review_frames": len(frames),
            "card_id": ", ".join(card_ids),
            "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "file_sha256": sha256,
            "source_path": str(mcap),
            "extracted_frame_dir": str(frame_dir) if frames else "",
        }

        json_path = Path(self.paths["results_dir"]) / f"{output_name}.json"
        json_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        csv_path = Path(self.paths["results_dir"]) / "screening_results.csv"
        fieldnames = list(record)
        write_header = not csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(record)

        audit = Path(self.paths["audit_log"])
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

        return record

    def process_card_folder(self, card_folder):
        return self.process_path(card_folder)
