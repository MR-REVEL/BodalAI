# Task Request Plan (TRP) Template
**Version:** 1.0  
**Purpose:** Defines the structure for agent execution plans.

---

## JSON Schema Overview
- `trp_id`: Unique identifier.
- `project_id`: Project reference.
- `user_tier`: free | premium.
- `goal`: Plain-language objective.
- `inputs`: Source files, entry point, scene name.
- `constraints`: Duration, fps, resolution, compute budget, sandbox phase, watermark flag.
- `plan`: Steps with tool, params, and reason.
- `acceptance_tests`: Checks for duration, fps, watermark, etc.
- `artifacts`: Paths for video, thumbnail, logs.
- `memory`: Carry-forward flag and notes.

---

## Example TRP (Free 8s Preview)
```json
{
  "trp_id": "trp_2025-09-08_001",
  "project_id": "proj_1234",
  "user_tier": "free",
  "goal": "Render an 8s 480p preview",
  "inputs": {
    "source_files": ["scene.py"],
    "entry_point": "scene.py",
    "scene_name": "Intro"
  },
  "constraints": {
    "duration_s": 8.0,
    "fps": 24,
    "resolution": { "width": 854, "height": 480 },
    "compute_budget_s": 10,
    "sandbox_phase": 1,
    "watermark_required": false,
    "no_network": true,
    "timeout_sandbox_s": 60
  },
  "plan": {
    "steps": [
      { "tool": "lint_ast", "params": {"paths": ["scene.py"]}, "why": "Block unsafe imports" },
      { "tool": "run_manim", "params": {"entry_point": "scene.py", "scene": "Intro", "fps": 24, "preset": "480p"}, "why": "Render preview" }
    ]
  },
  "acceptance_tests": [
    { "id": "AT-DUR", "check": "duration <= 8.0 + 0.25", "expected": "pass" }
  ],
  "artifacts": {
    "video": "/artifacts/out.mp4",
    "thumbnail": "/artifacts/out.jpg",
    "logs": "/artifacts/run.log"
  },
  "memory": {
    "carry_forward": true,
    "notes": "User approved 8s preview preset."
  }
}

