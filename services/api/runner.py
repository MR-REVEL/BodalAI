"""
Job runner: calls orchestrator via subprocess and updates job state.
"""
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from .config import ARTIFACTS_DIR, ORCHESTRATOR
from .models import Job, JobStatus
from .storage import save_job

logger = logging.getLogger(__name__)


def execute_job(job: Job) -> None:
    """
    Execute a TRP job using the orchestrator.
    Updates job status and saves results to disk.
    """
    logger.info(f"Starting execution for job {job.job_id}")
    job.status = JobStatus.RUNNING
    job.started_at = time.time()
    save_job(job)

    # Write TRP to temp file
    job_artifacts = ARTIFACTS_DIR / job.job_id
    job_artifacts.mkdir(parents=True, exist_ok=True)
    trp_file = job_artifacts / "trp_request.json"
    trp_file.write_text(json.dumps(job.trp, indent=2), encoding="utf-8")

    # Call orchestrator
    cmd = [sys.executable, str(ORCHESTRATOR), "--trp", str(trp_file), "--validate-schema"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    job.completed_at = time.time()

    if proc.returncode != 0:
        job.status = JobStatus.FAILED
        job.error = proc.stdout or proc.stderr
        logger.error(f"Job {job.job_id} failed: {job.error}")
    else:
        job.status = JobStatus.COMPLETED
        try:
            job.result = json.loads(proc.stdout.strip())
            # Collect artifact paths
            if "final_video" in job.result:
                job.artifacts["video"] = job.result["final_video"]
            if "meta" in job.result:
                job.artifacts["meta"] = job.result["meta"]
            if "thumbnail" in job.result:
                job.artifacts["thumbnail"] = job.result["thumbnail"]
            if "log" in job.result:
                job.artifacts["log"] = job.result["log"]
        except Exception as e:
            logger.warning(f"Could not parse orchestrator output for job {job.job_id}: {e}")
            job.result = {"raw": proc.stdout}

    save_job(job)
    logger.info(f"Job {job.job_id} finished with status {job.status.value}")
