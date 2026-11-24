# AI Video Quality Compliance Checker

Windows desktop application for reviewing video quality/compliance from USB drives. It focuses on bilateral wrist visibility, prolonged possible mobile-phone use, and lighting.

## USB auto-scan

The app checks for removable drives every two seconds. **Auto-scan USB drives** is enabled by default: drives already connected at launch and drives inserted later are scanned automatically. Turn the checkbox off to disable auto-scanning; manual folder selection and scanning remain available.

Successfully analyzed files are recorded in a cache under `%LOCALAPPDATA%\\AI-Video-Quality-Compliance-Checker\\scan_cache.json`. The cache uses a USB volume ID when Windows provides one, the file's relative path, size, and modification time. Unchanged files are skipped on subsequent scans; changed files are analyzed again. Files that fail analysis are not cached so they can be retried. The app reads source files only and does not modify or delete them.

## Compliance checks

- **Wrist visibility (critical):** both wrist landmarks must be confidently visible and in-frame. Default minimum is 90% of sampled frames; falling below it marks the video **FAIL**.
- **Possible phone use:** a phone detected near a hand is counted as possible use. A continuous detected period longer than 120 seconds marks the video **FAIL**. The detector cannot determine whether a person is using social media or what is shown on-screen.
- **Lighting:** insufficient brightness/coverage marks the video **FAIL** according to configurable thresholds.
- **Hand absence:** a long absence remains a review signal; it is not the primary wrist-motion criterion.

These are automated estimates. Occlusion, camera angle, PPE, blur, sampling intervals, and detector limitations can cause false positives or negatives. Validate against representative videos and have a person review results before consequential decisions.

## Windows setup

1. Install Python 3.11 (MediaPipe support depends on platform/Python compatibility).
2. Install FFmpeg and add `ffprobe` to `PATH`.
3. In PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Phone detection uses an Ultralytics COCO model and may download model weights at first use. Video processing is local.

## Adjusting rules

Choose **Visual Rules** in the app. Settings are saved in the local, ignored `compliance_rules.json`. Defaults include a 120-second phone-use limit and 90% bilateral wrist visibility.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Google Sheets export

Set up a Google service account as described in `.env.example`, then select **Export to Google Sheets** before scanning.
