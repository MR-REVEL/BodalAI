"""
Test suite for models: Job lifecycle, validation, and JSON serialization.
"""
import json
import time
import uuid
import pytest

from services.api.models import (
    Job,
    JobStatus,
    new_job_from_trp,
    artifacts_dir,
    validate_job_id,
)


# ============================================================================
# JobStatus Tests
# ============================================================================

def test_job_status_values():
    """Test that JobStatus has expected values."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.SUCCEEDED.value == "succeeded"
    assert JobStatus.FAILED.value == "failed"


def test_job_status_string_conversion():
    """Test JobStatus.__str__ returns lowercase value."""
    assert str(JobStatus.PENDING) == "pending"
    assert str(JobStatus.SUCCEEDED) == "succeeded"


def test_job_status_from_string_valid():
    """Test parsing valid status strings."""
    assert JobStatus.from_string("pending") == JobStatus.PENDING
    assert JobStatus.from_string("running") == JobStatus.RUNNING
    assert JobStatus.from_string("succeeded") == JobStatus.SUCCEEDED
    assert JobStatus.from_string("failed") == JobStatus.FAILED
    
    # Case insensitive
    assert JobStatus.from_string("PENDING") == JobStatus.PENDING
    assert JobStatus.from_string("Succeeded") == JobStatus.SUCCEEDED


def test_job_status_from_string_invalid():
    """Test parsing invalid status strings raises ValueError."""
    with pytest.raises(ValueError, match="Invalid job status: 'completed'"):
        JobStatus.from_string("completed")
    
    with pytest.raises(ValueError, match="Invalid job status: 'invalid'"):
        JobStatus.from_string("invalid")


# ============================================================================
# Job Creation Tests
# ============================================================================

def test_new_job_from_trp_valid():
    """Test creating a job from valid TRP."""
    trp = {
        "user_tier": "free",
        "constraints": {"max_duration": 30},
        "scene_name": "TestScene",
    }
    
    job = new_job_from_trp(trp)
    
    assert job.tier == "free"
    assert job.trp == trp
    assert job.status == JobStatus.PENDING
    assert job.project_id is None
    assert job.started_ts is None
    assert job.finished_ts is None
    assert job.error is None
    assert job.artifacts == {}
    
    # ID should be UUID v4
    parsed_uuid = uuid.UUID(job.id, version=4)
    assert str(parsed_uuid) == job.id


def test_new_job_from_trp_with_project_id():
    """Test creating a job with project_id."""
    trp = {"user_tier": "premium"}
    project_id = "proj-123"
    
    job = new_job_from_trp(trp, project_id=project_id)
    
    assert job.project_id == project_id


def test_new_job_from_trp_invalid_tier():
    """Test creating job with invalid tier raises ValueError."""
    trp = {"user_tier": "enterprise"}
    
    with pytest.raises(ValueError, match="Invalid or missing user_tier"):
        new_job_from_trp(trp)


def test_new_job_from_trp_missing_tier():
    """Test creating job without tier raises ValueError."""
    trp = {"scene_name": "Test"}
    
    with pytest.raises(ValueError, match="Invalid or missing user_tier"):
        new_job_from_trp(trp)


# ============================================================================
# Job Validation Tests
# ============================================================================

def test_job_post_init_validates_tier():
    """Test __post_init__ validates tier."""
    with pytest.raises(ValueError, match="Invalid tier: 'basic'"):
        Job(
            id=str(uuid.uuid4()),
            trp={},
            tier="basic",  # Invalid
            status=JobStatus.PENDING,
            created_ts=time.time(),
        )


def test_job_post_init_validates_id():
    """Test __post_init__ validates job ID format."""
    with pytest.raises(ValueError, match="Invalid job ID"):
        Job(
            id="not-a-uuid",
            trp={},
            tier="free",
            status=JobStatus.PENDING,
            created_ts=time.time(),
        )


def test_job_post_init_converts_status_string():
    """Test __post_init__ converts status string to enum."""
    job = Job(
        id=str(uuid.uuid4()),
        trp={},
        tier="free",
        status="pending",  # String instead of enum
        created_ts=time.time(),
    )
    
    assert job.status == JobStatus.PENDING
    assert isinstance(job.status, JobStatus)


# ============================================================================
# State Transition Tests
# ============================================================================

def test_set_status_pending_to_running():
    """Test valid transition PENDING → RUNNING."""
    job = new_job_from_trp({"user_tier": "free"})
    
    assert job.status == JobStatus.PENDING
    assert job.started_ts is None
    
    before = time.time()
    job.set_status(JobStatus.RUNNING)
    after = time.time()
    
    assert job.status == JobStatus.RUNNING
    assert job.started_ts is not None
    assert before <= job.started_ts <= after


def test_set_status_running_to_succeeded():
    """Test valid transition RUNNING → SUCCEEDED."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    
    assert job.finished_ts is None
    
    before = time.time()
    job.set_status(JobStatus.SUCCEEDED)
    after = time.time()
    
    assert job.status == JobStatus.SUCCEEDED
    assert job.finished_ts is not None
    assert before <= job.finished_ts <= after


