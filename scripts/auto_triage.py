#!/usr/bin/env python3
"""Create explainable AI-assisted triage suggestions without making final decisions."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re


def _norm(value):
    return set(re.findall(r"[\w-]+", str(value or "").casefold()))


def triage(candidates, question, threshold=0.72):
    if not isinstance(candidates, list):
        raise ValueError("candidates must be an array")
    q_terms = _norm(question)
    rows = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError(f"candidate #{index} must be an object")
        title_terms = _norm(item.get("title"))
        abstract_terms = _norm(item.get("abstract") or item.get("abstractNote"))
        title_overlap = len(q_terms & title_terms) / max(1, len(q_terms))
        abstract_overlap = len(q_terms & abstract_terms) / max(1, len(q_terms))
        has_id = bool(item.get("DOI") or item.get("doi") or item.get("id") or item.get("arxiv"))
        has_abstract = bool(abstract_terms)
        score = round(min(1.0, 0.55 * title_overlap + 0.25 * abstract_overlap +
                          0.10 * bool(has_id) + 0.10 * bool(has_abstract)), 4)
        if score >= threshold and has_id:
            suggestion = "include_review"
        elif score < 0.25:
            suggestion = "exclude_review"
        else:
            suggestion = "human_review"
        rows.append({"candidate_id": str(item.get("DOI") or item.get("doi") or item.get("id") or f"row-{index}"),
                     "title": str(item.get("title") or ""), "source": item.get("source"),
                     "suggestion": suggestion, "confidence": score,
                     "reasons": {"title_overlap": round(title_overlap, 4),
                                 "abstract_overlap": round(abstract_overlap, 4),
                                 "stable_id_present": has_id, "abstract_present": has_abstract},
                     "final_decision": "pending"})
    return {"schema_version": "1.0", "status": "suggestions_only",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "note": "Suggestions never count as human screening decisions or formal inclusion.",
            "items": sorted(rows, key=lambda row: (-row["confidence"], row["candidate_id"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        raw = json.loads(pathlib.Path(args.candidates).read_text(encoding="utf-8"))
        candidates = raw if isinstance(raw, list) else raw.get("items", raw.get("additions", []))
        result = triage(candidates, args.question)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['items'])} triage suggestions; human confirmation remains required.")


if __name__ == "__main__":
    main()
