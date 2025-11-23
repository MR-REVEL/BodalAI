#!/usr/bin/env python3
"""
Flask app factory for BodalAI service API.

Run:
  python -m services.api.app
"""
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from .config import CONFIG
from .models import new_job_from_trp, validate_job_id
from .queue import start_worker, enqueue_job
from .runner import execute_job
from .storage import save_job, load_job
from .validators import ensure_json_content_type, validate_trp_minimal
from .artifacts import artifact_path, guess_mime, is_allowed_filename


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
        # Pass through HTTP errors (like 404, 405)
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify({"error": e.description, "code": e.name.upper().replace(" ", "_")}), e.code
            
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
    
    @app.route("/jobs", methods=["POST"])
    def create_job():
        """
        Create a new job from TRP payload.
        
        Expects: JSON body with TRP data
        Returns: 201 Created with job details
        """
        # 1. Validate Content-Type
        ok, err = ensure_json_content_type(request.content_type)
        if not ok:
            return jsonify(err), 415
            
        # 2. Parse JSON
        trp_data = request.get_json(silent=True)
        
        # 3. Validate TRP structure
        ok, err = validate_trp_minimal(trp_data)
        if not ok:
            return jsonify(err), 400
            
        try:
            # 4. Create job (validates tier and generates ID)
            job = new_job_from_trp(trp_data)
            
            # Persist immediately
            save_job(job)
            
            # Enqueue for execution
            enqueue_job(job)
            
            app.logger.info(f"Job created: {job.id} (tier={job.tier})")
            
            return jsonify({
                "job_id": job.id,
                "status": job.status.value,
                "links": {
                    "self": f"/jobs/{job.id}",
                    "artifacts": f"/artifacts/{job.id}/"
                }
            }), 201
            
        except ValueError as e:
            return jsonify({
                "error": str(e),
                "code": "BAD_REQUEST"
            }), 400
        except Exception as e:
            app.logger.exception("Failed to create job")
            return jsonify({"error": str(e)}), 500

    @app.route("/jobs/<job_id>", methods=["GET"])
    def get_job(job_id):
        """
        Get job status and details.
        
        Args:
            job_id: UUID v4 string
            
        Returns:
            200 OK with job details
            404 Not Found if job doesn't exist
            400 Bad Request if ID is invalid
        """
        try:
            validate_job_id(job_id)
        except ValueError:
            return jsonify({
                "error": "Invalid job ID format",
                "code": "BAD_REQUEST"
            }), 400
            
        job = load_job(job_id)
        if not job:
            return jsonify({
                "error": "not found",
                "code": "NOT_FOUND"
            }), 404
            
        # Build response with artifact links
        response = job.as_dict()
        
        # Add links
        links = {
            "self": f"/jobs/{job.id}"
        }
        
        # Add artifact links if they exist
        if job.artifacts:
            for key, path in job.artifacts.items():
                # Assuming path is relative or we just want to expose it under /artifacts/<job_id>/<filename>
                import os
                filename = os.path.basename(path)
                links[f"{key}_url"] = f"/artifacts/{job.id}/{filename}"
                
        response["links"] = links
        
        app.logger.info(f"Job polled: {job.id} status={job.status.value}")
        return jsonify(response), 200

    @app.route("/artifacts/<job_id>/<filename>", methods=["GET"])
    def get_artifact(job_id: str, filename: str):
        """
        Stream job artifact.
        
        Args:
            job_id: UUID v4 string
            filename: Whitelisted filename (e.g. out.mp4)
            
        Returns:
            200 OK with file stream
            404 Not Found if file missing
            400 Bad Request if ID/filename invalid
        """
        # Validate UUID
        try:
            validate_job_id(job_id)
        except ValueError:
            return jsonify({"error": "invalid job_id", "code": "BAD_REQUEST"}), 400
            
        # Validate allowed filename
        if not is_allowed_filename(filename):
            return jsonify({"error": "invalid filename", "code": "BAD_REQUEST"}), 400
            
        p = artifact_path(job_id, filename)
        if p is None:
            return jsonify({"error": "not found", "code": "NOT_FOUND"}), 404
            
        mimetype = guess_mime(filename)
        
        app.logger.info(f"Streaming artifact: {job_id}/{filename}")
        return send_file(p, mimetype=mimetype, as_attachment=False)
    
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
