#!/usr/bin/env python3
"""Build conservative A3 snapshots from institutional database exports.

The manifest is per source: it preserves the source-specific syntax, filters,
result totals, export limits, timestamp, and a hash of the original export.
No commercial API is contacted. Missing completeness evidence always yields a
partial snapshot, which cannot support an A3 coverage conclusion.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib

from import_library import load
from audit_core.safe_paths import prepare_output_file

SUPPORTED = {"openalex", "crossref", "arxiv", "europepmc", "ieee_xplore",
             "scopus", "web_of_science", "ei_compendex", "inspec"}


def _read_manifest(path):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source manifest: {exc}") from exc
    entries = value.get("sources") if isinstance(value, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("source manifest must contain a non-empty sources array")
    return entries


def _quality(items):
    total = len(items)
    if not total:
        raise ValueError("export contains no records")
    missing = {"title": sum(not item.get("title") for item in items),
               "year": sum(item.get("year") is None for item in items),
               "stable_id": sum(not item.get("DOI") for item in items)}
    rates = {key: round(value / total, 3) for key, value in missing.items()}
    if missing["title"] == total or missing["stable_id"] == total:
        raise ValueError("all records lack a title or stable identifier; check the database export format")
    warnings = [f"high missing {key} rate ({rate:.0%})" for key, rate in rates.items() if rate > .20]
    return {"record_count": total, "missing": missing, "missing_rates": rates, "warnings": warnings}


def _source_result(entry, manifest_dir):
    if not isinstance(entry, dict):
        raise ValueError("each source manifest entry must be an object")
    source = entry.get("source")
    if source not in SUPPORTED:
        raise ValueError(f"unsupported source: {source}")
    required = ("input", "query", "scope_filters", "dedup_rule", "exported_at")
    absent = [key for key in required if not entry.get(key)]
    if absent:
        raise ValueError(f"{source}: missing required manifest fields: {', '.join(absent)}")
    if not isinstance(entry["scope_filters"], dict) or not entry["scope_filters"]:
        raise ValueError(f"{source}: scope_filters must be a non-empty object")
    raw_path = (manifest_dir / entry["input"]).resolve()
    if not raw_path.is_file() or manifest_dir not in raw_path.parents:
        raise ValueError(f"{source}: input must be a file inside the manifest directory")
    items = load(raw_path)
    quality = _quality(items)
    exported_count = entry.get("exported_count", len(items))
    reported_total = entry.get("reported_total")
    export_limit = entry.get("export_limit")
    if not isinstance(exported_count, int) or exported_count != len(items):
        raise ValueError(f"{source}: exported_count must equal the imported record count")
    if reported_total is not None and (not isinstance(reported_total, int) or reported_total < 0):
        raise ValueError(f"{source}: reported_total must be a non-negative integer when supplied")
    if export_limit is not None and (not isinstance(export_limit, int) or export_limit < 1):
        raise ValueError(f"{source}: export_limit must be a positive integer when supplied")
    basis = entry.get("completeness_basis")
    complete = reported_total is not None and exported_count >= reported_total and basis in {
        "reported_total_matches_export", "uncapped_full_export"}
    return source, {"status": "complete" if complete else "partial", "complete": complete,
                    "reported_total": reported_total, "retrieved": exported_count,
                    "items": items, "scope_filters": entry["scope_filters"], "dedup_rule": entry["dedup_rule"],
                    "import_quality": quality,
                    "provenance": {"mode": "user_export", "filename": raw_path.name,
                                   "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                                   "query": entry["query"], "exported_at": entry["exported_at"],
                                   "export_limit": export_limit, "completeness_basis": basis}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Per-source JSON manifest; see docs/integrations.md")
    parser.add_argument("--out", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        manifest_path = pathlib.Path(args.manifest).resolve()
        entries = _read_manifest(manifest_path)
        sources = dict(_source_result(entry, manifest_path.parent) for entry in entries)
        if len(sources) != len(entries):
            raise ValueError("each source may occur only once in a manifest")
    except ValueError as exc:
        parser.error(str(exc))
    result = {"schema_version": "1.2", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "queries": [{"id": "institutional-exports", "sources": sources}]}
    target = prepare_output_file(args.out, force=args.force)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"sources": sorted(sources), "records": sum(x["retrieved"] for x in sources.values()),
                      "complete_sources": sorted(k for k, v in sources.items() if v["complete"]), "out": target.name}, ensure_ascii=False))


if __name__ == "__main__":
    main()
