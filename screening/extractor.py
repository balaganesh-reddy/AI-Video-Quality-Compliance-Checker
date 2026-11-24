from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def extract_mcap_to_images(path: str | Path, output_dir: str | Path, fps: float = 2.0):
    """Extract decodable image frames from an MCAP to timestamp-named JPEG files.

    Requires rosbags and mcap ROS support. Output is a local directory.
    """
    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise RuntimeError("Install rosbags and mcap ROS support") from exc

    source = Path(path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    interval_ns = int(1e9 / max(float(fps), 0.1))
    last_timestamp = None
    extracted = []

    with AnyReader([source]) as reader:
        connections = [
            connection for connection in reader.connections
            if _supported_topic(connection.msgtype)
        ]
        if not connections:
            raise RuntimeError("No supported image topic found in MCAP")

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            if last_timestamp is not None and timestamp - last_timestamp < interval_ns:
                continue

            message = reader.deserialize(rawdata, connection.msgtype)
            frame = _decode_image(message, connection.msgtype)
            if frame is None:
                continue

            timestamp_ns = int(timestamp)
            filename = destination / f"{timestamp_ns}.jpg"
            cv2.imwrite(str(filename), frame)
            extracted.append({"timestamp_ns": timestamp_ns, "path": str(filename), "topic": connection.topic})
            last_timestamp = timestamp

    if not extracted:
        raise RuntimeError("No decodable frames found in supported MCAP image topics")
    return extracted


def extract_frame_at(path: str | Path, timestamp_ns: int, topic: str | None = None):
    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise RuntimeError("Install rosbags and mcap ROS support") from exc

    source = Path(path)
    best = None
    best_distance = None

    with AnyReader([source]) as reader:
        connections = [
            connection for connection in reader.connections
            if _supported_topic(connection.msgtype)
            and (topic is None or connection.topic == topic)
        ]
        for connection, timestamp, rawdata in reader.messages(connections=connections):
            distance = abs(timestamp - timestamp_ns)
            if best_distance is not None and distance >= best_distance:
                continue
            message = reader.deserialize(rawdata, connection.msgtype)
            frame = _decode_image(message, connection.msgtype)
            if frame is not None:
                best = frame
                best_distance = distance
    return best


def _supported_topic(message_type: str) -> bool:
    value = message_type.lower()
    return any(marker in value for marker in (
        "compressedimage",
        "sensor_msgs/msg/image",
        "sensor_msgs/image",
        "rawimage",
    ))


def _decode_image(message, message_type: str):
    data = getattr(message, "data", None)
    if data is None:
        return None

    if "compressedimage" in message_type.lower():
        encoded = np.frombuffer(bytes(data), dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    try:
        width = int(message.width)
        height = int(message.height)
        encoding = str(getattr(message, "encoding", "rgb8")).lower()
        raw = np.frombuffer(bytes(data), dtype=np.uint8)
    except (AttributeError, TypeError, ValueError):
        return None

    try:
        if encoding in ("rgb8", "rgb"):
            return raw.reshape((height, width, 3))[:, :, ::-1]
        if encoding in ("bgr8", "bgr"):
            return raw.reshape((height, width, 3))
        if encoding in ("rgba8", "rgba"):
            return cv2.cvtColor(raw.reshape((height, width, 4)), cv2.COLOR_RGBA2BGR)
        if encoding in ("bgra8", "bgra"):
            return cv2.cvtColor(raw.reshape((height, width, 4)), cv2.COLOR_BGRA2BGR)
        if encoding in ("mono8", "gray", "8uc1"):
            return cv2.cvtColor(raw.reshape((height, width)), cv2.COLOR_GRAY2BGR)
        if encoding in ("mono16", "16uc1"):
            values = np.frombuffer(bytes(data), dtype=np.uint16).reshape((height, width))
            normalized = cv2.normalize(values, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            return cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    except (TypeError, ValueError):
        return None
    return None
