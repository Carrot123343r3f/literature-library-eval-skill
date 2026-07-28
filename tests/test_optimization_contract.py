import json

import pytest

from scripts.evalset_audit import audit as audit_evalsets
from scripts.experiment_attribution import attribute
from scripts.optimization import (
    dump,
    evaluate_metrics,
    init_run,
    init_workspace,
    load,
    transition_candidate,
    validate_run,
    write_candidate,
    write_observation,
)
from scripts.quality_optimization import build_screen_queue, compare_canary
from scripts.quality_optimization import append_counterexample


def make_workspace(tmp_path):
    skill = tmp_path / "skill"
    evaluation = tmp_path / "eval"
    run = tmp_path / "run"
    skill.mkdir()
    evaluation.mkdir()
    init_workspace(skill, evaluation, run, "topic", "objective")
    return run


def test_observation_rejects_unknown_raw_payload(tmp_path):
    run = make_workspace(tmp_path)
    with pytest.raises(ValueError, match="non-aggregate|forbidden"):
        write_observation(run, {"observation_id": "o1", "stage": "heldout", "candidate_id": "c1",
                                "outcome": {"raw_trace": "secret"}})
    with pytest.raises(ValueError, match="invalid aggregate key"):
        write_observation(run, {"observation_id": "o2", "stage": "heldout", "candidate_id": "c1",
                                "outcome": {"leaked_data": "secret"}})


def test_candidate_acceptance_requires_pr_val_and_regression(tmp_path):
    run = make_workspace(tmp_path)
    write_candidate(run, {"candidate_id": "c1", "parent_candidate": None,
                          "change_type": "add_synonym", "patch": {"term": "transfer"}})
    transition_candidate(run, "c1", "under_evaluation")
    with pytest.raises(ValueError, match="requires pr_val"):
        transition_candidate(run, "c1", "accepted", metrics={"eligible": True})
    for stage in ("pr_val", "regression"):
        write_observation(run, {"observation_id": f"o-{stage}", "stage": stage, "candidate_id": "c1",
                                "outcome": {"eligible": True}, "metrics": {"validation_recall": 0.8}})
    accepted = transition_candidate(run, "c1", "accepted", metrics={"eligible": True})
    assert accepted["state"] == "accepted"


def test_store_path_cannot_escape_run(tmp_path):
    root = tmp_path / "legacy"
    init_run(root, "topic", "objective")
    run = load(root / "run.json")
    run["stores"]["decision_history"] = "../outside.jsonl"
    dump(root / "run.json", run)
    errors, _ = validate_run(root)
    assert any("escapes run root" in error for error in errors)


def test_metrics_are_normalized_and_unconfigured_cost_is_not_used():
    result = evaluate_metrics({"validation_recall": 0.8, "duration_s": 10000})
    assert result["components"]["validation_recall"]["normalized"] == 0.8
    assert "duration_s" not in result["components"]
    assert any("duration_s" in warning for warning in result["warnings"])
    low = evaluate_metrics({"cost": 10}, constraints={"max_cost": 100})
    high = evaluate_metrics({"cost": 90}, constraints={"max_cost": 100})
    assert low["objective"] > high["objective"]


def test_quality_utilities_and_new_components():
    queue = build_screen_queue([{"id": "a", "uncertainty": 0.9, "impact": 0.8}, {"id": "b"}], 1)
    assert queue[0]["id"] == "a"
    assert compare_canary({"count": 100}, {"count": 120})["status"] == "drift"
    metadata_drift = compare_canary({"metrics": {"count": 100}, "metadata": {"query_hash": "a"}},
                                    {"metrics": {"count": 100}, "metadata": {"query_hash": "b"}})
    assert metadata_drift["status"] == "drift"
    attribution = attribute({"validation_recall": 0.5}, [{"candidate_id": "c1", "metrics": {"validation_recall": 0.7}}])
    assert attribution["candidates"][0]["deltas"]["validation_recall"]["delta"] == 0.2
    eval_report = audit_evalsets([{"doi": "10/dev1"}, {"doi": "10/dev2"}, {"doi": "10/dev3"}],
                                 [{"doi": "10/val1"}, {"doi": "10/val2"}, {"doi": "10/val3"}])
    assert eval_report["status"] == "valid"
    multi_id = audit_evalsets([{"doi": "10/dev4", "pmid": "4"}], [{"doi": "10/val4"}], 1, 1)
    assert multi_id["status"] == "valid"


def test_counterexample_is_linked_to_decision_history(tmp_path):
    run = make_workspace(tmp_path)
    append_counterexample(run, {"counterexample_id": "ce1", "type": "false_positive",
                                "diagnosis": "boundary", "observed": "x", "expected": "y"})
    history = (run / "decision-history" / "decision-history.jsonl").read_text(encoding="utf-8")
    assert "counterexample-ce1" in history
