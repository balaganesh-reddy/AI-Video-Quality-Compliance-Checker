# AI Video Quality Compliance Checker

A Windows desktop application that detects removable/USB drives, recursively finds video files, evaluates basic quality and compliance rules, exports a CSV report, and optionally sends results to Google Sheets.

## Features

- Automatic removable-drive detection every 2 seconds
- Manual folder browsing
- Recursive supported video scanning
- FFprobe metadata checks
- OpenCV frame sharpness sampling
- Background processing
- CSV export
- Optional Google Sheets export through a service account

## Windows setup

1. Install Python 3.11 or newer.
2. Install FFmpeg and add `ffmpeg` and `ffprobe` to `PATH`.
3. Create a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Google Sheets setup

1. Create a Google Cloud project.
2. Enable Google Sheets API and Google Drive API.
3. Create a service account and download its JSON key.
4. Save it as `credentials/service-account.json`.
5. Create a Google Sheet and share it with the service account email.
6. Copy `.env.example` to `.env` and set `GOOGLE_SHEET_NAME`.

## Compliance rules

Rules are in `app/analyzer.py`:

- Minimum width: 1280
- Minimum height: 720
- Minimum FPS: 24
- Minimum duration: 1 second
- Maximum duration: 7200 seconds

The app reads source files directly and does not modify or delete them.
