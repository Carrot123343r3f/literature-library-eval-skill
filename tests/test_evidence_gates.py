"""Regression tests for evidence gates on conclusion-bearing context claims."""
from __future__ import annotations

import json
import os
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
    seed_plan = json.loads((out / "citations" / "citation-seeds.json").read_text(encoding="utf-8"))
    assert seed_plan["status"] == "no_openalex_seed_available"


def test_citation_seed_plan_prefers_user_seed_then_library(tmp_path):
    from scripts.citation_seed_plan import make_plan
    library = [{"id": "https://openalex.org/W2", "title": "library", "cited_by_count": 10}]
    user = tmp_path / "user.json"
    user.write_text(json.dumps([{"openalex_id": "https://openalex.org/W1", "title": "user"}]), encoding="utf-8")
    seeds = make_plan(library, [], user)
    assert [seed["openalex_id"] for seed in seeds] == ["https://openalex.org/W1", "https://openalex.org/W2"]
    assert seeds[0]["seed_origin"] == "user_provided_seed"


def test_citation_expansion_degrades_to_structured_zero_result_without_key(tmp_path):
    config = tmp_path / "run-config.json"
    config.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test", "review_type": "narrative", "scope_status": "in_scope"},
        "library": {"provided": False},
        "automation": {"allow_search": True, "allow_citation_tracking": True, "allowed_sources": ["openalex"]},
        "output": {"formats": ["html", "json"]},
    }), encoding="utf-8")
    seed = tmp_path / "seeds.json"
    seed.write_text(json.dumps({"items": [{"openalex_id": "https://openalex.org/W1"}]}), encoding="utf-8")
    out = tmp_path / "citations"
    environment = dict(os.environ); environment.pop("OPENALEX_API_KEY", None)
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "citation_candidates.py"),
                             "--seed", str(seed), "--run-config", str(config), "--out", str(out), "--allow-unavailable"],
                            capture_output=True, text=True, encoding="utf-8", env=environment)
    assert result.returncode == 0, result.stderr
    payload = json.loads((out / "citation-candidates.json").read_text(encoding="utf-8"))
    assert payload["status"] == "not_expanded" and payload["seed_count"] == 1


def test_audit_reports_citation_candidates_without_treating_them_as_included(tmp_path):
    seed_plan = tmp_path / "citation-seeds.json"
    seed_plan.write_text(json.dumps({"status": "ready", "items": [{"openalex_id": "https://openalex.org/W1"}]}), encoding="utf-8")
    discovery = tmp_path / "citation-candidates.json"
    discovery.write_text(json.dumps({
        "status": "completed", "seed_count": 1,
        "items": [{"pathway": "backward_citation"}, {"pathway": "forward_citation"}],
    }), encoding="utf-8")
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
                            "--citation-seed-plan", seed_plan, "--citation-discovery", discovery)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    citation = report["context"]["citation_candidate_discovery"]
    assert citation["candidate_count"] == 2
    assert citation["backward_candidates"] == 1
    assert citation["forward_candidates"] == 1
    assert "not included studies or saturation evidence" in report["summary"]


def test_indicator_rows_never_mix_a_verdict_with_incompatible_evidence(tmp_path):
    run_log = tmp_path / "run-log.json"
    run_log.write_text(json.dumps({"queries": [{
        "source": "arxiv", "query": "robot localization", "fields": "title,abstract", "date": "2026-07-28",
    }]}), encoding="utf-8")
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
                            "--run-log", run_log)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert rows["F1"]["meets_standard"] == "pass"
    assert rows["F1"]["evidence_status"] == "measured"
    assert rows["E2"]["meets_standard"] == rows["E2"]["evidence_status"] == "not_assessable"
    assert rows["F6"]["meets_standard"] == rows["F6"]["evidence_status"] == "not_assessable"


def test_a2_reused_a1_file_is_marked_non_independent_and_downgraded(tmp_path):
    shared = ROOT / "tests" / "benchmark.json"
    result, out = run_audit(
        tmp_path,
        {"scope_status": "in_scope", "review_type": "systematic"},
        "--benchmark", shared, "--gold", shared,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert report["context"]["gold_independence_status"] == "same_records"
    assert report["artifacts"]["benchmark"]["provided"] is True
    assert report["artifacts"]["gold"]["provided"] is True
    assert rows["A2"]["evidence_status"] == "manual-verification-required"
    assert rows["A2"]["meets_standard"] == "screening"


def test_unconfirmed_standard_does_not_rewrite_measured_evidence(tmp_path):
    result, out = run_audit(
        tmp_path,
        {"scope_status": "in_scope", "review_type": "systematic"},
        "--benchmark", ROOT / "tests" / "benchmark.json",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    row = next(item for item in report["indicator_register"] if item["subproject"] == "A1")
    assert row["meets_standard"] == "screening"
    assert row["evidence_status"] == "measured"
    assert row["decision_status"] == "standards_unconfirmed"


def test_missing_taxonomy_and_search_dates_do_not_make_affirmative_claims(tmp_path):
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"})
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert rows["C1"]["meets_standard"] == "not_assessable"
    assert "无法判断" in rows["C1"]["description_and_action"]
    assert rows["D1"]["meets_standard"] == "not_assessable"
    assert "无法判断" in rows["D1"]["description_and_action"]


def test_a2_requires_record_and_metadata_independence_for_measured_evidence(tmp_path):
    benchmark = tmp_path / "benchmark.json"
    gold = tmp_path / "gold.json"
    hits = tmp_path / "hits.json"
    benchmark.write_text(json.dumps([{"doi": "10.1000/dev"}]), encoding="utf-8")
    gold.write_text(json.dumps([{"doi": "10.1000/validation"}]), encoding="utf-8")
    hits.write_text(json.dumps([{"doi": "10.1000/validation"}]), encoding="utf-8")
    result, out = run_audit(
        tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
        "--benchmark", benchmark, "--gold", gold, "--query-hits", hits,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    row = next(item for item in report["indicator_register"] if item["subproject"] == "A2")
    assert report["context"]["gold_independence_status"] == "distinct_records_unverified"
    assert row["evidence_status"] == "estimated"

    context = {
        "scope_status": "in_scope", "review_type": "systematic",
        "gold_set_metadata": {
            "validation_set_source": "independent review released after query development",
            "independence_rationale": "validation records were held out from all refinement rounds",
            "dev_validation_overlap_check": True,
            "validation_set_frozen": True,
            "validation_set_frozen_at": "2026-07-28",
        },
    }
    result, out = run_audit(
        tmp_path, context,
        "--benchmark", benchmark, "--gold", gold, "--query-hits", hits,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    row = next(item for item in report["indicator_register"] if item["subproject"] == "A2")
    assert report["context"]["gold_independence_status"] == "independence_confirmed"
    assert row["evidence_status"] == "measured"
    assert row["decision_status"] == "standards_unconfirmed"


def test_decision_status_and_html_language_are_explicit(tmp_path):
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"})
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert rows["C1"]["decision_status"] == "evidence_missing"
    assert rows["A3"]["decision_status"] == "descriptive_only"
    assert "<html lang='zh-CN'>" in (out / "audit.html").read_text(encoding="utf-8")
