"""Pure A-dimension evaluators with explicit input contracts.

The evaluator receives the stable-ID extractor as an argument so it can be
tested and reused without importing report generation or rendering code.
"""
from __future__ import annotations

import itertools
import json
from collections.abc import Callable


StableIds = Callable[[dict], set[str]]


def evaluate_gold_recall(gold, hits, stable_ids: StableIds):
    """Calculate A2 item-level recall from stable identifiers only."""
    if gold is None or hits is None:
        return {"status": "not_assessable", "recall": None,
                "note": "Supply both gold set and executed query-hit snapshot."}
    hit_ids = set().union(*(stable_ids(row) for row in hits if isinstance(row, dict)))
    gold_items = [row for row in gold if isinstance(row, dict) and stable_ids(row)]
    if not gold_items:
        return {"status": "not_assessable", "recall": None,
                "note": "Gold set lacks stable identifiers."}
    matched = sum(bool(stable_ids(row) & hit_ids) for row in gold_items)
    return {
        "status": "measured", "total": len(gold_items), "matched": matched,
        "recall": round(matched / len(gold_items), 3),
        "missing_ids": sorted(set().union(*(stable_ids(row) for row in gold_items
                                               if not (stable_ids(row) & hit_ids)))),
        "note": "Item-level match (any shared stable ID => matched). An executed zero-result query is measured recall 0.",
    }


def evaluate_multisource_lower_bound(sources, stable_ids: StableIds):
    """Calculate A3's bounded multi-source candidate count, never recall."""
    if not sources or len(sources) < 2:
        return {"status": "not_assessable",
                "note": "Supply deduplicable snapshots from at least two sources."}
    incomplete = sorted(name for name, meta in sources.items()
                        if any(status != "complete" for status in meta.get("statuses", []))
                        or not all(meta.get("completion_flags", [])))
    filters = {json.dumps(meta.get("scope_filters"), ensure_ascii=False, sort_keys=True)
               for meta in sources.values()}
    dedup_rules = {str(meta.get("dedup_rule") or "") for meta in sources.values()}
    boundaries_valid = len(filters) == 1 and next(iter(filters), "null") not in ("null", "{}")
    dedup_valid = len(dedup_rules) == 1 and bool(next(iter(dedup_rules), ""))
    source_ids = {name: set().union(*(stable_ids(row) for row in meta.get("items", [])
                                      if isinstance(row, dict))) for name, meta in sources.items()}
    union = set().union(*source_ids.values())
    if not union:
        return {"status": "not_assessable", "note": "Candidate snapshots contain no stable identifiers."}
    overlaps = {"|".join(pair): len(source_ids[pair[0]] & source_ids[pair[1]])
                for pair in itertools.combinations(sorted(source_ids), 2)}
    result = {
        "status": "estimated_lower_bound" if not incomplete and boundaries_valid and dedup_valid else "partial_snapshot",
        "deduplicated_candidate_lower_bound": len(union),
        "source_unique_identifier_counts": {key: len(value) for key, value in source_ids.items()},
        "pairwise_overlaps": overlaps, "incomplete_sources": incomplete,
        "boundaries_valid": boundaries_valid, "dedup_rule_valid": dedup_valid,
        "note": "Multi-source deduplicated lower bound; not Recall or capture-recapture.",
    }
    if incomplete or not boundaries_valid or not dedup_valid:
        result["note"] = "Source snapshots are incomplete or lack consistent scope filters/dedup rule; provisional count must not support A3 conclusions."
    return result
