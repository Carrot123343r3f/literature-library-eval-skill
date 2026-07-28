#!/usr/bin/env python3
"""Convert human screening decisions into auditable B/F evidence without overclaiming saturation."""
import argparse
import datetime as dt
import json
import pathlib


def candidate_id(item, index):
    return str(item.get("DOI") or item.get("doi") or item.get("id") or f"row-{index}")


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--candidates", required=True); parser.add_argument("--decisions", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        raw = json.loads(pathlib.Path(args.candidates).read_text(encoding="utf-8"))
        decisions_payload = json.loads(pathlib.Path(args.decisions).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        parser.error(f"cannot parse screening input: {exc}")
    if not isinstance(raw, (list, dict)) or not isinstance(decisions_payload, dict):
        parser.error("candidates and decisions must be JSON arrays/objects")
    rows = raw if isinstance(raw, list) else raw.get("items", [])
    decisions = decisions_payload.get("decisions", [])
    by_id = {candidate_id(item, i): item for i, item in enumerate(rows) if isinstance(item, dict)}
    final = {row["candidate_id"]: row for row in decisions if isinstance(row, dict) and row.get("decision") in {"include", "exclude"}}
    if set(final) - set(by_id): raise SystemExit("ERROR: decisions reference candidates outside this candidate set.")
    included = [by_id[key] for key, row in final.items() if row["decision"] == "include"]
    grouped = {}
    for item in rows:
        if not isinstance(item, dict): continue
        pathway = str(item.get("query_id") or item.get("source") or "screening")
        grouped.setdefault(pathway, []).append(item)
    yields = []
    for pathway, items in grouped.items():
        included_here = sum(1 for item in items if candidate_id(item, rows.index(item)) in final and final[candidate_id(item, rows.index(item))]["decision"] == "include")
        yields.append({"pathway": pathway, "candidates": len(items), "screened_high_confidence": included_here, "new_high_confidence": included_here, "dedup_rule": "canonical candidate identifiers", "screening_status": "screened_complete", "yield": round(included_here / len(items), 4) if items else 0})
    result = {
        "schema_version": "1.1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        # A screening export has no reliable information about the actual search
        # round or its planned pathways.  Do not fabricate those B inputs.
        "search_rounds": [],
        "planned_pathways": [],
        "independent_pathways": [],
        "source_marginal_yields": yields,
        "screening_summary": {
            "candidate_count": len(rows), "included": len(included),
            "excluded": sum(row["decision"] == "exclude" for row in final.values()),
            "pending": len(rows) - len(final),
        },
        "round_evidence_status": "requires_explicit_round_context",
        "note": "Screening evidence only. Merge it with recorded search-round and pathway context before using it for B saturation metrics.",
    }
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True); (out / "screening-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__": main()
