"""End-to-end contracts for the guided runner's offline and denied paths."""
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]


def config(path, *, allow_search=False, allow_external_discovery=False):
    payload = {
        "schema_version": "1.0",
        "project": {"research_question": "robot localization", "review_type": "systematic",
                    "scope_status": "in_scope", "allowed_assessment_level": "full"},
        "library": {"provided": False},
        "automation": {"allow_search": allow_search,
                       "allow_external_discovery": allow_external_discovery,
                       "allow_metadata_enrichment": False,
                       "allow_citation_tracking": False,
                       "local_only_confirmed": False,
                       "allowed_sources": ["arxiv"] if allow_search else []},
        "output": {"formats": ["html", "json"]},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def run(config_path, out, *extra):
    return subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run",
        "--run-config", str(config_path), "--library", str(ROOT / "tests" / "library.json"),
        "--out", str(out), *map(str, extra),
    ], capture_output=True, text=True, encoding="utf-8")


def test_offline_full_workflow_is_resumable_and_records_lineage(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    out = tmp_path / "out"
    first = run(run_config, out)
    assert first.returncode == 0, first.stderr
    assert (out / "sufficiency-precheck.html").is_file()
    assert (out / "sufficiency-precheck.json").is_file()

    resumed = run(run_config, out, "--resume")
    assert resumed.returncode == 0, resumed.stderr
    assert (out / "sufficiency-precheck.json").is_file()


def test_run_config_alone_completes_full_audit_and_archives_evidence(tmp_path):
    records = [{"title": f"Robot localization evidence {index}", "year": 2024,
                "language": "en", "DOI": f"10.1000/e2e{index}"} for index in range(3)]
    heldout = [{"title": row["title"], "year": 2024, "language": "en", "DOI": row["DOI"]} for row in records]
    for name, payload in {
        "library.json": records, "gold.json": heldout, "hits.json": heldout,
        "benchmark.json": heldout,
        "query-log.json": {"queries": [{"source": "openalex", "query": "robot localization", "fields": ["title"], "date": "2026-07-30"}]},
        "screening.json": {"decisions": [{"candidate_id": f"10.1000/e2e{index}", "decision": "include", "reason": "in scope"} for index in range(3)]},
        "pathways.json": [{"pathway_id": "db", "type": "db_boolean", "completed": True, "screening_status": "screened_complete", "yield": 0.0, "candidate_ids": [f"10.1000/e2e{index}" for index in range(3)], "screened_candidate_ids": [f"10.1000/e2e{index}" for index in range(3)]},
                           {"pathway_id": "backward", "type": "backward_citation", "completed": True, "screening_status": "screened_complete", "yield": 0.0, "candidate_ids": [f"10.1000/e2e{index}" for index in range(3)], "screened_candidate_ids": [f"10.1000/e2e{index}" for index in range(3)]},
                           {"pathway_id": "forward", "type": "forward_citation", "completed": True, "screening_status": "screened_complete", "yield": 0.0, "candidate_ids": [f"10.1000/e2e{index}" for index in range(3)], "screened_candidate_ids": [f"10.1000/e2e{index}" for index in range(3)]},
                           {"pathway_id": "related", "type": "related_articles", "completed": True, "screening_status": "screened_complete", "yield": 0.0, "candidate_ids": [f"10.1000/e2e{index}" for index in range(3)], "screened_candidate_ids": [f"10.1000/e2e{index}" for index in range(3)]}],
        "context.json": {"review_type": "systematic", "scope_status": "in_scope", "year_start": 2020, "year_end": 2026, "languages": ["en"]},
        "iterations.json": {"dev_validation_overlap_check": True, "dev_set": [{"doi": f"10.1000/dev{index}"} for index in range(3)],
                            "validation_set": [{"doi": f"10.1000/tuning{index}"} for index in range(3)], "heldout_test_set": heldout,
                            "iterations": [{"iteration_id": "v1", "change_type": "initial", "change_description": "initial", "change_source": "user_confirmed", "queries": {"db": "robot localization"}, "execution_date": "2026-07-30", "results": {"dev_recall": 1.0}, "decision": "continue"}]},
    }.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    run_config = tmp_path / "run-config.json"
    payload = {"schema_version": "1.0",
               "project": {"research_question": "robot localization", "review_type": "systematic", "scope_status": "in_scope", "time_range": {"start": 2020, "end": 2026}, "languages": ["en"]},
               "library": {"provided": True, "path": "library.json", "format": "json"},
               "automation": {"allow_search": False, "allowed_sources": []},
               "output": {"language": "en", "formats": ["html", "json"]},
               "evidence_inputs": {"context": "context.json", "benchmark": "benchmark.json", "gold": "gold.json", "query_hits": "hits.json", "query_log": "query-log.json", "screening_decisions": "screening.json", "search_iterations": "iterations.json", "independent_pathways": "pathways.json"}}
    run_config.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "out"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run", "--run-config", str(run_config), "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (out / "audit" / "audit.html").is_file()
    report = json.loads((out / "audit" / "audit.json").read_text(encoding="utf-8"))
    assert any(row["evidence_status"] == "measured" for row in report["indicator_register"])
    assert report["scope_routing"]["scope_status"] == "in_scope"
    manifest = json.loads((out / "audit" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input_files"]["independent-pathways"]["archive_status"] == "redacted_json_copy"
    assert str(tmp_path) not in (out / "audit" / "audit.html").read_text(encoding="utf-8")

    # A same-name output is not reusable merely because it still exists.  Its
    # recorded ledger hash must match before --resume can skip the audit step.
    (out / "audit" / "audit.json").write_text('{"tampered": true}', encoding="utf-8")
    resumed = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run",
                               "--run-config", str(run_config), "--out", str(out), "--resume"],
                              capture_output=True, text=True, encoding="utf-8")
    assert resumed.returncode != 0
    assert "SHA-256 mismatch: audit/audit.json" in resumed.stderr
    state = json.loads((out / "workflow-state.json").read_text(encoding="utf-8"))
    assert state["steps"]["audit"] == "tampered_or_stale"
    assert state["steps"]["actions"] == "stale_upstream"

    (tmp_path / "pathways.json").write_text(json.dumps([
        {"pathway_id": "db", "type": "db_boolean", "completed": True, "screening_status": "screened_complete", "yield": 0.0}
        for _ in range(4)
    ]), encoding="utf-8")
    (tmp_path / "screening.json").write_text(json.dumps({"decisions": [
        {"candidate_id": "10.1000/not-in-hits", "decision": "include", "reason": "in scope"}
    ]}), encoding="utf-8")
    blocked = tmp_path / "blocked"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run", "--run-config", str(run_config), "--out", str(blocked)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    precheck = json.loads((blocked / "sufficiency-precheck.json").read_text(encoding="utf-8"))
    reasons = " ".join(precheck["missing_minimum_inputs"])
    assert "unique" in reasons and "distinct pathway types" in reasons
    assert "outside query hits" in reasons
    assert not (blocked / "audit" / "audit.html").exists()

    (tmp_path / "library.csv").write_text("title,year,language,DOI\n" + "\n".join(
        f"Robot localization evidence {index},2024,en,10.1000/e2e{index}" for index in range(3)
    ), encoding="utf-8")
    csv_config = dict(payload)
    csv_config["library"] = {"provided": True, "path": "library.csv", "format": "csv"}
    csv_config_path = tmp_path / "csv-run-config.json"
    csv_config_path.write_text(json.dumps(csv_config), encoding="utf-8")
    # Restore valid evidence before exercising the non-JSON normalization path.
    (tmp_path / "pathways.json").write_text(json.dumps([
        {"pathway_id": path_id, "type": path_type, "completed": True, "screening_status": "screened_complete", "yield": 0.0,
         "candidate_ids": [f"10.1000/e2e{index}" for index in range(3)], "screened_candidate_ids": [f"10.1000/e2e{index}" for index in range(3)]}
        for path_id, path_type in (("db", "db_boolean"), ("backward", "backward_citation"), ("forward", "forward_citation"), ("related", "related_articles"))
    ]), encoding="utf-8")
    (tmp_path / "screening.json").write_text(json.dumps({"decisions": [
        {"candidate_id": f"10.1000/e2e{index}", "decision": "include", "reason": "in scope"} for index in range(3)
    ]}), encoding="utf-8")
    csv_out = tmp_path / "csv-out"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run", "--run-config", str(csv_config_path), "--out", str(csv_out)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (csv_out / "audit" / "audit.html").is_file()
    assert all(str(tmp_path).encode("utf-8") not in path.read_bytes() for path in csv_out.rglob("*") if path.is_file())

    autopilot_out = tmp_path / "autopilot-csv"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "autopilot.py"), "--question", "robot localization",
                             "--library", str(tmp_path / "library.csv"), "--out", str(autopilot_out), "--offline",
                             "--scope-status", "in_scope", "--mode", "sufficiency-audit", "--review-type", "systematic",
                             "--time-start", "2020", "--time-end", "2026", "--languages", "en", "--output-language", "en",
                             "--gold", str(tmp_path / "gold.json"), "--query-hits", str(tmp_path / "hits.json"),
                             "--query-log", str(tmp_path / "query-log.json"), "--screening-decisions", str(tmp_path / "screening.json"),
                             "--search-iterations", str(tmp_path / "iterations.json"), "--independent-pathways", str(tmp_path / "pathways.json")], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    resolved = autopilot_out / "resolved-run-config.json"
    assert resolved.is_file()
    replay_out = tmp_path / "csv-replay"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "run", "--run-config", str(resolved), "--out", str(replay_out)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert (replay_out / "audit" / "audit.html").is_file()


