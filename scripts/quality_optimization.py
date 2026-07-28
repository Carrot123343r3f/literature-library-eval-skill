#!/usr/bin/env python3
"""Counterexamples, active screening queues, and drift canaries.

These utilities complement optimization.py without changing the A-F score
definitions. They produce auditable, resumable artifacts for the optimizer and
human reviewer.
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

try:
    from scripts.optimization import _append_jsonl, _safe_id, load as load_run
except ImportError:  # pragma: no cover - supports direct script execution
    from optimization import _append_jsonl, _safe_id, load as load_run

COUNTEREXAMPLE_TYPES = {"false_positive", "false_negative", "boundary", "source_conflict", "tool_failure"}


def now():
    return datetime.now(timezone.utc).isoformat()


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_counterexample(run_root, item):
    if not isinstance(item, dict):
        raise ValueError("counterexample must be an object")
    required = ("counterexample_id", "type", "diagnosis", "observed", "expected")
    missing = [key for key in required if key not in item or item.get(key) is None or item.get(key) == ""]
    if missing:
        raise ValueError("counterexample missing: " + ", ".join(missing))
    if item["type"] not in COUNTEREXAMPLE_TYPES:
        raise ValueError(f"unknown counterexample type: {item['type']}")
    _safe_id(item["counterexample_id"], "counterexample_id")
    root = pathlib.Path(run_root)
    out = root / "candidates" / "counterexamples.jsonl"
    existing = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()] if out.exists() else []
    if any(row.get("counterexample_id") == item["counterexample_id"] for row in existing):
        raise ValueError(f"duplicate counterexample_id: {item['counterexample_id']}")
    record = dict(item)
    record["schema_version"] = "1.0"
    record["recorded_at"] = now()
    record["status"] = "unresolved"
    out.parent.mkdir(parents=True, exist_ok=True)
    _append_jsonl(out, record)
    run_path = root / "run.json"
    if run_path.exists():
        run = load_run(run_path)
        history = run.get("stores", {}).get("decision_history")
        if history:
            history_path = root / history
            _append_jsonl(history_path, {
                "iteration_id": f"counterexample-{item['counterexample_id']}",
                "recorded_at": record["recorded_at"],
                "diagnosis": {"type": item["type"], "summary": str(item["diagnosis"])[:160]},
                "candidate_revision": {"change_type": "counterexample_capture",
                                        "counterexample_id": item["counterexample_id"]},
                "evidence": {"stage": "probe", "type": item["type"],
                             "contains_validation_items": False},
                "outcome": {"decision": "defer", "counterexample_status": "unresolved"},
            })
    return record


def _number(value, default=0.0):
    return float(value) if isinstance(value, (int, float)) else default


def build_screen_queue(candidates, budget=50):
    """Rank candidates for human review using uncertainty and decision impact."""
    if not isinstance(candidates, list):
        raise ValueError("candidates must be an array")
    if not isinstance(budget, int) or budget < 1:
        raise ValueError("budget must be a positive integer")
    queue = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError(f"candidate #{index} must be an object")
        uncertainty = _number(item.get("uncertainty"), 0.5)
        impact = _number(item.get("impact"), 0.5)
        source_conflict = _number(item.get("source_conflict"), 0.0)
        missingness = _number(item.get("missingness"), 0.0)
        novelty = _number(item.get("novelty"), 0.0)
        priority = (0.30 * uncertainty + 0.25 * impact + 0.20 * source_conflict +
                    0.15 * missingness + 0.10 * novelty)
        row = dict(item)
        row["queue_rank"] = None
        row["review_priority"] = round(min(1.0, max(0.0, priority)), 6)
        row["priority_components"] = {
            "uncertainty": uncertainty, "impact": impact,
            "source_conflict": source_conflict, "missingness": missingness, "novelty": novelty,
        }
        row["input_order"] = index
        queue.append(row)
    queue.sort(key=lambda row: (-row["review_priority"], row["input_order"]))
    for rank, row in enumerate(queue[:max(0, int(budget))], 1):
        row["queue_rank"] = rank
    return [row for row in queue if row["queue_rank"] is not None]


def compare_canary(baseline, current, tolerances=None):
    """Compare aggregate canary metrics and flag environment drift."""
    if not isinstance(baseline, dict) or not isinstance(current, dict):
        raise ValueError("baseline and current canary inputs must be objects")
    tolerances = tolerances or {}
    baseline = baseline or {}
    current = current or {}
    baseline_metrics = baseline.get("metrics", baseline)
    current_metrics = current.get("metrics", current)
    baseline_metadata = baseline.get("metadata", {}) if isinstance(baseline, dict) else {}
    current_metadata = current.get("metadata", {}) if isinstance(current, dict) else {}
    metric_names = sorted(set(baseline_metrics or {}) | set(current_metrics or {}))
    changes, alerts = [], []
    for name in metric_names:
        before, after = baseline_metrics.get(name), current_metrics.get(name)
        if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
            changes.append({"metric": name, "status": "not_comparable"})
            continue
        delta = after - before
        relative = delta / abs(before) if before else (0.0 if delta == 0 else math.inf)
        tolerance = tolerances.get(name, 0.05)
        changed = abs(delta) > tolerance if tolerance >= 1 else abs(relative) > tolerance
        row = {"metric": name, "before": before, "after": after, "delta": delta,
               "relative_delta": relative, "tolerance": tolerance,
               "status": "drift" if changed else "stable"}
        changes.append(row)
        if changed:
            alerts.append(row)
    for name in sorted(set(baseline_metadata) | set(current_metadata)):
        before, after = baseline_metadata.get(name), current_metadata.get(name)
        if before != after:
            row = {"metadata": name, "before": before, "after": after,
                   "status": "metadata_drift"}
            changes.append(row)
            alerts.append(row)
    return {"schema_version": "1.0", "checked_at": now(), "status": "drift" if alerts else "stable",
            "changes": changes, "alerts": alerts,
            "note": "Drift is a maintenance signal, not proof that the skill or source is defective."}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("counterexample"); p.add_argument("--run", required=True); p.add_argument("--item", required=True)
    p = sub.add_parser("screen-queue"); p.add_argument("--candidates", required=True); p.add_argument("--out", required=True); p.add_argument("--budget", type=int, default=50)
    p = sub.add_parser("canary"); p.add_argument("--baseline", required=True); p.add_argument("--current", required=True); p.add_argument("--tolerances"); p.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "counterexample":
            print(json.dumps(append_counterexample(args.run, load(args.item)), ensure_ascii=False, indent=2))
        elif args.command == "screen-queue":
            queue = build_screen_queue(load(args.candidates), args.budget); dump(args.out, {"schema_version": "1.0", "created_at": now(), "budget": args.budget, "queue": queue}); print(f"screen queue written: {args.out}")
        else:
            result = compare_canary(load(args.baseline), load(args.current), load(args.tolerances) if args.tolerances else None); dump(args.out, result); print(json.dumps(result, ensure_ascii=False, indent=2)); sys.exit(1 if result["status"] == "drift" else 0)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
