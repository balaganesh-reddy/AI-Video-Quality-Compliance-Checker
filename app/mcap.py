"""Extract decodable video frames from ROS MCAP recordings."""

import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def is_mcap(path):
    return Path(path).suffix.lower() == ".mcap"


def extract_mcap_frames(path, max_frames=900):
    """Extract a supported MCAP image/video topic to a temporary MP4."""
    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise RuntimeError("Install MCAP dependencies with: pip install rosbags mcap") from exc

    source = Path(path)
    temp_dir = tempfile.TemporaryDirectory(prefix="mcap_extract_")
    temp_path = Path(temp_dir.name)

    frames = []
    video_data = {}

    try:
        with AnyReader([source]) as reader:
            connections = [
                c for c in reader.connections
                if _supported_topic(c.msgtype)
            ]
            if not connections:
                raise RuntimeError("MCAP has no supported image or video topic")

            for connection, _timestamp, rawdata in reader.messages(connections=connections):
                msg_type = connection.msgtype.lower()
                try:
                    message = reader.deserialize(rawdata, connection.msgtype)
                except Exception:
                    continue

                if "compressedvideo" in msg_type:
                    data = bytes(getattr(message, "data", b""))
                    if data:
                        format_name = str(getattr(message, "format", "h264")).lower()
                        video_data.setdefault(format_name, []).append(data)
                    continue

                frame = _decode_image(message, msg_type)
                if frame is not None:
                    frames.append(frame)
                    if len(frames) >= max_frames:
                        break

        if video_data:
            for format_name, chunks in video_data.items():
                output = temp_path / "extracted.mp4"
                input_file = temp_path / "stream.bin"
                input_file.write_bytes(b"".join(chunks))
                demuxer = {"h265": "hevc", "hevc": "hevc", "h264": "h264", "av1": "ivf"}.get(format_name)
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
                if demuxer:
                    command += ["-f", demuxer]
                command += ["-i", str(input_file), "-an", "-vcodec", "copy", str(output)]
                completed = subprocess.run(command, capture_output=True, check=False)
                if completed.returncode == 0 and output.exists():
                    return temp_dir, output

        if not frames:
            raise RuntimeError("No decodable frames found in supported MCAP image/video topics")

        height, width = frames[0].shape[:2]
        output = temp_path / "extracted.mp4"
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), 10, (width, height))
        if not writer.isOpened():
            raise RuntimeError("Could not create temporary MP4 from MCAP frames")
        for frame in frames:
            writer.write(cv2.resize(frame, (width, height)))
        writer.release()
        if not output.exists():
            raise RuntimeError("MCAP frame extraction produced no MP4")
        return temp_dir, output
    except Exception:
        temp_dir.cleanup()
        raise


def _supported_topic(msg_type):
    value = msg_type.lower()
    return any(marker in value for marker in (
        "compressedimage", "compressedvideo", "sensor_msgs/msg/image",
        "rawimage", "foxglove_msgs/msg/compressedvideo",
    ))


def _decode_image(message, msg_type):
    data = getattr(message, "data", None)
    if data is None:
        return None

    if "compressedimage" in msg_type:
        encoded = np.frombuffer(bytes(data), dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    try:
        width = int(message.width)
        height = int(message.height)
        encoding = str(getattr(message, "encoding", "rgb8")).lower()
        raw = np.frombuffer(bytes(data), dtype=np.uint8)
    except (AttributeError, TypeError, ValueError):
        return None

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
    return None
