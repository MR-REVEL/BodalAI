"""
In-memory job queue and worker thread.
"""
import logging
import queue
import threading
from typing import Optional

from .config import CONFIG
from .models import Job

logger = logging.getLogger(__name__)

# Global queue and worker
_job_queue: queue.Queue = queue.Queue()
_worker_thread: Optional[threading.Thread] = None


def enqueue_job(job: Job) -> None:
    """Add a job to the execution queue."""
    _job_queue.put(job)
    logger.info(f"Enqueued job {job.job_id}")


def start_worker(executor_func):
    """
    Start the background worker thread.
    
    Note: Phase-1 uses CONFIG.CONCURRENCY=1 (single worker).
    Future phases may spawn multiple workers based on this value.
    """
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        logger.warning("Worker already running")
        return

    def worker():
        logger.info(f"Worker thread started (concurrency={CONFIG.CONCURRENCY})")
        while True:
            job = _job_queue.get()
            try:
                executor_func(job)
            except Exception as e:
                logger.exception(f"Worker failed for job {job.job_id}: {e}")
            finally:
                _job_queue.task_done()

    _worker_thread = threading.Thread(target=worker, daemon=True)
    _worker_thread.start()
