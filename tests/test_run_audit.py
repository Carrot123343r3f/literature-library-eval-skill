#!/usr/bin/env python3
"""System-level tests for run_audit.py — verify output shape, thresholds, and guardrails."""
import json
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]

def run_audit(context_file, out_dir, extra_args=None):
    """Run run_audit.py with standard test inputs and return audit JSON."""
    args = [sys.executable, str(root / "scripts" / "run_audit.py"),
            "--library", str(root / "tests" / "library.json"),
            "--benchmark", str(root / "tests" / "benchmark.json"),
            "--gold", str(root / "tests" / "gold.json"),
            "--query-hits", str(root / "tests" / "zero-hits.json"),
            "--candidate-snapshots", str(root / "tests" / "snapshot.json"),
            "--context", context_file,
            "--out", out_dir]
    if extra_args:
        args.extend(extra_args)
    subprocess.run(args, check=True)
    return json.loads((pathlib.Path(out_dir) / "audit.json").read_text(encoding="utf-8"))

# ── Baseline test (existing) ──
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out))
    assert audit["coverage"]["a1"]["recall"] == 0.5
    assert audit["coverage"]["a2"]["status"] == "measured"
    assert audit["coverage"]["a2"]["recall"] == 0.0
    assert audit["coverage"]["a3"]["deduplicated_candidate_lower_bound"] == 3
    assert "empty_topic" in audit["topic_balance"]["flags"]
    assert audit["balance"]["top_source_share"] == 0.5
    assert audit["recency"]["recent_share"] == 1.0
    assert (out / "audit.md").exists() and (out / "audit.html").exists()
    markdown = (out / "audit.md").read_text(encoding="utf-8")
    assert "| 维度 | 编号 | 评估项 | 标准 | 判定 | 当前值 | 证据状态 | 说明与行动 |" in markdown
    register = audit["indicator_register"]
    assert len(register) == 21
    assert {row["subproject"] for row in register} >= {"A1", "B1", "C1", "D1", "E1", "F6"}
    # non-umbrella: A4/C4/F7 absent
    assert "A4" not in {row["subproject"] for row in register}
    assert "C4" not in {row["subproject"] for row in register}
    assert "F7" not in {row["subproject"] for row in register}
    # dedup depth exists
    assert "dedup_log_depth" in audit["library_health"]
    # normalize_candidates
    normalized = pathlib.Path(temp) / "normalized"
    subprocess.run([sys.executable, str(root / "scripts" / "normalize_candidates.py"),
                    "--snapshot", str(root / "tests" / "snapshot.json"),
                    "--out", str(normalized)], check=True)
    dedup = json.loads((normalized / "deduplication-log.json").read_text(encoding="utf-8"))
    assert len(dedup["exact_identifier_groups"]) == 3

print("Baseline tests: PASSED")

# ── Test: umbrella review → 24 rows ──
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context_umbrella.json"), str(out))
    register = audit["indicator_register"]
    assert len(register) == 24, f"Expected 24 umbrella rows, got {len(register)}"
    subs = {r["subproject"] for r in register}
    assert "A4" in subs; assert "C4" in subs; assert "F7" in subs
    assert "AMSTAR-2" in audit["summary"]
    assert any("AMSTAR-2" in l for l in audit["limitations"])
    assert audit["umbrella"]["a4"] is not None
    # umbrella thresholds
    assert float(audit["standards"]["a1_min_recall"]) == 0.90
    assert float(audit["standards"]["f_access_rate"]) == 0.85

print("Umbrella 24-row test: PASSED")

# ── Test: rapid review thresholds ──
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context_rapid.json"), str(out))
    assert float(audit["standards"]["a2_min_recall"]) == 0.60
    assert float(audit["standards"]["f_access_rate"]) == 0.50
    assert len(audit["indicator_register"]) == 21

print("Rapid review thresholds: PASSED")

# ── Test: manifest + input copy ──
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "input_files" in manifest
    inputs_dir = out / "inputs"
    assert inputs_dir.is_dir()
    names = [p.name for p in inputs_dir.iterdir()]
    for expected in ("library.json", "benchmark.json", "context.json"):
        assert expected in names, f"Missing input copy: {expected} — got {names}"
    for key in ("library", "benchmark", "context"):
        assert manifest["input_files"].get(key, {}).get("sha256"), f"No sha256 for {key}"

print("Manifest + input copy: PASSED")

# ── Test: F1 fails on run_log with only source+query (no fields) ──
with tempfile.TemporaryDirectory() as temp:
    # Create a shallow run log — has source+query+date but no fields
    shallow_log = pathlib.Path(temp) / "shallow_run_log.json"
    shallow_log.write_text(json.dumps({
        "queries": [{"source": "openalex", "query": "test", "date": "2026-07-20"}]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out),
                      extra_args=["--run-log", str(shallow_log)])
    # F1 should fail because "fields" is missing
    f1_row = [r for r in audit["indicator_register"] if r["subproject"] == "F1"][0]
    assert f1_row["meets_standard"] in ("fail", "not_assessable"), \
        f"F1 should fail/not_assessable for log without fields, got {f1_row['meets_standard']}"
    assert audit.get("context", {}).get("run_log_complete") is not True

print("F1 shallow run-log guard: PASSED")

# ── Test: F4 fails on dedup log with candidates but no decisions ──
with tempfile.TemporaryDirectory() as temp:
    # Create a dedup log that has version families but no decisions
    shallow_dedup = pathlib.Path(temp) / "shallow_dedup.json"
    shallow_dedup.write_text(json.dumps({
        "exact_identifier_groups": [{"stable_id": "doi:10.1000/1", "records": 1}],
        "possible_version_families": [
            {"title_year": ("test", "2025"), "stable_ids": ["arxiv:1234.5678", "doi:10.1000/2"]}
            # no "decision" field!
        ]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out),
                      extra_args=["--deduplication-log", str(shallow_dedup)])
    f4_row = [r for r in audit["indicator_register"] if r["subproject"] == "F4"][0]
    # F4_version_decisions should not pass — no actual decisions
    h = audit["library_health"]
    assert h.get("dedup_log_depth") in ("structured_no_decisions", "parseable_but_shallow", "unparseable"), \
        f"Expected dedup_log_depth to reflect no decisions, got {h.get('dedup_log_depth')}"
    # F4 overall should NOT be pure pass
    assert f4_row["meets_standard"] != "pass", \
        f"F4 should not pass when version candidates lack decisions, got {f4_row['meets_standard']}"

print("F4 no-decision guard: PASSED")

print("\nAll tests passed.")
