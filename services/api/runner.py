"""
Job runner: calls orchestrator via subprocess and updates job state.
"""
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from .config import CONFIG
from .models import Job, JobStatus
from .storage import save_job

logger = logging.getLogger(__name__)


def execute_job(job: Job) -> None:
    """
    Execute a TRP job using the orchestrator.
    Updates job status and saves results to disk.
    
    Uses CONFIG for:
    - ARTIFACTS_ROOT: base path for job artifacts
    - ORCHESTRATOR: path to orchestrator.py
    - SCHEMA_PATH: TRP schema for validation
    - LOGO_DEFAULT: watermark logo (future use)
    """
    logger.info(f"Starting execution for job {job.id}")
    job.set_status(JobStatus.RUNNING)  # Auto-sets started_ts
    save_job(job)

    # Create job-specific artifact directory
    job_artifacts = CONFIG.ARTIFACTS_ROOT / job.id
    job_artifacts.mkdir(parents=True, exist_ok=True)
    
    # Write TRP to job artifacts directory
    trp_file = job_artifacts / "trp_request.json"
    trp_file.write_text(json.dumps(job.trp, indent=2), encoding="utf-8")
    
    # Write run log to job artifacts
    run_log = job_artifacts / "run.log"

    # Call orchestrator with schema validation
    cmd = [
        sys.executable,
        str(CONFIG.ORCHESTRATOR),
        "--trp", str(trp_file),
        "--validate-schema"
    ]
    
    logger.info(f"Executing: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    
    # Save run log
    run_log.write_text(
        f"COMMAND: {' '.join(cmd)}\n\n"
        f"STDOUT:\n{proc.stdout}\n\n"
        f"STDERR:\n{proc.stderr}\n\n"
        f"RETURNCODE: {proc.returncode}\n",
        encoding="utf-8"
    )

    if proc.returncode != 0:
        # set_error automatically sets status to FAILED and finished_ts
        error_msg = proc.stdout or proc.stderr
        job.set_error(error_msg)
        logger.error(f"Job {job.id} failed: {error_msg}")
    else:
        try:
            result = json.loads(proc.stdout.strip())
            # Collect artifact paths from orchestrator output
            artifacts = {}
            if "final_video" in result:
                artifacts["video"] = result["final_video"]
            if "meta" in result:
                artifacts["meta"] = result["meta"]
            if "thumbnail" in result:
                artifacts["thumbnail"] = result["thumbnail"]
            if "log" in result:
                artifacts["log"] = result["log"]
            # Add run log
            artifacts["run_log"] = str(run_log)
            
            job.set_artifacts(artifacts)
            job.set_status(JobStatus.SUCCEEDED)  # Auto-sets finished_ts
        except Exception as e:
            logger.warning(f"Could not parse orchestrator output for job {job.id}: {e}")
            # Still mark as succeeded but note parsing issue
            job.set_artifacts({"run_log": str(run_log), "raw_output": proc.stdout})
            job.set_status(JobStatus.SUCCEEDED)

    save_job(job)
    logger.info(f"Job {job.id} finished with status {job.status.value}")
