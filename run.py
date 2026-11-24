#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os

from screening.config import load_config

HERE = os.path.dirname(os.path.abspath(__file__))


def setup_directories(cfg):
    for key in ("output_dir", "results_dir", "pending_dir", "backup_dir"):
        os.makedirs(cfg["paths"][key], exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Automatic MCAP card screening")
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    subparsers.add_parser("check")
    subparsers.add_parser("watch")

    process = subparsers.add_parser("process")
    process.add_argument("path")
    process.add_argument("--card-id", action="append", default=[])

    frame = subparsers.add_parser("frame")
    frame.add_argument("file")
    frame.add_argument("timestamp_ns", type=int)
    frame.add_argument("out")
    frame.add_argument("--topic")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    setup_directories(cfg)

    if args.cmd == "frame":
        import cv2
        from screening.extractor import extract_frame_at
        image = extract_frame_at(args.file, args.timestamp_ns, args.topic)
        if image is None:
            print("No frame found at that timestamp")
            return 1
        cv2.imwrite(args.out, image)
        print("Wrote", args.out)
        return 0

    from screening.pipeline import Screener
    screener = Screener(cfg)

    if args.cmd == "check":
        print(json.dumps(screener.check(), indent=2))
        return 0

    if args.cmd == "process":
        results = screener.process_path(args.path, args.card_id)
        for result in results:
            print(result["video_name"] + ": " + result["status"] + " " + result["reasons"])
        return 0

    if args.cmd == "watch":
        from screening.usb_watcher import watch

        def inserted(drive):
            print("SD/card inserted:", drive)
            results = screener.process_drive(drive)
            for result in results:
                print(result["video_name"] + ": " + result["status"] + " " + result["reasons"])

        print("Watching for inserted cards. Press Ctrl+C to stop.")
        try:
            watch(cfg["usb"], inserted)
        except KeyboardInterrupt:
            print("Stopped")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
