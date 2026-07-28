#!/usr/bin/env python3
"""Audit development/validation set independence and basic composition."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


ID_KEYS = ("doi", "pmid", "pmcid", "arxiv_id", "openalex_id", "id")


def load_items(path):
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("items", value.get("records", []))
    if not isinstance(value, list):
        raise ValueError(f"evaluation set must be a list: {path}")
    return value


def ids(items):
    result = set()
    missing = 0
    for item in items:
        if not isinstance(item, dict):
            missing += 1; continue
        found = False
        for key in ID_KEYS:
            value = item.get(key)
            if value:
                result.add(f"{key}:{str(value).strip().lower()}"); found = True
        if not found:
            missing += 1
    return result, missing


def canonical_ids(items):
    """Choose one stable identity per record to avoid DOI+PMID false duplicates."""
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ID_KEYS:
            value = item.get(key)
            if value:
                result.append(f"{key}:{str(value).strip().lower()}")
                break
    return result


def audit(dev, validation, min_dev=3, min_validation=3):
    dev_ids, dev_missing = ids(dev)
    val_ids, val_missing = ids(validation)
    overlap = dev_ids & val_ids
    dev_canonical = canonical_ids(dev)
    val_canonical = canonical_ids(validation)
    duplicate_dev = len(set(dev_canonical)) < len(dev_canonical)
    duplicate_val = len(set(val_canonical)) < len(val_canonical)
    errors, warnings = [], []
    if len(dev) < min_dev: errors.append(f"development set too small: {len(dev)} < {min_dev}")
    if len(validation) < min_validation: errors.append(f"validation set too small: {len(validation)} < {min_validation}")
    if overlap: errors.append(f"dev/validation overlap detected: {len(overlap)} stable IDs")
    if duplicate_dev: errors.append("development set contains duplicate stable IDs")
    if duplicate_val: errors.append("validation set contains duplicate stable IDs")
    if dev_missing: warnings.append(f"development records without stable IDs: {dev_missing}")
    if val_missing: warnings.append(f"validation records without stable IDs: {val_missing}")
    return {"schema_version": "1.0", "status": "invalid" if errors else "valid",
            "development": {"count": len(dev), "stable_id_count": len(dev_ids)},
            "validation": {"count": len(validation), "stable_id_count": len(val_ids)},
            "overlap_count": len(overlap), "overlap_digest": hashlib.sha256("|".join(sorted(overlap)).encode()).hexdigest() if overlap else None,
            "errors": errors, "warnings": warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dev", required=True); parser.add_argument("--validation", required=True); parser.add_argument("--out", required=True); parser.add_argument("--min-dev", type=int, default=3); parser.add_argument("--min-validation", type=int, default=3)
    args = parser.parse_args()
    try:
        result = audit(load_items(args.dev), load_items(args.validation), args.min_dev, args.min_validation)
        pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 1 if result["status"] == "invalid" else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
