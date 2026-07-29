#!/usr/bin/env python3
"""Enrich a literature library with authorized metadata, without blocking the audit.

User-supplied values win. A source outage, missing credential, or ambiguous
match produces a report and leaves the original record unchanged.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

from artifact_manifest import write_manifest
from paper_evaluation.contracts import load_items
from paper_evaluation.evaluation import clean
from paper_evaluation.external import ExternalSearchError, enrich_openalex_record, require_openalex_authorization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--run-config", required=True)
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    artifacts = {"library": args.library, "run-config": args.run_config}
    try:
        rows = load_items(args.library)
        config = json.loads(pathlib.Path(args.run_config).read_text(encoding="utf-8"))
        automation = config.get("automation") or {}
        report = {"schema_version": "1.0", "module": "metadata-enrichment", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "source": "openalex", "status": "not_requested", "records_total": len(rows), "records_matched": 0,
                  "records_unchanged": 0, "records_ambiguous_or_missing": 0, "records": []}
        enriched_rows = [dict(row) if isinstance(row, dict) else row for row in rows]
        if automation.get("allow_search") is not True or automation.get("allow_metadata_enrichment", False) is not True:
            report.update(status="disabled_by_user", records_unchanged=len(rows))
        elif "openalex" not in {str(x).lower() for x in automation.get("allowed_sources", [])}:
            report.update(status="source_not_allowed", records_unchanged=len(rows))
        else:
            try:
                key = require_openalex_authorization(config, "allow_metadata_enrichment")
            except ExternalSearchError:
                report.update(status="unavailable", reason="credential_or_source_unavailable", records_unchanged=len(rows))
            else:
                report["status"] = "complete_with_gaps"
                cache = {}
                for index, row in enumerate(rows):
                    if not isinstance(row, dict):
                        report["records"].append({"index": index, "status": "invalid_record"})
                        report["records_unchanged"] += 1
                        continue
                    cache_key = (clean(row.get("DOI") or row.get("doi")).lower() or
                                 f"{clean(row.get('title')).casefold()}::{row.get('year') or row.get('publication_year') or ''}")
                    if cache_key in cache:
                        updated, lookup = dict(cache[cache_key][0]), dict(cache[cache_key][1])
                    else:
                        try:
                            updated, lookup = enrich_openalex_record(row, key, config)
                        except Exception as exc:
                            lookup = {"status": "source_error", "error_type": type(exc).__name__}
                            updated = dict(row)
                        cache[cache_key] = (dict(updated), dict(lookup))
                    enriched_rows[index] = updated
                    filled = lookup.get("filled_fields", [])
                    if filled:
                        report["records_matched"] += 1
                        item_status = "matched"
                    else:
                        report["records_unchanged"] += 1
                        report["records_ambiguous_or_missing"] += 1
                        item_status = lookup.get("status", "unchanged")
                    report["records"].append({"index": index, "title": clean(row.get("title")), "status": item_status,
                                              "match_confidence": lookup.get("match_confidence"), "filled_fields": filled,
                                              "lookup_status": lookup.get("status")})
        (out / "library-enriched.json").write_text(json.dumps(enriched_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "metadata-enrichment.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["manifest"] = write_manifest(out, "metadata-enrichment", "1.0", artifacts, {"input_validation": "complete", "enrichment": report["status"], "report": "complete"})
        (out / "metadata-enrichment.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Metadata enrichment: {report['status']}; matched {report['records_matched']}/{len(rows)} records.")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        (out / "metadata-enrichment-error.json").write_text(json.dumps({"module": "metadata-enrichment", "status": "error", "message": "input_or_output_error", "error_type": type(exc).__name__}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: metadata enrichment failed ({type(exc).__name__}).", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__":
    main()
