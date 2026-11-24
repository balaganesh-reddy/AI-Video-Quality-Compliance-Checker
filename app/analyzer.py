"""Video quality, child-safety, and NSFW screening.

The classifiers provide probabilistic visual screening, not proof of age or
content. Any positive child-safety or NSFW result is a hard FAIL and is sent
to a dedicated sheet. The app does not depend on filenames or metadata.
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


_AGE_PIPELINE = None
_NSFW_PIPELINE = None
_PHONE_MODEL = None
_PHONE_CLASS_ID = 67


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


def _get_age_pipeline():
    global _AGE_PIPELINE
    if _AGE_PIPELINE is not None:
        return _AGE_PIPELINE
    try:
        from transformers import pipeline
        _AGE_PIPELINE = pipeline("image-classification", model="nateraw/vit-age-classifier")
    except Exception:
        _AGE_PIPELINE = None
    return _AGE_PIPELINE


def _get_nsfw_pipeline():
    global _NSFW_PIPELINE
    if _NSFW_PIPELINE is not None:
        return _NSFW_PIPELINE
    try:
        from transformers import pipeline
        _NSFW_PIPELINE = pipeline("image-classification", model="Falconsai/nsfw_image_detection")
    except Exception:
        _NSFW_PIPELINE = None
    return _NSFW_PIPELINE


def _minor_score(face_rgb, confidence):
    classifier = _get_age_pipeline()
    if classifier is None:
        return None, False
    try:
        predictions = classifier(face_rgb)
        for prediction in predictions:
            label = str(prediction.get("label", "")).lower().replace(" ", "")
            score = float(prediction.get("score", 0.0))
            if (label in {"0-2", "3-9", "10-19"}) and score >= confidence:
                # 10-19 is ambiguous. It is only a likely minor signal, not a
                # confirmed age; it is safer to fail than to admit this frame.
                return score, True
        return max((float(p.get("score", 0.0)) for p in predictions), default=0.0), False
    except Exception:
        return None, False


def _nsfw_score(frame_rgb, confidence):
    classifier = _get_nsfw_pipeline()
    if classifier is None:
        return None, False
    try:
        predictions = classifier(frame_rgb)
        for prediction in predictions:
            label = str(prediction.get("label", "")).lower()
            score = float(prediction.get("score", 0.0))
            if label == "nsfw" and score >= confidence:
                return score, True
        return max((float(p.get("score", 0.0)) for p in predictions), default=0.0), False
    except Exception:
        return None, False


def analyze_visual_conditions(path, rules=None):
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
    denominator = 0
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
    minor_frames = 0
    nsfw_frames = 0
    highest_minor_confidence = 0.0
    highest_nsfw_confidence = 0.0
    phone_detector_available = True
    age_detector_available = True
    nsfw_detector_available = True

    try:
        with mp.solutions.hands.Hands(
            static_image_mode=True, max_num_hands=4,
            min_detection_confidence=0.5,
        ) as hands_model, mp.solutions.pose.Pose(
            static_image_mode=True, model_complexity=0,
            min_detection_confidence=0.5,
        ) as pose_model, mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5,
        ) as face_detector:
            for timestamp in timestamps:
                capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp) * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                denominator += 1
                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))
                brightness_scores.append(brightness)
                sharpness_scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
                if brightness >= rules.minimum_average_brightness:
                    well_lit_frames += 1

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
                    wrists_visible = all(
                        point.visibility >= rules.minimum_wrist_visibility_confidence
                        and 0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0
                        for point in (left, right)
                    )
                    if wrists_visible:
                        both_wrists_visible_frames += 1

                phone_boxes, detector_available = _detect_phone_boxes(frame, rules.phone_detection_confidence)
                phone_detector_available = phone_detector_available and detector_available
                possible_phone_use = bool(phone_boxes and found_hands and _hand_near_phone(hand_result, phone_boxes, width, height))
                if phone_boxes:
                    phone_detected_frames += 1
                if possible_phone_use:
                    phone_use_frames += 1
                    current_phone_run += interval
                    longest_phone_run = max(longest_phone_run, current_phone_run)
                else:
                    current_phone_run = 0.0

                face_result = face_detector.process(rgb)
                if face_result.detections:
                    for detection in face_result.detections:
                        box = detection.location_data.relative_bounding_box
                        x1 = max(0, int(box.xmin * width))
                        y1 = max(0, int(box.ymin * height))
                        x2 = min(width, int((box.xmin + box.width) * width))
                        y2 = min(height, int((box.ymin + box.height) * height))
                        if x2 <= x1 or y2 <= y1:
                            continue
                        minor_score, is_minor = _minor_score(rgb[y1:y2, x1:x2], rules.minor_detection_confidence)
                        if minor_score is not None:
                            age_detector_available = True
                            highest_minor_confidence = max(highest_minor_confidence, minor_score)
                            if is_minor:
                                minor_frames += 1
                                break

                nsfw_score, is_nsfw = _nsfw_score(rgb, rules.nsfw_detection_confidence)
                if nsfw_score is not None:
                    nsfw_detector_available = True
                    highest_nsfw_confidence = max(highest_nsfw_confidence, nsfw_score)
                    if is_nsfw:
                        nsfw_frames += 1
    finally:
        capture.release()

    denominator = max(1, denominator)
    wrist_ratio = both_wrists_visible_frames / denominator
    well_lit_ratio = well_lit_frames / denominator
    issues = []

    if minor_frames > 0:
        issues.append(f"minor-like appearance detected in {minor_frames} sampled frame(s); video marked FAILED")
    if nsfw_frames > 0:
        issues.append(f"NSFW content detected in {nsfw_frames} sampled frame(s); video marked FAILED")
    if wrist_ratio < rules.minimum_wrist_visible_frame_ratio:
        issues.append(f"both wrists clearly visible in only {wrist_ratio:.0%} of sampled frames")
    if longest_phone_run > rules.maximum_phone_use_seconds:
        issues.append(f"possible phone use lasted {longest_phone_run:.0f}s")
    if well_lit_ratio < rules.minimum_well_lit_frame_ratio:
        issues.append(f"lighting threshold met in only {well_lit_ratio:.0%} of sampled frames")

    hard_fail = minor_frames > 0 or nsfw_frames > 0 or wrist_ratio < rules.minimum_wrist_visible_frame_ratio or longest_phone_run > rules.maximum_phone_use_seconds or well_lit_ratio < rules.minimum_well_lit_frame_ratio

    if not age_detector_available:
        issues.append("minor/age classifier unavailable")
        age_detector_available = False
    if not nsfw_detector_available:
        issues.append("NSFW classifier unavailable")

    return {
        "status": "FAIL" if hard_fail else "PASS",
        "issues": issues,
        "nsfw_detected": nsfw_frames > 0,
        "nsfw_detected_frames": nsfw_frames,
        "nsfw_max_confidence": round(highest_nsfw_confidence, 3) if highest_nsfw_confidence else None,
        "nsfw_detector_available": nsfw_detector_available,
        "minor_like_detected": minor_frames > 0,
        "minor_like_detected_frames": minor_frames,
        "minor_like_max_confidence": round(highest_minor_confidence, 3) if highest_minor_confidence else None,
        "age_classifier_available": age_detector_available,
        "hand_visible_frame_ratio": round(hand_frames / denominator, 3),
        "longest_hand_absence_seconds": round(max(longest_hand_gap, current_hand_gap), 2),
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
    global _PHONE_MODEL
    try:
        from ultralytics import YOLO
        if _PHONE_MODEL is None:
            _PHONE_MODEL = YOLO("yolo11n.pt")
        prediction = _PHONE_MODEL.predict(frame, verbose=False, conf=confidence, classes=[_PHONE_CLASS_ID])[0]
        boxes = prediction.boxes.xyxy.cpu().numpy().tolist() if prediction.boxes is not None else []
        return boxes, True
    except Exception:
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
            if not (hand_box[2] + pad < phone[0] or phone[2] + pad < hand_box[0] or hand_box[3] + pad < phone[1] or phone[3] + pad < hand_box[1]):
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
