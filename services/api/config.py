"""
Configuration constants and environment parsing for the Flask service.
"""
import os
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[2]

# Service configuration
HOST = os.getenv("SERVICE_HOST", "127.0.0.1")
PORT = int(os.getenv("SERVICE_PORT", "8000"))
DEBUG = os.getenv("SERVICE_DEBUG", "true").lower() == "true"

# Data paths
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
ARTIFACTS_DIR = ROOT / "artifacts"
LOGS_DIR = ROOT / "logs"
LOG_FILE = LOGS_DIR / "service.log"

# Orchestrator
ORCHESTRATOR = ROOT / "runtime" / "orchestrator.py"
SCHEMA_PATH = ROOT / "schemas" / "trp.schema.json"
