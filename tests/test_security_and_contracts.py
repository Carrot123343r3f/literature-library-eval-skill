"""Focused regression tests for safety and evidence-contract guarantees."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_open_sources import load_authorized_plan
from run_audit import _validate_run_config, stability
from search_for_eval import compute_recall, entry_ids


def test_threshold_boundary_is_inclusive():
    context = {
        "standards": {"b_ggr_threshold": 0.02, "b_drr_threshold": 0.05},
        "review_type": "快速综述",
        "planned_pathways": ["db-openalex", "backward-seed"],
        "independent_validation_passed": True,
        "run_log_complete": True,
        "search_rounds": [
            {"pathway": "db-openalex", "completed": True, "core_before": 100, "included_high": 2, "screening_status": "screened_complete"},
            {"pathway": "backward-seed", "completed": True, "core_before": 100, "included_high": 2, "screening_status": "screened_complete"},
        ],
        "independent_pathways": [
            {"pathway_id": "db-openalex", "type": "db_boolean", "completed": True, "yield": 0.05, "screening_status": "screened_complete"},
            {"pathway_id": "backward-seed", "type": "backward_citation", "completed": True, "yield": 0.05, "screening_status": "screened_complete"},
        ],
    }
    result = stability(context)
    assert all(value == "pass" for value in result["checks"].values())


def test_a2_recall_counts_items_not_identifiers():
    gold = [{"DOI": "10.1000/example", "PMID": "12345"}]
    hit_ids = entry_ids({"doi": "10.1000/example", "PMID": "12345"})
    recall, total = compute_recall(gold, hit_ids)
    assert (recall, total) == (1.0, 1)


def test_b_requires_explicit_screening_and_independent_pathways():
    result = stability({
        "review_type": "快速综述", "planned_pathways": ["db"],
        "independent_validation_passed": True, "run_log_complete": True,
        "search_rounds": [
            {"pathway": "db", "completed": True, "core_before": 100, "included_high": 0},
            {"pathway": "db", "completed": True, "core_before": 100, "included_high": 0},
        ],
    })
    assert result["checks"]["B1_ggr"] == "not_assessable"
    assert result["checks"]["B3_pathway_completion"] == "fail"


def test_discovery_layer_exposes_b_values_without_promoting_them_to_formal_b():
    result = stability({
        "review_type": "快速综述", "planned_pathways": ["openalex-first-round"],
        "search_rounds": [{
            "pathway": "openalex-first-round", "completed": True, "core_before": 100,
            "included_high": 0, "discovery_candidates": 12,
            "screening_status": "discovery_only",
        }],
        "source_marginal_yields": [{
            "pathway": "broad-query", "candidates": 20, "new_discovery_candidates": 8,
            "yield": 0.4, "screening_status": "discovery_only",
        }],
    })
    candidate = result["candidate_discovery"]
    assert candidate["status"] == "candidate_discovery"
    assert candidate["ggr_rates"] == [0.12]
    assert candidate["pathway_yields"][0]["yield"] == 0.4
    assert candidate["pathway_completion"] == 1.0
    assert result["checks"]["B1_ggr"] == "not_assessable"
    assert result["checks"]["B2_drr"] == "not_assessable"


def test_a2_uses_independent_validation_as_primary_value():
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        hits = root / "query-hits.json"
        meta = root / "search_meta.json"
        out = root / "out"
        hits.write_text("[]", encoding="utf-8")
        meta.write_text(json.dumps({
            "queries": [{"status": "complete"}], "a2_evidence_status": "measured",
            "dev_recall": 1.0, "validation_recall": 0.5,
            "validation_recall_total": 2, "validation_recall_matched": 1,
        }), encoding="utf-8")
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_audit.py"),
            "--library", str(ROOT / "tests" / "library.json"),
            "--gold", str(ROOT / "tests" / "gold.json"),
            "--query-hits", str(hits), "--search-meta", str(meta), "--out", str(out),
        ], check=True)
        audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
        assert audit["coverage"]["a2"]["recall"] == 0.5
        assert audit["coverage"]["a2"]["matched"] == 1


def test_config_requires_nested_review_fields_and_boolean_consent():
    config = {
        "schema_version": "1.0",
        "project": {"research_question": "q"},
        "library": {"provided": "yes"},
        "automation": {"allow_search": "true"},
        "output": {},
    }
    errors = _validate_run_config(config)
    assert any("review_type is required" in error for error in errors)
    assert any("scope_status is required" in error for error in errors)
    assert any("library.provided" in error for error in errors)
    assert any("allow_search must be boolean" in error for error in errors)


def test_collector_requires_persisted_consent_and_source_allowlist():
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        plan = root / "plan.json"
        config = root / "run-config.json"
        plan.write_text(json.dumps({"queries": [{"id": "q1", "query": "test", "sources": ["crossref"]}]}), encoding="utf-8")
        config.write_text(json.dumps({"automation": {"allow_search": False}}), encoding="utf-8")
        try:
            load_authorized_plan(config, plan)
            raise AssertionError("collection without consent must fail")
        except PermissionError:
            pass
        config.write_text(json.dumps({"automation": {"allow_search": True, "allowed_sources": ["openalex"]}}), encoding="utf-8")
        _, allowed = load_authorized_plan(config, plan)
        assert "crossref" not in allowed
        config.write_text(json.dumps({"automation": {"allow_search": True, "allowed_sources": []}}), encoding="utf-8")
        _, allowed = load_authorized_plan(config, plan)
        assert allowed == set()


def test_report_does_not_disclose_workspace_path_or_secret_context():
    with tempfile.TemporaryDirectory() as temp:
        temp_root = pathlib.Path(temp)
        context = json.loads((ROOT / "tests" / "context.json").read_text(encoding="utf-8"))
        context["api_key"] = "never-render-this"
        context["private_path"] = str(ROOT / "tests" / "library.json")
        context_path = temp_root / "context.json"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        out = temp_root / "out"
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_audit.py"),
            "--library", str(ROOT / "tests" / "library.json"),
            "--context", str(context_path), "--out", str(out),
        ], check=True)
        public = (out / "audit.json").read_text(encoding="utf-8")
        markdown = (out / "audit.md").read_text(encoding="utf-8")
        archived_context = next((out / "inputs").glob("context__*.json")).read_text(encoding="utf-8")
        assert "never-render-this" not in public
        assert str(ROOT) not in public
        assert "never-render-this" not in markdown
        assert str(ROOT) not in markdown
        assert "never-render-this" not in archived_context
        assert str(ROOT) not in archived_context


def test_first_run_register_reports_d2_and_missing_b_d3_evidence_explicitly():
    """A first-run report must distinguish a computed value from missing evidence."""
    with tempfile.TemporaryDirectory() as temp:
        out = pathlib.Path(temp) / "out"
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_audit.py"),
            "--run-config", str(ROOT / "tests" / "run-config-test.json"),
            "--gold", str(ROOT / "tests" / "gold.json"),
            "--query-hits", str(ROOT / "tests" / "zero-hits.json"), "--out", str(out),
        ], check=True)
        audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
        rows = {row["subproject"]: row for row in audit["indicator_register"]}
        assert rows["D2"]["meets_standard"] == "pass"
        assert "40.0%" in rows["D2"]["standard"]
        assert "0/2" in rows["B1"]["current_status"]
        assert "0/4" in rows["B2"]["current_status"]
        assert "0" in rows["D3"]["current_status"]


if __name__ == "__main__":
    test_threshold_boundary_is_inclusive()
    test_a2_recall_counts_items_not_identifiers()
    test_b_requires_explicit_screening_and_independent_pathways()
    test_discovery_layer_exposes_b_values_without_promoting_them_to_formal_b()
    test_a2_uses_independent_validation_as_primary_value()
    test_config_requires_nested_review_fields_and_boolean_consent()
    test_collector_requires_persisted_consent_and_source_allowlist()
    test_report_does_not_disclose_workspace_path_or_secret_context()
    test_first_run_register_reports_d2_and_missing_b_d3_evidence_explicitly()
    print("Security and contract tests: PASSED")
