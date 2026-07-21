#!/usr/bin/env python3
"""Search strategy iteration manager — validates and produces comparison tables.

This script does NOT execute searches itself. It consumes iteration records
produced by AI-assisted search rounds and validates protocol compliance:
  1. Atomic changes — only one change type per iteration
  2. Dev/validation set separation — no cross-contamination
  3. Comparison table — all iterations in a single diffable format
  4. Stop conditions — A2 stop ≠ B stop

Usage:
    python search_iterator.py validate --iterations iterations.json
    python search_iterator.py table --iterations iterations.json --output comparison.md

The iterations.json schema:
{
  "search_decomposition": { ... },   // Engineering PICO decomposition
  "dev_set": [{ "title": ..., "doi": ... }],  // At least 3 entries
  "validation_set": [{ "title": ..., "doi": ... }],  // Independent of dev_set
  "dev_validation_overlap_check": true/false,
  "iterations": [
    {
      "iteration_id": "v1",
      "parent_iteration": null,
      "change_type": "initial",
      "change_description": "...",
      "change_source": "...",
      "queries": { "pathway_id": { "query_label": "query_string" } },
      "execution_date": "2026-07-21",
      "results": { "total_hits": ..., "deduplicated_hits": ..., "dev_recall": ...,
                   "validation_recall": ..., "sampled_relevance_rate": ...,
                   "discovery_candidates": ... },
      "failures": [],
      "decision": "continue"
    }
  ]
}
"""
import argparse, json, sys, pathlib
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

ALLOWED_CHANGE_TYPES = {
    "initial",           # First round — no prior query exists
    "add_synonym",       # Add a synonym group
    "add_abbreviation",  # Add an abbreviation or historical term
    "modify_field",      # Change a field restriction
    "add_source",        # Add a new database source
    "add_exclusion",     # Add a verified exclusion condition
    "remove_low_yield",  # Remove a low-yield keyword
}

MIN_DEV_SET_SIZE = 3
MAX_ITERATIONS = 8
A2_STOP_DELTA = 0.03  # Two consecutive rounds with validation_recall increase < this → stop


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def validate(data, strict=False):
    """Validate iterations against the search strategy protocol. Returns (errors, warnings)."""
    errors, warnings = [], []

    # ── Dev set ──
    dev = data.get("dev_set", [])
    if len(dev) < MIN_DEV_SET_SIZE:
        errors.append(f"Dev set needs at least {MIN_DEV_SET_SIZE} entries, got {len(dev)}")

    # ── Validation set ──
    val = data.get("validation_set", [])
    if not val:
        warnings.append("No independent validation set — A2 will use dev_set as proxy "
                        "(evidence status: estimated)")
    else:
        # Check overlap
        dev_dois = {e.get("doi", "").lower() for e in dev if e.get("doi")}
        val_dois = {e.get("doi", "").lower() for e in val if e.get("doi")}
        overlap = dev_dois & val_dois
        if overlap:
            errors.append(f"Dev/validation sets overlap on {len(overlap)} DOI(s): {sorted(overlap)[:5]}")
        if not data.get("dev_validation_overlap_check"):
            warnings.append("dev_validation_overlap_check not explicitly declared")

    # ── Iterations ──
    iterations = data.get("iterations", [])
    if not iterations:
        errors.append("At least one iteration required")
        return errors, warnings

    for i, it in enumerate(iterations):
        it_id = it.get("iteration_id", f"#{i}")

        # Change type
        ct = it.get("change_type", "")
        if ct not in ALLOWED_CHANGE_TYPES:
            errors.append(f"{it_id}: unknown change_type '{ct}' — must be one of {ALLOWED_CHANGE_TYPES}")

        # Atomicity: only one change per iteration (except initial and after multi-step planning)
        if ct not in ("initial",):
            parent = it.get("parent_iteration")
            if not parent and i > 0:
                warnings.append(f"{it_id}: non-initial iteration has no parent_iteration")

        # Required fields
        for field in ("change_description", "change_source", "queries", "execution_date", "results"):
            if not it.get(field):
                errors.append(f"{it_id}: missing required field '{field}'")

        # Results fields
        results = it.get("results", {})
        for field in ("dev_recall",):
            if field not in results:
                warnings.append(f"{it_id}: missing recommended field 'results.{field}'")

    # ── Stop condition checks ──
    if len(iterations) >= 2:
        last_two = [it.get("results", {}).get("validation_recall") for it in iterations[-2:]]
        has_val = all(v is not None for v in last_two)
        if has_val:
            a2_stopped = all(last_two[i] - last_two[i-1] < A2_STOP_DELTA
                             for i in range(1, len(last_two)))
        else:
            a2_stopped = None

        decisions = [it.get("decision") for it in iterations]
        if decisions[-1] == "continue" and len(iterations) >= MAX_ITERATIONS:
            warnings.append(f"Reached {MAX_ITERATIONS} iterations without stop decision — "
                           "review whether search can be further improved")

    # ── Pathway types ──
    pathway_types_seen = set()
    for it in iterations:
        for pw_id in it.get("queries", {}):
            ptype = pw_id.split("_")[0] if "_" in pw_id else pw_id
            pathway_types_seen.add(ptype)
    INDEPENDENT_TYPES = {"db", "backward", "forward", "related", "standards"}
    missing_pathways = INDEPENDENT_TYPES - pathway_types_seen
    if missing_pathways:
        warnings.append(f"Independent pathway types not yet explored: {missing_pathways}")

    return errors, warnings


