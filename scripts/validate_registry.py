#!/usr/bin/env python3
"""Validate that run_audit.py indicator output is consistent with indicator-registry.json.

Usage:
    python validate_registry.py --audit audit.json
    python validate_registry.py --audit audit.json --registry schemas/indicator-registry.json

Exits 0 on pass, 1 on any inconsistency.

All expected values (indicator IDs, order, dimension names, umbrella-only
markers, valid evidence states) are read from indicator-registry.json at
runtime.  There are no hardcoded indicator-ID constants in this file.
"""
import argparse, json, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")

def load_registry(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def _derive_dim_names(registry):
    """Derive dimension-name mapping from the registry's dimensions section."""
    dims = registry.get("dimensions", {})
    return {k: v.get("name", k) for k, v in dims.items()}

def _derive_expected_ids(registry, is_umbrella):
    """Return the expected indicator ID list in registry order.

    For non-umbrella reviews, umbrella-only indicators are excluded.
    For umbrella reviews, all indicators are included in their registry order.
    """
    indicators = registry.get("indicators", [])
    all_ids = [ind["id"] for ind in indicators]
    umbrella_only = {ind["id"] for ind in indicators if ind.get("umbrella_only")}
    if is_umbrella:
        return all_ids  # keep registry order — A4 between A3/B1, C4 between C3/D1, etc.
    return [iid for iid in all_ids if iid not in umbrella_only]

def validate_audit(audit, registry):
    """Validate audit.json.indicator_register against indicator-registry.json."""
    errors = []
    rows = audit.get("indicator_register", [])
    if not rows:
        errors.append("audit.indicator_register is empty or missing")
        return errors

    ctx = audit.get("context", {})
    is_umbrella = ctx.get("review_type") == "伞式综述"
    dim_names = _derive_dim_names(registry)
    expected_ids = _derive_expected_ids(registry, is_umbrella)
    actual_ids = [r.get("subproject") for r in rows]
    reg_ids = {ind["id"]: ind for ind in registry.get("indicators", [])}

    # 1. Count and set identity
    if len(rows) != len(expected_ids):
        errors.append(
            f"Expected {len(expected_ids)} indicators"
            f" ({'umbrella' if is_umbrella else 'non-umbrella'}), got {len(rows)}"
        )
    missing = set(expected_ids) - set(actual_ids)
    extra = set(actual_ids) - set(expected_ids)
    if missing:
        errors.append(f"Missing indicators: {sorted(missing)}")
    if extra:
        errors.append(f"Unexpected indicators: {sorted(extra)}")

    # 2. Order
    if actual_ids != expected_ids:
        errors.append(
            f"Indicator order mismatch. Expected: {expected_ids}, Got: {actual_ids}"
        )

    # 3. Per-row validation
    for row in rows:
        rid = row.get("subproject")
        reg = reg_ids.get(rid)
        if not reg:
            errors.append(f"{rid}: not found in indicator-registry.json")
            continue

        dim = reg["dimension"]
        parent_dim = row.get("parent_dimension", "")
        expected_dim = dim_names.get(dim, dim)
        if parent_dim != expected_dim:
            errors.append(
                f"{rid}: parent_dimension '{parent_dim}'"
                f" does not match registry dimension '{expected_dim}'"
            )

        reg_name = reg.get("display_name", {}).get("zh", "")
        row_name = row.get("project_name", "")
        if reg_name and row_name:
            reg_norm = reg_name.replace("(", "（").replace(")", "）").strip()
            row_norm = row_name.replace("(", "（").replace(")", "）").strip()
            if reg_norm != row_norm:
                errors.append(
                    f"{rid}: project_name '{row_name}'"
                    f" does not match registry display_name '{reg_name}'"
                )

        if reg.get("umbrella_only") and not is_umbrella:
            errors.append(f"{rid}: umbrella-only indicator found in non-umbrella audit")

        ev = row.get("evidence_status", "")
        valid_ev = reg.get("evidence_states", [])
        if valid_ev and ev not in valid_ev and ev != "screening":
            errors.append(
                f"{rid}: evidence_status '{ev}' not in registry valid states {valid_ev}"
            )

    # 4. Umbrella-only indicators must be present for umbrella reviews
    if is_umbrella:
        umbrella_only_reg = {ind["id"] for ind in registry.get("indicators", [])
                            if ind.get("umbrella_only")}
        for expected in sorted(umbrella_only_reg):
            if expected not in actual_ids:
                errors.append(f"Umbrella review missing {expected} indicator")

    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--audit", required=True, help="audit.json output from run_audit.py")
    p.add_argument("--registry", help="Path to indicator-registry.json (default: auto-detect)")
    a = p.parse_args()

    audit_path = pathlib.Path(a.audit)
    if not audit_path.is_file():
        print(f"Error: audit file not found: {a.audit}")
        sys.exit(1)

    if a.registry:
        reg_path = pathlib.Path(a.registry)
    else:
        script_dir = pathlib.Path(__file__).resolve().parent
        reg_path = script_dir.parent / "schemas" / "indicator-registry.json"
    if not reg_path.is_file():
        print(f"Error: registry not found: {reg_path}")
        sys.exit(1)

    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    registry = load_registry(reg_path)
    errors = validate_audit(audit, registry)

    if errors:
        print(f"[FAIL] {len(errors)} inconsistency(s) found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("[PASS] audit.json is consistent with indicator-registry.json")


if __name__ == "__main__":
    main()