def test_set_status_running_to_failed():
    """Test valid transition RUNNING → FAILED."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    
    before = time.time()
    job.set_status(JobStatus.FAILED)
    after = time.time()
    
    assert job.status == JobStatus.FAILED
    assert job.finished_ts is not None
    assert before <= job.finished_ts <= after


def test_set_status_invalid_transition_running_to_pending():
    """Test invalid transition RUNNING → PENDING raises ValueError."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    
    with pytest.raises(ValueError, match="Invalid status transition"):
        job.set_status(JobStatus.PENDING)


def test_set_status_invalid_transition_succeeded_to_running():
    """Test invalid transition SUCCEEDED → RUNNING raises ValueError."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    job.set_status(JobStatus.SUCCEEDED)
    
    with pytest.raises(ValueError, match="Invalid status transition"):
        job.set_status(JobStatus.RUNNING)


def test_set_status_invalid_transition_pending_to_succeeded():
    """Test invalid transition PENDING → SUCCEEDED raises ValueError."""
    job = new_job_from_trp({"user_tier": "free"})
    
    with pytest.raises(ValueError, match="Invalid status transition"):
        job.set_status(JobStatus.SUCCEEDED)


def test_set_status_terminal_states():
    """Test terminal states allow no transitions."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    job.set_status(JobStatus.FAILED)
    
    # Can't transition from FAILED to anything
    with pytest.raises(ValueError, match="terminal state"):
        job.set_status(JobStatus.RUNNING)


# ============================================================================
# Artifact Management Tests
# ============================================================================

def test_set_artifacts_merge():
    """Test set_artifacts merges without overwriting."""
    job = new_job_from_trp({"user_tier": "free"})
    
    job.set_artifacts({"video": "/path/to/video.mp4"})
    assert job.artifacts == {"video": "/path/to/video.mp4"}
    
    job.set_artifacts({"thumbnail": "/path/to/thumb.jpg"})
    assert job.artifacts == {
        "video": "/path/to/video.mp4",
        "thumbnail": "/path/to/thumb.jpg",
    }
    
    # Can overwrite specific key
    job.set_artifacts({"video": "/new/path/video.mp4"})
    assert job.artifacts["video"] == "/new/path/video.mp4"
    assert job.artifacts["thumbnail"] == "/path/to/thumb.jpg"


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_set_error_marks_failed():
    """Test set_error marks job as FAILED and sets timestamps."""
    job = new_job_from_trp({"user_tier": "free"})
    job.set_status(JobStatus.RUNNING)
    
    before = time.time()
    job.set_error("Schema validation failed")
    after = time.time()
    
    assert job.status == JobStatus.FAILED
    assert job.error == "Schema validation failed"
    assert job.finished_ts is not None
    assert before <= job.finished_ts <= after


def test_set_error_from_pending():
    """Test set_error can be called from PENDING (e.g., pre-execution failure)."""
    job = new_job_from_trp({"user_tier": "free"})
    
    job.set_error("Invalid TRP format")
    
    assert job.status == JobStatus.FAILED
    assert job.error == "Invalid TRP format"
    assert job.finished_ts is not None


# ============================================================================
# JSON Serialization Tests
# ============================================================================

