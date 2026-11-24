# AI Video Quality Compliance Checker

Windows desktop application for reviewing video quality/compliance from USB drives. It focuses on bilateral wrist visibility, prolonged possible mobile-phone use, and lighting.

## Compliance checks

- **Wrist visibility (critical):** both wrist landmarks must be confidently visible and in-frame. Default minimum is 90% of sampled frames; falling below it marks the video **FAIL**.
- **Possible phone use:** a phone detected near a hand is counted as possible use. A continuous detected period longer than 120 seconds marks the video **FAIL**. Change the limit to 60–120 seconds in **Visual Rules** if your policy is stricter. The detector cannot determine whether a person is using social media or what appears on the screen.
- **Lighting:** insufficient brightness/coverage marks the video **FAIL** according to configurable thresholds.
- **Hand absence:** a long absence remains a review signal; it is not the primary wrist-motion criterion.

The app samples frames at the configured interval, so short events between samples may be missed. Occlusion, camera angle, PPE, blur, and detector limitations can also cause false positives/negatives. Validate thresholds on representative videos and have a human review results before consequential decisions. Video duration itself is not a pass/fail condition.

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

Phone detection uses an Ultralytics COCO model and may download its model weights at first use. All video processing is local.

## Adjusting rules

Choose **Visual Rules** in the app. Settings are stored in the local, ignored `compliance_rules.json` file. Defaults include a 120-second phone-use limit and 90% bilateral wrist visibility. The phone limit is configurable from 1 to 600 seconds.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Google Sheets export

Set up a Google service account as described in `.env.example`, then select **Export to Google Sheets** before scanning.
