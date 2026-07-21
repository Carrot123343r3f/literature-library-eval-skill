#!/usr/bin/env python3
"""Normalize a source snapshot without silently merging uncertain version families.

Normalises stable identifiers (DOI, arXiv, PMID, PMCID, OpenAlex) to
canonical forms, deduplicates exact matches, and flags uncertain
title-year candidates and preprint–published version families for
human review.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from collections import defaultdict


# ── Identifier normalisation ──────────────────────────────────────

def doi(value):
    """Extract and normalise a DOI from a string, URL, or prefixed form."""
    raw = str(value or "").strip()
    # already prefixed: doi:10.xxxx/abc
    m = re.match(r"^doi:\s*(10\.\d{4,9}/\S+)", raw, re.I)
    if m:
        return m.group(1).rstrip(".,;:)]}").lower()
    # full URL
    m = re.search(r"https?://(?:dx\.)?doi\.org/(10\.\d{4,9}/\S+)", raw, re.I)
    if m:
        return m.group(1).rstrip(".,;:)]}").lower()
    # bare DOI
    m = re.search(r"(10\.\d{4,9}/\S+)", raw, re.I)
    if m:
        return m.group(1).rstrip(".,;:)]}").lower()
    return ""


def normalise_openalex(raw):
    """Normalise an OpenAlex identifier to canonical form."""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    # openalex:W123…
    m = re.match(r"^openalex:\s*(W\d+)", raw, re.I)
    if m:
        return ("openalex:" + m.group(1)).casefold()
    # https://openalex.org/W123…
    m = re.search(r"openalex\.org/(W\d+)", raw, re.I)
    if m:
        return ("openalex:" + m.group(1)).casefold()
    # bare W123… (OpenAlex work IDs always start with W)
    m = re.match(r"^(W\d+)$", raw.strip(), re.I)
    if m:
        return ("openalex:" + m.group(1)).casefold()
    return ""


def normalise_pmid(raw):
    """Normalise a PubMed ID.  Returns 'pmid:N' or ''."""
    raw = str(raw or "").strip()
    m = re.match(r"^(?:pmid:)?\s*(\d{1,8})$", raw, re.I)
    return ("pmid:" + m.group(1)) if m else ""


def normalise_pmcid(raw):
    """Normalise a PubMed Central ID.  Returns 'pmcid:PMC…' or ''."""
    raw = str(raw or "").strip()
    m = re.match(r"^(?:pmcid:)?\s*(PMC\d+)$", raw, re.I)
    return ("pmcid:" + m.group(1)).casefold() if m else ""


def normalise_arxiv(raw):
    """Normalise an arXiv identifier to canonical form 'arxiv:YYMM.NNNNN'."""
    raw = str(raw or "").strip()
    # already prefixed
    m = re.match(r"^arxiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", raw, re.I)
    if m:
        # strip version suffix
        base = re.sub(r"v\d+$", "", m.group(1))
        return "arxiv:" + base.casefold()
    # arXiv URL
    m = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?", raw, re.I)
    if m:
        return "arxiv:" + m.group(1).casefold()
    # bare ID
    m = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?$", raw.strip())
    if m:
        return "arxiv:" + m.group(1).casefold()
    return ""


def key(item):
    """Extract a single stable identifier from a snapshot item.

    Returns '' when no stable identifier could be found (the item
    will be routed to title-year matching or to the unidentifiable log).
    """
    # DOI — check id and doi fields
    for field in ("id", "doi", "DOI"):
        d = doi(item.get(field))
        if d:
            return "doi:" + d

    raw = str(item.get("id") or "")

    # OpenAlex
    oaid = normalise_openalex(raw)
    if oaid:
        return oaid

    # arXiv — explicit source field
    if item.get("source") == "arxiv" and raw:
        ax = normalise_arxiv(raw)
        if ax:
            return ax

    # Prefixed forms
    for normaliser in (normalise_pmid, normalise_pmcid, normalise_arxiv):
        result = normaliser(raw)
        if result:
            return result

    return ""


def title_year(item):
    """Return a (title, year) tuple for fuzzy matching, or None."""
    title = re.sub(r"[^\w]", "", str(item.get("title") or "").casefold())
    year = str(item.get("year") or "")[:4]
    return (title, year) if title else None


# ── Input validation ──────────────────────────────────────────────

def validate_snapshot(snapshot):
    """Validate snapshot structure.  Returns list of warning strings."""
    warnings = []
    if not isinstance(snapshot, dict):
        return ["snapshot must be a JSON object"]
    queries = snapshot.get("queries")
    if not isinstance(queries, list) or not queries:
        warnings.append("snapshot.queries is missing or empty")
        return warnings
    for qi, query in enumerate(queries):
        qid = query.get("id", f"query[{qi}]")
        sources = query.get("sources", {})
        if not isinstance(sources, dict):
            warnings.append(f"{qid}: sources must be an object")
            continue
        for src_name, result in sources.items():
            if not isinstance(result, dict):
                warnings.append(f"{qid}/{src_name}: result must be an object")
                continue
            items = result.get("items")
            if not isinstance(items, list):
                warnings.append(f"{qid}/{src_name}: items must be a list")
            status = result.get("status")
            if status not in ("complete", "partial", "failed", None):
                warnings.append(
                    f"{qid}/{src_name}: unexpected status {status!r}")
    return warnings


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Normalise candidate snapshots — dedup, version families, human-review queues")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    snap_path = pathlib.Path(args.snapshot)
    if not snap_path.is_file():
        print(f"ERROR: snapshot file not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)
    try:
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: cannot parse snapshot: {exc}", file=sys.stderr)
        sys.exit(1)

    validate_warnings = validate_snapshot(snapshot)
    if validate_warnings:
        for w in validate_warnings:
            print(f"WARNING: {w}", file=sys.stderr)

    stable = defaultdict(list)
    uncertain = defaultdict(list)
    unidentifiable = []          # items with no title AND no stable ID
    source_status = {}

    for query in snapshot.get("queries", []):
        for source, result in query.get("sources", {}).items():
            source_status[f"{query.get('id')}:{source}"] = result.get("status", "unknown")
            for row in result.get("items", []):
                if not isinstance(row, dict):
                    continue
                item = dict(row)
                item["source"] = item.get("source") or source
                item["query_id"] = query.get("id")
                k = key(item)
                if k:
                    stable[k].append(item)
                else:
                    ty = title_year(item)
                    if ty:
                        uncertain[ty].append(item)
                    else:
                        unidentifiable.append(item)

    canonical = []
    exact_groups = []
    candidates = []
    version_families = []

    # Stable-ID groups → keep first, record group
    for identifier, rows in stable.items():
        canonical.append(rows[0])
        exact_groups.append({
            "stable_id": identifier,
            "records": len(rows),
            "sources": sorted({x["source"] for x in rows}),
        })

    # Title-year groups → single → canonical; multiple → human review
    for title_key, rows in uncertain.items():
        if len(rows) == 1:
            canonical.append(rows[0])
            continue
        candidates.append({
            "candidate_id": "title-year:" + "|".join(title_key),
            "records": len(rows),
            "sources": sorted({x["source"] for x in rows}),
            "decision": "manual_review_required",
            "reason": "title-year match has no shared stable identifier",
            "items": rows,
        })

    # Version families (arXiv + DOI for same title-year)
    by_title = defaultdict(list)
    for item in canonical:
        ty = title_year(item)
        if ty:
            by_title[ty].append(item)
    for title_key, rows in by_title.items():
        ids_ = sorted({key(x) for x in rows if key(x)})
        if len(ids_) > 1 and any(x.get("source") == "arxiv" for x in rows):
            version_families.append({
                "title_year": title_key,
                "stable_ids": ids_,
                "decision": "manual_review_required",
                "reason": "possible preprint–published version family",
                "items": rows,
            })

    result = {
        "schema_version": "1.0",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "snapshot_source_status": source_status,
        "canonical_items": canonical,
        "unidentifiable_items": len(unidentifiable),
        "unidentifiable_reason": "items without stable identifier and without title — cannot deduplicate",
        "deduplication_log": {
            "exact_identifier_groups": exact_groups,
            "uncertain_title_year_candidates": candidates,
            "possible_version_families": version_families,
            "policy": (
                "Only shared stable identifiers are automatically consolidated; "
                "uncertain matches are retained for human review. "
                "Items with no stable ID and no title are logged but cannot be deduplicated."
            ),
        },
        "input_validation": {
            "warnings": validate_warnings,
        },
    }

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(
        json.dumps({"items": canonical}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "deduplication-log.json").write_text(
        json.dumps(result["deduplication_log"], ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "normalization-manifest.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "deduplication_log"},
                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
