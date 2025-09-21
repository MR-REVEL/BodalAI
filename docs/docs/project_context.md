# Project Context: Manim Platform Integration

This document provides essential context for agents working on the Manim-based educational platform. It outlines technical specifications, infrastructure preferences, user experience goals, and agent behavior expectations to ensure seamless implementation and alignment with project objectives.

## 🎬 Manim & Media Configuration

**Manim Version:** Use Manim Community v0.19.0 as the standard baseline. Future updates will be integrated post-launch.

**Rendering Strategy:** Begin with CPU-only rendering. Consider GPU acceleration in future phases based on performance needs.

**FFmpeg Integration:** Bundle FFmpeg within the runner image to support media encoding. The platform must be fully web-based (similar to Google Colab), allowing users to preview creations without extensions or downloads. An integrated AI agent will assist users.

## ⚙️ Runtime & Infrastructure

**Phase 1:** Host runner on a single VM to simplify orchestration and debugging.

**Phase 2:** Evaluate Docker-in-Docker vs. Kubernetes with strict PodSecurity policies. Choose based on cache efficiency, memory usage, speed, and agent accuracy.

## 🔐 Security & Classroom Readiness

**User Demographics:** Primarily for adult learners and math educators. Student accounts (including minors) may be included. Guardrails optional.

**Privacy Compliance:** Adhere to Canadian/Ontario educational privacy standards.

**Project Isolation:** Implement only if necessary for classroom or tenant segregation. Prioritize cache, memory, and usability for individual accounts.

## 🎨 Product Experience & UX

**Branding:** Watermark assets and brand guidelines will be added later.

**Trial Experience:** Display a 30-second trial banner in the bottom-right corner of the preview window.

**MVP Criteria:**
- Seamless scene rendering
- Basic classroom account provisioning
- Trial experience without watermark unless using premium features
- UI feedback loop for render status

## 🤖 Agent Behavior & Prompting

**Request Handling:** Agent will prompt users before auto-downgrading requests (e.g., suggesting 8s @ 480p).

**Prompting Style:** Encourage users to provide detailed prompts. Include an instructional page to guide users in crafting effective prompts. Maintain educational tone without restricting creativity.

## 📊 Observability & Metrics

**Key Metrics:**
- Render success rate
- Timeout frequency
- Average wall time
- Watermark coverage
- Documentation compliance

**UI Features:** Display per-project run history in the UI. Note: history may be cleared periodically.

---

This context page is designed for integration within VS Code to support agent understanding and implementation.

---

## 🧰 Developer quick start (repo specifics)

This repository includes schema, linter, examples, and CI to keep TRPs and source code safe and consistent.

### TRP schema and examples
- Schema: `schemas/trp.schema.json` (JSON Schema draft 2020-12)
- Examples (valid/invalid):
	- `schemas/examples/valid_trp.json`
	- `schemas/examples/free_trp_2025-09-21.json`
	- `schemas/examples/premium_trp_2025-09-21.json`
	- `examples/trp/trp_free_trial_30s_valid.json` (premium constraints with watermark for free trial)
	- Invalid cases: `schemas/examples/invalid_trp_missing_required.json`, `examples/trp/trp_free_over_duration_invalid.json`, `examples/trp/trp_wrong_fps_invalid.json`

### Validate a TRP locally
- Preflight runner validates a TRP against the schema and optionally lints referenced source files:
	- Script: `scripts/preflight_validate.py`
	- Example (PowerShell):
		- `& "./.venv/Scripts/python.exe" "scripts/preflight_validate.py" "examples/trp/trp_free_trial_30s_valid.json" --fail-on-warn`
	- Output shows PASS/FAIL for schema validation and AST linter.

### AST linter (safety checks)
- Linter: `runtime/ast_linter.py`
- Blocks/disallows:
	- Dangerous calls: `eval`, `exec`, `os.system`, `os.popen`
	- Process/network use: `subprocess.*`, `socket.*`, `requests.*`
	- Writes outside `/project` or `/artifacts` when path is a literal
- Run directly (PowerShell):
	- `& "./.venv/Scripts/python.exe" runtime/ast_linter.py --paths runtime/examples/clean_scene.py --project-root /project --artifacts-root /artifacts`

### Continuous integration (CI)
- Workflow: `.github/workflows/validate-trp.yml`
- On PRs and pushes to `main`/`master`:
	- Validates all TRPs under `examples/trp/` and `plans/` against the schema
	- If any TRP lists existing `inputs.source_files`, runs the AST linter for those files

### Folder map
- `schemas/` — TRP schema and example TRPs
- `runtime/` — AST linter and runtime helpers
- `scripts/` — Validation utilities (preflight)
- `examples/trp/` — Additional TRP scenarios used for docs/CI
- `.github/workflows/` — CI configuration

### Notes
- The UI/session layer should enforce eligibility for one‑off free trials when using premium constraints with `watermark_required: true`.
- Keep `fps` at 24 in TRPs (schema-enforced). Free-tier constraints cap duration/compute/timeouts per schema.

For a quick tour of TRP examples and how to validate them, see `examples/trp/README.md`.

