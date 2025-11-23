from typing import Tuple, Any, Dict

def ensure_json_content_type(content_type: str | None) -> Tuple[bool, Dict[str, Any]]:
    """
    Returns (ok, error_json). ok=False if content_type is missing or not application/json.
    """
    if not content_type or "application/json" not in content_type.lower():
        return False, {"error": "json required", "code": "UNSUPPORTED_MEDIA_TYPE"}
    return True, {}

def validate_trp_minimal(trp: dict | None) -> Tuple[bool, Dict[str, Any]]:
    """
    Minimal TRP sanity checks for API layer (runner enforces full schema later).
    - Must be an object (dict)
    - Must contain 'user_tier' (free|premium) for Job factory
    - Optional: 'project_id' can be present
    """
    if trp is None or not isinstance(trp, dict):
        return False, {"error": "payload must be a JSON object", "code": "BAD_REQUEST"}
    
    if "user_tier" not in trp:
        return False, {"error": "missing 'user_tier' in TRP", "code": "BAD_REQUEST"}
    
    # Note: Detailed tier enum validation happens in new_job_from_trp()
    return True, {}
