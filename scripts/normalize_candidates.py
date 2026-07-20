#!/usr/bin/env python3
"""Normalize a source snapshot without silently merging uncertain version families."""
import argparse
import datetime as dt
import json
import pathlib
import re
from collections import defaultdict


def doi(value):
    match = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return match.group(1).rstrip(".,;:)]}").lower() if match else ""


def key(item):
    found = doi(item.get("id")) or doi(item.get("doi"))
    if found: return "doi:" + found
    raw = str(item.get("id") or "")
    if item.get("source") == "arxiv" and raw: return "arxiv:" + raw.casefold()
    if raw.startswith(("pmid:", "pmcid:", "arxiv:", "openalex:")): return raw.casefold()
    return ""


def title_year(item):
    title = re.sub(r"[^\w]", "", str(item.get("title") or "").casefold())
    year = str(item.get("year") or "")[:4]
    return (title, year) if title else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args()
    snapshot = json.loads(pathlib.Path(args.snapshot).read_text(encoding="utf-8"))
    stable, uncertain, source_status = defaultdict(list), defaultdict(list), {}
    for query in snapshot.get("queries", []):
        for source, result in query.get("sources", {}).items():
            source_status[f"{query.get('id')}:{source}"] = result.get("status", "unknown")
            for row in result.get("items", []):
                item = dict(row); item["source"] = item.get("source") or source; item["query_id"] = query.get("id")
                (stable[key(item)] if key(item) else uncertain[title_year(item)] if title_year(item) else []).append(item)
    canonical, exact_groups, candidates, version_families = [], [], [], []
    for identifier, rows in stable.items():
        canonical.append(rows[0]); exact_groups.append({"stable_id": identifier, "records": len(rows), "sources": sorted({x["source"] for x in rows})})
    for title_key, rows in uncertain.items():
        if len(rows) == 1: canonical.append(rows[0]); continue
        candidates.append({"candidate_id": "title-year:" + "|".join(title_key), "records": len(rows), "sources": sorted({x["source"] for x in rows}),
                           "decision": "manual_review_required", "reason": "title-year match has no shared stable identifier", "items": rows})
    by_title = defaultdict(list)
    for item in canonical:
        if title_year(item): by_title[title_year(item)].append(item)
    for title_key, rows in by_title.items():
        ids = sorted({key(x) for x in rows if key(x)})
        if len(ids) > 1 and any(x.get("source") == "arxiv" for x in rows):
            version_families.append({"title_year": title_key, "stable_ids": ids, "decision": "manual_review_required", "reason": "possible preprint–published version family", "items": rows})
    result = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "snapshot_source_status": source_status,
              "canonical_items": canonical, "deduplication_log": {"exact_identifier_groups": exact_groups, "uncertain_title_year_candidates": candidates,
              "possible_version_families": version_families, "policy": "Only shared stable identifiers are automatically consolidated; uncertain matches are retained for review."}}
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(json.dumps({"items": canonical}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "deduplication-log.json").write_text(json.dumps(result["deduplication_log"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "normalization-manifest.json").write_text(json.dumps({k: v for k, v in result.items() if k != "deduplication_log"}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
