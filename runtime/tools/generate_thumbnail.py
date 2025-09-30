#!/usr/bin/env python3
"""
generate_thumbnail.py
Extract a single frame from a video at a given time.

Usage:
  python runtime/tools/generate_thumbnail.py \
    --video /artifacts/out.mp4 \
    --time-s 0.5 \
    --out /artifacts/out.jpg
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--time-s", type=float, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jpeg-quality", type=int, default=2, help="Lower is better quality (ffmpeg -q:v)")
    args = ap.parse_args()

    video = Path(args.video)
    out = Path(args.out)
    if not video.exists():
        print(f"Video not found: {video}", file=sys.stderr)
        sys.exit(2)

    out.parent.mkdir(parents=True, exist_ok=True)

    # -ss before -i seeks quickly; -frames:v 1 grabs a single frame
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(args.time_s),
        "-i", str(video),
        "-frames:v", "1",
        "-q:v", str(args.jpeg_quality),
        str(out)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        sys.exit(proc.returncode)

    print(f"OK: wrote {out}")


if __name__ == "__main__":
    main()
