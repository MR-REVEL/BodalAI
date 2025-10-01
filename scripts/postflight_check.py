#!/usr/bin/env python3
"""
Postflight checks: validate that an output video (as described by /artifacts/meta.json)
matches TRP constraints for duration and fps, with small tolerances.
"""
import argparse
import json
import math
import sys
from pathlib import Path


def load_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not read JSON from {p}: {e}", file=sys.stderr)
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description="Postflight: enforce duration and FPS against TRP constraints.")
    ap.add_argument("--trp", required=True, help="Path to the TRP JSON used for this run")
    ap.add_argument("--meta", default="/artifacts/meta.json", help="Path to ffprobe meta JSON")
    ap.add_argument("--tol", type=float, default=0.25, help="Duration tolerance seconds (+/-)")
    ap.add_argument("--fps-eps", type=float, default=0.05, help="Allowable absolute FPS deviation from 24.0")
    args = ap.parse_args()

    trp = load_json(Path(args.trp))
    meta = load_json(Path(args.meta))

    constraints = trp.get("constraints") or {}
    want_dur = constraints.get("duration_s")
    want_fps = constraints.get("fps", 24)
    got_dur = meta.get("duration_s")
    got_fps = meta.get("fps")

    failures = []

    # Duration check
    if isinstance(want_dur, (int, float)) and isinstance(got_dur, (int, float)):
        lo, hi = (want_dur - args.tol), (want_dur + args.tol)
        if not (lo <= got_dur <= hi):
            failures.append(
                f"Duration {got_dur:.3f}s outside [{lo:.3f}, {hi:.3f}] (target {want_dur:.3f}±{args.tol}s)"
            )
    else:
        failures.append(f"Missing duration (wanted={want_dur}, got={got_dur})")

    # FPS check
    if isinstance(got_fps, (int, float)):
        target_fps = 24.0 if want_fps is None else float(want_fps)
        if not math.isclose(float(got_fps), target_fps, abs_tol=args.fps_eps):
            failures.append(f"FPS {got_fps} not within ±{args.fps_eps} of {target_fps}")
    else:
        failures.append(f"Missing fps (got={got_fps})")

    if failures:
        print("Postflight: FAIL")
        for f in failures:
            print(f" - {f}")
        sys.exit(2)

    print("Postflight: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
