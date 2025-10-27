"""
JSON persistence helpers for job storage.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .config import CONFIG
from .models import Job


def save_job(job: Job) -> None:
    """
    Save job to disk as JSON.
    
    Jobs are persisted under CONFIG.JOBS_ROOT/{id}.json
    Uses Job.as_dict() for consistent serialization.
    """
    CONFIG.JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    job_file = CONFIG.JOBS_ROOT / f"{job.id}.json"
    data = job.as_dict()
    job_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_job(job_id: str) -> Optional[Job]:
    """
    Load job from disk by ID.
    
    Reads from CONFIG.JOBS_ROOT/{job_id}.json
    Uses Job.from_dict() for consistent deserialization.
    """
    job_file = CONFIG.JOBS_ROOT / f"{job_id}.json"
    if not job_file.exists():
        return None
    data = json.loads(job_file.read_text(encoding="utf-8"))
    return Job.from_dict(data)
