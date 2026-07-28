import json

import pytest

from scripts.lle_core.contracts import validate_run_config_contract, validate_stage_inputs, validate_stage_outputs
from scripts.lle_core.models import WorkflowState
from scripts.lle_core.runtime import WorkflowContext
from scripts.lle_core.state_machine import advance
from scripts.audit_core.coverage import evaluate_gold_recall, evaluate_multisource_lower_bound


def test_kernel_records_stage_and_artifact_lineage(tmp_path):
    context = WorkflowContext.open(tmp_path, "sig-1")
    context.advance("config_validated")
    artifact = tmp_path / "audit.json"
    artifact.write_text('{"status":"ok"}\n', encoding="utf-8")
    context.complete_step("audit", [artifact])
    saved = json.loads((tmp_path / "workflow-state.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "2.0"
    assert saved["stage"] == "config_validated"
    assert saved["artifacts"]["audit.json"]["producer"] == "audit"
    assert len(saved["artifacts"]["audit.json"]["sha256"]) == 64


def test_kernel_rejects_backward_transition_and_escape(tmp_path):
    state = WorkflowState("r", "s", stage="audit_ready")
    with pytest.raises(ValueError, match="backward"):
        advance(state, "library_ready")
    outside = tmp_path.parent / "outside.json"
    outside.write_text("x", encoding="utf-8")
    assert validate_stage_outputs(tmp_path, "audit", [outside])
    assert validate_stage_inputs("audit", [tmp_path / "missing.json"])


def test_kernel_migrates_legacy_step_state():
    state = WorkflowState.from_dict({"schema_version": "1.1", "run_signature": "s",
                                     "steps": {"audit": "complete"}})
    assert state.stage == "report_ready"
    assert state.as_dict()["schema_version"] == "2.0"


def test_kernel_uses_shared_run_config_contract():
    errors = validate_run_config_contract({"schema_version": "1.0", "project": {},
                                           "library": {}, "automation": {}, "output": {}})
    assert any("research_question" in error for error in errors)


def test_coverage_evaluators_are_report_independent_and_identifier_bound():
    stable_ids = lambda row: {row["doi"]} if row.get("doi") else set()
    a2 = evaluate_gold_recall([{"doi": "10/a"}], [{"doi": "10/a"}], stable_ids)
    assert a2["status"] == "measured" and a2["recall"] == 1.0
    sources = {
        "one": {"items": [{"doi": "10/a"}], "statuses": ["complete"], "completion_flags": [True],
                "scope_filters": {"year": 2025}, "dedup_rule": "stable_id"},
        "two": {"items": [{"doi": "10/b"}], "statuses": ["complete"], "completion_flags": [True],
                "scope_filters": {"year": 2025}, "dedup_rule": "stable_id"},
    }
    a3 = evaluate_multisource_lower_bound(sources, stable_ids)
    assert a3["status"] == "estimated_lower_bound"
    assert a3["deduplicated_candidate_lower_bound"] == 2
