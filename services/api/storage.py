"""
JSON persistence helpers for job storage.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import JOBS_DIR
from .models import Job, JobStatus


def save_job(job: Job) -> None:
    """Save job to disk as JSON."""
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_file = JOBS_DIR / f"{job.job_id}.json"
    data = {
        "job_id": job.job_id,
        "status": job.status.value,
        "trp": job.trp,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "result": job.result,
        "error": job.error,
        "artifacts": job.artifacts,
    }
    job_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_job(job_id: str) -> Optional[Job]:
    """Load job from disk by ID."""
    job_file = JOBS_DIR / f"{job_id}.json"
    if not job_file.exists():
        return None
    data = json.loads(job_file.read_text(encoding="utf-8"))
    return Job(
        job_id=data["job_id"],
        status=JobStatus(data["status"]),
        trp=data["trp"],
        created_at=data["created_at"],
        started_at=data.get("started_at"),
        completed_at=data.get("completed_at"),
        result=data.get("result"),
        error=data.get("error"),
        artifacts=data.get("artifacts", {}),
    )
