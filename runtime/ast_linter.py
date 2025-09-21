#!/usr/bin/env python3
"""
AST Linter (Phase 1)
- Blocks disallowed imports (network/process/etc)
- Flags dangerous calls (eval/exec, os.system, subprocess.*, socket, requests)
- Warns on write operations outside /project or /artifacts when path is a string literal
- Exits non-zero on violations

Usage:
  python runtime/ast_linter.py --paths scene.py another.py \
    --project-root /project --artifacts-root /artifacts \
    --deny-imports socket requests subprocess multiprocessing ftplib paramiko psutil \
    --fail-on-warn

Integrate this in Preflight BEFORE sandbox execution.
"""

import argparse
import ast
import json
import os
import sys
from typing import List, Set, Tuple


DEFAULT_DENY_IMPORTS = {
    "socket", "requests", "subprocess", "multiprocessing",
    "ftplib", "paramiko", "psutil"
}

DANGEROUS_CALLS = {
    ("os", "system"),
    ("os", "popen"),
    ("builtins", "eval"),
    ("builtins", "exec"),
}

WRITE_FUNCS = {
    # (module, func) pairs; module can be None for builtins
    (None, "open"),  # mode includes 'w', 'a', or 'x'
}


class Finding:
    def __init__(self, path: str, lineno: int, col: int, level: str, code: str, msg: str):
        self.path = path
        self.lineno = lineno
        self.col = col
        self.level = level  # "ERROR" or "WARN"
        self.code = code
        self.msg = msg

    def to_dict(self):
        return {
            "file": self.path,
            "line": self.lineno,
            "col": self.col,
            "level": self.level,
            "code": self.code,
            "message": self.msg
        }

    def __str__(self):
        return f"{self.level} [{self.code}] {self.path}:{self.lineno}:{self.col} {self.msg}"


class LintVisitor(ast.NodeVisitor):
    def __init__(self, path: str, deny_imports: Set[str], project_root: str, artifacts_root: str):
        self.path = path
        self.deny_imports = deny_imports
        self.project_root = os.path.normpath(project_root)
        self.artifacts_root = os.path.normpath(artifacts_root)
        self.findings: List[Finding] = []
        self.alias_map = {}  # name -> module path (e.g., "sp" -> "subprocess")

    def error(self, node: ast.AST, code: str, msg: str):
        self.findings.append(Finding(self.path, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), "ERROR", code, msg))

    def warn(self, node: ast.AST, code: str, msg: str):
        self.findings.append(Finding(self.path, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), "WARN", code, msg))

    # --- Imports ---
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod = alias.name.split(".")[0]
            if mod in self.deny_imports:
                self.error(node, "IMP001", f"Disallowed import: '{mod}'")
            if alias.asname:
                self.alias_map[alias.asname] = alias.name
            else:
                self.alias_map[mod] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod = node.module.split(".")[0]
            if mod in self.deny_imports:
                self.error(node, "IMP001", f"Disallowed import: '{mod}'")
        for alias in node.names:
            name = alias.asname or alias.name
            self.alias_map[name] = (node.module or alias.name)
        self.generic_visit(node)

    # --- Calls ---
    def visit_Call(self, node: ast.Call):
        # Detect dangerous calls
        target_mod, target_func = self._resolve_call_target(node.func)

        # eval/exec & os.system/popen
        if (target_mod, target_func) in DANGEROUS_CALLS:
            self.error(node, "CAL001", f"Dangerous call: {target_mod}.{target_func}")

        # subprocess.* (direct or via alias)
        if target_mod and target_mod.split(".")[0] == "subprocess":
            self.error(node, "CAL002", "Process spawning via 'subprocess' is disallowed")

        # socket.* or requests.* usage
        if target_mod and target_mod.split(".")[0] in {"socket", "requests"}:
            self.error(node, "CAL003", f"Network usage via '{target_mod}' is disallowed")

        # Detect file writes outside allowed roots when path literal is known
        if (target_mod is None and target_func == "open") and len(node.args) >= 1:
            path_arg = node.args[0]
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], (ast.Str, ast.Constant)):
                mode = (node.args[1].s if isinstance(node.args[1], ast.Str) else node.args[1].value)

            write_mode = isinstance(mode, str) and any(c in mode for c in ("w", "a", "x"))
            if isinstance(path_arg, (ast.Str, ast.Constant)):
                path_val = path_arg.s if isinstance(path_arg, ast.Str) else path_arg.value
                if isinstance(path_val, str) and write_mode:
                    norm = os.path.normpath(path_val)
                    if not (norm.startswith(self.project_root) or norm.startswith(self.artifacts_root) or norm.startswith("./") or not os.path.isabs(norm)):
                        self.error(node, "FS001", f"Write outside allowed dirs: '{path_val}'")

        self.generic_visit(node)

    # --- Helpers ---
    def _resolve_call_target(self, func: ast.AST) -> Tuple[str, str]:
        # Returns (module, function) where module may be None for builtins
        if isinstance(func, ast.Name):
            # e.g., eval(...)
            name = func.id
            if name in {"eval", "exec", "open"}:
                return ("builtins" if name in {"eval", "exec"} else None, name)
            # If function name is an alias to a module, we can't be sure; return (name, "")
            alias_mod = self.alias_map.get(name)
            if alias_mod:
                return (alias_mod, "")
            return (None, name)
        if isinstance(func, ast.Attribute):
            # e.g., os.system(...), subprocess.Popen(...)
            mod = self._resolve_base(func.value)
            return (mod, func.attr)
        return (None, "")

    def _resolve_base(self, node: ast.AST) -> str:
        # Resolve 'subprocess' in 'subprocess.Popen', accounting for aliases
        if isinstance(node, ast.Name):
            name = node.id
            return self.alias_map.get(name, name)
        if isinstance(node, ast.Attribute):
            base = self._resolve_base(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

def lint_file(path: str, deny_imports: Set[str], project_root: str, artifacts_root: str) -> List[Finding]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src, filename=path)
    except SyntaxError as e:
        return [Finding(path, getattr(e, "lineno", 0), getattr(e, "offset", 0), "ERROR", "SYN001", f"SyntaxError: {e}")]
    v = LintVisitor(path, deny_imports, project_root, artifacts_root)
    v.visit(tree)
    return v.findings

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="+", required=True, help="Python files to lint")
    ap.add_argument("--project-root", default="/project", help="Allowed project root for writes")
    ap.add_argument("--artifacts-root", default="/artifacts", help="Allowed artifacts root for writes")
    ap.add_argument("--deny-imports", nargs="*", default=list(DEFAULT_DENY_IMPORTS))
    ap.add_argument("--json", action="store_true", help="Output findings as JSON")
    ap.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings too")
    args = ap.parse_args()

    deny = set(args.deny_imports)
    findings: List[Finding] = []
    for p in args.paths:
        findings.extend(lint_file(p, deny, args.project_root, args.artifacts_root))

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(str(f))

    has_error = any(f.level == "ERROR" for f in findings)
    has_warn = any(f.level == "WARN" for f in findings)
    if has_error or (args.fail_on_warn and has_warn):
        sys.exit(2)
    sys.exit(0)

if __name__ == "__main__":
    main()