def test_as_dict():
    """Test Job.as_dict() serialization."""
    job = new_job_from_trp({"user_tier": "premium"}, project_id="proj-1")
    job.set_status(JobStatus.RUNNING)
    job.set_artifacts({"video": "/path/to/video.mp4"})
    
    data = job.as_dict()
    
    assert data["id"] == job.id
    assert data["project_id"] == "proj-1"
    assert data["tier"] == "premium"
    assert data["trp"] == {"user_tier": "premium"}
    assert data["status"] == "running"  # Lowercase string
    assert data["created_ts"] == job.created_ts
    assert data["started_ts"] == job.started_ts
    assert data["finished_ts"] is None
    assert data["artifacts"] == {"video": "/path/to/video.mp4"}
    assert data["error"] is None


def test_from_dict_minimal():
    """Test Job.from_dict() with minimal required fields."""
    data = {
        "id": str(uuid.uuid4()),
        "tier": "free",
        "trp": {"user_tier": "free"},
        "status": "pending",
        "created_ts": time.time(),
    }
    
    job = Job.from_dict(data)
    
    assert job.id == data["id"]
    assert job.tier == "free"
    assert job.status == JobStatus.PENDING
    assert job.created_ts == data["created_ts"]
    assert job.project_id is None
    assert job.started_ts is None
    assert job.finished_ts is None
    assert job.artifacts == {}
    assert job.error is None


def test_from_dict_complete():
    """Test Job.from_dict() with all fields."""
    data = {
        "id": str(uuid.uuid4()),
        "project_id": "proj-1",
        "tier": "premium",
        "trp": {"user_tier": "premium", "constraints": {}},
        "status": "succeeded",
        "created_ts": 1698412800.0,
        "started_ts": 1698412810.0,
        "finished_ts": 1698412850.0,
        "artifacts": {"video": "/path/to/video.mp4"},
        "error": None,
    }
    
    job = Job.from_dict(data)
    
    assert job.id == data["id"]
    assert job.project_id == "proj-1"
    assert job.tier == "premium"
    assert job.status == JobStatus.SUCCEEDED
    assert job.started_ts == 1698412810.0
    assert job.finished_ts == 1698412850.0
    assert job.artifacts == {"video": "/path/to/video.mp4"}


def test_from_dict_missing_required_field():
    """Test Job.from_dict() raises ValueError for missing required fields."""
    data = {
        "id": str(uuid.uuid4()),
        # Missing tier, trp, status, created_ts
    }
    
    with pytest.raises(ValueError, match="Missing required fields"):
        Job.from_dict(data)


def test_from_dict_invalid_status():
    """Test Job.from_dict() raises ValueError for invalid status."""
    data = {
        "id": str(uuid.uuid4()),
        "tier": "free",
        "trp": {},
        "status": "completed",  # Old status name
        "created_ts": time.time(),
    }
    
    with pytest.raises(ValueError, match="Invalid job status"):
        Job.from_dict(data)


def test_json_round_trip():
    """Test round-trip: Job → as_dict() → JSON → from_dict() → Job."""
    original = new_job_from_trp({"user_tier": "free", "scene": "Test"})
    original.set_status(JobStatus.RUNNING)
    original.set_artifacts({"video": "/path/video.mp4"})
    original.set_status(JobStatus.SUCCEEDED)
    
    # Serialize to JSON
    json_str = json.dumps(original.as_dict())
    
    # Deserialize from JSON
    parsed = json.loads(json_str)
    restored = Job.from_dict(parsed)
    
    # Verify equivalence
    assert restored.id == original.id
    assert restored.tier == original.tier
    assert restored.trp == original.trp
    assert restored.status == original.status
    assert restored.created_ts == original.created_ts
    assert restored.started_ts == original.started_ts
    assert restored.finished_ts == original.finished_ts
    assert restored.artifacts == original.artifacts
    assert restored.error == original.error


# ============================================================================
# Helper Methods Tests
# ============================================================================

def test_is_terminal():
    """Test is_terminal() identifies terminal states."""
    job = new_job_from_trp({"user_tier": "free"})
    
    assert not job.is_terminal()  # PENDING
    
    job.set_status(JobStatus.RUNNING)
    assert not job.is_terminal()  # RUNNING
    
    job.set_status(JobStatus.SUCCEEDED)
    assert job.is_terminal()  # SUCCEEDED
    
    # Test FAILED
    job2 = new_job_from_trp({"user_tier": "free"})
    job2.set_status(JobStatus.RUNNING)
    job2.set_error("Test error")
    assert job2.is_terminal()  # FAILED


