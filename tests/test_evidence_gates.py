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
    if out.exists():
        command.append("--force")
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
    assert report["context"]["evidence_validation"]["independent_validation"] == "invalid"
    assert report["context"]["independent_validation_passed"] is False
    assert report["context"]["gold_independence_status"] != "independence_confirmed"
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


def test_autopilot_confirmed_scope_without_library_delivers_search_preparation_only(tmp_path):
    out = tmp_path / "first-pass"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--out", str(out), "--offline",
               "--scope-status", "in_scope"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (out / "search-preparation.html").is_file()
    manifest = json.loads((out / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "search_preparation"
    assert manifest["audit_status"] == "not_started"
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_library_health_does_not_emit_a_sufficiency_audit(tmp_path):
    out = tmp_path / "health"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--library", str(ROOT / "tests" / "library.json"),
               "--out", str(out), "--offline", "--scope-status", "in_scope", "--mode", "library-health"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (out / "library-health.html").is_file()
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_auto_never_upgrades_to_audit_from_review_type(tmp_path):
    out = tmp_path / "implicit"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--library", str(ROOT / "tests" / "library.json"),
               "--review-type", "systematic", "--out", str(out), "--offline", "--scope-status", "in_scope"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "library_health"
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_sufficiency_audit_requires_boundaries_before_starting(tmp_path):
    out = tmp_path / "missing-boundaries"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--library", str(ROOT / "tests" / "library.json"),
               "--out", str(out), "--offline", "--scope-status", "in_scope",
               "--mode", "sufficiency-audit", "--review-type", "systematic"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode != 0
    assert "--time-start" in result.stderr
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_rejects_inverted_future_and_invalid_language_boundaries(tmp_path):
    common = ["--question", "robot localization", "--library", str(ROOT / "tests" / "library.json"),
              "--offline", "--scope-status", "in_scope", "--mode", "sufficiency-audit",
              "--review-type", "systematic", "--output-language", "zh-CN"]
    inverted = subprocess.run([sys.executable, str(ROOT / "scripts" / "autopilot.py"), *common,
                               "--out", str(tmp_path / "inverted"), "--time-start", "2026", "--time-end", "2020", "--languages", "en"],
                              capture_output=True, text=True, encoding="utf-8")
    assert inverted.returncode != 0
    assert "not later" in inverted.stderr
    invalid_language = subprocess.run([sys.executable, str(ROOT / "scripts" / "autopilot.py"), *common,
                                       "--out", str(tmp_path / "language"), "--time-start", "2020", "--time-end", "2026", "--languages", "xx"],
                                      capture_output=True, text=True, encoding="utf-8")
    assert invalid_language.returncode != 0
    assert "ISO language" in invalid_language.stderr


def test_autopilot_accepts_common_bcp47_language_tag(tmp_path):
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--library", str(ROOT / "tests" / "library.json"),
               "--out", str(tmp_path / "bcp47"), "--offline", "--scope-status", "in_scope",
               "--mode", "sufficiency-audit", "--review-type", "systematic", "--time-start", "2020",
               "--time-end", "2026", "--languages", "zh-CN", "--output-language", "zh-CN"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "bcp47" / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "sufficiency_precheck"


def test_scoped_library_is_used_by_all_record_based_metrics_and_english_html(tmp_path):
    library = tmp_path / "scoped.json"
    library.write_text(json.dumps([
        {"title": "English in scope", "year": 2024, "date": "2024", "language": "en-US", "source": "A", "abstractNote": "x", "cited_by_count": 10},
        {"title": "Chinese in scope", "year": 2024, "date": "2024", "language": "zh-CN", "source": "B", "abstractNote": "x", "cited_by_count": 100},
        {"title": "English out of time", "year": 1990, "date": "1990", "language": "en", "source": "C", "abstractNote": "x", "cited_by_count": 100},
        {"title": "Unknown language", "year": 2024, "date": "2024", "source": "D", "abstractNote": "x", "cited_by_count": 100},
    ]), encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"scope_status": "in_scope", "review_type": "systematic",
                                   "year_start": 2020, "year_end": 2026, "languages": ["en"],
                                   "output_language": "en"}), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_audit.py"), "--library", str(library),
                             "--context", str(context), "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    scope = report["context"]["scope_application"]
    assert scope["total_records"] == 4 and scope["in_scope_records"] == 1
    assert scope["time_excluded_records"] == 1 and scope["language_excluded_records"] == 2
    assert report["library_health"]["records"] == 1
    assert report["quality"]["h_core"] == 1
    html = (out / "audit.html").read_text(encoding="utf-8")
    assert "Literature Library Evidence Audit" in html
    assert not any("\u4e00" <= char <= "\u9fff" for char in html)


def test_source_labels_do_not_establish_f5_traceability(tmp_path):
    library = tmp_path / "labels.json"
    library.write_text(json.dumps([
        {"title": f"Paper {index}", "year": 2024, "date": "2024", "source": "claimed-db"}
        for index in range(3)
    ]), encoding="utf-8")
    context = tmp_path / "context.json"
    context.write_text(json.dumps({"scope_status": "in_scope", "review_type": "systematic"}), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_audit.py"), "--library", str(library),
                             "--context", str(context), "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert report["library_health"]["source_label_rate"] == 1.0
    assert report["library_health"]["provenance_rate"] == 0.0
    row = next(row for row in report["indicator_register"] if row["subproject"] == "F5")
    assert row["meets_standard"] == "not_assessable"


def test_autopilot_invalid_evidence_is_a_precheck_not_a_traceback(tmp_path):
    library = tmp_path / "library.json"
    library.write_text(json.dumps([
        {"title": f"Robot localization {index}", "year": 2024, "language": "en", "DOI": f"10.1/lib{index}"}
        for index in range(3)
    ]), encoding="utf-8")
    bad_files = {}
    for name, payload in (("gold", {}), ("hits", {}), ("log", {}), ("decisions", {}), ("iterations", {}), ("paths", [{}, {}])):
        path = tmp_path / f"{name}.json"; path.write_text(json.dumps(payload), encoding="utf-8"); bad_files[name] = path
    out = tmp_path / "invalid-evidence"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"), "--question", "robot localization",
               "--library", str(library), "--out", str(out), "--offline", "--scope-status", "in_scope",
               "--mode", "sufficiency-audit", "--review-type", "systematic", "--time-start", "2020", "--time-end", "2026", "--languages", "en", "--output-language", "en",
               "--gold", str(bad_files["gold"]), "--query-hits", str(bad_files["hits"]), "--query-log", str(bad_files["log"]),
               "--screening-decisions", str(bad_files["decisions"]), "--search-iterations", str(bad_files["iterations"]), "--independent-pathways", str(bad_files["paths"])]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr + result.stdout
    manifest = json.loads((out / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "sufficiency_precheck"
    assert {"library", "gold", "query_hits", "heldout"} <= set(manifest["scope_matrix"])
    assert any("Gold set" in item for item in manifest["missing_minimum_inputs"])
    config_text = (out / ".autopilot" / "run-config.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in config_text
    assert not (out / "audit" / "audit.html").exists()


def test_run_full_audit_cannot_bypass_shared_preflight(tmp_path):
    config = tmp_path / "run-config.json"
    config.write_text(json.dumps({"schema_version": "1.0", "project": {"research_question": "robot localization", "review_type": "systematic", "scope_status": "in_scope", "time_range": {"start": 2020, "end": 2026}, "languages": ["en"], "allowed_assessment_level": "full"}, "library": {"provided": True, "path": str(ROOT / "tests" / "library.json"), "format": "json"}, "automation": {"allow_search": False, "allowed_sources": []}, "output": {"language": "en", "formats": ["html"]}}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run", "--run-config", str(config), "--out", str(tmp_path / "out")], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0
    assert (tmp_path / "out" / "sufficiency-precheck.json").is_file()


def test_autopilot_relevance_mismatch_stops_at_sufficiency_precheck(tmp_path):
    library = tmp_path / "bridges.json"
    library.write_text(json.dumps([
        {"title": "Bridge corrosion monitoring", "year": 2024},
        {"title": "Steel bridge inspection", "year": 2023},
        {"title": "Concrete corrosion review", "year": 2022},
    ]), encoding="utf-8")
    out = tmp_path / "mismatch"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"), "--question", "robot localization",
               "--library", str(library), "--out", str(out), "--offline", "--scope-status", "in_scope",
               "--mode", "sufficiency-audit", "--review-type", "systematic", "--time-start", "2020",
               "--time-end", "2026", "--languages", "en", "--output-language", "zh-CN"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "autopilot-manifest.json").read_text(encoding="utf-8"))
    assert manifest["mode"] == "sufficiency_precheck"
    assert not (out / "audit" / "audit.html").exists()


def test_autopilot_library_health_imports_csv_before_checking(tmp_path):
    source = tmp_path / "library.csv"
    source.write_text("title,year,DOI,abstract\nOne,2024,10.1/one,short\n", encoding="utf-8")
    out = tmp_path / "csv-health"
    command = [sys.executable, str(ROOT / "scripts" / "autopilot.py"),
               "--question", "robot localization", "--library", str(source), "--out", str(out),
               "--offline", "--scope-status", "in_scope", "--mode", "library-health"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert "可读取记录：1" in (out / "library-health.html").read_text(encoding="utf-8")


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
    assert rows["F1"]["meets_standard"] == "screening"
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


def test_unconfirmed_standards_never_emit_pass_fail_or_warning(tmp_path):
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"})
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    verdicts = {row["meets_standard"] for row in report["indicator_register"]}
    assert not verdicts & {"pass", "fail", "warning"}
    overview = (out / "audit.html").read_text(encoding="utf-8")
    assert "尚不能作充分性判断" in overview


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
    assert report["context"]["gold_independence_status"] == "distinct_records_unverified"
    assert row["evidence_status"] == "estimated"

    iterations = {
        "dev_validation_overlap_check": True,
        "dev_set": [{"doi": f"10.1000/dev{i}"} for i in range(3)],
        "validation_set": [{"doi": f"10.1000/validation{i}"} for i in range(3)],
        "iterations": [{
            "iteration_id": "v1", "change_type": "initial", "change_description": "initial query",
            "change_source": "user_confirmed", "queries": {"db": "title:test"},
            "execution_date": "2026-07-28", "results": {"dev_recall": 1.0}, "decision": "continue",
        }],
    }
    iteration_path = tmp_path / "iterations.json"
    iteration_path.write_text(json.dumps(iterations), encoding="utf-8")
    result, out = run_audit(
        tmp_path, context,
        "--benchmark", benchmark, "--gold", gold, "--query-hits", hits,
        "--search-iterations", iteration_path,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    row = next(item for item in report["indicator_register"] if item["subproject"] == "A2")
    assert report["context"]["gold_independence_status"] != "independence_confirmed"
    assert row["evidence_status"] == "estimated"
    assert row["decision_status"] == "standards_unconfirmed"


def test_decision_status_and_html_language_are_explicit(tmp_path):
    result, out = run_audit(tmp_path, {"scope_status": "in_scope", "review_type": "systematic"})
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    rows = {row["subproject"]: row for row in report["indicator_register"]}
    assert rows["C1"]["decision_status"] == "evidence_missing"
    assert rows["A3"]["decision_status"] == "descriptive_only"
    assert "C 主题平衡 不可评估" in report["summary"]
    assert "<html lang='zh-CN'>" in (out / "audit.html").read_text(encoding="utf-8")


def test_a2_measured_requires_gold_bound_heldout_test_set(tmp_path):
    benchmark = tmp_path / "benchmark.json"
    gold = tmp_path / "gold.json"
    hits = tmp_path / "hits.json"
    iterations = tmp_path / "iterations.json"
    dev = [{"doi": f"10.1000/dev{i}"} for i in range(3)]
    tuning = [{"doi": f"10.1000/tuning{i}"} for i in range(3)]
    heldout = [{"doi": f"10.1000/heldout{i}"} for i in range(3)]
    benchmark.write_text(json.dumps(dev), encoding="utf-8")
    gold.write_text(json.dumps(heldout), encoding="utf-8")
    hits.write_text(json.dumps(heldout), encoding="utf-8")
    iterations.write_text(json.dumps({
        "dev_validation_overlap_check": True,
        "dev_set": dev, "validation_set": tuning, "heldout_test_set": heldout,
        "iterations": [{
            "iteration_id": "v1", "change_type": "initial", "change_description": "initial",
            "change_source": "user_confirmed", "queries": {"db": "title:test"},
            "execution_date": "2026-07-29", "results": {"dev_recall": 1.0}, "decision": "continue",
        }],
    }), encoding="utf-8")
    result, out = run_audit(
        tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
        "--benchmark", benchmark, "--gold", gold, "--query-hits", hits,
        "--search-iterations", iterations,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    row = next(item for item in report["indicator_register"] if item["subproject"] == "A2")
    assert report["context"]["gold_independence_status"] == "independence_confirmed"
    assert row["evidence_status"] == "measured"


def test_screening_summary_cannot_replace_search_execution_metadata(tmp_path):
    search_meta = tmp_path / "search-meta.json"
    screening = tmp_path / "screening-summary.json"
    search_meta.write_text(json.dumps({"queries": [{"status": "failed"}]}), encoding="utf-8")
    screening.write_text(json.dumps({"screening_summary": {"included": 4}}), encoding="utf-8")
    result, out = run_audit(
        tmp_path, {"scope_status": "in_scope", "review_type": "systematic"},
        "--search-meta", search_meta, "--screening-summary", screening,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert report["context"]["_search_meta_query_failed"] is True
    assert report["context"]["screening_summary"]["included"] == 4
    assert report["artifacts"]["search-meta"]["provided"] is True
    assert report["artifacts"]["screening-summary"]["provided"] is True


def test_run_config_alone_maps_iteration_query_plan_and_search_meta(tmp_path):
    benchmark = tmp_path / "benchmark.json"
    gold = tmp_path / "gold.json"
    hits = tmp_path / "hits.json"
    iterations = tmp_path / "iterations.json"
    query_plan = tmp_path / "query-plan.json"
    search_meta = tmp_path / "search-meta.json"
    benchmark.write_text(json.dumps([{"doi": "10.1000/dev"}]), encoding="utf-8")
    gold.write_text(json.dumps([{"doi": "10.1000/validation"}]), encoding="utf-8")
    hits.write_text(json.dumps([{"doi": "10.1000/validation"}]), encoding="utf-8")
    iterations.write_text(json.dumps({
        "dev_validation_overlap_check": True,
        "dev_set": [{"doi": f"10.1000/dev{i}"} for i in range(3)],
        "validation_set": [{"doi": f"10.1000/validation{i}"} for i in range(3)],
        "iterations": [{
            "iteration_id": "v1", "change_type": "initial", "change_description": "initial",
            "change_source": "user_confirmed", "queries": {"db": "title:test"},
            "execution_date": "2026-07-28", "results": {"dev_recall": 1.0}, "decision": "continue",
        }],
    }), encoding="utf-8")
    query_plan.write_text(json.dumps({"arxiv": "title:test"}), encoding="utf-8")
    search_meta.write_text(json.dumps({
        "queries": [{"status": "complete"}], "a2_evidence_status": "measured",
        "validation_recall": 1.0, "validation_recall_total": 1, "validation_recall_matched": 1,
    }), encoding="utf-8")
    config = json.loads((ROOT / "tests" / "run-config-test.json").read_text(encoding="utf-8"))
    config["library"]["path"] = str(ROOT / "tests" / "library.json")
    config["evidence_inputs"]["source_snapshot"] = None
    config["evidence_inputs"].update({
        "benchmark": str(benchmark), "gold": str(gold), "query_hits": str(hits),
        "query_plan": str(query_plan), "search_meta": str(search_meta),
        "search_iterations": str(iterations),
    })
    config_path = tmp_path / "run-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_audit.py"),
        "--run-config", str(config_path), "--out", str(out),
    ], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert report["context"]["gold_independence_status"] != "independence_confirmed"
    assert report["artifacts"]["query-plan"]["provided"] is True
    assert report["artifacts"]["search-meta"]["provided"] is True
    assert report["artifacts"]["search-iterations"]["provided"] is True
