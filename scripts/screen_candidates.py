#!/usr/bin/env python3
"""Create and validate a human screening decision log; never auto-promotes candidates."""
import argparse
import datetime as dt
import json
import pathlib


VALID = {"include", "exclude", "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True); parser.add_argument("--out", required=True); parser.add_argument("--decisions")
    args = parser.parse_args(); output = pathlib.Path(args.out); output.mkdir(parents=True, exist_ok=True)
    raw_candidates = json.loads(pathlib.Path(args.candidates).read_text(encoding="utf-8")); rows = raw_candidates if isinstance(raw_candidates, list) else raw_candidates.get("items", raw_candidates.get("additions", []))
    candidate_ids = {str(item.get("DOI") or item.get("id") or f"row-{i}") for i, item in enumerate(rows) if isinstance(item, dict)}
    if args.decisions:
        value = json.loads(pathlib.Path(args.decisions).read_text(encoding="utf-8")); decisions = value.get("decisions", [])
        seen = set(); invalid = [row for row in decisions if not isinstance(row, dict) or not row.get("candidate_id") or row.get("candidate_id") not in candidate_ids or row.get("candidate_id") in seen or seen.add(row.get("candidate_id")) or row.get("decision") not in VALID or (row.get("decision") != "pending" and not row.get("reason"))]
        if invalid: raise SystemExit("ERROR: each final include/exclude decision requires candidate_id and reason.")
        result = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "decisions": decisions,
                  "status": "human_screened", "note": "Only human-confirmed includes may contribute to B metrics."}
    else:
        result = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "template",
                  "instructions": "Set decision to include/exclude/pending. Include and exclude require a reason.",
                  "decisions": [{"candidate_id": item.get("DOI") or item.get("id") or f"row-{i}", "title": item.get("title", ""), "decision": "pending", "reason": ""} for i, item in enumerate(rows) if isinstance(item, dict)]}
    (output / "screening-decisions.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {result['status']} screening log.")


if __name__ == "__main__": main()
