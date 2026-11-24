# AI Video Quality Compliance Checker

Windows desktop application for reviewing video quality/compliance from USB drives. The initial checks focus on the three requested visual conditions: hands/wrists visible during the task, possible mobile-phone use, and adequate lighting.

## Checks

- **Hands/wrists:** samples frames and flags continuous hand absence beyond the configured threshold (default 60 seconds); estimates wrist landmark visibility.
- **Phone use:** detects the COCO `cell phone` class and flags frames where a detected phone is near a detected hand. Phone detection is a review signal only; it cannot identify social-media apps or determine what is shown on a phone screen.
- **Lighting:** measures average grayscale brightness in sampled frames and reports the well-lit-frame ratio.
- Video metadata is reported for reference. Minimum/maximum video duration are not used as pass/fail rules.

These automated signals can miss or misclassify content due to camera angle, occlusion, lighting, frame rate, model limitations, and the nature of the task. Review flagged and unflagged videos before making consequential decisions. The app processes video locally; the YOLO model weights may be downloaded the first time phone detection is used.

## Windows setup

1. Install Python 3.11 (MediaPipe support depends on Python/platform compatibility).
2. Install FFmpeg and add `ffprobe` to `PATH`.
3. In PowerShell, create an environment and install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Configure conditions

Choose **Visual Rules** in the application. Settings are saved in the local, ignored `compliance_rules.json` file. Defaults:

- Maximum continuous hand absence: 60 seconds
- Wrist/lighting visibility ratio: 75%
- Minimum average brightness: 55 on a 0–255 grayscale scale
- Phone detection confidence: 0.35
- Frame sampling interval: 1 second

The task itself is not known to the app, so it cannot yet decide whether the correct task or all required objects are visible. Wrist/hand and brightness checks are configurable screening proxies, not task-specific validation.

## Google Sheets export

Configure a Google service account as described in `.env.example` and the Google Cloud console, then check **Export to Google Sheets** before scanning.
