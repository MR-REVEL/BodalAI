#!/usr/bin/env python3
import json, subprocess, sys, os, argparse
from jsonschema import Draft202012Validator

SCHEMA = "schemas/trp.schema.json"

def validate_trp(trp_path: str):
    try:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            schema = json.load(f)
        with open(trp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        Draft202012Validator(schema).validate(data)
        print("Schema validation: PASS")
        return data
    except Exception as e:
        print("Schema validation: FAIL")
        print(e)
        sys.exit(2)

def run_linter(files, project_root: str, artifacts_root: str, fail_on_warn: bool = False):
    cmd = [
        sys.executable,
        "runtime/ast_linter.py",
        "--paths",
        *files,
        "--project-root",
        project_root,
        "--artifacts-root",
        artifacts_root,
    ]
    if fail_on_warn:
        cmd.append("--fail-on-warn")

    res = subprocess.run(cmd, text=True)
    if res.returncode != 0:
        print("AST linter: FAIL")
        sys.exit(res.returncode if isinstance(res.returncode, int) else 3)
    print("AST linter: PASS")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Validate TRP and lint referenced source files.")
    ap.add_argument("trp", help="Path to TRP JSON file")
    ap.add_argument("--fail-on-warn", action="store_true", help="Treat linter warnings as failures")
    ap.add_argument("--project-root", default="/project", help="Allowed project root for writes (passed to linter)")
    ap.add_argument("--artifacts-root", default="/artifacts", help="Allowed artifacts root for writes (passed to linter)")
    args = ap.parse_args()

    trp = validate_trp(args.trp)
    inputs = trp.get("inputs", {})
    srcs = inputs.get("source_files", [])
    if srcs:
        run_linter(srcs, args.project_root, args.artifacts_root, args.fail_on_warn)
    else:
        print("No source_files found in TRP; skipping linter.")
    sys.exit(0)
