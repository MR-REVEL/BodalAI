#!/usr/bin/env python3
"""
Minimal Backend Service API v1 (FastAPI)

Endpoints:
- GET /health: simple liveness probe
- POST /validate-trp: validate TRP payload against schema
- POST /run-trp: run orchestrator on uploaded TRP JSON and return result JSON
- GET /artifacts/{name}: serve files from /artifacts (read-only)

Run locally:
  uvicorn runtime.service.app:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "trp.schema.json"
ORCHESTRATOR = ROOT / "runtime" / "orchestrator.py"
ARTIFACTS = Path("/artifacts")

app = FastAPI(title="BodalAI Service API v1")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/validate-trp")
def validate_trp(payload: Dict[str, Any]):
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"jsonschema not available: {exc}")
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)
        return {"status": "valid"}
    except Exception as e:  # broad: return validator error message
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/run-trp")
def run_trp(payload: Dict[str, Any]):
    # Write TRP to a temp file under /artifacts for traceability
    ARTIFACTS.mkdir(exist_ok=True)
    tmp = ARTIFACTS / "trp_request.json"
    tmp.write_text(json.dumps(payload), encoding="utf-8")

    cmd = [sys.executable, str(ORCHESTRATOR), "--trp", str(tmp)]
    # Optionally validate schema inside orchestrator as well
    # cmd += ["--validate-schema"]

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"orchestrator failed: {proc.stdout or proc.stderr}")

    try:
        result = json.loads(proc.stdout.strip())
    except Exception:
        # If orchestrator printed logs, wrap as text
        return JSONResponse(content={"status": "unknown", "raw": proc.stdout}, status_code=200)

    return result


@app.get("/artifacts/{name}")
def get_artifact(name: str):
    path = ARTIFACTS / name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    # Security: restrict traversal
    try:
        path.resolve().relative_to(ARTIFACTS.resolve())
    except Exception:
        raise HTTPException(status_code=403, detail="forbidden")
    return FileResponse(str(path))