def test_duration_seconds():
    """Test duration_seconds() calculation."""
    job = new_job_from_trp({"user_tier": "free"})
    
    # Not started
    assert job.duration_seconds() is None
    
    # Started but not finished
    job.set_status(JobStatus.RUNNING)
    assert job.duration_seconds() is None
    
    # Finished
    time.sleep(0.1)  # Ensure measurable duration
    job.set_status(JobStatus.SUCCEEDED)
    duration = job.duration_seconds()
    
    assert duration is not None
    assert duration >= 0.1
    assert duration < 1.0  # Should be quick


# ============================================================================
# Factory Functions Tests
# ============================================================================

def test_validate_job_id_valid():
    """Test validate_job_id accepts valid UUID v4."""
    valid_id = str(uuid.uuid4())
    validate_job_id(valid_id)  # Should not raise


def test_validate_job_id_invalid():
    """Test validate_job_id raises ValueError for invalid IDs."""
    with pytest.raises(ValueError, match="Invalid job ID"):
        validate_job_id("not-a-uuid")
    
    with pytest.raises(ValueError, match="Invalid job ID"):
        validate_job_id("12345")
    
    # UUID v1 (time-based) should fail
    uuid_v1 = str(uuid.uuid1())
    with pytest.raises(ValueError, match="Invalid job ID"):
        validate_job_id(uuid_v1)


def test_artifacts_dir():
    """Test artifacts_dir returns correct path."""
    job_id = str(uuid.uuid4())
    path = artifacts_dir(job_id)
    
    # Should be Path object ending with job_id
    assert str(path).endswith(job_id)
    assert "artifacts" in str(path)


def test_artifacts_dir_invalid_id():
    """Test artifacts_dir raises ValueError for invalid ID."""
    with pytest.raises(ValueError, match="Invalid job ID"):
        artifacts_dir("invalid-id")


# ============================================================================
# Integration Scenario Tests
# ============================================================================

def test_typical_job_lifecycle_success():
    """Test typical successful job lifecycle."""
    # 1. Create job
    trp = {
        "user_tier": "free",
        "constraints": {"max_duration": 30},
        "scene_name": "IntroScene",
    }
    job = new_job_from_trp(trp)
    assert job.status == JobStatus.PENDING
    
    # 2. Start execution
    job.set_status(JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING
    assert job.started_ts is not None
    
    # 3. Add artifacts
    job.set_artifacts({
        "video": "/artifacts/123/final.mp4",
        "thumbnail": "/artifacts/123/thumb.jpg",
    })
    
    # 4. Complete successfully
    job.set_status(JobStatus.SUCCEEDED)
    assert job.status == JobStatus.SUCCEEDED
    assert job.finished_ts is not None
    assert job.is_terminal()
    
    # 5. Verify duration
    duration = job.duration_seconds()
    assert duration is not None
    assert duration >= 0


def test_typical_job_lifecycle_failure():
    """Test typical failed job lifecycle."""
    # 1. Create job
    job = new_job_from_trp({"user_tier": "premium"})
    
    # 2. Start execution
    job.set_status(JobStatus.RUNNING)
    
    # 3. Encounter error
    job.set_error("Manim rendering failed: invalid syntax")
    
    assert job.status == JobStatus.FAILED
    assert job.error == "Manim rendering failed: invalid syntax"
    assert job.finished_ts is not None
    assert job.is_terminal()


def test_job_serialization_persistence():
    """Test job can be saved and loaded via JSON."""
    # Create and modify job
    original = new_job_from_trp({"user_tier": "free"})
    original.set_status(JobStatus.RUNNING)
    original.set_artifacts({"log": "/path/log.txt"})
    original.set_status(JobStatus.SUCCEEDED)
    
    # Serialize
    json_data = json.dumps(original.as_dict(), indent=2)
    
    # Deserialize
    loaded_data = json.loads(json_data)
    restored = Job.from_dict(loaded_data)
    
    # Verify state matches
    assert restored.id == original.id
    assert restored.status == original.status
    assert restored.artifacts == original.artifacts
    assert restored.started_ts == original.started_ts
    assert restored.finished_ts == original.finished_ts
