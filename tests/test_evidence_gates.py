"""Regression tests for evidence gates on conclusion-bearing context claims."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def run_audit(tmp_path, context, *extra):
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    out = tmp_path / "out"
    command = [sys.executable, str(ROOT / "scripts" / "run_audit.py"),
               "--library", str(ROOT / "tests" / "library.json"),
               "--context", str(context_path), "--out", str(out), *map(str, extra)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    return result, out


def test_context_booleans_cannot_claim_independent_validation_or_run_log(tmp_path):
    context = {
        "scope_status": "in_scope", "review_type": "systematic",
        "search_rounds": [
            {"pathway": "db", "completed": True, "core_before": 100,
             "included_high": 0, "screening_status": "screened_complete"},
            {"pathway": "backward", "completed": True, "core_before": 100,
             "included_high": 0, "screening_status": "screened_complete"},
        ],
        "planned_pathways": ["db", "backward"],
        "independent_pathways": [
            {"pathway_id": "db", "type": "db_boolean", "completed": True, "screening_status": "screened_complete", "yield": 0},
            {"pathway_id": "backward", "type": "backward_citation", "completed": True, "screening_status": "screened_complete", "yield": 0},
            {"pathway_id": "forward", "type": "forward_citation", "completed": True, "screening_status": "screened_complete", "yield": 0},
        ],
        "independent_validation_passed": True,
        "run_log_complete": True,
    }
    result, out = run_audit(tmp_path, context)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert rows["B3"]["meets_standard"] != "pass"
    assert rows["F1"]["meets_standard"] != "pass"
    assert report["context"]["evidence_validation"]["independent_validation"] == "self_reported_ignored"
    assert report["context"]["run_log_depth"] == "missing_artifact"


def test_validated_iterations_are_recorded_as_evidence(tmp_path):
    iterations = {
        "dev_validation_overlap_check": True,
        "dev_set": [{"doi": f"10.1/dev{i}"} for i in range(3)],
        "validation_set": [{"doi": f"10.1/val{i}"} for i in range(3)],
        "iterations": [{
            "iteration_id": "v1", "change_type": "initial", "change_description": "initial query",
            "change_source": "user_confirmed", "queries": {"db_main": "title:test"},
            "execution_date": "2026-07-28", "results": {"dev_recall": 0.8}, "decision": "continue",
        }],
    }
    iteration_path = tmp_path / "iterations.json"
    iteration_path.write_text(json.dumps(iterations), encoding="utf-8")
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
                            "--search-iterations", iteration_path)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert report["context"]["evidence_validation"]["independent_validation"] == "validated"
    assert report["context"]["independent_validation_passed"] is True
    assert report["artifacts"]["search-iterations"]["provided"] is True


def test_dev_requirements_include_tracked_mcp_runtime_dependency():
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "mcp>=" in requirements


def test_autopilot_unconfirmed_scope_writes_onboarding_without_audit(tmp_path):
    out = tmp_path / "first-pass"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--out", str(out), "--offline"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (out / "onboarding.html").is_file()
    manifest = json.loads((out / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "needs_scope_confirmation"
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_confirmed_scope_can_start_without_library(tmp_path):
    out = tmp_path / "first-pass"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--out", str(out), "--offline",
               "--scope-status", "in_scope"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (out / ".autopilot" / "starter-library.json").is_file()
    assert (out / "audit" / "audit.html").is_file()
