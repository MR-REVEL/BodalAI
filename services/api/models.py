"""
Data models for job management.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Represents a TRP execution job."""
    job_id: str
    status: JobStatus
    trp: Dict[str, Any]
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