def test_collection_permission_is_rejected_before_any_online_step(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    plan = tmp_path / "query-plan.json"
    plan.write_text(json.dumps({"arxiv": "robot localization"}), encoding="utf-8")
    result = run(run_config, tmp_path / "out", "--collect", "--query-plan", plan)
    assert result.returncode != 0
    assert "allow_external_discovery" in result.stderr


def test_init_uses_three_questions_and_creates_a_local_first_config(tmp_path):
    output = tmp_path / "run-config.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "init", "--out", str(output),
    ], input="robot localization\ny\n\n", capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    config_data = json.loads(output.read_text(encoding="utf-8"))
    assert config_data["project"]["scope_status"] == "in_scope"
    assert config_data["project"]["review_type"] == "narrative"
    assert config_data["automation"]["allow_search"] is False
    assert config_data["automation"]["local_only_confirmed"] is False
    assert "Allow online" not in result.stdout


def test_init_accepts_noninteractive_flags_and_reports_missing_input_cleanly(tmp_path):
    output = tmp_path / "run-config.json"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "init", "--out", str(output),
        "--question", "robot localization", "--scope-status", "in_scope", "--library", "library.json",
    ], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    config_data = json.loads(output.read_text(encoding="utf-8"))
    assert config_data["project"]["scope_status"] == "in_scope"
    assert config_data["library"]["path"] == "library.json"
    missing = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "init", "--out", str(tmp_path / "missing.json"),
    ], input="", capture_output=True, text=True, encoding="utf-8")
    assert missing.returncode != 0
    assert "interactive input is unavailable" in missing.stderr
    assert "Traceback" not in missing.stderr


