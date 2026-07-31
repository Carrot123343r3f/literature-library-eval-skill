#!/usr/bin/env python3
"""Create a deterministic citation-expansion seed plan without inventing inclusions."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from audit_core.safe_paths import prepare_output_file
import re


def load_items(path):
    if not path:
        return []
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("items", value.get("records", []))
    return value if isinstance(value, list) else []


def openalex_id(item):
    for key in ("openalex_id", "id"):
        raw = str(item.get(key) or "").strip()
        match = re.search(r"(?:openalex\.org/|openalex:)?(W\d+)$", raw, re.I)
        if match:
            return "https://openalex.org/" + match.group(1).upper()
    return ""


def make_plan(library, candidates, user_seeds=None, limit=5):
    supplied = load_items(user_seeds) if user_seeds else []
    pools = [("user_provided_seed", supplied), ("auto_seed_from_library", library),
             ("auto_seed_from_initial_search", candidates)]
    seen, seeds = set(), []
    for origin, rows in pools:
        def rank(row):
            try:
                cited = int(row.get("cited_by_count") or 0)
            except (TypeError, ValueError):
                cited = 0
            return (-cited, str(row.get("title") or ""))
        ranked = sorted((row for row in rows if isinstance(row, dict)), key=rank)
        for row in ranked:
            work_id = openalex_id(row)
            if not work_id or work_id in seen:
                continue
            seen.add(work_id)
            seeds.append({"openalex_id": work_id, "title": str(row.get("title") or ""), "seed_origin": origin})
            if len(seeds) >= limit:
                return seeds
    return seeds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True); parser.add_argument("--candidates")
    parser.add_argument("--user-seed"); parser.add_argument("--out", required=True); parser.add_argument("--limit", type=int, default=5); parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    library, candidates = load_items(args.library), load_items(args.candidates)
    seeds = make_plan(library, candidates, args.user_seed, args.limit)
    status = "ready" if seeds else "no_openalex_seed_available"
    payload = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
               "status": status, "items": seeds,
               "counts": {"user_seed_candidates": len(load_items(args.user_seed)) if args.user_seed else 0,
                          "library_records": len(library), "initial_search_candidates": len(candidates), "selected_seeds": len(seeds)},
               "note": "Automatic seeds are candidate-discovery inputs only; citation results require screening before formal inclusion."}
    output = prepare_output_file(args.out, force=args.force)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(seeds)} citation seed(s): {status}.")


if __name__ == "__main__":
    main()
