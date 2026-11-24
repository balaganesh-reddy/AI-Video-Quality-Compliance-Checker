"""Video metadata extraction and quality/compliance checks."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.config import load_rules


def ffprobe_video(path):
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe was not found. Install FFmpeg and add it to PATH.")

    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_name,bit_rate,duration:format=duration,size",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "ffprobe could not read the video")

    data = json.loads(completed.stdout)
    stream = (data.get("streams") or [{}])[0]
    video_format = data.get("format") or {}

    frame_rate = _frame_rate(stream.get("avg_frame_rate", "0/1"))
    duration = _float(stream.get("duration")) or _float(video_format.get("duration"))
    bit_rate = _int(stream.get("bit_rate")) or _int(video_format.get("bit_rate"))

    return {
        "width": _int(stream.get("width")),
        "height": _int(stream.get("height")),
        "fps": round(frame_rate, 2),
        "codec": stream.get("codec_name"),
        "duration_seconds": round(duration or 0, 2),
        "bitrate_kbps": round(bit_rate / 1000, 2) if bit_rate else None,
        "file_size_mb": round(_int(video_format.get("size")) / (1024 * 1024), 2)
        if video_format.get("size") else round(path.stat().st_size / (1024 * 1024), 2),
    }


def analyze_video(path, rules=None):
    """Analyze a video using a ComplianceRules object or configured JSON rules."""
    rules = rules or load_rules()
    path = Path(path)
    metadata = ffprobe_video(path)

    failures = []
    if metadata["width"] < rules.minimum_width:
        failures.append(f"width<{rules.minimum_width}")
    if metadata["height"] < rules.minimum_height:
        failures.append(f"height<{rules.minimum_height}")
    if metadata["fps"] < rules.minimum_fps:
        failures.append(f"fps<{rules.minimum_fps}")
    if metadata["duration_seconds"] < rules.minimum_duration_seconds:
        failures.append("duration too short")
    if metadata["duration_seconds"] > rules.maximum_duration_seconds:
        failures.append("duration too long")

    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_name": path.name,
        "source_path": str(path),
        "status": "PASS" if not failures else "FAIL",
        "issues": "; ".join(failures) if failures else "",
        **metadata,
        "sharpness_score": sample_sharpness(path),
    }


def sample_sharpness(path, frame_count=5):
    """Return mean Laplacian variance from evenly sampled frames."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return None
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    scores = []
    for index in range(frame_count):
        position = int(total * (index + 1) / (frame_count + 1)) if total > 0 else index
        capture.set(cv2.CAP_PROP_POS_FRAMES, position)
        ok, frame = capture.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
    capture.release()
    return round(float(np.mean(scores)), 2) if scores else None


def _frame_rate(value):
    try:
        numerator, denominator = value.split("/")
        return float(numerator) / float(denominator) if float(denominator) else 0
    except (AttributeError, ValueError, ZeroDivisionError):
        return 0


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
