#!/usr/bin/env python3
"""Validate that run_audit.py indicator output is consistent with indicator-registry.json.

Usage:
    python validate_registry.py --audit audit.json
    python validate_registry.py --audit audit.json --registry schemas/indicator-registry.json

Exits 0 on pass, 1 on any inconsistency.
"""
import argparse, json, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")

def _load_registry_indicators(reg_path):
    """Load indicator-registry.json and return (base_ids, umbrella_ids, dim_names, id_map).
    This is the single source of truth for indicator order, names, and dimensions."""
    reg = json.loads(pathlib.Path(reg_path).read_text(encoding="utf-8"))
    indicators = reg.get("indicators", [])
    dim_names = {}
    for dim_key, dim_info in reg.get("dimensions", {}).items():
        dim_names[dim_key] = dim_info.get("name", dim_key)
    all_ids = [ind["id"] for ind in indicators]
    umbrella_only = {ind["id"] for ind in indicators if ind.get("umbrella_only")}
    base_ids = [iid for iid in all_ids if iid not in umbrella_only]
    umbrella_ids = [iid for iid in all_ids if iid in umbrella_only]
    id_map = {ind["id"]: ind for ind in indicators}
    return base_ids, umbrella_ids, dim_names, id_map

# Expected indicator IDs from the registry (in order)
EXPECTED_BASE = ["A1","A2","A3","B1","B2","B3","C1","C2","C3","D1","D2","D3","D4","E1","E2","F1","F2","F3","F4","F5","F6"]
EXPECTED_UMBRELLA = EXPECTED_BASE + ["A4","C4","F7"]

# Dimension mapping
DIM_NAMES = {
    "A": "A 覆盖", "B": "B 饱和度", "C": "C 平衡",
    "D": "D 时效", "E": "E 学术影响", "F": "F 可用性"
}

def load_registry(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def validate_audit(audit, registry):
    """Validate audit.json.indicator_register against indicator-registry.json.
    Uses the registry as the single source of truth for indicator IDs, order,
    dimension affiliation, and display names."""
    errors = []
    rows = audit.get("indicator_register", [])
    if not rows:
        errors.append("audit.indicator_register is empty or missing")
        return errors

    ctx = audit.get("context", {})
    is_umbrella = ctx.get("review_type") == "伞式综述"
    indicators = registry.get("indicators", [])
    # Auto-derive expected IDs from registry order rather than hardcoded constants
    all_reg_ids = [ind["id"] for ind in indicators]
    umbrella_only_reg = {ind["id"] for ind in indicators if ind.get("umbrella_only")}
    expected_ids = [iid for iid in all_reg_ids
                    if not is_umbrella or iid not in (umbrella_only_reg - umbrella_only_reg)
                    if is_umbrella or iid not in umbrella_only_reg]
    # For non-umbrella: filter out umbrella_only. For umbrella: include all.
    # Simpler: base = ids without umbrella_only, umbrella_extra = umbrella_only ids
    base_from_reg = [iid for iid in all_reg_ids if iid not in umbrella_only_reg]
    umbrella_from_reg = [iid for iid in all_reg_ids if iid in umbrella_only_reg]
    expected_ids = base_from_reg + (umbrella_from_reg if is_umbrella else [])
    actual_ids = [r.get("subproject") for r in rows]
    if len(rows) != len(expected_ids):
        errors.append(f"Expected {len(expected_ids)} indicators ({'umbrella' if is_umbrella else 'non-umbrella'}), got {len(rows)}")
    if set(actual_ids) != set(expected_ids):
        missing = set(expected_ids) - set(actual_ids)
        extra = set(actual_ids) - set(expected_ids)
        if missing: errors.append(f"Missing indicators: {sorted(missing)}")
        if extra: errors.append(f"Unexpected indicators: {sorted(extra)}")

    # 2. Check order
    if actual_ids != expected_ids:
        errors.append(f"Indicator order mismatch. Expected: {expected_ids}, Got: {actual_ids}")

    # 3. Verify every register row against registry
    reg_ids = {ind["id"]: ind for ind in registry.get("indicators", [])}
    for row in rows:
        rid = row.get("subproject")
        reg = reg_ids.get(rid)
        if not reg:
            errors.append(f"{rid}: not found in indicator-registry.json")
            continue
        # Check dimension affiliation
        dim = reg["dimension"]
        parent_dim = row.get("parent_dimension", "")
        expected_dim = DIM_NAMES.get(dim, dim)
        if parent_dim != expected_dim:
            errors.append(f"{rid}: parent_dimension '{parent_dim}' does not match registry dimension '{expected_dim}'")
        # Check display name — use substring matching to handle Chinese character encoding
        reg_name = reg.get("display_name", {}).get("zh", "")
        row_name = row.get("project_name", "")
        if reg_name and row_name:
            # Normalize both to remove encoding artifacts
            reg_norm = reg_name.replace("(", "（").replace(")", "）").strip()
            row_norm = row_name.replace("(", "（").replace(")", "）").strip()
            if reg_norm != row_norm:
                errors.append(f"{rid}: project_name '{row_name}' does not match registry display_name '{reg_name}'")
        # Check umbrella-only indicators only appear in umbrella audits
        if reg.get("umbrella_only") and not is_umbrella:
            errors.append(f"{rid}: umbrella-only indicator found in non-umbrella audit")
        # Check evidence status is valid
        ev = row.get("evidence_status", "")
        valid_ev = reg.get("evidence_states", [])
        if valid_ev and ev not in valid_ev:
            # Allow "screening" as a valid transient state
            if ev != "screening":
                errors.append(f"{rid}: evidence_status '{ev}' not in registry valid states {valid_ev}")

    # 4. Verify umbrella-only indicators are present when needed
    if is_umbrella:
        for expected in ["A4","C4","F7"]:
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
        # Auto-detect: schemas/indicator-registry.json relative to script dir
        script_dir = pathlib.Path(__file__).resolve().parent
        reg_path = script_dir.parent / "schemas" / "indicator-registry.json"
    if not reg_path.is_file():
        print(f"Error: registry not found: {reg_path}")
        sys.exit(1)

    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    registry = load_registry(reg_path)
    errors = validate_audit(audit, registry)

    if errors:
        print(f"❌ {len(errors)} inconsistency(s) found:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ audit.json is consistent with indicator-registry.json")


if __name__ == "__main__":
    main()
