#!/usr/bin/env python3
"""Compile one research question into source-aware query-plan rows."""
from __future__ import annotations

import re

SUPPORTED_SOURCES = ("openalex", "arxiv", "crossref", "europepmc")


def _terms(question):
    words = re.findall(r"[\w-]+", str(question or ""), flags=re.UNICODE)
    stop = {"what", "which", "does", "how", "are", "the", "and", "for", "with", "from", "研究", "哪些", "什么", "如何"}
    result = []
    for word in words:
        if len(word) < 2 or word.casefold() in stop or word.casefold() in {x.casefold() for x in result}:
            continue
        result.append(word)
    return result[:8]


def compile_query_plan(question, sources):
    """Return a reproducible plan with source-specific syntax and provenance."""
    sources = [str(source).casefold() for source in sources]
    unknown = sorted(set(sources) - set(SUPPORTED_SOURCES))
    if unknown:
        raise ValueError("unsupported sources: " + ", ".join(unknown))
    if not str(question or "").strip():
        raise ValueError("question must be non-empty")
    terms = _terms(question)
    phrase = " ".join(terms[:5]) or str(question).strip()
    rows = []
    for source in dict.fromkeys(sources):
        if source == "arxiv":
            query = f'all:"{phrase}"'
        elif source == "europepmc":
            query = f'TITLE:"{phrase}" OR ABSTRACT:"{phrase}"'
        else:
            query = phrase
        rows.append({"id": f"autopilot-{source}-q1", "query": query,
                     "sources": [source], "source_syntax": source,
                     "generated_from": "research_question", "terms": terms})
    return {"schema_version": "1.0", "question": str(question).strip(),
            "compiler": "query_compiler.v1", "queries": rows,
            "dedup_rule": "stable identifiers first; title-year only for manual review"}


if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--sources", default=",".join(SUPPORTED_SOURCES))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    pathlib = __import__("pathlib")
    plan = compile_query_plan(args.question, [x.strip() for x in args.sources.split(",") if x.strip()])
    path = pathlib.Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
