"""Video quality checks for hand/wrist visibility, phone use, and lighting.

These are computer-vision screening signals, not a substitute for human review.
The phone detector can identify a phone, but cannot determine which social-media
app is displayed or reliably infer intent.
"""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from app.config import ComplianceRules, load_rules


_PHONE_MODEL = None
_PHONE_MODEL_ERROR = None
_PHONE_CLASS_ID = 67  # COCO class "cell phone" in the Ultralytics COCO model.


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
    """Analyze sampled frames using configurable visual compliance checks."""
    rules = rules or load_rules()
    path = Path(path)
    metadata = ffprobe_video(path)
    visual = analyze_visual_conditions(path, rules)
    issues = visual.pop("issues")

    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_name": path.name,
        "source_path": str(path),
        "status": "REVIEW" if issues else "PASS",
        "issues": "; ".join(issues),
        **metadata,
        **visual,
    }


def analyze_visual_conditions(path, rules=None):
    """Sample video for hands, wrist landmarks, phone-use signals, and lighting."""
    rules = rules or ComplianceRules()
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open this video")

    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        capture.release()
        raise RuntimeError("Video frame rate or frame count is unavailable")

    duration = frame_count / fps
    interval = max(0.25, float(rules.sample_interval_seconds))
    timestamps = np.arange(0, duration, interval)
    issues = []
    hand_frames = 0
    wrist_visible_frames = 0
    lit_frames = 0
    dark_frames = 0
    phone_frames = 0
    phone_use_frames = 0
    longest_hand_gap = 0.0
    current_hand_gap = 0.0
    sharpness_scores = []
    pose_frames = 0
    phone_detector_available = True

    try:
        with mp.solutions.hands.Hands(
            static_image_mode=True, max_num_hands=4,
            min_detection_confidence=0.5,
        ) as hands_model, mp.solutions.pose.Pose(
            static_image_mode=True, model_complexity=0,
            min_detection_confidence=0.5,
        ) as pose_model:
            for timestamp in timestamps:
                capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp) * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue

                height, width = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                if brightness >= rules.minimum_average_brightness:
                    lit_frames += 1
                else:
                    dark_frames += 1
                sharpness_scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hand_result = hands_model.process(rgb)
                found_hands = bool(hand_result.multi_hand_landmarks)
                if found_hands:
                    hand_frames += 1
                    current_hand_gap = 0.0
                else:
                    current_hand_gap += interval
                    longest_hand_gap = max(longest_hand_gap, current_hand_gap)

                pose_result = pose_model.process(rgb)
                if pose_result.pose_landmarks:
                    pose_frames += 1
                    landmarks = pose_result.pose_landmarks.landmark
                    wrist_ids = (mp.solutions.pose.PoseLandmark.LEFT_WRIST, mp.solutions.pose.PoseLandmark.RIGHT_WRIST)
                    if any(landmarks[int(i)].visibility >= rules.minimum_wrist_visibility_confidence for i in wrist_ids):
                        wrist_visible_frames += 1

                phone_boxes, detector_available = _detect_phone_boxes(
                    frame, rules.phone_detection_confidence
                )
                phone_detector_available = phone_detector_available and detector_available
                if phone_boxes:
                    phone_frames += 1
                    if found_hands and _hand_near_phone(hand_result, phone_boxes, width, height):
                        phone_use_frames += 1
    finally:
        capture.release()

    analyzed_frames = max(1, len(timestamps))
    effective_hand_gap = max(longest_hand_gap, current_hand_gap)
    lit_ratio = lit_frames / analyzed_frames
    wrist_ratio = wrist_visible_frames / analyzed_frames

    if effective_hand_gap > rules.maximum_hand_absence_seconds:
        issues.append(f"hands absent for about {effective_hand_gap:.0f}s continuously (limit {rules.maximum_hand_absence_seconds:.0f}s)")
    if wrist_ratio < rules.minimum_well_lit_frame_ratio:
        issues.append(f"wrists clearly visible in only {wrist_ratio:.0%} of sampled frames")
    if lit_ratio < rules.minimum_well_lit_frame_ratio:
        issues.append(f"lighting below threshold in {dark_frames}/{analyzed_frames} sampled frames")
    if phone_use_frames:
        issues.append(f"possible phone use detected in {phone_use_frames} sampled frame(s)")
    elif phone_frames:
        issues.append(f"phone detected in {phone_frames} sampled frame(s); review for use")

    return {
        "hand_visible_frame_ratio": round(hand_frames / analyzed_frames, 3),
        "longest_hand_absence_seconds": round(effective_hand_gap, 2),
        "wrist_visible_frame_ratio": round(wrist_ratio, 3),
        "average_brightness": round(float(np.mean([0])) if not (lit_frames + dark_frames) else 0, 2),
        "well_lit_frame_ratio": round(lit_ratio, 3),
        "phone_detected_frames": phone_frames,
        "possible_phone_use_frames": phone_use_frames,
        "phone_detection_available": phone_detector_available,
        "sharpness_score": round(float(np.mean(sharpness_scores)), 2) if sharpness_scores else None,
        "issues": issues,
    }


def _detect_phone_boxes(frame, confidence):
    """Use optional Ultralytics COCO model; initialize/download weights on demand."""
    global _PHONE_MODEL, _PHONE_MODEL_ERROR
    try:
        from ultralytics import YOLO
        if _PHONE_MODEL is None and _PHONE_MODEL_ERROR is None:
            _PHONE_MODEL = YOLO("yolo11n.pt")
        if _PHONE_MODEL is None:
            return [], False
        prediction = _PHONE_MODEL.predict(frame, verbose=False, conf=confidence, classes=[_PHONE_CLASS_ID])[0]
        boxes = prediction.boxes.xyxy.cpu().numpy().tolist() if prediction.boxes is not None else []
        return boxes, True
    except Exception as exc:
        _PHONE_MODEL_ERROR = str(exc)
        return [], False


def _hand_near_phone(hand_result, phone_boxes, width, height):
    if not hand_result.multi_hand_landmarks:
        return False
    for hand in hand_result.multi_hand_landmarks:
        xs = [point.x * width for point in hand.landmark]
        ys = [point.y * height for point in hand.landmark]
        hand_box = (min(xs), min(ys), max(xs), max(ys))
        for phone in phone_boxes:
            # Expand hand bbox modestly to tolerate detector/landmark localization error.
            pad = max(width, height) * 0.03
            if not (hand_box[2] + pad < phone[0] or phone[2] + pad < hand_box[0]
                    or hand_box[3] + pad < phone[1] or phone[3] + pad < hand_box[1]):
                return True
    return False


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
