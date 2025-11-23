import pytest
import json
import uuid
from unittest.mock import patch
from services.api.app import create_app
from services.api.config import CONFIG
from services.api.models import JobStatus

@pytest.fixture
def client():
    # Patch start_worker to prevent background processing during tests
    with patch('services.api.app.start_worker'):
        app = create_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

@pytest.fixture
def valid_trp():
    return {
        "user_tier": "free",
        "constraints": {
            "duration_s": 10,
            "fps": 24,
            "resolution": [1920, 1080]
        },
        "scenes": []
    }

def test_post_jobs_happy_path(client, valid_trp):
    """Test creating a job with valid TRP."""
    # Patch enqueue_job to ensure status doesn't change to running
    with patch('services.api.app.enqueue_job'):
        response = client.post("/jobs", json=valid_trp)
        assert response.status_code == 201
        data = response.get_json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert "links" in data
        assert "self" in data["links"]
        
        # Verify persistence
        job_id = data["job_id"]
        job_file = CONFIG.JOBS_ROOT / f"{job_id}.json"
        assert job_file.exists()
        
        # Verify content
        saved_data = json.loads(job_file.read_text(encoding="utf-8"))
        assert saved_data["id"] == job_id
        assert saved_data["status"] == "pending"
        assert saved_data["tier"] == "free"

def test_post_jobs_non_json(client):
    """Test 415 for non-JSON payload."""
    response = client.post("/jobs", data="not json")
    assert response.status_code == 415
    data = response.get_json()
    assert data["code"] == "UNSUPPORTED_MEDIA_TYPE"

def test_post_jobs_invalid_tier(client, valid_trp):
    """Test 400 for invalid tier."""
    valid_trp["user_tier"] = "invalid"
    response = client.post("/jobs", json=valid_trp)
    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == "BAD_REQUEST"
    assert "Invalid or missing user_tier" in data["error"]

def test_get_job_happy_path(client, valid_trp):
    """Test getting a job by ID."""
    # Create first
    with patch('services.api.app.enqueue_job'):
        create_resp = client.post("/jobs", json=valid_trp)
        job_id = create_resp.get_json()["job_id"]
    
    # Get
    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == job_id
    assert data["status"] == "pending"
    assert data["tier"] == "free"
    assert "links" in data
    assert data["links"]["self"] == f"/jobs/{job_id}"

def test_get_job_invalid_uuid(client):
    """Test 400 for invalid UUID."""
    response = client.get("/jobs/not-a-uuid")
    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == "BAD_REQUEST"

def test_get_job_not_found(client):
    """Test 404 for unknown job."""
    # Valid UUID v4 but not existing
    random_uuid = str(uuid.uuid4())
    response = client.get(f"/jobs/{random_uuid}")
    assert response.status_code == 404
    data = response.get_json()
    assert data["code"] == "NOT_FOUND"

def test_post_jobs_requires_json_content_type(client):
    """Test 415 when Content-Type is not application/json."""
    rv = client.post("/jobs", data="not json", headers={"Content-Type": "text/plain"})
    assert rv.status_code == 415
    assert rv.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"

def test_post_jobs_requires_object_body(client):
    """Test 400 when body is not a JSON object."""
    # Empty body
    rv = client.post("/jobs", data="{}", headers={"Content-Type": "application/json"})
    # This might fail missing user_tier, which is fine, but let's check the validator logic for type
    # Actually {} is a dict, so it passes "isinstance(trp, dict)" but fails "user_tier" check.
    # The test asks to check for "[]" which is a list.
    
    rv = client.post("/jobs", data="[]", headers={"Content-Type": "application/json"})
    assert rv.status_code == 400
    assert rv.get_json()["code"] == "BAD_REQUEST"
    assert "payload must be a JSON object" in rv.get_json()["error"]

def test_post_jobs_missing_user_tier(client):
    """Test 400 when user_tier is missing."""
    rv = client.post("/jobs", json={"goal": "render something"})
    assert rv.status_code == 400
    assert rv.get_json()["error"].startswith("missing 'user_tier'")

def test_stream_artifact_happy_path(client, tmp_path):
    """Test streaming an existing artifact."""
    job_id = "07e57c44-4b1e-4f88-8f85-0e6b8d2e7f6d"
    artifacts_dir = tmp_path / "artifacts" / job_id
    artifacts_dir.mkdir(parents=True)
    mp4 = artifacts_dir / "out.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # minimal mp4 header stub
    
    # Patch CONFIG in artifacts module to use tmp_path
    with patch("services.api.artifacts.CONFIG") as mock_config:
        mock_config.ARTIFACTS_ROOT = tmp_path / "artifacts"
        
        rv = client.get(f"/artifacts/{job_id}/out.mp4")
        assert rv.status_code == 200
        assert rv.headers["Content-Type"].startswith("video/mp4")
        assert rv.data == b"\x00\x00\x00\x18ftypmp42"

def test_stream_artifact_invalid_uuid(client):
    """Test 400 for invalid UUID."""
    rv = client.get("/artifacts/not-a-uuid/out.mp4")
    assert rv.status_code == 400
    assert rv.get_json()["code"] == "BAD_REQUEST"
    assert "invalid job_id" in rv.get_json()["error"]

def test_stream_artifact_invalid_filename(client):
    """Test 400 for invalid or non-whitelisted filename."""
    job_id = str(uuid.uuid4())
    
    # Not in whitelist
    rv = client.get(f"/artifacts/{job_id}/foo.mp4")
    assert rv.status_code == 400
    assert "invalid filename" in rv.get_json()["error"]
    
    # Traversal attempt (note: client/server usually normalize '..' to 404 before hitting app)
    # But if it somehow reached the app, it would be rejected by whitelist.
    # We'll just test that a filename with special chars is rejected if not in whitelist.
    rv = client.get(f"/artifacts/{job_id}/secret.txt")
    assert rv.status_code == 400

def test_stream_artifact_not_found(client, tmp_path):
    """Test 404 for missing file."""
    job_id = str(uuid.uuid4())
    
    # Patch CONFIG to ensure we look in the right place (which is empty)
    with patch("services.api.artifacts.CONFIG") as mock_config:
        mock_config.ARTIFACTS_ROOT = tmp_path / "artifacts"
        
        rv = client.get(f"/artifacts/{job_id}/out.jpg")
        assert rv.status_code == 404
        assert rv.get_json()["code"] == "NOT_FOUND"

def test_stream_artifact_logs(client, tmp_path):
    """Test streaming a log file."""
    job_id = str(uuid.uuid4())
    artifacts_dir = tmp_path / "artifacts" / job_id
    artifacts_dir.mkdir(parents=True)
    log_file = artifacts_dir / "run.log"
    log_file.write_text("Log content")
    
    with patch("services.api.artifacts.CONFIG") as mock_config:
        mock_config.ARTIFACTS_ROOT = tmp_path / "artifacts"
        
        rv = client.get(f"/artifacts/{job_id}/run.log")
        assert rv.status_code == 200
        assert "text/plain" in rv.headers["Content-Type"]
        assert rv.data.decode() == "Log content"
