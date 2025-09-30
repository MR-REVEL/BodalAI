#!/usr/bin/env python3
"""
run_manim.py
Phase-1 tool: render a Manim scene to /artifacts as MP4.

Requirements:
- Manim Community v0.19.0
- FFmpeg available in PATH
- Entry point (.py) and scene class must exist

Usage example:
  python runtime/tools/run_manim.py \
    --entry-point /project/scene.py \
    --scene Intro \
    --width 854 --height 480 \
    --fps 24 \
    --out /artifacts/out.mp4 \
    --log /artifacts/run.log

Notes:
- We set MANIM_DISABLE_CACHING to reduce disk churn in ephemeral sandboxes.
- We avoid quality presets (-ql/-qm) and explicitly set resolution & FPS.
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def ensure_under(path: Path, allowed_roots):
    p = path.resolve()
    for root in allowed_roots:
        if str(p).startswith(str(Path(root).resolve())):
            return
    raise ValueError(f"Path must be under allowed roots {allowed_roots}: {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry-point", required=True, help="Path to the Python file containing the scene")
    ap.add_argument("--scene", required=True, help="Scene class name to render")
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--fps", type=int, required=True)
    ap.add_argument("--out", required=True, help="Output MP4 path under /artifacts")
    ap.add_argument("--extra-args", nargs="*", default=[], help="Additional CLI flags for manim")
    ap.add_argument("--log", default="/artifacts/run.log", help="Log file path under /artifacts")
    args = ap.parse_args()

    entry = Path(args.entry_point)
    out_path = Path(args.out)
    log_path = Path(args.log)

    # Basic path guards (Phase‑1); Phase‑2 will rely on container mounts
    ensure_under(entry, ["/project"])
    ensure_under(out_path, ["/artifacts"])
    ensure_under(log_path, ["/artifacts"])

    # Build manim command
    # Prefer explicit -r WxH and --fps for reproducibility
    cmd = [
        sys.executable, "-m", "manim",
        str(entry),
        args.scene,
        "-r", f"{args.width},{args.height}",
        "--fps", str(args.fps),
        "-o", out_path.name,      # Manim writes into its media dirs; we move/resolve below
        "--disable_caching"
    ]
    if args.extra_args:
        cmd.extend(args.extra_args)

    env = os.environ.copy()
    env["MANIM_DISABLE_CACHING"] = "1"  # belt & suspenders with --disable_caching
    # Force non-interactive rendering
    env["TERM"] = "dumb"

    # We run from /project so relative imports work cleanly for the user’s code
    cwd = Path("/project") if Path("/project").exists() else entry.parent

    # Run and tee logs into /artifacts/run.log
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as logf:
        logf.write(f"$ {' '.join(shlex.quote(x) for x in cmd)}\n\n")
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=logf, stderr=subprocess.STDOUT, text=True)
        rc = proc.returncode

    if rc != 0:
        print(f"Manim exited with code {rc}. See log: {log_path}", file=sys.stderr)
        sys.exit(rc)

    # Manim typically writes to ./media/videos/<module>/<quality>/out.mp4
    # Find the most recent mp4 in cwd and move/copy to requested /artifacts path if needed
    # If user supplied -o name, it should be present in media dirs
    produced = None
    for p in sorted(cwd.glob("media/videos/**/*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        produced = p
        break

    if not produced or not produced.exists():
        print("Could not locate produced MP4 under media/videos/. Check the log for details.", file=sys.stderr)
        sys.exit(3)

    # Ensure target directory exists; then copy/move
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if produced.resolve() != out_path.resolve():
        # Copy (rename may cross devices)
        out_path.write_bytes(produced.read_bytes())

    print(f"OK: wrote {out_path}")
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
