#!/usr/bin/env python3
"""Validate evidence-set provenance and separation for A/B assessment.

This module checks procedural independence, not an absolute ground truth.
It is deliberately metadata-first: agents must declare how a set was found,
when it was frozen, and whether it was exposed to query optimization.
"""
import json
import pathlib
import re


def _doi(value):
    match = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return match.group(1).rstrip(".,;:)]}").lower() if match else ""


def item_ids(item):
    if not isinstance(item, dict):
        return set()
    found = set()
    for key in ("DOI", "doi", "extra"):
        value = _doi(item.get(key))
        if value:
            found.add("doi:" + value)
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"),
                        ("PMCID", "pmcid"), ("pmcid", "pmcid"),
                        ("arxiv", "arxiv"), ("arXiv", "arxiv"),
                        ("openalex_id", "openalex")):
        if item.get(key):
            found.add(prefix + ":" + str(item[key]).casefold())
    raw = str(item.get("id") or "").casefold()
    if raw.startswith(("doi:", "pmid:", "pmcid:", "arxiv:", "openalex:")):
        found.add(raw)
    return found


def _read_items(entry, base_dir):
    """Read optional dataset items for overlap checks; never expose paths."""
    if not isinstance(entry, dict):
        return []
    if isinstance(entry.get("item_ids"), list):
        return [{"id": value} for value in entry["item_ids"]]
    raw_path = entry.get("path")
    if not raw_path:
        return []
    path = pathlib.Path(raw_path)
    if not path.is_absolute() and base_dir:
        path = pathlib.Path(base_dir) / path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else data.get("items", [])


def inspect_manifest(manifest, manifest_path=None):
    """Return a serializable evidence-integrity report.

    Required roles are metadata conventions rather than assumptions. A missing
    manifest leaves the result not_assessable; it never upgrades evidence.
    """
    result = {
        "status": "not_assessable",
        "manifest_present": isinstance(manifest, dict),
        "a2_validation_independent": None,
        "a2_b3_shared_validation": False,
        "a3_b2_overlap": False,
        "dev_validation_overlap_count": 0,
        "warnings": [],
        "errors": [],
    }
    if not isinstance(manifest, dict):
        result["warnings"].append("No evidence manifest supplied; procedural independence was not assessed.")
        return result

    datasets = manifest.get("datasets", {})
    if not isinstance(datasets, dict):
        result["errors"].append("datasets must be an object")
        result["status"] = "invalid"
        return result

    base_dir = pathlib.Path(manifest_path).parent if manifest_path else None
    dev = datasets.get("dev", {})
    val = datasets.get("validation", {})
    dev_ids = set().union(*(item_ids(x) for x in _read_items(dev, base_dir))) if dev else set()
    val_ids = set().union(*(item_ids(x) for x in _read_items(val, base_dir))) if val else set()
    overlap = dev_ids & val_ids
    result["dev_validation_overlap_count"] = len(overlap)
    if overlap:
        result["errors"].append(f"Dev/validation overlap: {len(overlap)} stable identifier(s)")

    if val:
        independent = not bool(val.get("used_tested_query")) and not bool(val.get("used_for_query_optimization"))
        result["a2_validation_independent"] = independent and not bool(overlap)
        if val.get("used_tested_query"):
            result["errors"].append("Validation set was discovered by the tested query")
        if val.get("used_for_query_optimization"):
            result["errors"].append("Validation set was exposed to query optimization")
        if not val.get("frozen_at"):
            result["warnings"].append("Validation set has no frozen_at timestamp")
        routes = val.get("source_routes", [])
        if not routes:
            result["warnings"].append("Validation set has no source_routes provenance")
    else:
        result["warnings"].append("No validation dataset declared; A2 cannot be measured independently")

    relationships = manifest.get("relationships", {})
    if relationships.get("a2_validation_dataset") and relationships.get("b3_validation_dataset"):
        result["a2_b3_shared_validation"] = (
            relationships["a2_validation_dataset"] == relationships["b3_validation_dataset"]
        )
        if result["a2_b3_shared_validation"]:
            result["warnings"].append("A2 and B3 reuse the same validation dataset")

    a3_sources = set(relationships.get("a3_source_ids", []))
    b2_sources = set(relationships.get("b2_pathway_source_ids", []))
    result["a3_b2_overlap"] = bool(a3_sources & b2_sources)
    if result["a3_b2_overlap"]:
        result["warnings"].append("A3 snapshots and B2 pathway evidence share source IDs")

    if result["errors"]:
        result["status"] = "invalid"
    elif result["warnings"]:
        result["status"] = "warning"
    else:
        result["status"] = "pass"
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    path = pathlib.Path(args.manifest)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[FAIL] cannot read manifest: {exc}")
        raise SystemExit(1)
    report = inspect_manifest(manifest, path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "invalid" else 0)


if __name__ == "__main__":
    main()
