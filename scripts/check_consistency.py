#!/usr/bin/env python3
"""Check cross-file consistency for the literature-library-eval project."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATH_RE = re.compile(r"(?<![\w/])((?:scripts|references|schemas|docs)/[A-Za-z0-9_.\-/]+)")


def check_references():
    errors = []
    for path in list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md")) + list((ROOT / "references").glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PATH_RE.findall(text):
            target = match.rstrip("`.,:;)]}")
            if not (ROOT / target).exists():
                errors.append(f"{path.relative_to(ROOT)} references missing {target}")
    return errors


def check_json():
    errors = []
    for path in ROOT.glob("schemas/*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)} invalid JSON: {exc}")
    return errors


def check_scripts():
    errors = []
    for name in ("optimization.py", "quality_optimization.py", "experiment_attribution.py", "evalset_audit.py", "search_iterator.py", "run_full_audit.py", "check_consistency.py"):
        path = ROOT / "scripts" / name
        if not path.exists():
            errors.append(f"missing expected script: scripts/{name}")
    for name in ("__init__.py", "models.py", "state_machine.py", "contracts.py", "artifacts.py", "runtime.py"):
        if not (ROOT / "scripts" / "lle_core" / name).exists():
            errors.append(f"missing architecture kernel file: scripts/lle_core/{name}")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "optimization.py"), "--help"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(f"optimization CLI help failed: {result.stderr.strip()}")
    else:
        for command in ("init-workspace", "candidate-status", "rollback", "observe", "history-search", "metric-evaluate"):
            if command not in result.stdout:
                errors.append(f"optimization CLI missing command: {command}")
    quality_help = subprocess.run([sys.executable, str(ROOT / "scripts" / "quality_optimization.py"), "--help"], capture_output=True, text=True)
    if quality_help.returncode != 0:
        errors.append(f"quality optimization CLI help failed: {quality_help.stderr.strip()}")
    else:
        for command in ("counterexample", "screen-queue", "canary"):
            if command not in quality_help.stdout:
                errors.append(f"quality optimization CLI missing command: {command}")
    for script, commands in (("experiment_attribution.py", ("--baseline", "--candidates")), ("evalset_audit.py", ("--dev", "--validation"))):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), "--help"], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"{script} CLI help failed: {result.stderr.strip()}")
        for command in commands:
            if command not in result.stdout:
                errors.append(f"{script} CLI missing argument: {command}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="reserved for CI compatibility")
    parser.parse_args()
    errors = check_references() + check_json() + check_scripts()
    if errors:
        print("CONSISTENCY FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("CONSISTENCY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
