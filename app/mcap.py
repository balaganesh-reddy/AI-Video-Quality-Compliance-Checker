"""MCAP extraction helpers for ROS/ROS 2 image and video recordings."""

import subprocess
import tempfile
from pathlib import Path

import cv2


SUPPORTED_IMAGE_TYPES = (
    "sensor_msgs/msg/CompressedImage",
    "sensor_msgs/msg/Image",
    "foxglove_msgs/msg/CompressedImage",
)
SUPPORTED_VIDEO_TYPES = (
    "foxglove_msgs/msg/CompressedVideo",
)


def is_mcap(path):
    return Path(path).suffix.lower() == ".mcap"


def inspect_mcap(path):
    """Best-effort describe a MCAP file and its image/video channels."""
    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise RuntimeError("Install MCAP support dependencies from requirements.txt") from exc

    path = Path(path)
    image_topics = []
    video_topics = []
    count = 0
    with AnyReader([path]) as reader:
        for connection in reader.connections:
            msg_type = connection.msgtype.lower()
            if any(part in msg_type for part in ("compressedimage", "rawimage", "/image")):
                image_topics.append(connection.topic)
            if any(part in msg_type for part in ("compressedvideo", "video")):
                video_topics.append(connection.topic)
        for connection, timestamp, rawdata in reader.messages():
            count += 1
    return {
        "image_topics": sorted(set(image_topics)),
        "video_topics": sorted(set(video_topics)),
        "message_count": count,
    }


def extract_mcap_frames(path, max_frames=900):
    """Extract frames from a ROS/ROS 2 MCAP into a temporary MP4.

    Supports common sensor_msgs/CompressedImage, sensor_msgs/Image,
    Foxglove CompressedImage/RawImage, and CompressedVideo recordings.
    Returns (temporary_directory, output_video) so caller owns cleanup.
    """
    try:
        from rosbags.highlevel import AnyReader
    except ImportError as exc:
        raise RuntimeError("Install MCAP support dependencies from requirements.txt") from exc

    source = Path(path)
    temp_dir = tempfile.TemporaryDirectory(prefix="mcap_extract_")
    temp_path = Path(temp_dir.name)

    frames = []
    video_chunks = []
    with AnyReader([source]) as reader:
        connections = [
            connection for connection in reader.connections
            if _is_supported_type(connection.msgtype)
        ]
        if not connections:
            info = inspect_mcap(source)
            temp_dir.cleanup()
            raise RuntimeError(
                "No supported image/video topic found in MCAP "
                f"(image topics: {info['image_topics']}, video topics: {info['video_topics']})"
            )

        selected = {connection.id for connection in connections}
        for connection, timestamp, rawdata in reader.messages(connections=connections):
            if len(frames) >= max_frames and not video_chunks:
                break
            msg_type = connection.msgtype.lower()
            try:
                message = reader.deserialize(rawdata, connection.msgtype)
            except Exception:
                continue

            if "compressedvideo" in msg_type:
                data = bytes(getattr(message, "data", b""))
                if data:
                    video_chunks.append(data)
                continue

            frame = _decode_image_message(message, msg_type)
            if frame is not None:
                frames.append(frame)
                if len(frames) >= max_frames:
                    break

    if video_chunks:
        output = temp_path / "extracted.mp4"
        input_file = temp_path / "stream.bin"
        input_file.write_bytes(b"".join(video_chunks))
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-y", "-f", "h264", "-i", str(input_file),
            "-an", "-vcodec", "mjpeg", "-q:v", "2", str(output),
        ]
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode == 0 and output.exists():
            return temp_dir, output

    if not frames:
        temp_dir.cleanup()
        raise RuntimeError("MCAP contained supported topics but no decodable frame data")

    height, width = frames[0].shape[:2]
    output = temp_path / "extracted.mp4"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), 10, (width, height))
    if not writer.isOpened():
        temp_dir.cleanup()
        raise RuntimeError("Could not create an MP4 from extracted MCAP frames")
    for frame in frames:
        resized = cv2.resize(frame, (width, height))
        writer.write(resized)
    writer.release()
    if not output.exists():
        temp_dir.cleanup()
        raise RuntimeError("MCAP frame extraction produced no output")
    return temp_dir, output


def _is_supported_type(msg_type):
    value = msg_type.lower()
    return any(
        marker in value
        for marker in (
            "compressedimage", "compressedvideo", "sensor_msgs/msg/image",
            "rawimage", "/image", "foxglove_msgs/msg/compressedvideo",
        )
    )


def _decode_image_message(message, msg_type):
    data = getattr(message, "data", None)
    if data is None:
        return None

    if "compressedimage" in msg_type:
        try:
            encoded = bytes(data)
            frame = cv2.imdecode(__import__("numpy").frombuffer(encoded, dtype=__import__("numpy").uint8), cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    if "rawimage" in msg_type:
        msg_type_name = msg_type

    try:
        width = int(getattr(message, "width"))
        height = int(getattr(message, "height"))
        encoding = str(getattr(message, "encoding", "rgb8")).lower()
    except (AttributeError, TypeError, ValueError):
        return None

    import numpy as np
    raw = np.frombuffer(bytes(data), dtype=np.uint8)

    if encoding in ("rgb8", "rgb"):
        frame = raw.reshape((height, width, 3))[:, :, ::-1]
    elif encoding in ("bgr8", "bgr"):
        frame = raw.reshape((height, width, 3))
    elif encoding in ("rgba8", "rgba"):
        frame = cv2.cvtColor(raw.reshape((height, width, 4)), cv2.COLOR_RGBA2BGR)
    elif encoding in ("bgra8", "bgra"):
        frame = cv2.cvtColor(raw.reshape((height, width, 4)), cv2.COLOR_BGRA2BGR)
    elif encoding in ("mono8", "gray", "8uc1"):
        frame = cv2.cvtColor(raw.reshape((height, width)), cv2.COLOR_GRAY2BGR)
    elif encoding in ("mono16", "16uc1"):
        array = np.frombuffer(bytes(data), dtype=np.uint16).reshape((height, width))
        normalized = cv2.normalize(array, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        frame = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    else:
        return None
    return frame
