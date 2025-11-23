from pathlib import Path
from typing import Optional
from services.api.config import CONFIG
from services.api.models import validate_job_id

# Whitelisted filenames (Phase-1)
WHITELIST = {
    "out.mp4",
    "out.jpg",
    "meta.json",
    "run.log",
    "out_watermarked.mp4",  # future: watermark tool
}

MIME_MAP = {
    ".mp4": "video/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".json": "application/json",
    ".log": "text/plain",
    ".txt": "text/plain",
}

def is_allowed_filename(name: str) -> bool:
    # Prevent traversal and enforce whitelist
    return name in WHITELIST and "/" not in name and "\\" not in name

def artifact_path(job_id: str, filename: str) -> Optional[Path]:
    """
    Returns the absolute Path to the artifact if valid and exists, else None.
    Validates UUID v4, enforces whitelist, and resolves within ARTIFACTS_ROOT/<job_id>/.
    """
    validate_job_id(job_id)  # raises ValueError on invalid
    
    if not is_allowed_filename(filename):
        return None
    
    base = CONFIG.ARTIFACTS_ROOT / job_id
    p = (base / filename).resolve()
    
    # Ensure path is under base (extra guard)
    if not str(p).startswith(str(base.resolve())):
        return None
        
    return p if p.exists() else None

def guess_mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return MIME_MAP.get(ext, "application/octet-stream")