def generate_comparison_table(data):
    """Generate a markdown comparison table of all iterations."""
    iterations = data.get("iterations", [])
    lines = ["## 检索迭代比较表\n"]
    lines.append("| 轮次 | 改动类型 | 改动说明 | 来源 | 总命中 | 去重命中 | dev_recall | val_recall | 发现候选 | 决策 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    for it in iterations:
        iid = it.get("iteration_id", "?")
        ct = it.get("change_type", "?")
        desc = it.get("change_description", "—")[:60]
        src = it.get("change_source", "—")[:40]
        res = it.get("results", {})
        th = str(res.get("total_hits", "—"))
        dh = str(res.get("deduplicated_hits", "—"))
        dr = f"{res['dev_recall']:.3f}" if res.get("dev_recall") is not None else "—"
        vr = f"{res['validation_recall']:.3f}" if res.get("validation_recall") is not None else "—"
        dc = str(res.get("discovery_candidates", "—"))
        decision = it.get("decision", "—")
        lines.append(f"| {iid} | {ct} | {desc} | {src} | {th} | {dh} | {dr} | {vr} | {dc} | {decision} |")

    # Summary row
    lines.append("")
    if iterations:
        best_val = max((it.get("results", {}).get("validation_recall") or 0) for it in iterations)
        best_dev = max((it.get("results", {}).get("dev_recall") or 0) for it in iterations)
        total_disc = sum(it.get("results", {}).get("discovery_candidates") or 0 for it in iterations)
        last = iterations[-1]
        lines.append(f"**共 {len(iterations)} 轮** | | | | | | "
                     f"最佳 dev_recall={best_dev:.3f} | "
                     f"最佳 val_recall={best_val:.3f} | "
                     f"累计发现候选={total_disc} | "
                     f"最终: {last.get('decision','—')} |")

    return "\n".join(lines)


def generate_pathway_matrix(data):
    """Generate a pathway × iteration matrix showing marginal contribution per pathway."""
    iterations = data.get("iterations", [])
    # Collect all pathway IDs
    all_pathways = []
    seen = set()
    for it in iterations:
        for pw_id in it.get("queries", {}):
            if pw_id not in seen:
                all_pathways.append(pw_id)
                seen.add(pw_id)

    if not all_pathways:
        return ""

    lines = ["## 路径贡献矩阵\n"]
    header = "| 轮次 | " + " | ".join(pw for pw in all_pathways) + " |"
    lines.append(header)
    lines.append("| --- |" + "|".join(" --- " for _ in all_pathways) + "|")

    for it in iterations:
        iid = it.get("iteration_id", "?")
        cells = []
        for pw in all_pathways:
            q = it.get("queries", {}).get(pw)
            if q:
                cells.append("✓")
            else:
                cells.append("—")
        lines.append(f"| {iid} | " + " | ".join(cells) + " |")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = p.add_subparsers(dest="command")

    vp = sp.add_parser("validate", help="Validate iterations.json against protocol")
    vp.add_argument("--iterations", required=True, help="iterations.json file")
    vp.add_argument("--strict", action="store_true", help="Treat warnings as errors")

    tp = sp.add_parser("table", help="Generate comparison table from iterations.json")
    tp.add_argument("--iterations", required=True, help="iterations.json file")
    tp.add_argument("--output", help="Output markdown file (stdout if omitted)")

    a = p.parse_args()

    if a.command == "validate":
        data = load_json(a.iterations)
        errors, warnings = validate(data, strict=a.strict)
        if errors:
            print(f"❌ {len(errors)} error(s):")
            for e in errors:
                print(f"  - {e}")
        if warnings:
            print(f"⚠ {len(warnings)} warning(s):")
            for w in warnings:
                print(f"  - {w}")
        if errors:
            sys.exit(1)
        if not errors and not warnings:
            print("✅ All checks passed.")
        elif not errors:
            print("⚠ Protocol compliant with warnings (see above).")

    elif a.command == "table":
        data = load_json(a.iterations)
        table = generate_comparison_table(data)
        matrix = generate_pathway_matrix(data)
        output = table + "\n\n" + matrix if matrix else table
        if a.output:
            pathlib.Path(a.output).write_text(output + "\n", encoding="utf-8")
            print(f"Comparison table written to {a.output}")
        else:
            print(output)


if __name__ == "__main__":
    main()
