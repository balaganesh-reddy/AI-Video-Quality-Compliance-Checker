# Video Compliance Analyzer - Online Deployment

A Streamlit web interface is provided for browser-based video uploads.

## Streamlit Community Cloud

1. Open Streamlit Community Cloud and create a new app.
2. Select this repository and branch `main`.
3. Set the main file to `app.py`.
4. Set the requirements file to `web_requirements.txt`.
5. The `packages.txt` file installs FFmpeg.
6. Deploy.

The app accepts MP4, MOV, MKV, AVI, WMV, M4V, MPEG, MPG, and WebM uploads. It does not currently accept MCAP files.

## Hugging Face Spaces

Use this repository as a Docker or Streamlit Space, with `app.py` as the entry point and `web_requirements.txt` as the Python requirements. Add FFmpeg to the system image before deployment.

## Privacy

Uploads are temporarily written to the hosting environment during analysis and deleted after the request completes. Do not upload confidential recordings unless the selected hosting provider's retention and access policies are acceptable.
