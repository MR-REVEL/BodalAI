#!/usr/bin/env python3
"""
Orchestrator v0: execute a TRP plan end to end.

Features:
- Load a TRP JSON
- Optionally validate against the schema
- Run prep (AST linter) and each tool step in order
- Ensure metadata is captured and run postflight checks (duration/FPS)
- Apply watermark when required (if not already done via plan)
- Produce a result JSON documenting artifacts and timing

Usage:
  python runtime/orchestrator.py --trp examples/trp/trp_free_trial_30s_valid.json --validate-schema
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCHEMA_PATH = ROOT / "schemas" / "trp.schema.json"
POSTFLIGHT_SCRIPT = ROOT / "scripts" / "postflight_check.py"
LINTER = ROOT / "runtime" / "ast_linter.py"
RUN_MANIM = HERE / "tools" / "run_manim.py"
APPLY_WATERMARK = HERE / "tools" / "apply_watermark.py"
FFPROBE = HERE / "tools" / "ffprobe_meta.py"
THUMBNAIL = HERE / "tools" / "generate_thumbnail.py"

ARTIFACT_DEFAULTS = {
    "video": "/artifacts/out.mp4",
    "watermarked": "/artifacts/out_watermarked.mp4",
    "thumbnail": "/artifacts/out.jpg",
    "meta": "/artifacts/meta.json",
    "log": "/artifacts/run.log",
}


def run_subprocess(cmd: List[str], *, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    start = time.perf_counter()
    cp = subprocess.run(cmd, text=True, env=env)
    cp.elapsed = time.perf_counter() - start  # type: ignore[attr-defined]
    return cp


def ensure_paths():
    project_root = Path("/project")
    artifacts_root = Path("/artifacts")
    project_root.mkdir(exist_ok=True)
    artifacts_root.mkdir(exist_ok=True)

    # Stage branding assets so watermark defaults work out of the box
    branding_dir = project_root / "config"
    branding_dir.mkdir(parents=True, exist_ok=True)
    for name in ("watermark.png", "Main Logo.png"):
        src = ROOT / "config" / name
        if src.exists():
            dst = branding_dir / name
            if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)

    # Legacy alias expected by some TRPs
    default_logo = branding_dir / "watermark.png"
    legacy_logo = project_root / "watermark_logo.png"
    if default_logo.exists() and not legacy_logo.exists():
        shutil.copy2(default_logo, legacy_logo)


def validate_schema(trp: dict) -> None:
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception as exc:  # pragma: no cover - guard for missing dependency
        print("jsonschema not installed; skipping validation", file=sys.stderr)
        print(exc, file=sys.stderr)
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(trp)
    print("Schema validation: PASS")


def run_ast_linter(source_files: List[str]) -> None:
    if not source_files:
        return
    existing = [f for f in source_files if Path(f).exists()]
    if not existing:
        print("AST linter: no existing files to lint; skipping")
        return
    cp = run_subprocess([sys.executable, str(LINTER), "--paths", *existing])
    if cp.returncode != 0:
        raise SystemExit(f"AST linter failed (rc={cp.returncode})")


def stage_file(path_str: str) -> Path:
    path = Path(path_str)
    project_root = Path("/project").resolve()

    # Already under /project?
    try:
        if path.is_absolute() and Path(path).resolve().is_relative_to(project_root):  # type: ignore[attr-defined]
            return path
    except AttributeError:
        # Python <3.9 compat; fallback manual check
        if path.is_absolute() and str(Path(path).resolve()).lower().startswith(str(project_root).lower()):
            return path

    candidates: List[Path] = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(ROOT / path)
        candidates.append(Path.cwd() / path)

    for candidate in candidates:
        if candidate.exists():
            relative_part = path.name if path.is_absolute() else path
            dest = project_root / relative_part
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, dest)
            return dest

    raise SystemExit(f"Source file not found for staging: {path_str}")


def stage_sources(source_files: List[str]) -> Dict[str, Path]:
    staged: Dict[str, Path] = {}
    for item in source_files:
        staged[item] = stage_file(item)
    return staged


def handle_run_manim(params: Dict[str, Any], constraints: Dict[str, Any]) -> str:
    entry_in_project = stage_file(params["entry_point"])
    cmd = [
        sys.executable,
        str(RUN_MANIM),
        "--entry-point",
        str(entry_in_project),
        "--scene",
        params["scene"],
        "--fps",
        str(params.get("fps", constraints.get("fps", 24))),
        "--out",
        ARTIFACT_DEFAULTS["video"],
        "--log",
        ARTIFACT_DEFAULTS["log"],
    ]
    # Optional explicit resolution overrides the preset
    resolution = constraints.get("resolution", {})
    if "width" in resolution and "height" in resolution:
        cmd.extend(["--width", str(resolution["width"]), "--height", str(resolution["height"])])
    cp = run_subprocess(cmd)
    if cp.returncode != 0:
        raise SystemExit("run_manim failed")
    return ARTIFACT_DEFAULTS["video"]


def handle_ffprobe(video: str, json_out: Optional[str] = None) -> str:
    meta_path = json_out or ARTIFACT_DEFAULTS["meta"]
    cmd = [
        sys.executable,
        str(FFPROBE),
        "--video",
        video,
        "--json-out",
        meta_path,
    ]
    cp = run_subprocess(cmd)
    if cp.returncode != 0:
        raise SystemExit("ffprobe_meta failed")
    return meta_path


def handle_thumbnail(video: str, params: Dict[str, Any]) -> str:
    cmd = [
        sys.executable,
        str(THUMBNAIL),
        "--video",
        video,
        "--out",
        params.get("out", ARTIFACT_DEFAULTS["thumbnail"]),
    ]
    if "time_s" in params:
        cmd += ["--time-s", str(params["time_s"])]
    cp = run_subprocess(cmd)
    if cp.returncode != 0:
        raise SystemExit("generate_thumbnail failed")
    return params.get("out", ARTIFACT_DEFAULTS["thumbnail"])


def handle_apply_watermark(params: Dict[str, Any], default_video: str) -> str:
    cmd = [
        sys.executable,
        str(APPLY_WATERMARK),
        "--video-in",
        params.get("video_in", default_video),
    ]
    if "logo_path" in params or "logo" in params:
        cmd += ["--logo", params.get("logo_path", params.get("logo"))]
    if "video_out" in params:
        cmd += ["--video-out", params["video_out"]]
    for key, flag in [("opacity", "--opacity"), ("size_pct", "--size-pct"), ("margins_pct", "--margins-pct"), ("position", "--position")]:
        if key in params:
            cmd += [flag, str(params[key])]
    cp = run_subprocess(cmd)
    if cp.returncode != 0:
        raise SystemExit("apply_watermark failed")
    # Script auto-appends _watermarked if no explicit output
    if "video_out" in params:
        return params["video_out"]
    vin = Path(params.get("video_in", default_video))
    return str(vin.with_name(vin.stem + "_watermarked" + vin.suffix))


def run_postflight(trp_path: Path, meta: str, tol: float = 0.25, fps_eps: float = 0.05) -> None:
    cmd = [
        sys.executable,
        str(POSTFLIGHT_SCRIPT),
        "--trp",
        str(trp_path),
        "--meta",
        meta,
        "--tol",
        str(tol),
        "--fps-eps",
        str(fps_eps),
    ]
    cp = run_subprocess(cmd)
    if cp.returncode != 0:
        raise SystemExit("postflight check failed")


def run_plan(trp: Dict[str, Any], trp_path: Path, staged_sources: Dict[str, Path]) -> Dict[str, Any]:
    constraints = trp.get("constraints", {})
    watermark_required = constraints.get("watermark_required", False)

    final_video = ARTIFACT_DEFAULTS["video"]
    watermark_applied = False
    timings: List[Dict[str, Any]] = []

    steps = trp.get("plan", {}).get("steps", [])
    for idx, step in enumerate(steps, start=1):
        tool = step.get("tool")
        params = step.get("params", {})
        if not tool:
            raise SystemExit(f"Plan step {idx} missing tool name")
        start = time.perf_counter()
        if tool == "lint_ast":
            resolved = [str(staged_sources.get(p, stage_file(p))) for p in params.get("paths", [])]
            run_ast_linter(resolved)
        elif tool == "run_manim":
            final_video = handle_run_manim(params, constraints)
        elif tool == "ffprobe_meta":
            meta = handle_ffprobe(params.get("video", final_video))
        elif tool == "generate_thumbnail":
            handle_thumbnail(params.get("video", final_video), params)
        elif tool == "apply_watermark":
            final_video = handle_apply_watermark(params, final_video)
            watermark_applied = True
        elif tool == "noop":
            pass
        elif tool == "postflight":
            # Allow plan to force postflight with custom tolerances
            handle_ffprobe(params.get("video", final_video))
            run_postflight(trp_path, params.get("meta", ARTIFACT_DEFAULTS["meta"]), params.get("tol", 0.25), params.get("fps_eps", 0.05))
        else:
            raise SystemExit(f"Unknown tool: {tool}")
        timings.append({"step": tool, "elapsed_s": time.perf_counter() - start})

    # Ensure metadata is fresh
    meta_path = handle_ffprobe(final_video)
    run_postflight(trp_path, meta_path)

    if watermark_required and not watermark_applied:
        final_video = handle_apply_watermark({}, final_video)
        meta_path = handle_ffprobe(final_video)
        run_postflight(trp_path, meta_path)

    return {
        "status": "pass",
        "final_video": final_video,
        "meta": meta_path,
        "thumbnail": ARTIFACT_DEFAULTS["thumbnail"],
        "log": ARTIFACT_DEFAULTS["log"],
        "timings": timings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a TRP end to end")
    parser.add_argument("--trp", required=True, help="Path to TRP JSON")
    parser.add_argument("--validate-schema", action="store_true", help="Validate against schemas/trp.schema.json")
    args = parser.parse_args()

    trp_path = Path(args.trp).resolve()
    if not trp_path.exists():
        raise SystemExit(f"TRP not found: {trp_path}")

    ensure_paths()
    trp = json.loads(trp_path.read_text(encoding="utf-8"))

    if args.validate_schema:
        validate_schema(trp)

    inputs = trp.get("inputs", {})
    staged_sources = stage_sources(inputs.get("source_files", []))
    run_ast_linter([str(path) for path in staged_sources.values()])

    result = run_plan(trp, trp_path, staged_sources)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
