#!/usr/bin/env python3
"""System-level tests for run_audit.py — verify output shape, thresholds, and guardrails."""
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from jsonschema import Draft202012Validator
from evidence_isolation import inspect_manifest

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
    # strict order check — must match canonical registry
    canonical_ids = ["A1","A2","A3","B1","B2","B3","C1","C2","C3","D1","D2","D3","D4","E1","E2","F1","F2","F3","F4","F5","F6"]
    actual_ids = [row["subproject"] for row in register]
    assert actual_ids == canonical_ids, f"Indicator order mismatch!\nExpected: {canonical_ids}\nGot:      {actual_ids}"
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
    for expected_prefix in ("library", "benchmark", "context"):
        found = any(n.startswith(expected_prefix) for n in names)
        assert found, f"Missing input copy with prefix '{expected_prefix}' — got {names}"
    for key in ("library", "benchmark", "context"):
        assert manifest["input_files"].get(key, {}).get("sha256"), f"No sha256 for {key}"
    # Verify no absolute paths leaked
    for v in manifest["input_files"].values():
        assert "original_path" not in v, f"Absolute path leaked in manifest: {v}"
    # Verify git commit and script hash present
    if manifest.get("git_commit"):
        print(f'  git_commit: {manifest["git_commit"][:8]}')
    print(f'  run_audit_sha256: {manifest.get("run_audit_sha256","")[:12]}')
    print(f'  python_version: {manifest.get("python_version")}')

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

# Test: F4 rejects manual_review_required (pending, not resolved)
with tempfile.TemporaryDirectory() as temp:
    dedup_mrr = pathlib.Path(temp) / "dedup_mrr.json"
    dedup_mrr.write_text(json.dumps({
        "exact_identifier_groups": [{"stable_id": "doi:10.1000/1", "records": 1}],
        "possible_version_families": [
            {"title_year": ("test", "2025"), "stable_ids": ["arxiv:1234.5678", "doi:10.1000/2"],
             "decision": "manual_review_required"}
        ]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out),
                      extra_args=["--deduplication-log", str(dedup_mrr)])
    h = audit["library_health"]
    # manual_review_required is PENDING → should NOT be structured_decisions
    assert h.get("dedup_log_depth") == "structured_no_decisions", \
        f"Expected structured_no_decisions for manual_review_required, got {h.get('dedup_log_depth')}"
    f4_row = [r for r in audit["indicator_register"] if r["subproject"] == "F4"][0]
    assert f4_row["meets_standard"] != "pass", \
        f"F4 should not pass with manual_review_required, got {f4_row['meets_standard']}"

print("F4 manual_review_required guard: PASSED")

# Test: F4 PASSES on fully-resolved dedup log (all decisions resolved, no pending)
with tempfile.TemporaryDirectory() as temp:
    dedup_ok = pathlib.Path(temp) / "dedup_resolved.json"
    dedup_ok.write_text(json.dumps({
        "exact_identifier_groups": [{"stable_id": "doi:10.1000/1", "records": 1}],
        "possible_version_families": [
            {"title_year": ("test", "2025"), "stable_ids": ["arxiv:1234.5678", "doi:10.1000/2"],
             "decision": "merge"}
        ]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out),
                      extra_args=["--deduplication-log", str(dedup_ok)])
    h = audit["library_health"]
    # merge is a RESOLVED decision → structured_decisions, dedup_log_ok=True
    assert h.get("dedup_log_depth") == "structured_decisions", \
        f"Expected structured_decisions for resolved merge, got {h.get('dedup_log_depth')}"
    # F4_version_decisions should be "pass"
    assert h["checks"]["F4_version_decisions"] == "pass", \
        f"Expected F4_version_decisions=pass, got {h['checks']['F4_version_decisions']}"
    f4_row = [r for r in audit["indicator_register"] if r["subproject"] == "F4"][0]
    # F4 overall should be pass (both exact dups clean and version decisions resolved)
    assert f4_row["meets_standard"] == "pass", \
        f"F4 should pass with fully resolved decisions, got {f4_row['meets_standard']}"

print("F4 resolved-decisions pass guard: PASSED")

# Test: B discovery_only rounds → not_assessable, never 趋稳
with tempfile.TemporaryDirectory() as temp:
    # context with discovery_only rounds
    disco_ctx = pathlib.Path(temp) / "disco_context.json"
    disco_ctx.write_text(json.dumps({
        "review_type": "叙事综述",
        "planned_pathways": ["openalex-first-round"],
        "search_rounds": [
            {"pathway": "openalex-first-round", "completed": True,
             "core_before": 100, "included_high": 0,
             "discovery_candidates": 12,
             "screening_status": "discovery_only",
             "note": "auto-generated candidates"}
        ],
        "source_marginal_yields": [
            {"yield": 0.12, "screening_status": "discovery_only"}
        ]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(disco_ctx), str(out))
    proc = audit["process"]
    b1 = proc["checks"]["B1_ggr"]
    b2 = proc["checks"]["B2_drr"]
    # B1/B2 must be not_assessable when only discovery_only rounds exist
    assert b1 == "not_assessable", f"B1 should be not_assessable for discovery_only, got {b1}"
    assert b2 == "not_assessable", f"B2 should be not_assessable for discovery_only, got {b2}"
    assert proc["verdict"] != "趋稳", f"Verdict should not be 趋稳 for discovery_only, got {proc['verdict']}"

print("B discovery_only guard: PASSED")

# Test: F1 fails when only 1 of 3 queries is valid
with tempfile.TemporaryDirectory() as temp:
    partial_log = pathlib.Path(temp) / "partial_run_log.json"
    partial_log.write_text(json.dumps({
        "queries": [
            {"source": "openalex", "query": "complete", "fields": "title,doi", "date": "2026-01-01"},
            {"source": "crossref", "query": "incomplete"},  # no fields or date
            {"source": "arxiv", "query": "also incomplete"}
        ]
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out),
                      extra_args=["--run-log", str(partial_log)])
    f1_row = [r for r in audit["indicator_register"] if r["subproject"] == "F1"][0]
    # Only 1/3 queries valid → F1 should fail
    assert f1_row["meets_standard"] == "fail", \
        f"F1 should fail when only 1/3 queries valid, got {f1_row['meets_standard']}"
    ctx = audit.get("context", {})
    assert ctx.get("run_log_completeness") == 0.333, \
        f"Expected 0.333 completeness, got {ctx.get('run_log_completeness')}"

print("F1 partial log guard: PASSED")

# ── Test: registry validation passes for non-umbrella and umbrella ──
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out))
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "validate_registry.py"),
         "--audit", str(out / "audit.json")],
        capture_output=True, text=True, encoding="utf-8"
    )
    assert r.returncode == 0, f"Registry validation failed:\n{r.stdout}\n{r.stderr}"
    assert "[PASS]" in r.stdout
    print("Registry validation (non-umbrella): PASSED")

