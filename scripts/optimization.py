#!/usr/bin/env python3
"""Reusable two-store optimization harness for literature workflows.

The harness keeps development evidence and held-out validation evidence in
separate stores.  It records one atomic revision per iteration as a durable
decision-history tuple:
diagnosis -> candidate_revision -> redacted_evidence -> outcome.

This module is deliberately domain-agnostic.  Search iteration, query-plan
construction, screening-rule refinement, and other workflow optimizers can all
write the same contract.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import re
import sys
import time
from datetime import datetime, timezone

MAX_ITERATIONS = 8
PLATEAU_DELTA = 0.03
FORBIDDEN_OBSERVATION_KEYS = {
    "gold", "gold_set", "validation_items", "validation_set", "full_questions",
    "raw_questions", "answer_key", "reference_answers", "doi", "pmid", "pmcid",
    "arxiv_id", "openalex_id", "raw_trace", "trace", "prompt", "target", "question",
    "answer", "abstract", "title", "fulltext", "text", "url", "records", "items",
}
FORBIDDEN_AGGREGATE_KEY_PARTS = {
    "leak", "raw", "trace", "prompt", "target", "question", "answer",
    "abstract", "title", "fulltext", "text", "url", "record", "item",
    "payload", "content", "excerpt", "source_text", "stable_id",
}
OBSERVATION_TOP_KEYS = {
    "observation_id", "stage", "candidate_id", "outcome", "metrics", "failure_categories",
    "counts", "redaction_summary", "source_hashes", "contains_validation_items",
}
OBSERVATION_ALLOWED_STAGES = {"probe", "pr_val", "regression", "heldout"}
CANDIDATE_STATES = {"proposed", "under_evaluation", "accepted", "rejected", "deferred", "reverted"}
EVALUATION_STAGES = ("probe", "pr_val", "regression", "heldout")
DEFAULT_METRIC_WEIGHTS = {
    "validation_recall": 1.0,
    "precision": 0.5,
    "discovery_yield": 0.25,
    "source_coverage": 0.2,
    # Objective components are normalized so that larger is always better.
    "cost": 0.1,
    "duration_s": 0.05,
}
DEFAULT_METRIC_CONSTRAINTS = {
    "regression_tolerance": 0.02,
    "max_cost": None,
    "max_duration_s": None,
}
DEFAULT_METRIC_SPECS = {
    "validation_recall": {"direction": "max", "minimum": 0.0, "maximum": 1.0},
    "precision": {"direction": "max", "minimum": 0.0, "maximum": 1.0},
    "discovery_yield": {"direction": "max", "minimum": 0.0, "maximum": 1.0},
    "source_coverage": {"direction": "max", "minimum": 0.0, "maximum": 1.0},
    "cost": {"direction": "min"},
    "duration_s": {"direction": "min"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, p)


def stable_ids(items):
    keys = ("doi", "pmid", "pmcid", "arxiv_id", "openalex_id", "id")
    result = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if value:
                result.add(f"{key}:{str(value).strip().lower()}")
    return result


def sha(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_history(root):
    root = pathlib.Path(root)
    run = load(root / "run.json")
    path = _store_path(root, run.get("stores", {}).get("decision_history"), "decision_history")
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tokens(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    return set(re.findall(r"[a-z0-9_\u4e00-\u9fff]+", text))


def search_history(root, query, limit=10):
    """Return prior decisions ranked by token overlap with a new diagnosis."""
    query_tokens = _tokens(query)
    scored = []
    for item in read_history(root):
        haystack = {**item.get("diagnosis", {}), **item.get("candidate_revision", {}),
                    **item.get("evidence", {}), **item.get("outcome", {})}
        overlap = len(query_tokens & _tokens(haystack))
        if overlap:
            scored.append((overlap, item))
    scored.sort(key=lambda pair: (pair[0], pair[1].get("recorded_at", "")), reverse=True)
    return [{"score": score, "decision": item} for score, item in scored[:max(1, int(limit))]]


def _append_jsonl(path, item):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.lock")
    acquired = False
    for _ in range(500):
        try:
            lock.mkdir()
            acquired = True
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 60:
                    lock.rmdir()
                    continue
            except FileNotFoundError:
                continue
            time.sleep(0.01)
    if not acquired:
        raise TimeoutError(f"could not acquire write lock: {lock}")
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass


def _store_path(root, relative, label):
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError(f"missing {label} store path")
    root = pathlib.Path(root).resolve()
    path = pathlib.Path(relative)
    resolved_path = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not _inside(resolved_path, root):
        raise ValueError(f"{label} store path escapes run root: {relative}")
    return resolved_path


def _safe_id(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value):
        raise ValueError(f"invalid {label}: use only letters, numbers, '.', '_' and '-'")
    return value


def resolved(path):
    return pathlib.Path(path).expanduser().resolve()


def _inside(child, parent):
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_workspace_paths(skill_repo, eval_repo, run_root):
    """Validate the hard filesystem boundary between skill, eval and runs."""
    skill, evaluation, run = map(resolved, (skill_repo, eval_repo, run_root))
    errors = []
    if skill == evaluation or _inside(skill, evaluation) or _inside(evaluation, skill):
        errors.append("skill_repo and eval_repo must be separate; neither may contain the other")
    if _inside(run, skill) or _inside(run, evaluation):
        errors.append("run_root must not be inside skill_repo or eval_repo")
    if run == skill or run == evaluation:
        errors.append("run_root must be a separate directory")
    return errors


def init_workspace(skill_repo, eval_repo, run_root, topic, objective,
                   review_type="narrative", max_iterations=MAX_ITERATIONS):
    """Create a run workspace without copying eval data into the skill repo."""
    errors = validate_workspace_paths(skill_repo, eval_repo, run_root)
    if errors:
        raise ValueError("; ".join(errors))
    skill, evaluation, root = map(resolved, (skill_repo, eval_repo, run_root))
    if not skill.exists():
        raise ValueError(f"skill_repo does not exist: {skill}")
    if not evaluation.exists():
        raise ValueError(f"eval_repo does not exist: {evaluation}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "candidates").mkdir(exist_ok=True)
    (root / "observations").mkdir(exist_ok=True)
    (root / "decision-history").mkdir(exist_ok=True)
    run = init_run(root, topic, objective, review_type, max_iterations, legacy_layout=False)
    run["workspace"] = {
        "skill_repo": str(skill),
        "eval_repo": str(evaluation),
        "run_root": str(root),
        "transport": "redacted_observation_only",
        "eval_readable_by_optimizer": False,
    }
    run["stores"] = {
        "optimization": "candidates",
        "validation": "observations",
        "decision_history": "decision-history/decision-history.jsonl",
    }
    dump(root / "run.json", run)
    (root / "decision-history" / "decision-history.jsonl").write_text("", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "run_id": run["run_id"],
        "created_at": now(),
        "roles": {"skill_repo": str(skill), "eval_repo": str(evaluation), "run_root": str(root)},
        "read_write_policy": {
            "optimizer": {"read": ["observations", "decision-history"], "write": ["candidates", "decision-history"]},
            "evaluator": {"read": ["skill_repo", "eval_repo", "candidates"], "write": ["observations"]},
        },
        "transport": {"format": "observation-v1", "validation_payload": "aggregate-only"},
    }
    dump(root / "workspace-manifest.json", manifest)
    return run


def _scan_forbidden(value, path=""):
    """Reject keys that could carry validation examples or stable IDs."""
    errors = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9_]", "", str(key).lower())
            if normalized in FORBIDDEN_OBSERVATION_KEYS:
                errors.append(f"forbidden observation key at {path}/{key}")
            errors.extend(_scan_forbidden(item, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_scan_forbidden(item, f"{path}/{index}"))
    return errors


def _validate_redacted_observation(observation):
    errors = []
    unknown = set(observation) - OBSERVATION_TOP_KEYS
    errors.extend(f"observation contains non-aggregate field: {key}" for key in sorted(unknown))
    scalar_types = (str, int, float, bool)
    if not isinstance(observation.get("outcome"), dict):
        errors.append("observation.outcome must be an aggregate object")
    for field in ("metrics", "counts", "redaction_summary", "source_hashes"):
        if field in observation and not isinstance(observation[field], dict):
            errors.append(f"observation.{field} must be an object")
    if "failure_categories" in observation:
        cats = observation["failure_categories"]
        if not isinstance(cats, list) or len(cats) > 100 or not all(isinstance(x, str) and len(x) <= 120 for x in cats):
            errors.append("observation.failure_categories must be a short list of labels")

    def check_aggregate(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                normalized_key = re.sub(r"[^a-z0-9_]", "", key_text.lower())
                if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,80}", key_text)
                        or any(part in normalized_key for part in FORBIDDEN_AGGREGATE_KEY_PARTS)):
                    errors.append(f"invalid aggregate key at {path}/{key}")
                check_aggregate(child, f"{path}/{key}")
        elif isinstance(value, list):
            if len(value) > 100:
                errors.append(f"aggregate list too long at {path}")
            for index, child in enumerate(value):
                check_aggregate(child, f"{path}/{index}")
        elif isinstance(value, str):
            if len(value) > 160 or "\n" in value or "\r" in value:
                errors.append(f"aggregate string too long or multiline at {path}")
        elif not isinstance(value, scalar_types):
            errors.append(f"unsupported aggregate value at {path}")
    for field in ("outcome", "metrics", "counts", "redaction_summary", "source_hashes"):
        if field in observation:
            check_aggregate(observation[field], field)
    errors.extend(_scan_forbidden(observation))
    return errors


def write_observation(run_root, observation):
    """Persist only aggregate, redacted evidence from evaluator to optimizer."""
    root = pathlib.Path(run_root)
    errors = _required(observation, ["observation_id", "stage", "candidate_id", "outcome"], "observation")
    try:
        _safe_id(observation.get("observation_id"), "observation_id")
        _safe_id(observation.get("candidate_id"), "candidate_id")
    except ValueError as exc:
        errors.append(str(exc))
    if observation.get("stage") not in OBSERVATION_ALLOWED_STAGES:
        errors.append("observation.stage must be probe, pr_val, regression, or heldout")
    errors.extend(_validate_redacted_observation(observation))
    if observation.get("contains_validation_items") is True:
        errors.append("observation declares contains_validation_items=true")
    if errors:
        raise ValueError("; ".join(errors))
    safe = copy.deepcopy(observation)
    safe["schema_version"] = "1.0"
    safe["recorded_at"] = now()
    safe["validation_payload"] = "aggregate-only"
    out = root / "observations" / f"{safe['observation_id']}.json"
    dump(out, safe)
    return safe


def evaluate_metrics(metrics, baseline=None, weights=None, constraints=None, metric_specs=None):
    """Compute a transparent objective vector without collapsing audit metrics."""
    metrics = metrics or {}
    baseline = baseline or {}
    weights = {**DEFAULT_METRIC_WEIGHTS, **(weights or {})}
    constraints = {**DEFAULT_METRIC_CONSTRAINTS, **(constraints or {})}
    specs = {**DEFAULT_METRIC_SPECS, **(metric_specs or {})}
    objective = 0.0
    components = {}
    warnings = []
    for key, weight in weights.items():
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            spec = specs.get(key, {})
            minimum, maximum = spec.get("minimum"), spec.get("maximum")
            if minimum is not None and maximum is not None and maximum > minimum:
                normalized = (float(value) - minimum) / (maximum - minimum)
                normalized = min(1.0, max(0.0, normalized))
            elif spec.get("direction") == "min":
                ceiling = constraints.get(f"max_{key}")
                if not isinstance(ceiling, (int, float)) or ceiling <= 0:
                    warnings.append(f"{key} omitted from objective until max_{key} is configured")
                    continue
                normalized = 1.0 - min(1.0, max(0.0, float(value) / ceiling))
            else:
                normalized = float(value)
            if spec.get("direction") == "min" and minimum is not None and maximum is not None:
                normalized = 1.0 - normalized
            contribution = normalized * float(weight)
            components[key] = {"value": value, "normalized": normalized, "weight": weight, "contribution": contribution}
            objective += contribution
    regressions = []
    tolerance = float(constraints.get("regression_tolerance", 0.02))
    for key, before in baseline.items():
        after = metrics.get(key)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            if key not in {"cost", "duration_s"} and after < before - tolerance:
                regressions.append({"metric": key, "before": before, "after": after,
                                    "drop": before - after, "tolerance": tolerance})
    max_cost = constraints.get("max_cost")
    max_duration = constraints.get("max_duration_s")
    violations = list(regressions)
    if max_cost is not None and isinstance(metrics.get("cost"), (int, float)) and metrics["cost"] > max_cost:
        violations.append({"metric": "cost", "value": metrics["cost"], "maximum": max_cost})
    if max_duration is not None and isinstance(metrics.get("duration_s"), (int, float)) and metrics["duration_s"] > max_duration:
        violations.append({"metric": "duration_s", "value": metrics["duration_s"], "maximum": max_duration})
    return {"objective": objective, "components": components, "warnings": warnings,
            "regressions": regressions, "constraint_violations": violations, "eligible": not violations}


def write_candidate(run_root, candidate):
    """Persist one atomic candidate revision for the evaluator to test."""
    errors = _required(candidate, ["candidate_id", "change_type", "patch"], "candidate")
    if "parent_candidate" not in candidate:
        errors.append("candidate: missing parent_candidate")
    if not isinstance(candidate.get("patch"), dict):
        errors.append("candidate.patch must be an object")
    try:
        _safe_id(candidate.get("candidate_id"), "candidate_id")
        parent = candidate.get("parent_candidate")
        if parent is not None:
            _safe_id(parent, "parent_candidate")
    except ValueError as exc:
        errors.append(str(exc))
    if candidate.get("change_type") in ("", "rewrite", "bulk_rewrite"):
        errors.append("candidate.change_type must describe one focused change")
    if errors:
        raise ValueError("; ".join(errors))
    safe = copy.deepcopy(candidate)
    safe["schema_version"] = "1.0"
    safe["created_at"] = now()
    safe["state"] = "proposed"
    safe["candidate_hash"] = sha(safe["patch"])
    out = pathlib.Path(run_root) / "candidates" / f"{safe['candidate_id']}.json"
    if out.exists():
        raise ValueError(f"candidate already exists: {safe['candidate_id']}")
    dump(out, safe)
    _append_jsonl(pathlib.Path(run_root) / "decision-history" / "candidate-events.jsonl", {
        "event": "candidate_created", "candidate_id": safe["candidate_id"],
        "state": "proposed", "at": now(), "candidate_hash": safe["candidate_hash"]})
    return safe


def transition_candidate(run_root, candidate_id, state, reason="", metrics=None):
    """Move a candidate through its auditable lifecycle."""
    if state not in CANDIDATE_STATES:
        raise ValueError(f"unknown candidate state: {state}")
    root = pathlib.Path(run_root).resolve()
    candidate_id = _safe_id(candidate_id, "candidate_id")
    path = root / "candidates" / f"{candidate_id}.json"
    if not path.exists():
        raise ValueError(f"candidate not found: {candidate_id}")
    candidate = load(path)
    old = candidate.get("state", "proposed")
    allowed = {
        "proposed": {"under_evaluation", "deferred", "rejected"},
        "under_evaluation": {"accepted", "rejected", "deferred"},
        "accepted": {"reverted"},
        "rejected": {"under_evaluation", "deferred"},
        "deferred": {"under_evaluation", "rejected"},
        "reverted": {"under_evaluation", "deferred"},
    }
    if state != old and state not in allowed.get(old, set()):
        raise ValueError(f"invalid candidate transition: {old} -> {state}")
    if state == "accepted":
        if not isinstance(metrics, dict) or metrics.get("eligible") is not True:
            raise ValueError("accepted candidate requires eligible metrics")
        stages = set()
        for item in (root / "observations").glob("*.json"):
            try:
                observation = load(item)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid observation {item.name}: {exc}") from exc
            if observation.get("candidate_id") != candidate_id:
                continue
            if observation.get("outcome", {}).get("eligible") is True:
                stages.add(observation.get("stage"))
        if not {"pr_val", "regression"}.issubset(stages):
            raise ValueError("accepted candidate requires pr_val and regression observations")
    candidate["state"] = state
    candidate["state_updated_at"] = now()
    candidate["state_reason"] = reason
    if metrics is not None:
        candidate["latest_metrics"] = metrics
    dump(path, candidate)
    event = {"event": "candidate_transition", "candidate_id": candidate_id,
             "from": old, "to": state, "reason": reason, "at": now()}
    if metrics is not None:
        event["metrics"] = metrics
    _append_jsonl(root / "decision-history" / "candidate-events.jsonl", event)
    run = load(root / "run.json")
    if state == "accepted":
        run["current_candidate"] = candidate_id
    elif state == "reverted" and run.get("current_candidate") == candidate_id:
        run["current_candidate"] = candidate.get("parent_candidate")
    run["updated_at"] = now()
    dump(root / "run.json", run)
    return candidate


def rollback_candidate(run_root, candidate_id, reason="manual rollback"):
    """Rollback the active candidate while retaining all artifacts and history."""
    root = pathlib.Path(run_root)
    candidate = transition_candidate(root, candidate_id, "reverted", reason)
    return {"rolled_back": candidate_id, "next_candidate": load(root / "run.json").get("current_candidate")}


def validate_workspace(root):
    """Validate the immutable path manifest and the run contract together."""
    root = pathlib.Path(root)
    manifest_path = root / "workspace-manifest.json"
    if not manifest_path.exists():
        return ["missing workspace-manifest.json"], []
    manifest = load(manifest_path)
    roles = manifest.get("roles", {})
    errors = _required(roles, ["skill_repo", "eval_repo", "run_root"], "workspace.roles")
    if not errors:
        errors.extend(validate_workspace_paths(roles["skill_repo"], roles["eval_repo"], roles["run_root"]))
    if resolved(roles.get("run_root", "")) != root.resolve():
        errors.append("workspace manifest run_root does not match requested run root")
    warnings = []
    if manifest.get("transport", {}).get("format") != "observation-v1":
        errors.append("unsupported observation transport format")
    return errors, warnings


def init_run(output, topic, objective, review_type="narrative", max_iterations=MAX_ITERATIONS,
             legacy_layout=True):
    root = pathlib.Path(output)
    root.mkdir(parents=True, exist_ok=True)
    if legacy_layout:
        (root / "optimization_store").mkdir(exist_ok=True)
        (root / "validation_store").mkdir(exist_ok=True)
    run = {
        "schema_version": "1.0",
        "run_id": f"opt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": now(),
        "topic": topic,
        "objective": objective,
        "review_type": review_type,
        "max_iterations": max_iterations,
        "stores": {
            "optimization": "optimization_store",
            "validation": "validation_store",
            "decision_history": "optimization_store/decision-history.jsonl",
        },
        "best_candidate": None,
        "current_candidate": None,
        "evaluation_stages": list(EVALUATION_STAGES),
        "metric_weights": dict(DEFAULT_METRIC_WEIGHTS),
        "metric_constraints": dict(DEFAULT_METRIC_CONSTRAINTS),
        "metric_specs": dict(DEFAULT_METRIC_SPECS),
        "status": "initialized",
        "stop_reason": None,
    }
    dump(root / "run.json", run)
    if legacy_layout:
        (root / "optimization_store" / "decision-history.jsonl").write_text("", encoding="utf-8")
    return run


def _required(value, fields, label):
    errors = []
    for field in fields:
        if not value.get(field):
            errors.append(f"{label}: missing {field}")
    return errors


def validate_run(root):
    root = pathlib.Path(root)
    errors, warnings = [], []
    workspace_mode = (root / "workspace-manifest.json").exists()
    if workspace_mode:
        workspace_errors, workspace_warnings = validate_workspace(root)
        errors.extend(workspace_errors)
        warnings.extend(workspace_warnings)
    run_path = root / "run.json"
    if not run_path.exists():
        return [f"missing {run_path}"], []
    run = load(run_path)
    errors += _required(run, ["run_id", "topic", "objective", "stores"], "run")
    try:
        opt = _store_path(root, run.get("stores", {}).get("optimization", "optimization_store"), "optimization")
        val = _store_path(root, run.get("stores", {}).get("validation", "validation_store"), "validation")
        history = _store_path(root, run.get("stores", {}).get("decision_history", "optimization_store/decision-history.jsonl"), "decision_history")
    except ValueError as exc:
        errors.append(str(exc))
        return errors, warnings
    if opt.resolve() == val.resolve():
        errors.append("optimization and validation stores must be physically separate")
    if not opt.exists():
        errors.append(f"missing optimization store: {opt}")
    if not val.exists():
        warnings.append("validation store is empty; final validation is not assessable")

    if not workspace_mode:
        dev_path, val_path = opt / "dev-set.json", val / "validation-set.json"
        dev = load(dev_path) if dev_path.exists() else []
        heldout = load(val_path) if val_path.exists() else []
        overlap = stable_ids(dev) & stable_ids(heldout)
        if overlap:
            errors.append(f"dev/validation overlap: {sorted(overlap)[:5]}")
        if dev_path.exists() and len(dev) < 3:
            warnings.append("development set has fewer than 3 stable-ID items")
    else:
        # Held-out records remain in Eval Repo. The optimizer must not read them.
        if not (root / "candidates").exists():
            errors.append("workspace missing candidates directory")
        if not (root / "observations").exists():
            errors.append("workspace missing observations directory")

    records = []
    if history.exists():
        for line_no, line in enumerate(history.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"decision history line {line_no}: invalid JSON ({exc})")
                continue
            errors += _required(item, ["iteration_id", "diagnosis", "candidate_revision", "evidence", "outcome"], f"history {line_no}")
            if item.get("evidence", {}).get("contains_validation_items") is True:
                errors.append(f"history {line_no}: validation items leaked into optimization evidence")
            records.append(item)
    ids = [r.get("iteration_id") for r in records]
    if len(ids) != len(set(ids)):
        errors.append("decision history contains duplicate iteration_id values")
    if len(records) > int(run.get("max_iterations", MAX_ITERATIONS)):
        errors.append("decision history exceeds max_iterations")
    return errors, warnings


def record_iteration(root, iteration):
    root = pathlib.Path(root)
    run = load(root / "run.json")
    errors = _required(iteration, ["iteration_id", "diagnosis", "candidate_revision", "evidence", "outcome"], "iteration")
    try:
        _safe_id(iteration.get("iteration_id"), "iteration_id")
    except ValueError as exc:
        errors.append(str(exc))
    evidence = iteration.get("evidence", {})
    if evidence.get("contains_validation_items") is True:
        errors.append("validation evidence must be redacted before recording")
    if not isinstance(iteration.get("candidate_revision"), dict):
        errors.append("candidate_revision must be an object describing one atomic change")
    if errors:
        raise ValueError("; ".join(errors))

    history = _store_path(root, run["stores"]["decision_history"], "decision_history")
    existing = [json.loads(x) for x in history.read_text(encoding="utf-8").splitlines() if x.strip()] if history.exists() else []
    if any(x.get("iteration_id") == iteration["iteration_id"] for x in existing):
        raise ValueError(f"duplicate iteration_id: {iteration['iteration_id']}")
    item = copy.deepcopy(iteration)
    item["recorded_at"] = now()
    item["evidence"] = dict(item["evidence"], validation_items_redacted=True)
    history.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl(history, item)

    score = item.get("outcome", {}).get("validation_score")
    if isinstance(score, (int, float)):
        best = run.get("best_candidate")
        if best is None or score > best.get("validation_score", -1):
            run["best_candidate"] = {"iteration_id": item["iteration_id"], "validation_score": score,
                                      "candidate_revision_hash": sha(item["candidate_revision"])}
    run["status"] = "iterating"
    run["updated_at"] = now()
    dump(root / "run.json", run)
    return item


def status(root):
    root = pathlib.Path(root)
    run = load(root / "run.json")
    history = _store_path(root, run["stores"]["decision_history"], "decision_history")
    items = [json.loads(x) for x in history.read_text(encoding="utf-8").splitlines() if x.strip()] if history.exists() else []
    validation_scores = [x.get("outcome", {}).get("validation_score") for x in items]
    validation_scores = [x for x in validation_scores if isinstance(x, (int, float))]
    stop = None
    if len(items) >= 2 and len(validation_scores) >= 2:
        stop = (validation_scores[-1] - validation_scores[-2]) < PLATEAU_DELTA
    if len(items) >= int(run.get("max_iterations", MAX_ITERATIONS)):
        stop = True
    return {"run_id": run["run_id"], "iterations": len(items), "validation_scores": validation_scores,
            "best_candidate": run.get("best_candidate"), "current_candidate": run.get("current_candidate"),
            "evaluation_stages": run.get("evaluation_stages", list(EVALUATION_STAGES)),
            "plateau_or_limit": stop,
            "status": run.get("status"), "stop_reason": run.get("stop_reason")}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("--output", required=True); p.add_argument("--topic", required=True); p.add_argument("--objective", required=True); p.add_argument("--review-type", default="narrative"); p.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    p = sub.add_parser("init-workspace"); p.add_argument("--skill-repo", required=True); p.add_argument("--eval-repo", required=True); p.add_argument("--run-root", required=True); p.add_argument("--topic", required=True); p.add_argument("--objective", required=True); p.add_argument("--review-type", default="narrative"); p.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    p = sub.add_parser("record"); p.add_argument("--run", required=True); p.add_argument("--iteration", required=True)
    p = sub.add_parser("candidate"); p.add_argument("--run", required=True); p.add_argument("--candidate", required=True)
    p = sub.add_parser("candidate-status"); p.add_argument("--run", required=True); p.add_argument("--candidate-id", required=True); p.add_argument("--state", required=True); p.add_argument("--reason", default=""); p.add_argument("--metrics")
    p = sub.add_parser("rollback"); p.add_argument("--run", required=True); p.add_argument("--candidate-id", required=True); p.add_argument("--reason", default="manual rollback")
    p = sub.add_parser("observe"); p.add_argument("--run", required=True); p.add_argument("--observation", required=True)
    p = sub.add_parser("history-search"); p.add_argument("--run", required=True); p.add_argument("--query", required=True); p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("metric-evaluate"); p.add_argument("--metrics", required=True); p.add_argument("--baseline"); p.add_argument("--weights"); p.add_argument("--constraints"); p.add_argument("--metric-specs")
    p = sub.add_parser("validate"); p.add_argument("--run", required=True); p.add_argument("--strict", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--run", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            print(json.dumps(init_run(args.output, args.topic, args.objective, args.review_type, args.max_iterations), ensure_ascii=False, indent=2))
        elif args.command == "init-workspace":
            print(json.dumps(init_workspace(args.skill_repo, args.eval_repo, args.run_root, args.topic, args.objective, args.review_type, args.max_iterations), ensure_ascii=False, indent=2))
        elif args.command == "record":
            print(json.dumps(record_iteration(args.run, load(args.iteration)), ensure_ascii=False, indent=2))
        elif args.command == "candidate":
            print(json.dumps(write_candidate(args.run, load(args.candidate)), ensure_ascii=False, indent=2))
        elif args.command == "candidate-status":
            metrics = load(args.metrics) if args.metrics else None
            print(json.dumps(transition_candidate(args.run, args.candidate_id, args.state, args.reason, metrics), ensure_ascii=False, indent=2))
        elif args.command == "rollback":
            print(json.dumps(rollback_candidate(args.run, args.candidate_id, args.reason), ensure_ascii=False, indent=2))
        elif args.command == "observe":
            print(json.dumps(write_observation(args.run, load(args.observation)), ensure_ascii=False, indent=2))
        elif args.command == "history-search":
            print(json.dumps(search_history(args.run, args.query, args.limit), ensure_ascii=False, indent=2))
        elif args.command == "metric-evaluate":
            print(json.dumps(evaluate_metrics(load(args.metrics), load(args.baseline) if args.baseline else None,
                                              load(args.weights) if args.weights else None,
                                              load(args.constraints) if args.constraints else None,
                                              load(args.metric_specs) if args.metric_specs else None), ensure_ascii=False, indent=2))
        elif args.command == "validate":
            errors, warnings = validate_run(args.run)
            print(json.dumps({"errors": errors, "warnings": warnings, "valid": not errors and not (args.strict and warnings)}, ensure_ascii=False, indent=2))
            sys.exit(1 if errors or (args.strict and warnings) else 0)
        else:
            print(json.dumps(status(args.run), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main()
