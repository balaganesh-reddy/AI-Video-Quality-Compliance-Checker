# AI Video Quality Compliance Checker

A Windows desktop application that detects removable/USB drives and recursively analyzes supported video files and ROS MCAP recordings.

## Supported inputs

- Standard video: MP4, MOV, MKV, AVI, WMV, M4V, MPEG, MPG, and WebM
- MCAP: recordings containing supported image or video topics

### MCAP topics

Extraction currently supports:

- `sensor_msgs/msg/CompressedImage`
- `sensor_msgs/msg/Image`
- Foxglove and common `CompressedImage`/`RawImage` topics
- Foxglove `CompressedVideo` where the payload codec is H264, H265/HEVC, or AV1

Raw-image encodings supported include RGB8, BGR8, RGBA8, BGRA8, MONO8, and MONO16. Extracted frames are written to a temporary MP4 and analyzed by the existing FFprobe/OpenCV pipeline. The temporary file is deleted after analysis.

MCAP files with no supported topic are reported as an error rather than silently passing.

## Setup

1. Install Python 3.11 or newer.
2. Install FFmpeg and add `ffmpeg` and `ffprobe` to `PATH`.
3. Create an environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

For MCAP support, `rosbags` provides the recording reader and `mcap` provides MCAP parsing.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The app reads source files directly and does not modify or delete them.