def test_configure_permissions_records_explicit_online_authorization(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "configure-permissions", "--run-config", str(run_config),
    ], input="n\ny\nn\nn\nn\narxiv\n\n\n", capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    config_data = json.loads(run_config.read_text(encoding="utf-8"))
    assert config_data["automation"]["allow_search"] is True
    assert config_data["automation"]["allow_metadata_enrichment"] is True
    assert config_data["automation"]["local_only_confirmed"] is False
    assert config_data["automation"]["allowed_sources"] == ["arxiv"]
    assert "Current permissions:" in result.stdout


def test_configure_permissions_accepts_noninteractive_flags(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "configure-permissions",
        "--run-config", str(run_config), "--non-interactive", "--allow-external-discovery",
        "--online-sources", "arxiv", "--offline-snapshot-sources", "scopus",
    ], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    automation = json.loads(run_config.read_text(encoding="utf-8"))["automation"]
    assert automation["allow_external_discovery"] is True
    assert automation["online_allowed_sources"] == ["arxiv"]
    assert automation["offline_snapshot_sources"] == ["scopus"]


def test_unsupported_permission_source_leaves_config_unchanged(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    before = run_config.read_bytes()
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "configure-permissions", "--run-config", str(run_config),
    ], input="n\nn\nn\ny\nn\nunsupported-source\n", capture_output=True, text=True, encoding="utf-8")
    assert result.returncode != 0
    assert "no live connector" in result.stderr
    assert run_config.read_bytes() == before


def test_configure_permissions_records_explicit_local_choice_and_clears_sources(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config, allow_search=True, allow_external_discovery=True)
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "configure-permissions", "--run-config", str(run_config),
    ], input="y\n", capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    automation = json.loads(run_config.read_text(encoding="utf-8"))["automation"]
    assert automation["local_only_confirmed"] is True
    assert all(automation[key] is False for key in ("allow_search", "allow_metadata_enrichment", "allow_external_discovery", "allow_citation_tracking"))
    assert automation["allowed_sources"] == []


def test_configure_permissions_validates_existing_config_before_prompting(tmp_path):
    run_config = tmp_path / "run-config.json"
    config(run_config)
    malformed = json.loads(run_config.read_text(encoding="utf-8"))
    malformed["automation"] = "not an object"
    run_config.write_text(json.dumps(malformed), encoding="utf-8")
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "run_full_audit.py"), "configure-permissions", "--run-config", str(run_config),
    ], input="y\n", capture_output=True, text=True, encoding="utf-8")
    assert result.returncode != 0
    assert "invalid run-config" in result.stderr
    assert "Confirm fully local" not in result.stdout
