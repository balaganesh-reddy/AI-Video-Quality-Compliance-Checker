# AI Video Quality Compliance Checker

Windows desktop application for USB video screening.

## Safety classifications

- **Minor-like appearance:** any sampled detected face classified into a child/minor-like age bucket is marked `FAIL` and is immediately routed to the dedicated `NSFW` Google Sheet. Because visual age estimation is uncertain, the app stores `minor_like_detected` and confidence rather than asserting a verified age.
- **NSFW:** sampled frames classified above the configured confidence are marked `FAIL` and sent to the same dedicated `NSFW` sheet.
- **Wrists and hands:** insufficient bilateral wrist visibility and prolonged phone use remain hard quality failures.
- **Lighting:** insufficient sampled-frame brightness remains a hard quality failure.

The classifiers are probabilistic screening tools. They can miss content and can produce false positives. Downloaded model weights are processed locally; no video frame is uploaded by this app.

## Setup

1. Install Python 3.11 (MediaPipe support depends on platform/Python compatibility).
2. Install FFmpeg and add `ffprobe` to `PATH`.
3. Create and activate a virtual environment, then install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

At first use, Transformers may download the age and NSFW models; Ultralytics may download `yolo11n.pt`.

## Google Sheets

Regular results are written to `Results`. Any row with `minor_like_detected=true` or `nsfw_detected=true` is also written to the dedicated `NSFW` worksheet. Restrict access to that worksheet according to your data policy.
