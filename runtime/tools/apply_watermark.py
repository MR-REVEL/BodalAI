#!/usr/bin/env python3
"""
apply_watermark.py
Overlay a logo onto a video with percent-based size and margins.

Usage:
  python runtime/tools/apply_watermark.py ^
    --video-in /artifacts/out.mp4 ^
    --logo /project/watermark_logo.png ^
    --opacity 0.85 ^
    --size-pct 10 ^
    --margins-pct 4 ^
    --position br ^
    --video-out /artifacts/out_watermarked.mp4
"""
import argparse
import subprocess
import sys
from pathlib import Path

ALLOWED_POS = {"br", "bl", "tr", "tl"}


def ensure_under(path: Path, roots):
    rp = path.resolve()
    for r in roots:
        if str(rp).lower().startswith(str(Path(r).resolve()).lower()):
            return
    raise ValueError(f"Path must be under {roots}: {rp}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-in", required=True, help="Input MP4 under /artifacts")
    ap.add_argument("--logo", required=True, help="Logo image under /project (png recommended)")
    ap.add_argument("--video-out", required=True, help="Output MP4 under /artifacts")
    ap.add_argument("--opacity", type=float, default=0.85, help="0..1 alpha for logo")
    ap.add_argument("--size-pct", type=float, default=10.0, help="Logo width as % of video width")
    ap.add_argument("--margins-pct", type=float, default=4.0, help="Margins from edges as % of video dims")
    ap.add_argument("--position", choices=sorted(ALLOWED_POS), default="br", help="Logo corner: br/bl/tr/tl")
    ap.add_argument("--crf", type=int, default=20, help="x264 quality (lower=better)")
    ap.add_argument("--preset", default="veryfast", help="x264 speed/quality tradeoff")
    args = ap.parse_args()

    vin = Path(args.video_in)
    logo = Path(args.logo)
    vout = Path(args.video_out)

    if not vin.exists():
        print(f"Input video not found: {vin}", file=sys.stderr); sys.exit(2)
    if not logo.exists():
        print(f"Logo not found: {logo}", file=sys.stderr); sys.exit(2)

    ensure_under(vin, ["/artifacts"])
    ensure_under(vout, ["/artifacts"])
    ensure_under(logo, ["/project"])

    # Compute margin expression in pixels inside ffmpeg (percent of main frame)
    m = max(args.margins_pct, 0.0) / 100.0
    # Overlay positions
    pos_map = {
        "br": ("main_w - w - main_w*{m}", "main_h - h - main_h*{m}"),
        "bl": ("main_w*{m}",               "main_h - h - main_h*{m}"),
        "tr": ("main_w - w - main_w*{m}", "main_h*{m}"),
        "tl": ("main_w*{m}",               "main_h*{m}"),
    }
    ox, oy = pos_map[args.position]
    ox = ox.format(m=m)
    oy = oy.format(m=m)

    # Size ratio for logo relative to video width
    s = max(args.size_pct, 0.1) / 100.0
    opacity = min(max(args.opacity, 0.0), 1.0)

    # Build filter:
    # 1) Scale logo to % of main video width using scale2ref
    # 2) Apply alpha via colorchannelmixer
    # 3) Overlay with margins at selected corner
    # Inputs mapped as: [0:v]=video-in, [1:v]=logo
    filter_complex = (
        f"[1:v][0:v]scale2ref=w=main_w*{s}:h=-1[logo][base];"
        f"[logo]format=rgba,colorchannelmixer=aa={opacity}[logo_a];"
        f"[base][logo_a]overlay=x={ox}:y={oy}"
    )

    vout.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(vin),
        "-i", str(logo),
        "-filter_complex", filter_complex,
        # Map streams: keep audio if present, re-encode video due to overlay
        "-map", "0:v:0",
        "-map", "0:a?",  # optional audio
        "-c:v", "libx264", "-crf", str(args.crf), "-preset", args.preset,
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(vout),
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        sys.exit(proc.returncode)

    print(f"OK: wrote {vout}")


if __name__ == "__main__":
    main()
