import csv
import tempfile
from pathlib import Path

import streamlit as st

from app.analyzer import analyze_video
from app.config import ComplianceRules, load_rules


st.set_page.set_page_config(page_title="Video Compliance Analyzer", layout="wide")

st.title("Video Compliance Analyzer")
st.caption("Online review for wrist visibility, possible phone use, lighting, and hand absence")

st.warning(
    "Screening results are probabilistic and are not proof of behavior or compliance. "
    "Use human review before any consequential action.",
    icon="⚠️",
)

with st.sidebar:
    st.header("Rules")
    wrist_ratio = st.slider("Minimum both-wrist visibility", 0.0, 1.0, 0.90, 0.01)
    wrist_confidence = st.slider("Wrist landmark confidence", 0.0, 1.0, 0.60, 0.01)
    phone_seconds = st.slider("Possible phone-use failure limit (seconds)", 1, 600, 120, 1)
    phone_confidence = st.slider("Phone detection confidence", 0.0, 1.0, 0.35, 0.01)
    lighting_ratio = st.slider("Minimum well-lit frame ratio", 0.0, 1.0, 0.75, 0.01)
    average_brightness = st.slider("Minimum average brightness", 0, 255, 55, 1)
    hand_absence = st.slider("Hand absence review limit (seconds)", 0, 3600, 60, 1)
    sample_interval = st.slider("Sampling interval (seconds)", 0.25, 30.0, 1.0, 0.25)

rules = ComplianceRules(
    minimum_wrist_visible_frame_ratio=wrist_ratio,
    minimum_wrist_visibility_confidence=wrist_confidence,
    maximum_phone_use_seconds=float(phone_seconds),
    phone_detection_confidence=phone_confidence,
    minimum_well_lit_frame_ratio=lighting_ratio,
    minimum_average_brightness=float(average_brightness),
    maximum_hand_absence_seconds=float(hand_absence),
    sample_interval_seconds=float(sample_interval),
)

uploaded = st.file_uploader(
    "Upload one or more videos",
    type=["mp4", "mov", "mkv", "avi", "wmv", "m4v", "mpeg", "mpg", "webm"],
    accept_multiple_files=True,
)

if uploaded:
    st.write(f"**{len(uploaded)} file(s) selected**")

if st.button("Analyze uploaded videos", type="primary", disabled=not uploaded):
    results = []
    progress = st.progress(0)

    for index, upload in enumerate(uploaded, start=1):
        suffix = Path(upload.name).suffix.lower()
        with tempfile.TemporaryDirectory(prefix="video_compliance_") as directory:
            video_path = Path(directory) / ("upload" + suffix)
            video_path.write_bytes(upload.getbuffer())

            try:
                result = analyze_video(video_path, rules)
                result["file_name"] = upload.name
            except Exception as exc:
                result = {
                    "file_name": upload.name,
                    "status": "ERROR",
                    "issues": str(exc),
                }

            results.append(result)
            progress.progress(index / len(uploaded))

    if results:
        st.subheader("Results")
        st.dataframe(results, use_container_width=True)

        failing = sum(result.get("status") == "FAIL" for result in results)
        passing = sum(result.get("status") == "PASS" for result in results)
        errors = sum(result.get("status") == "ERROR" for result in results)
        columns = st.columns(3)
        columns[0].metric("PASS", passing)
        columns[1].metric("FAIL", failing)
        columns[2].metric("ERROR", errors)

        fields = list(dict.fromkeys(key for result in results for key in result))
        output = tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="w", newline="", encoding="utf-8")
        with output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)

        st.download_button(
            "Download CSV results",
            data=Path(output.name).read_bytes(),
            file_name="video-compliance-results.csv",
            mime="text/csv",
        )
