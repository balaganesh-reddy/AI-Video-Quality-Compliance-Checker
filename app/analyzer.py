"""Video checks for task-wrist visibility, phone activity, and lighting.

These computer-vision checks are estimates and should be validated against real
videos before they are used for consequential decisions. Phone detection cannot
identify social-media apps or prove intent; it flags a phone held near a detected
hand as possible phone use.
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
_PHONE_CLASS_ID = 67  # COCO class "cell phone".


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
    """Analyze a video using explicit rules or the locally saved rules."""
    rules = rules or load_rules()
    path = Path(path)
    metadata = ffprobe_video(path)
    visual = analyze_visual_conditions(path, rules)
    status = visual.pop("status")
    issues = visual.pop("issues")
    return {
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file_name": path.name,
        "source_path": str(path),
        "status": status,
        "issues": "; ".join(issues),
        **metadata,
        **visual,
    }


def evaluate_visual_metrics(
    *, wrist_visible_ratio, phone_use_seconds, well_lit_ratio, rules,
    phone_detector_available=True, longest_hand_absence_seconds=0.0,
):
    """Evaluate measured metrics; separated to make compliance logic testable."""
    issues = []
    hard_failures = []

    if wrist_visible_ratio < rules.minimum_wrist_visible_frame_ratio:
        issue = (
            f"both wrists clearly visible in only {wrist_visible_ratio:.0%} of sampled frames "
            f"(minimum {rules.minimum_wrist_visible_frame_ratio:.0%})"
        )
        issues.append(issue)
        hard_failures.append(issue)

    if phone_use_seconds > rules.maximum_phone_use_seconds:
        issue = (
            f"possible phone use lasted {phone_use_seconds:.0f}s "
            f"(limit {rules.maximum_phone_use_seconds:.0f}s)"
        )
        issues.append(issue)
        hard_failures.append(issue)

    if well_lit_ratio < rules.minimum_well_lit_frame_ratio:
        issue = (
            f"lighting met the threshold in {well_lit_ratio:.0%} of sampled frames "
            f"(minimum {rules.minimum_well_lit_frame_ratio:.0%})"
        )
        issues.append(issue)
        hard_failures.append(issue)

    if longest_hand_absence_seconds > rules.maximum_hand_absence_seconds:
        issues.append(
            f"no hands detected for about {longest_hand_absence_seconds:.0f}s continuously "
            f"(limit {rules.maximum_hand_absence_seconds:.0f}s)"
        )

    if not phone_detector_available:
        issues.append("phone detector unavailable; phone-use check could not be completed")

    status = "FAIL" if hard_failures else ("REVIEW" if issues else "PASS")
    return {"status": status, "issues": issues}


def analyze_visual_conditions(path, rules=None):
    """Sample video for bilateral wrist visibility, possible phone use, and lighting."""
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
    sampled_frames = 0
    both_wrists_visible_frames = 0
    hand_frames = 0
    well_lit_frames = 0
    brightness_scores = []
    sharpness_scores = []
    longest_hand_gap = 0.0
    current_hand_gap = 0.0
    longest_phone_run = 0.0
    current_phone_run = 0.0
    phone_detected_frames = 0
    phone_use_frames = 0
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
                sampled_frames += 1

                height, width = frame.shape[:2]
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                brightness_scores.append(brightness)
                if brightness >= rules.minimum_average_brightness:
                    well_lit_frames += 1
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
                    landmarks = pose_result.pose_landmarks.landmark
                    left = landmarks[int(mp.solutions.pose.PoseLandmark.LEFT_WRIST)]
                    right = landmarks[int(mp.solutions.pose.PoseLandmark.RIGHT_WRIST)]
                    # Both task-relevant wrists must be confidently detected and in-frame.
                    wrists_visible = all(
                        point.visibility >= rules.minimum_wrist_visibility_confidence
                        and 0.0 <= point.x <= 1.0
                        and 0.0 <= point.y <= 1.0
                        for point in (left, right)
                    )
                    if wrists_visible:
                        both_wrists_visible_frames += 1

                phone_boxes, detector_available = _detect_phone_boxes(
                    frame, rules.phone_detection_confidence
                )
                phone_detector_available = phone_detector_available and detector_available
                possible_phone_use = bool(
                    phone_boxes and found_hands
                    and _hand_near_phone(hand_result, phone_boxes, width, height)
                )
                if phone_boxes:
                    phone_detected_frames += 1
                if possible_phone_use:
                    phone_use_frames += 1
                    current_phone_run += interval
                    longest_phone_run = max(longest_phone_run, current_phone_run)
                else:
                    current_phone_run = 0.0
    finally:
        capture.release()

    denominator = max(1, sampled_frames)
    wrist_ratio = both_wrists_visible_frames / denominator
    well_lit_ratio = well_lit_frames / denominator
    hand_gap = max(longest_hand_gap, current_hand_gap)
    decision = evaluate_visual_metrics(
        wrist_visible_ratio=wrist_ratio,
        phone_use_seconds=longest_phone_run,
        well_lit_ratio=well_lit_ratio,
        rules=rules,
        phone_detector_available=phone_detector_available,
        longest_hand_absence_seconds=hand_gap,
    )

    return {
        "status": decision["status"],
        "issues": decision["issues"],
        "hand_visible_frame_ratio": round(hand_frames / denominator, 3),
        "longest_hand_absence_seconds": round(hand_gap, 2),
        "both_wrists_visible_frame_ratio": round(wrist_ratio, 3),
        "average_brightness": round(float(np.mean(brightness_scores)), 2) if brightness_scores else None,
        "well_lit_frame_ratio": round(well_lit_ratio, 3),
        "phone_detected_frames": phone_detected_frames,
        "possible_phone_use_frames": phone_use_frames,
        "longest_possible_phone_use_seconds": round(longest_phone_run, 2),
        "phone_detection_available": phone_detector_available,
        "sharpness_score": round(float(np.mean(sharpness_scores)), 2) if sharpness_scores else None,
    }


def _detect_phone_boxes(frame, confidence):
    """Use the optional Ultralytics COCO model, loading weights on first use."""
    global _PHONE_MODEL, _PHONE_MODEL_ERROR
    try:
        from ultralytics import YOLO
        if _PHONE_MODEL is None and _PHONE_MODEL_ERROR is None:
            _PHONE_MODEL = YOLO("yolo11n.pt")
        if _PHONE_MODEL is None:
            return [], False
        prediction = _PHONE_MODEL.predict(
            frame, verbose=False, conf=confidence, classes=[_PHONE_CLASS_ID]
        )[0]
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
            pad = max(width, height) * 0.03
            if not (
                hand_box[2] + pad < phone[0] or phone[2] + pad < hand_box[0]
                or hand_box[3] + pad < phone[1] or phone[3] + pad < hand_box[1]
            ):
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
