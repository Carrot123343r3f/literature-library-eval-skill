#!/usr/bin/env python3
"""Build multi-source candidate A1 anchors and an A3 source snapshot.

The output is deliberately not a measured benchmark.  It is a reproducible,
multi-source starting point for the first assessment: OpenAlex and Crossref are
used for all engineering profiles, with arXiv or Europe PMC added when the
profile makes either source relevant.  An agent must still screen relevance,
preserve provenance, and freeze accepted items before A1 becomes measured.
"""
import argparse
import datetime as dt
import json
import pathlib
import time

try:
    from collect_open_sources import COLLECTORS
    from stable_ids import stable_ids
except ImportError:  # pragma: no cover
    from scripts.collect_open_sources import COLLECTORS
    from scripts.stable_ids import stable_ids


def default_sources(context):
    profile = str(context.get("profile") or " ".join(context.get("engineering_profile", []))).casefold()
    sources = ["openalex", "crossref"]
    if any(token in profile for token in ("computer", "ai", "software", "electronic", "communication")):
        sources.append("arxiv")
    if any(token in profile for token in ("biomedical", "bio", "medical")):
        sources.append("europepmc")
    return sources


def candidate_key(item):
    identifiers = sorted(stable_ids(item))
    return identifiers[0] if identifiers else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--context", required=True, help="context.json with anchor_discovery_query or keywords")
    parser.add_argument("--out", required=True)
    parser.add_argument("--snapshot-out", help="write the multi-source A3 snapshot here")
    parser.add_argument("--sources", default="auto", help="comma list, or auto based on engineering profile")
    parser.add_argument("--max", type=int, default=80, help="maximum deduplicated anchor candidates")
    parser.add_argument("--max-per-source", type=int, default=80)
    args = parser.parse_args()
    context = json.loads(pathlib.Path(args.context).read_text(encoding="utf-8-sig"))
    query = (context.get("anchor_discovery_query") or " ".join(context.get("keywords", [])[:3])
             or context.get("research_question"))
    if not query:
        parser.error("context needs anchor_discovery_query or at least one keyword")
    if args.max < 1 or args.max_per_source < 1:
        parser.error("--max and --max-per-source must be positive")
    sources = default_sources(context) if args.sources == "auto" else [x.strip() for x in args.sources.split(",") if x.strip()]
    if len(sources) < 2:
        parser.error("at least two sources are required for a first-run multi-source snapshot")
    snapshot = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "max_records_per_source_query": args.max_per_source,
                "queries": [{"id": "anchor-discovery-q0", "query": query, "sources": {}}]}
    source_results = snapshot["queries"][0]["sources"]
    for source in sources:
        collector = COLLECTORS.get(source)
        if not collector:
            source_results[source] = {"status": "failed", "error": "unsupported open-source collector"}
            continue
        try:
            result = collector(query, args.max_per_source)
            result["status"] = "complete" if result.get("complete") else "partial"
            source_results[source] = result
        except Exception as exc:
            source_results[source] = {"status": "failed", "error": str(exc)[:240]}

    merged = {}
    for source, result in source_results.items():
        for item in result.get("items", []):
            key = candidate_key(item)
            if not key:
                continue
            candidate = merged.setdefault(key, {
                "title": item.get("title", ""), "id": item.get("id", ""),
                "DOI": item.get("DOI") or item.get("doi", ""),
                "openalex_id": item.get("openalex_id", ""),
                "arxiv": item.get("arxiv", "") or (item.get("id", "") if item.get("source") == "arxiv" else ""),
                "PMID": item.get("PMID") or item.get("pmid", ""), "year": item.get("year"),
                "source_routes": [], "candidate_status": "needs_relevance_screening",
            })
            if not candidate.get("title") and item.get("title"):
                candidate["title"] = item["title"]
            if not candidate.get("id") and item.get("id"):
                candidate["id"] = item["id"]
            candidate["source_routes"].append(source)
    candidates = sorted(merged.values(), key=lambda item: (-len(set(item["source_routes"])), str(item.get("title", "")).casefold()))[:args.max]
    for candidate in candidates:
        candidate["source_routes"] = sorted(set(candidate["source_routes"]))
    statuses = [result.get("status", "failed") for result in source_results.values()]
    status = "complete" if statuses and all(x == "complete" for x in statuses) else "partial" if any(x != "failed" for x in statuses) else "failed"
    output = {
        "role": "candidate_a1_benchmark", "status": status,
        "source_route": "multisource_candidate_discovery_unverified", "sources": sources, "query": query,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "independence_status": "not_established", "can_measure_a1": False,
        "next_step": "Screen relevance; document an external review/standard/citation or held-out route; then freeze accepted items as benchmark.json and evidence-manifest.json.",
        "source_statuses": {source: result.get("status", "failed") for source, result in source_results.items()},
        "items": candidates,
    }
    pathlib.Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.snapshot_out:
        pathlib.Path(args.snapshot_out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"candidate anchors: {len(candidates)} | sources: {', '.join(sources)} | status: {status}")


if __name__ == "__main__":
    main()
