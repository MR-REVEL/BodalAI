"""
Configuration constants and environment parsing for the Flask service.

Single source of truth for service settings (paths, ports, timeouts, schema path).
Supports environment overrides with BODAL_* prefix.
Ensures required directories exist at import time.

Edge cases handled:
- Missing schema file: warns but doesn't crash (fails at runtime with clear message)
- Permission errors: logs exception and exits with code 1 (fail fast)
- Invalid concurrency: defaults to 1 with warning
"""
import logging
import os
import sys
from pathlib import Path
from dataclasses import dataclass

# Project root (for resolving relative paths)
ROOT = Path(__file__).resolve().parents[2]

# Setup basic logging for config loading
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ---- Environment helpers ----
def _get_env_str(key: str, default: str) -> str:
    """Get string environment variable with fallback."""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """
    Get integer environment variable with fallback.
    
    Validates range for specific keys (e.g., CONCURRENCY must be >= 1).
    """
    try:
        value = int(os.environ.get(key, str(default)))
        
        # Special validation for CONCURRENCY
        if key == "BODAL_CONCURRENCY" and value < 1:
            logger.warning(f"{key}={value} is invalid (must be >= 1), using default={default}")
            return default
        
        return value
    except ValueError:
        logger.warning(f"{key} has invalid integer value, using default={default}")
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """Get boolean environment variable with fallback."""
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ServiceConfig:
    """Immutable configuration for the Flask service."""
    
    # Server
    HOST: str
    PORT: int
    DEBUG: bool
    
    # Paths
    ARTIFACTS_ROOT: Path
    JOBS_ROOT: Path
    LOGS_ROOT: Path
    LOG_FILE: Path
    SCHEMA_PATH: Path
    ORCHESTRATOR: Path
    
    # Runtime params (Phase-1 defaults)
    CONCURRENCY: int  # single worker for Phase-1
    LOGO_DEFAULT: Path  # default watermark logo path


def load_config() -> ServiceConfig:
    """
    Load service configuration from environment variables or defaults.
    Creates required directories on load.
    
    Guardrails:
    - Fails fast if directories cannot be created (permissions)
    - Warns if schema file doesn't exist (but doesn't crash)
    - Validates concurrency >= 1
    
    Raises:
        SystemExit: If critical directories cannot be created
    """
    # Server defaults (Phase-1)
    host = _get_env_str("BODAL_HOST", "127.0.0.1")
    port = _get_env_int("BODAL_PORT", 8000)
    debug = _get_env_bool("BODAL_DEBUG", True)
    
    # Path defaults (relative to project root)
    artifacts_root = ROOT / Path(_get_env_str("BODAL_ARTIFACTS_ROOT", "artifacts"))
    jobs_root = ROOT / Path(_get_env_str("BODAL_JOBS_ROOT", "data/jobs"))
    logs_root = ROOT / Path(_get_env_str("BODAL_LOGS_ROOT", "logs"))
    schema_path = ROOT / Path(_get_env_str("BODAL_SCHEMA_PATH", "schemas/trp.schema.json"))
    orchestrator = ROOT / Path(_get_env_str("BODAL_ORCHESTRATOR", "runtime/orchestrator.py"))
    
    # Runtime defaults
    concurrency = _get_env_int("BODAL_CONCURRENCY", 1)  # single-threaded Phase-1
    logo_default = ROOT / Path(_get_env_str("BODAL_LOGO_DEFAULT", "config/watermark.png"))
    
    # Ensure directories exist - FAIL FAST on permission errors
    try:
        artifacts_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Artifacts directory ready: {artifacts_root}")
    except (PermissionError, OSError) as e:
        logger.error(f"FATAL: Cannot create artifacts directory {artifacts_root}: {e}")
        sys.exit(1)
    
    try:
        jobs_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Jobs directory ready: {jobs_root}")
    except (PermissionError, OSError) as e:
        logger.error(f"FATAL: Cannot create jobs directory {jobs_root}: {e}")
        sys.exit(1)
    
    try:
        logs_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"Logs directory ready: {logs_root}")
    except (PermissionError, OSError) as e:
        logger.error(f"FATAL: Cannot create logs directory {logs_root}: {e}")
        sys.exit(1)
    
    log_file = logs_root / "service.log"
    
    # Check if schema file exists - WARN but don't crash (will fail at runtime)
    if not schema_path.exists():
        logger.warning(
            f"Schema file not found: {schema_path}. "
            "TRP validation will fail at runtime with a clear error message."
        )
    else:
        logger.info(f"Schema file found: {schema_path}")
    
    # Check if orchestrator exists - WARN but don't crash
    if not orchestrator.exists():
        logger.warning(
            f"Orchestrator not found: {orchestrator}. "
            "Job execution will fail at runtime with a clear error message."
        )
    else:
        logger.info(f"Orchestrator found: {orchestrator}")
    
    # Validate concurrency for Phase-1
    if concurrency != 1:
        logger.warning(
            f"BODAL_CONCURRENCY={concurrency} but Phase-1 only supports 1 worker. "
            "Using configured value for future compatibility."
        )
    
    return ServiceConfig(
        HOST=host,
        PORT=port,
        DEBUG=debug,
        ARTIFACTS_ROOT=artifacts_root,
        JOBS_ROOT=jobs_root,
        LOGS_ROOT=logs_root,
        LOG_FILE=log_file,
        SCHEMA_PATH=schema_path,
        ORCHESTRATOR=orchestrator,
        CONCURRENCY=concurrency,
        LOGO_DEFAULT=logo_default,
    )


# Singleton-style config loaded at import time
CONFIG = load_config()

# Backward compatibility: expose commonly used values as module-level constants
# This allows existing code to continue using `from .config import HOST, PORT` etc.
HOST = CONFIG.HOST
PORT = CONFIG.PORT
DEBUG = CONFIG.DEBUG
ARTIFACTS_DIR = CONFIG.ARTIFACTS_ROOT
JOBS_DIR = CONFIG.JOBS_ROOT
LOGS_DIR = CONFIG.LOGS_ROOT
LOG_FILE = CONFIG.LOG_FILE
SCHEMA_PATH = CONFIG.SCHEMA_PATH
ORCHESTRATOR = CONFIG.ORCHESTRATOR
