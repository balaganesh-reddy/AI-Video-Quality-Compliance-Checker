This repository now includes a local MCAP card watcher.

## Start local automatic processing

```bat
py -3.11 -m pip install -r requirements.txt
py -3.11 run.py check
py -3.11 run.py watch
```

When a removable Windows drive is inserted and settles, the watcher scans it recursively for `*.mcap` files. Decodable frames are extracted to:

```text
output/results/<MCAP-name>/extracted_frames/
```

JSON and CSV results are written to `output/results/`. Until ONNX detectors are installed and configured, extracted files remain in `REVIEW`, so the pipeline cannot silently PASS.

## Manual processing

```bat
py -3.11 run.py process D:\
py -3.11 run.py frame recording.mcap 1000000000 output/frame.jpg
```

Stop the watcher with `Ctrl+C`.
