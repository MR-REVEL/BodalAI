#!/usr/bin/env python3
"""
ffprobe_meta.py
Extract duration (seconds), fps, width, height from a video using ffprobe.

Usage:
  python runtime/tools/ffprobe_meta.py --video /artifacts/out.mp4 --json-out /artifacts/meta.json
"""

import argparse
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def ffprobe_json(video: Path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,avg_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        str(video)
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout)


def rational_to_float(text):
    # Handles "24/1" etc.
    try:
        return float(Fraction(text))
    except Exception:
        try:
            return float(text)
        except Exception:
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"Video not found: {video}", file=sys.stderr)
        sys.exit(2)

    data = ffprobe_json(video)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}

    width = stream.get("width")
    height = stream.get("height")

    # Prefer avg_frame_rate; fallback to r_frame_rate
    fps_text = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    fps = rational_to_float(fps_text) if fps_text else None

    duration = None
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except Exception:
            pass

    meta = {
        "video": str(video),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_s": duration
    }

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"OK: wrote {out}")
    else:
        print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
