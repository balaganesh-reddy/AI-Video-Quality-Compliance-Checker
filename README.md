# AI Video Quality Compliance Checker

Windows desktop application for USB video screening.

## Supported inputs

- Standard video files: MP4, MOV, MKV, AVI, WMV, M4V, MPEG, MPG, and WebM.
- MCAP recordings containing supported image/video topics.

MCAP support currently extracts frames from common ROS/ROS 2 and Foxglove topics:

- `sensor_msgs/msg/CompressedImage`
- `sensor_msgs/msg/Image`
- Foxglove `CompressedImage` and `RawImage`
- Foxglove `CompressedVideo`

Sensor images are reconstructed into a temporary 10 FPS MP4 for metadata and visual analysis. MCAP files that contain no supported image/video topic are reported as unsupported. Raw encodings include RGB8, BGR8, RGBA8, BGRA8, MONO8, and MONO16.

## Safety classifications

- **Minor-like appearance:** a detected face classified into a child/minor-like age bucket is marked `FAIL` and is routed to the dedicated `NSFW` Google Sheet.
- **NSFW:** sampled frames classified above the configured confidence are marked `FAIL` and sent to the same dedicated `NSFW` sheet.
- **Wrists and hands:** insufficient bilateral wrist visibility and prolonged phone use remain hard quality failures.
- **Lighting:** insufficient sampled-frame brightness remains a hard quality failure.

## Setup

1. Install Python 3.11 (MediaPipe support depends on platform/Python compatibility).
2. Install FFmpeg and add `ffprobe` to `PATH`.
3. Install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

The MCAP reader requires `mcap`, `mcap-ros1-support`, `mcap-ros2-support`, and `rosbags`. It does not upload recordings or extracted frames.
