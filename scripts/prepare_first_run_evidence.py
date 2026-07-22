#!/usr/bin/env python3
"""Prepare reproducible, AI-led provisional evidence sets for a first audit.

The script accepts candidate anchors produced by OpenAlex discovery, applies a
transparent lexical relevance screen, and deterministically splits accepted
items into development and held-out sets. Every output is labelled
``automated-screening``: it is useful for a first-run A1/A2 estimate but is
not an independently verified benchmark or validation set.
"""
import argparse
import hashlib
import json
import pathlib
import re

try:
    from stable_ids import stable_ids
except ImportError:  # pragma: no cover
    from scripts.stable_ids import stable_ids


def tokens(value):
    return {x.casefold() for x in re.findall(r"[\w-]{3,}", str(value or ""))}


def relevance_score(item, keywords):
    title_tokens = tokens(item.get("title"))
    keyword_tokens = set().union(*(tokens(k) for k in keywords)) if keywords else set()
    # When the agent supplied only a research question, retain candidates but
    # expose the weaker screen through the automated evidence tier.
    return len(title_tokens & keyword_tokens) if keyword_tokens else 1


def split_items(items, validation_share=0.30, min_validation=15, min_dev=15):
    """Make a stable holdout with a usable first-run denominator.

    Seven held-out records make a recall estimate far too volatile to be useful
    even as a provisional diagnostic.  We therefore keep at least
    ``min_validation`` records whenever the accepted candidate pool permits it,
    while also preserving ``min_dev`` records for query refinement.  When the
    pool cannot support both minima, split it approximately in half rather than
    leaving the optimizer with a token development set.  The hash order makes the
    split reproducible and prevents a rerun from silently moving records between
    dev and validation.
    """
    ranked = sorted(
        items,
        key=lambda item: hashlib.sha256(
            ("|".join(sorted(stable_ids(item))) or item.get("title", "")).encode("utf-8")
        ).hexdigest(),
    )
    if len(ranked) < 2:
        return ranked, []
    if len(ranked) < min_validation + min_dev:
        validation_count = len(ranked) // 2
    else:
        requested = max(min_validation, int(round(len(ranked) * validation_share)))
        validation_count = min(requested, len(ranked) - min_dev)
    validation = ranked[:validation_count]
    dev = ranked[validation_count:]
    return dev, validation


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--candidates", required=True, help="JSON from build_anchor_candidates.py")
    parser.add_argument("--context", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-overlap", type=int, default=1)
    parser.add_argument("--validation-share", type=float, default=0.30)
    parser.add_argument("--min-validation", type=int, default=15,
                        help="minimum held-out A2 records when the candidate pool permits it")
    parser.add_argument("--min-dev", type=int, default=15,
                        help="minimum development records when the candidate pool permits it")
    args = parser.parse_args()
    candidate_payload = json.loads(pathlib.Path(args.candidates).read_text(encoding="utf-8-sig"))
    context = json.loads(pathlib.Path(args.context).read_text(encoding="utf-8-sig"))
    keywords = context.get("keywords", [])
    raw_items = candidate_payload.get("items", []) if isinstance(candidate_payload, dict) else []
    accepted = []
    for item in raw_items:
        if not stable_ids(item):
            continue
        score = relevance_score(item, keywords)
        if score >= args.min_overlap:
            accepted.append(dict(item, automated_relevance_score=score,
                                 screening_status="automated-screening"))
    if not 0 < args.validation_share < 1:
        parser.error("--validation-share must be between 0 and 1")
    if args.min_validation < 1 or args.min_dev < 1:
        parser.error("--min-validation and --min-dev must be positive")
    dev, validation = split_items(accepted, args.validation_share, args.min_validation, args.min_dev)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    metadata = {
        "evidence_status": "automated-screening",
        "method": "candidate-anchor lexical relevance screen + deterministic held-out split",
        "candidate_source": candidate_payload.get("source_route", "unknown"),
        "independence_status": "not_established",
        "validation_target": args.min_validation,
        "validation_actual": len(validation),
        "dev_target": args.min_dev,
        "dev_actual": len(dev),
        "limitations": "Candidate discovery and relevance screening are automated; the mechanically held-out set is not an independently sourced final validation set. Human/domain review and external-route provenance are still required.",
    }
    for filename, items, role in (("ai-benchmark.json", accepted, "benchmark"),
                                  ("ai-dev-set.json", dev, "dev"),
                                  ("ai-validation-set.json", validation, "validation")):
        payload = dict(metadata, role=role, items=items)
        (out / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate_routes = candidate_payload.get("sources") or [metadata["candidate_source"]]
    manifest = {
        "schema_version": "1.0",
        "datasets": {
            "benchmark": {"role": "benchmark", "path": "ai-benchmark.json", "source_routes": [metadata["candidate_source"]], "used_tested_query": False, "used_for_query_optimization": False, "frozen_at": None, "notes": metadata["limitations"]},
            "dev": {"role": "dev", "path": "ai-dev-set.json", "source_routes": [metadata["candidate_source"]], "used_tested_query": False, "used_for_query_optimization": True, "frozen_at": None, "notes": "AI-led provisional development set"},
            "validation": {"role": "validation", "path": "ai-validation-set.json", "source_routes": [metadata["candidate_source"]], "used_tested_query": False, "used_for_query_optimization": False, "frozen_at": None, "notes": "Held out mechanically, but not independently sourced or human-reviewed"},
        },
        "relationships": {
            "a3_source_ids": candidate_routes,
            "b2_pathway_source_ids": candidate_routes,
            "note": "First-run A3 and source-level B2 reuse the same open-source routes. B2 is shown only as an automated diagnostic and cannot support a saturation claim."
        },
    }
    (out / "evidence-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accepted": len(accepted), "dev": len(dev), "validation": len(validation), "evidence_status": "automated-screening"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
