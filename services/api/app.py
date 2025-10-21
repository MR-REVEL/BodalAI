#!/usr/bin/env python3
"""
Flask app factory for BodalAI service API.

Run:
  python -m services.api.app
"""
import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from .config import DEBUG, HOST, LOG_FILE, LOGS_DIR, PORT
from .queue import start_worker
from .runner import execute_job


def setup_logging():
    """Configure logging to file and console."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def create_app():
    """Create and configure the Flask application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
    
    # Enable CORS for localhost dev
    CORS(app, resources={r"/*": {"origins": "http://localhost:*"}})
    
    # Start background worker
    start_worker(execute_job)
    logger.info("Background worker started")
    
    @app.errorhandler(Exception)
    def handle_error(e):
        """Global error handler returning JSON."""
        logger.exception("Unhandled exception")
        return jsonify({"error": str(e)}), 500
    
    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({"ok": True}), 200
    
    # Additional routes will be implemented in later prompts
    # - POST /jobs - create new job
    # - GET /jobs/<job_id> - get job status
    # - GET /jobs/<job_id>/artifacts/<name> - download artifact
    
    return app


def main():
    """Run the development server."""
    app = create_app()
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Flask service on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)


if __name__ == "__main__":
    main()
