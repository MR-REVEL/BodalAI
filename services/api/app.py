#!/usr/bin/env python3
"""
Flask app factory for BodalAI service API.

Run:
  python -m services.api.app
"""
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify
from flask_cors import CORS

from .config import CONFIG
from .queue import start_worker
from .runner import execute_job


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # JSON settings
    app.config["JSON_SORT_KEYS"] = False
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
    
    # Enable CORS for localhost dev (both localhost and 127.0.0.1)
    CORS(app, resources={r"/*": {"origins": ["http://localhost:*", "http://127.0.0.1:*"]}})
    
    # Configure logging with rotation
    log_file = CONFIG.LOG_FILE
    handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,  # 2 MB
        backupCount=3,
        encoding="utf-8"
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    
    # Also log to console in debug mode
    if CONFIG.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        app.logger.addHandler(console_handler)
    
    # Start background worker
    start_worker(execute_job)
    app.logger.info("Background worker started")
    
    @app.errorhandler(Exception)
    def handle_error(e):
        """Global error handler returning JSON."""
        app.logger.exception("Unhandled exception")
        return jsonify({"error": str(e)}), 500
    
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"ok": True}), 200
    
    @app.route("/config", methods=["GET"])
    def config_debug():
        """
        Debug endpoint showing active configuration (dev-only).
        
        Only enabled when BODAL_DEBUG=true.
        Useful for troubleshooting containers and environment configuration.
        
        Returns redacted view of CONFIG (no sensitive paths exposed).
        """
        if not CONFIG.DEBUG:
            return jsonify({
                "error": "Config endpoint only available in debug mode",
                "hint": "Set BODAL_DEBUG=true to enable"
            }), 403
        
        return jsonify({
            "server": {
                "host": CONFIG.HOST,
                "port": CONFIG.PORT,
                "debug": CONFIG.DEBUG,
            },
            "paths": {
                "artifacts_root": str(CONFIG.ARTIFACTS_ROOT),
                "jobs_root": str(CONFIG.JOBS_ROOT),
                "logs_root": str(CONFIG.LOGS_ROOT),
                "schema_path": str(CONFIG.SCHEMA_PATH),
                "orchestrator": str(CONFIG.ORCHESTRATOR),
                "logo_default": str(CONFIG.LOGO_DEFAULT),
            },
            "runtime": {
                "concurrency": CONFIG.CONCURRENCY,
            },
            "files_exist": {
                "schema": CONFIG.SCHEMA_PATH.exists(),
                "orchestrator": CONFIG.ORCHESTRATOR.exists(),
                "logo": CONFIG.LOGO_DEFAULT.exists(),
            }
        }), 200
    
    # Additional routes will be implemented in later prompts
    # - POST /jobs - create new job
    # - GET /jobs/<job_id> - get job status
    # - GET /jobs/<job_id>/artifacts/<name> - download artifact
    
    return app


def main():
    """Run the development server."""
    app = create_app()
    app.logger.info(
        f"Starting Flask on {CONFIG.HOST}:{CONFIG.PORT} (debug={CONFIG.DEBUG}) | "
        f"ARTIFACTS_ROOT={CONFIG.ARTIFACTS_ROOT} JOBS_ROOT={CONFIG.JOBS_ROOT} "
        f"SCHEMA={CONFIG.SCHEMA_PATH}"
    )
    app.run(host=CONFIG.HOST, port=CONFIG.PORT, debug=CONFIG.DEBUG)


if __name__ == "__main__":
    main()
