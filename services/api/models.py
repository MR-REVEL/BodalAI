"""
Data models for job management.

Defines the canonical job model and status lifecycle for BodalAI's backend.
Ensures data integrity, safe state transitions, and developer-friendly debugging.

Job Lifecycle:
    PENDING → RUNNING → (SUCCEEDED | FAILED)
    
    - PENDING: Job accepted, waiting in queue
    - RUNNING: Worker claimed job, executing pipeline
    - SUCCEEDED: Completed successfully with artifacts
    - FAILED: Completed with error

JSON Serialization:
    - JobStatus serializes as lowercase strings ("pending", "running", etc.)
    - Timestamps are Unix epoch floats
    - All fields are optional except id, status, trp, tier, created_ts
    
Example:
    >>> job = new_job_from_trp({"user_tier": "free", ...})
    >>> job.set_status(JobStatus.RUNNING)
    >>> job.set_artifacts({"video": "/path/to/video.mp4"})
    >>> job.set_status(JobStatus.SUCCEEDED)
    >>> json_data = job.as_dict()
"""
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

# Import CONFIG for artifacts_dir helper (no side effects on import)
try:
    from .config import CONFIG
except ImportError:
    # Fallback for testing without full service context
    CONFIG = None


class JobStatus(str, Enum):
    """
    Job execution status with lifecycle constraints.
    
    Valid transitions:
        PENDING → RUNNING → SUCCEEDED
        PENDING → RUNNING → FAILED
        
    Invalid transitions:
        RUNNING → PENDING (can't un-start)
        SUCCEEDED → RUNNING (can't restart)
        FAILED → RUNNING (can't restart)
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"  # Changed from COMPLETED for clarity
    FAILED = "failed"
    
    def __str__(self) -> str:
        """Return lowercase value for JSON serialization."""
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> "JobStatus":
        """
        Parse status from string with validation.
        
        Args:
            value: Status string (case-insensitive)
            
        Returns:
            JobStatus enum
            
        Raises:
            ValueError: If status is invalid
        """
        value_lower = value.lower()
        for status in cls:
            if status.value == value_lower:
                return status
        raise ValueError(
            f"Invalid job status: '{value}'. "
            f"Valid statuses: {', '.join(s.value for s in cls)}"
        )


# Valid state transitions (current_status → allowed_next_statuses)
_VALID_TRANSITIONS: Dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.RUNNING},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED},
    JobStatus.SUCCEEDED: set(),  # Terminal state
    JobStatus.FAILED: set(),     # Terminal state
}


@dataclass
class Job:
    """
    Represents a TRP execution job with lifecycle management.
    
    Attributes:
        id: Unique job identifier (UUID v4)
        project_id: Optional project association
        tier: User tier ("free" or "premium")
        trp: Original TRP payload (validated JSON)
        status: Current execution status
        created_ts: Job creation timestamp (Unix epoch)
        started_ts: Execution start timestamp (None if not started)
        finished_ts: Completion timestamp (None if not finished)
        artifacts: Output file paths (video, thumbnail, meta, log)
        error: Error message if FAILED (None otherwise)
        
    Methods:
        as_dict(): Serialize to JSON-safe dict
        from_dict(data): Deserialize from dict with validation
        set_status(status): Transition to new status with validation
        set_artifacts(mapping): Merge artifact paths
        set_error(message): Mark as FAILED with error message
    """
    id: str
    trp: Dict[str, Any]
    tier: str
    status: JobStatus
    created_ts: float
    project_id: Optional[str] = None
    started_ts: Optional[float] = None
    finished_ts: Optional[float] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    
    def __post_init__(self):
        """Validate job data after initialization."""
        # Validate ID format (UUID v4)
        validate_job_id(self.id)
        
        # Validate tier
        if self.tier not in {"free", "premium"}:
            raise ValueError(f"Invalid tier: '{self.tier}'. Must be 'free' or 'premium'.")
        
        # Ensure status is JobStatus enum
        if isinstance(self.status, str):
            self.status = JobStatus.from_string(self.status)
    
    def as_dict(self) -> Dict[str, Any]:
        """
        Serialize job to JSON-safe dictionary.
        
        Returns:
            Dict with all job fields, status as lowercase string
            
        Example:
            >>> job.as_dict()
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "tier": "free",
                "created_ts": 1698412800.0,
                ...
            }
        """
        return {
            "id": self.id,
            "project_id": self.project_id,
            "tier": self.tier,
            "trp": self.trp,
            "status": self.status.value,  # Lowercase string
            "created_ts": self.created_ts,
            "started_ts": self.started_ts,
            "finished_ts": self.finished_ts,
            "artifacts": self.artifacts,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """
        Deserialize job from dictionary with validation.
        
        Args:
            data: Dictionary with job fields
            
        Returns:
            Job instance
            
        Raises:
            ValueError: If required fields missing or invalid
            KeyError: If required fields missing
            
        Example:
            >>> data = {"id": "...", "status": "pending", ...}
            >>> job = Job.from_dict(data)
        """
        # Required fields
        required = {"id", "trp", "tier", "status", "created_ts"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        
        # Parse status
        status = JobStatus.from_string(data["status"])
        
        return cls(
            id=data["id"],
            project_id=data.get("project_id"),
            tier=data["tier"],
            trp=data["trp"],
            status=status,
            created_ts=data["created_ts"],
            started_ts=data.get("started_ts"),
            finished_ts=data.get("finished_ts"),
            artifacts=data.get("artifacts", {}),
            error=data.get("error"),
        )
    
    def set_status(self, new_status: JobStatus) -> None:
        """
        Transition to new status with validation and automatic timestamping.
        
        Args:
            new_status: Target status
            
        Raises:
            ValueError: If transition is invalid
            
        Side effects:
            - Sets started_ts when transitioning to RUNNING
            - Sets finished_ts when transitioning to terminal state
            
        Example:
            >>> job.set_status(JobStatus.RUNNING)  # Sets started_ts
            >>> job.set_status(JobStatus.SUCCEEDED)  # Sets finished_ts
        """
        # Check if transition is valid
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed and new_status != self.status:
            raise ValueError(
                f"Invalid status transition: {self.status.value} → {new_status.value}. "
                f"Allowed transitions from {self.status.value}: "
                f"{', '.join(s.value for s in allowed) if allowed else 'none (terminal state)'}"
            )
        
        # Update status
        old_status = self.status
        self.status = new_status
        
        # Auto-timestamp based on transition
        now = time.time()
        
        if new_status == JobStatus.RUNNING and old_status == JobStatus.PENDING:
            self.started_ts = now
        
        if new_status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            if self.finished_ts is None:
                self.finished_ts = now
    
    def set_artifacts(self, mapping: Dict[str, str]) -> None:
        """
        Merge artifact paths without overwriting unrelated keys.
        
        Args:
            mapping: Dict of artifact_name → file_path
            
        Example:
            >>> job.set_artifacts({"video": "/path/to/video.mp4"})
            >>> job.set_artifacts({"thumbnail": "/path/to/thumb.jpg"})
            >>> job.artifacts
            {"video": "/path/to/video.mp4", "thumbnail": "/path/to/thumb.jpg"}
        """
        self.artifacts.update(mapping)
    
    def set_error(self, message: str) -> None:
        """
        Mark job as FAILED with error message.
        
        Automatically sets status to FAILED and finished_ts.
        
        Args:
            message: Error description
            
        Example:
            >>> job.set_error("Schema validation failed: missing field 'scene_name'")
            >>> job.status
            JobStatus.FAILED
        """
        self.error = message
        self.status = JobStatus.FAILED
        if self.finished_ts is None:
            self.finished_ts = time.time()
    
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state (SUCCEEDED or FAILED)."""
        return self.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}
    
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate job duration in seconds.
        
        Returns:
            Duration if job is finished, None otherwise
        """
        if self.started_ts and self.finished_ts:
            return self.finished_ts - self.started_ts
        return None


# ============================================================================
# Factory Functions
# ============================================================================

def new_job_from_trp(trp: Dict[str, Any], project_id: Optional[str] = None) -> Job:
    """
    Create a new job from a TRP payload.
    
    Args:
        trp: Task Rendering Plan (validated JSON)
        project_id: Optional project association
        
    Returns:
        Job initialized with PENDING status
        
    Raises:
        ValueError: If user_tier is invalid or missing
        KeyError: If required TRP fields are missing
        
    Example:
        >>> trp = {"user_tier": "free", "constraints": {...}, ...}
        >>> job = new_job_from_trp(trp)
        >>> job.status
        JobStatus.PENDING
    """
    # Validate tier
    tier = trp.get("user_tier")
    if tier not in {"free", "premium"}:
        raise ValueError(
            f"Invalid or missing user_tier in TRP: '{tier}'. "
            "Must be 'free' or 'premium'."
        )
    
    # Generate UUID v4
    job_id = str(uuid.uuid4())
    
    return Job(
        id=job_id,
        project_id=project_id,
        tier=tier,
        trp=trp,
        status=JobStatus.PENDING,
        created_ts=time.time(),
    )


def artifacts_dir(job_id: str) -> Path:
    """
    Get the artifacts directory path for a job.
    
    Args:
        job_id: Job UUID
        
    Returns:
        Path to job's artifact directory (CONFIG.ARTIFACTS_ROOT / job_id)
        
    Raises:
        ValueError: If job_id is not a valid UUID
        RuntimeError: If CONFIG is not available
        
    Example:
        >>> path = artifacts_dir("550e8400-e29b-41d4-a716-446655440000")
        >>> path
        PosixPath('/app/artifacts/550e8400-e29b-41d4-a716-446655440000')
    """
    validate_job_id(job_id)
    
    if CONFIG is None:
        raise RuntimeError("CONFIG not available. Cannot determine artifacts directory.")
    
    return CONFIG.ARTIFACTS_ROOT / job_id


def validate_job_id(job_id: str) -> None:
    """
    Validate that job_id is a valid UUID v4.
    
    Args:
        job_id: Job identifier to validate
        
    Raises:
        ValueError: If job_id is not a valid UUID v4
        
    Example:
        >>> validate_job_id("550e8400-e29b-41d4-a716-446655440000")  # OK
        >>> validate_job_id("invalid-id")  # Raises ValueError
    """
    try:
        parsed = uuid.UUID(job_id, version=4)
        # Ensure it's actually v4 and matches the input
        if str(parsed) != job_id:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError(
            f"Invalid job ID: '{job_id}'. Must be a valid UUID v4 string."
        )