with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context_umbrella.json"), str(out))
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "validate_registry.py"),
         "--audit", str(out / "audit.json")],
        capture_output=True, text=True, encoding="utf-8"
    )
    assert r.returncode == 0, f"Registry validation (umbrella) failed:\n{r.stdout}\n{r.stderr}"
    assert "[PASS]" in r.stdout
    print("Registry validation (umbrella): PASSED")

# ── Test: schema — missing required field (project) ──
with tempfile.TemporaryDirectory() as temp:
    bad_rc = pathlib.Path(temp) / "bad_run_config.json"
    bad_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(bad_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should fail on missing 'project' field\nerr: {combined}"
    assert "project" in combined.lower(), \
        f"Error should mention missing project field\noutput: {combined}"

print("Schema guard (missing required field): PASSED")

# ── Test: schema — illegal review_type ──
with tempfile.TemporaryDirectory() as temp:
    bad_rc = pathlib.Path(temp) / "bad_run_config.json"
    bad_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test", "review_type": "invalid_type", "scope_status": "in_scope"},
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(bad_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should fail on illegal review_type\nerr: {combined}"
    assert "review_type" in combined, \
        f"Error should mention review_type\noutput: {combined}"

print("Schema guard (illegal review_type): PASSED")

# ── Test: schema — illegal scope_status ──
with tempfile.TemporaryDirectory() as temp:
    bad_rc = pathlib.Path(temp) / "bad_run_config.json"
    bad_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test", "review_type": "systematic", "scope_status": "bogus_status"},
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(bad_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should fail on illegal scope_status\nerr: {combined}"
    assert "scope_status" in combined, \
        f"Error should mention scope_status\noutput: {combined}"

print("Schema guard (illegal scope_status): PASSED")

# ── Test: scope — out_of_scope refuses full evaluation ──
with tempfile.TemporaryDirectory() as temp:
    oos_rc = pathlib.Path(temp) / "oos_run_config.json"
    oos_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test", "review_type": "systematic", "scope_status": "out_of_scope"},
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(oos_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should refuse out_of_scope without --allow-out-of-scope\nerr: {combined}"
    assert "out_of_scope" in combined.lower(), \
        f"Error should mention out_of_scope\noutput: {combined}"

print("Scope guard (out_of_scope refusal): PASSED")

# ── Test: scope — out_of_scope + --allow-out-of-scope runs successfully ──
with tempfile.TemporaryDirectory() as temp:
    oos_rc = pathlib.Path(temp) / "oos_run_config.json"
    oos_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test", "review_type": "systematic", "scope_status": "out_of_scope"},
        "library": {"provided": True, "path": str(root / "tests" / "library.json"), "format": "json"},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(oos_rc), "--allow-out-of-scope",
         "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode == 0, f"Should succeed with --allow-out-of-scope\noutput: {combined}"
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    # out_of_scope override must be recorded in context
    ctx = audit.get("context", {})
    assert ctx.get("_scope_override_active") is True, \
        f"_scope_override_active should be True in context, got: {ctx}"
    assert ctx.get("scope_status") == "out_of_scope", \
        f"scope_status should be out_of_scope, got: {ctx.get('scope_status')}"

print("Scope guard (allow-out-of-scope override): PASSED")

# ── Test: schema — research_question empty is rejected ──
with tempfile.TemporaryDirectory() as temp:
    bad_rc = pathlib.Path(temp) / "bad_run_config.json"
    bad_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "", "review_type": "systematic", "scope_status": "in_scope"},
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(bad_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should fail on empty research_question\nerr: {combined}"
    assert "research_question" in combined, \
        f"Error should mention research_question\noutput: {combined}"

print("Schema guard (empty research_question): PASSED")

# ── Test: the checked-in JSON Schema itself validates the canonical fixture ──
schema = json.loads((root / "schemas" / "run-config-schema.json").read_text(encoding="utf-8"))
fixture = json.loads((root / "tests" / "run-config-test.json").read_text(encoding="utf-8"))
schema_errors = list(Draft202012Validator(schema).iter_errors(fixture))
assert not schema_errors, "Canonical run-config fixture violates run-config-schema.json: " + "; ".join(
    error.message for error in schema_errors
)
print("Schema contract (canonical fixture): PASSED")

# ── Test: nested project requirements are enforced ──
with tempfile.TemporaryDirectory() as temp:
    incomplete_rc = pathlib.Path(temp) / "incomplete_run_config.json"
    incomplete_rc.write_text(json.dumps({
        "schema_version": "1.0",
        "project": {"research_question": "test"},
        "library": {"provided": False},
        "automation": {"allow_search": False},
        "output": {}
    }), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_audit.py"),
         "--run-config", str(incomplete_rc),
         "--out", str(pathlib.Path(temp) / "out")],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    combined = (r.stderr or "") + (r.stdout or "")
    assert r.returncode != 0, f"Should fail when nested project fields are missing\noutput: {combined}"
    assert "review_type" in combined and "scope_status" in combined, \
        f"Error should name missing nested fields\noutput: {combined}"

print("Schema guard (nested project fields): PASSED")

# ── Test: procedural evidence isolation detects leakage and A/B reuse ──
with tempfile.TemporaryDirectory() as temp:
    manifest = {
        "schema_version": "1.0",
        "datasets": {
            "dev": {"role": "dev", "item_ids": ["doi:10.1000/dev"],
                    "source_routes": ["db_boolean"], "used_tested_query": True,
                    "used_for_query_optimization": True, "frozen_at": "2026-07-22"},
            "validation": {"role": "validation", "item_ids": ["doi:10.1000/val"],
                            "source_routes": ["backward_citation"], "used_tested_query": True,
                            "used_for_query_optimization": False, "frozen_at": "2026-07-22"}
        },
        "relationships": {
            "a2_validation_dataset": "validation",
            "b3_validation_dataset": "validation",
            "a3_source_ids": ["snapshot-openalex"],
            "b2_pathway_source_ids": ["snapshot-openalex"]
        }
    }
    report = inspect_manifest(manifest)
    assert report["status"] == "invalid"
    assert report["a2_validation_independent"] is False
    assert report["a2_b3_shared_validation"] is True
    assert report["a3_b2_overlap"] is True

print("Evidence isolation leakage guard: PASSED")

# ── Test: evidence manifest conforms to its declared JSON contract ──
manifest_schema = json.loads((root / "schemas" / "evidence-manifest-schema.json").read_text(encoding="utf-8"))
manifest_errors = list(Draft202012Validator(manifest_schema).iter_errors(manifest))
assert not manifest_errors, [error.message for error in manifest_errors]

print("Evidence manifest schema guard: PASSED")

# ── Test: run_audit downgrades reused evidence instead of claiming A/B independence ──
with tempfile.TemporaryDirectory() as temp:
    manifest_path = pathlib.Path(temp) / "evidence-manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": "1.0",
        "datasets": {
            "validation": {"role": "validation", "item_ids": ["doi:10.1000/val"],
                            "source_routes": ["backward_citation"], "used_tested_query": True,
                            "used_for_query_optimization": False, "frozen_at": "2026-07-22"}
        },
        "relationships": {
            "a2_validation_dataset": "validation",
            "b3_validation_dataset": "validation",
            "a3_source_ids": ["snapshot-openalex"],
            "b2_pathway_source_ids": ["snapshot-openalex"]
        }
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out), extra_args=[
        "--evidence-manifest", str(manifest_path)
    ])
    assert audit["coverage"]["a2"]["status"] == "estimated"
    assert audit["process"]["checks"]["B2_drr"] == "not_assessable"
    assert audit["process"]["checks"]["B3_independent_validation"] == "not_assessable"
    assert audit["context"]["evidence_integrity"]["a3_b2_overlap"] is True

print("Evidence reuse downgrade: PASSED")

# ── Test: independent validation recall from search_meta is the A2 primary value ──
with tempfile.TemporaryDirectory() as temp:
    search_meta = pathlib.Path(temp) / "search_meta.json"
    search_meta.write_text(json.dumps({
        "a2_evidence_status": "measured",
        "validation_recall": 0.75,
        "validation_recall_total": 4,
        "dev_recall": 1.0,
        "dev_recall_total": 4
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    audit = run_audit(str(root / "tests" / "context.json"), str(out), extra_args=[
        "--search-meta", str(search_meta)
    ])
    assert audit["coverage"]["a2"]["recall"] == 0.75
    assert audit["coverage"]["a2"]["total"] == 4
    assert audit["coverage"]["a2"]["matched"] == 3
    assert "A2 主值来自 search_meta" in audit["coverage"]["a2"]["note"]

print("Independent validation primary-value guard: PASSED")

# ── Test: q0 and first-round search metadata are visible without an iteration log ──
with tempfile.TemporaryDirectory() as temp:
    search_meta = pathlib.Path(temp) / "search_meta.json"
    search_meta.write_text(json.dumps({
        "query_versions": [{
            "query_id": "q0", "origin": "user_provided", "change_type": "initial",
            "query": '("defect detection") AND ("transfer learning")',
            "source": "OpenAlex", "execution_date": "2026-07-22",
            "hits": 17, "status": "complete"
        }],
        "initial_query_origin": "user_provided",
        "dev_recall": 0.8,
        "dev_recall_total": 5,
        "validation_recall": 0.75,
        "validation_recall_total": 4,
        "validation_source": "held-out citation tracking"
    }), encoding="utf-8")
    out = pathlib.Path(temp) / "out"
    run_audit(str(root / "tests" / "context.json"), str(out), extra_args=[
        "--search-meta", str(search_meta)
    ])
    markdown = (out / "audit.md").read_text(encoding="utf-8")
    assert "## 检索策略与迭代过程" in markdown
    assert "检索式起点与版本" in markdown
    assert '("defect detection") AND ("transfer learning")' in markdown
    assert "首轮诊断：dev_recall=0.800（n=5）；validation_recall=0.750（n=4）" in markdown
    assert "当前仅记录了首轮检索/诊断" in markdown

print("Search strategy report section: PASSED")

print("\nAll tests passed.")
