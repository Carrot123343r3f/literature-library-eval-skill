#!/usr/bin/env python3
"""Attribute metric changes to isolated optimization candidates."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def attribute(baseline, candidates, metric_specs=None, tolerance=0.02):
    specs = metric_specs or {}
    by_id = {item.get("candidate_id"): item for item in candidates or [] if item.get("candidate_id")}
    reports = []
    for item in candidates or []:
        candidate_id = item.get("candidate_id")
        parent_id = item.get("parent_candidate")
        parent = by_id.get(parent_id) if parent_id else None
        before = (parent or {}).get("metrics", baseline or {})
        after = item.get("metrics", {})
        deltas = {}
        regressions = []
        for metric in sorted(set(before) | set(after)):
            old, new = before.get(metric), after.get(metric)
            if not isinstance(old, (int, float)) or not isinstance(new, (int, float)):
                deltas[metric] = {"status": "not_comparable"}
                continue
            delta = round(new - old, 12)
            direction = specs.get(metric, {}).get("direction", "max")
            effective_delta = delta if direction == "max" else -delta
            row = {"before": old, "after": new, "delta": delta, "effective_delta": effective_delta}
            deltas[metric] = row
            if effective_delta < -abs(tolerance):
                regressions.append({"metric": metric, **row})
        reports.append({"candidate_id": candidate_id, "parent_candidate": parent_id,
                        "baseline_source": parent_id or "baseline", "deltas": deltas,
                        "regressions": regressions, "eligible": not regressions})
    pareto = []
    for report in reports:
        dominated = False
        for other in reports:
            if other is report or not other["eligible"]:
                continue
            improvements = []
            for metric, row in report["deltas"].items():
                other_row = other["deltas"].get(metric, {})
                if "effective_delta" in row and "effective_delta" in other_row:
                    improvements.append(other_row["effective_delta"] >= row["effective_delta"])
            if improvements and all(improvements) and any(
                    other["deltas"].get(metric, {}).get("effective_delta", 0) > row.get("effective_delta", 0)
                    for metric, row in report["deltas"].items() if "effective_delta" in row):
                dominated = True; break
        if not dominated and report["eligible"]:
            pareto.append(report["candidate_id"])
    return {"schema_version": "1.0", "baseline": baseline or {}, "candidates": reports,
            "pareto_front": pareto, "tolerance": tolerance}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True); parser.add_argument("--candidates", required=True); parser.add_argument("--out", required=True); parser.add_argument("--metric-specs"); parser.add_argument("--tolerance", type=float, default=0.02)
    args = parser.parse_args()
    try:
        result = attribute(load(args.baseline), load(args.candidates), load(args.metric_specs) if args.metric_specs else None, args.tolerance)
        dump(args.out, result); print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
