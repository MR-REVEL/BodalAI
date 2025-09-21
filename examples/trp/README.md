# TRP Examples

This folder contains example Task Request Plan (TRP) JSON files demonstrating valid and invalid scenarios for the platform.

## How to validate locally

- Using the preflight script (PowerShell):
  - & "./.venv/Scripts/python.exe" scripts/preflight_validate.py <path-to-trp.json> --fail-on-warn

## Examples

- free_trp_2025-09-21.json — Valid, free-tier 8s preview at 480p. Expected: PASS.
- premium_trp_2025-09-21.json — Valid, premium 30s at 1080p. Expected: PASS.
- trp_free_trial_30s_valid.json — Valid, one-off trial using premium constraints with watermark_required=true. Expected: PASS (UI must enforce trial eligibility).
- trp_free_over_duration_invalid.json — Invalid, free-tier exceeds 8s and empty steps. Expected: FAIL.
- trp_wrong_fps_invalid.json — Invalid, fps must be 24 and steps must be non-empty. Expected: FAIL.

## Notes

- The schema is located at `schemas/trp.schema.json` (JSON Schema draft 2020-12).
- The CI workflow `.github/workflows/validate-trp.yml` validates these examples on PRs and pushes.
- For linter checks to run, `inputs.source_files` listed in a TRP must exist on disk; otherwise the linter step is skipped.
