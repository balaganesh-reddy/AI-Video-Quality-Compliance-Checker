# AI Video Quality Compliance Checker

A Windows desktop application that detects removable/USB drives, recursively finds video files, evaluates quality/compliance, exports CSV reports, and optionally sends results to Google Sheets.

## Features

- Automatic removable-drive detection
- Manual folder browsing
- Recursive supported-video scanning
- FFprobe metadata checks
- OpenCV frame sharpness sampling
- Configurable compliance rules in `compliance_rules.json`
- UTC scan timestamps
- Background processing
- CSV and optional Google Sheets export

## Windows setup

1. Install Python 3.11 or newer.
2. Install FFmpeg and ensure `ffmpeg` and `ffprobe` are in `PATH`.
3. Open PowerShell in the repository:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Compliance rules

Use the **Rules** button in the app. Settings are stored in `compliance_rules.json`:

```json
{
  "minimum_width": 1280,
  "minimum_height": 720,
  "minimum_fps": 24,
  "minimum_duration_seconds": 1,
  "maximum_duration_seconds": 7200
}
```

The app reads source files directly and does not modify or delete them.
