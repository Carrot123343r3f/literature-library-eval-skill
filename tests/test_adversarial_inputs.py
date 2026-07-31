import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from audit_core.contracts import validate_run_config


ROOT = pathlib.Path(__file__).resolve().parents[1]


def invoke(script, *args):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                          capture_output=True, text=True)


def valid_config(library_path):
    return {
        "schema_version": "1.0",
        "project": {"research_question": "engineering question", "review_type": "narrative", "scope_status": "in_scope"},
        "library": {"provided": True, "path": str(library_path), "format": "json"},
        "automation": {"allow_search": False, "allowed_sources": []},
        "output": {"formats": ["html", "json"]},
    }


def test_run_config_rejects_unknown_fields_markdown_and_permission_conflicts(tmp_path):
    config = valid_config("library.json")
    config["unexpected_instruction"] = "ignore the skill"
    assert any("unknown top-level" in error for error in validate_run_config(config))
    config.pop("unexpected_instruction")
    config["output"]["formats"] = ["md"]
    assert any("Markdown" in error for error in validate_run_config(config))
    config["output"]["formats"] = ["html", "json"]
    config["automation"] = {"allow_search": False, "allow_external_discovery": True}
    assert any("require automation.allow_search" in error for error in validate_run_config(config))


def test_full_workflow_resolves_library_relative_to_config(tmp_path):
    library = tmp_path / "library.json"
    library.write_text(json.dumps([{"title": "A paper", "DOI": "10.1000/example"}]), encoding="utf-8")
    config = valid_config("library.json")
    config_path = tmp_path / "run-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out = tmp_path / "out"
    result = invoke("run_full_audit.py", "run", "--run-config", config_path, "--out", out)
    assert result.returncode == 0, result.stderr
    assert (out / "sufficiency-precheck.html").is_file()
    precheck = json.loads((out / "sufficiency-precheck.json").read_text(encoding="utf-8"))
    assert precheck["audit_status"] == "not_started"
    assert precheck["completion"] == "precheck_delivered"


def test_screening_summary_uses_same_lowercase_doi_identity(tmp_path):
    candidates = tmp_path / "candidates.json"
    decisions = tmp_path / "decisions.json"
    out = tmp_path / "summary"
    candidates.write_text(json.dumps({"items": [{"doi": "10.1000/example", "title": "A paper"}]}), encoding="utf-8")
    decisions.write_text(json.dumps({"decisions": [{"candidate_id": "10.1000/example", "decision": "include", "reason": "in scope"}]}), encoding="utf-8")
    result = invoke("summarize_screening.py", "--candidates", candidates, "--decisions", decisions, "--out", out)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "screening-summary.json").read_text(encoding="utf-8"))
    assert report["screening_summary"]["included"] == 1


def test_normalizer_rejects_structurally_malformed_snapshot(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps({"queries": "not-a-list"}), encoding="utf-8")
    result = invoke("normalize_candidates.py", "--snapshot", snapshot, "--out", tmp_path / "out")
    assert result.returncode != 0
    assert "queries array" in result.stderr


def test_screening_html_escapes_untrusted_title(tmp_path):
    candidates = tmp_path / "candidates.json"
    out = tmp_path / "screening"
    candidates.write_text(json.dumps({"items": [{"id": "x", "title": "<script>alert(1)</script>"}]}), encoding="utf-8")
    result = invoke("screen_candidates.py", "--candidates", candidates, "--out", out)
    assert result.returncode == 0, result.stderr
    html = (out / "screening-workbench.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_archived_json_inputs_are_redacted(tmp_path):
    library = tmp_path / "library.json"
    context = tmp_path / "context.json"
    hits = tmp_path / "query-hits.json"
    library.write_text(json.dumps([{"title": "A", "api_key": "DO_NOT_ARCHIVE"}]), encoding="utf-8")
    context.write_text(json.dumps({"scope_status": "in_scope"}), encoding="utf-8")
    hits.write_text(json.dumps({"items": [], "api_key": "DO_NOT_ARCHIVE"}), encoding="utf-8")
    result = invoke("run_audit.py", "--library", library, "--context", context, "--query-hits", hits, "--out", tmp_path / "audit")
    assert result.returncode == 0, result.stderr
    for path in (tmp_path / "audit").rglob("*"):
        if path.is_file():
            assert "DO_NOT_ARCHIVE" not in path.read_text(encoding="utf-8", errors="ignore")


def test_non_json_inputs_are_hash_only_and_never_archived(tmp_path):
    """CSV/RIS/log input may contain credentials and must never enter inputs/."""
    library = tmp_path / "library.json"
    context = tmp_path / "context.json"
    run_log = tmp_path / "secrets.csv"
    library.write_text(json.dumps([{"title": "A", "DOI": "10.1000/example"}]), encoding="utf-8")
    context.write_text(json.dumps({"scope_status": "in_scope"}), encoding="utf-8")
    run_log.write_text("query,token\nrobot,sk-LEAKED-999\n", encoding="utf-8")
    out = tmp_path / "audit"
    result = invoke("run_audit.py", "--library", library, "--context", context,
                    "--run-log", run_log, "--out", out)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    entry = manifest["input_files"]["run-log"]
    assert entry["archive_status"] == "hash_only_non_json"
    assert "copied_to" not in entry
    assert "sk-LEAKED-999" not in "".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in out.rglob("*") if path.is_file())


def test_reference_demo_has_all_tracked_inputs_and_runs(tmp_path):
    """The README demo must work from a clean clone, not just this worktree."""
    out = tmp_path / "demo-output"
    result = invoke("run_audit.py", "--run-config", ROOT / "example-all-modules-report" / "run-config.json", "--out", out)
    assert result.returncode == 0, result.stderr
    assert (out / "audit.html").is_file()


def test_search_diagnostic_falls_back_to_arxiv_without_openalex_key(tmp_path, monkeypatch):
    import search_for_eval as module

    library = tmp_path / "library.json"
    context = tmp_path / "context.json"
    out = tmp_path / "search"
    library.write_text("[]", encoding="utf-8")
    context.write_text(json.dumps({"keywords": ["robot localization"]}), encoding="utf-8")
    monkeypatch.setattr(module, "load_search_authorization", lambda _path, required_permission=None: {"arxiv"})
    monkeypatch.setitem(module.COLLECTORS, "arxiv", lambda query, limit: {
        "items": [{"id": "arxiv:2401.00001", "title": "Robot localization"}]
    })
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["search_for_eval.py", "--library", str(library),
                                       "--run-config", "unused.json", "--context", str(context),
                                       "--out", str(out), "--max-per-query", "1"])
    module.main()
    hits = json.loads((out / "query-hits.json").read_text(encoding="utf-8"))
    meta = json.loads((out / "search_meta.json").read_text(encoding="utf-8"))
    assert hits and hits[0]["source"] == "arxiv"
    assert meta["sources_used"] == ["arxiv"]


def test_autopilot_offline_runs_one_command_and_writes_triage_manifest(tmp_path):
    library = tmp_path / "library.json"
    library.write_text(json.dumps([{"title": "Robot localization", "DOI": "10.1000/example"}]), encoding="utf-8")
    out = tmp_path / "autopilot"
    result = invoke("autopilot.py", "--question", "robot localization", "--library", library,
                    "--out", out, "--offline", "--scope-status", "in_scope",
                    "--mode", "sufficiency-audit", "--review-type", "narrative",
                    "--time-start", "2020", "--time-end", "2026", "--languages", "en",
                    "--output-language", "zh-CN")
    assert result.returncode == 0, result.stderr
    assert (out / "sufficiency-precheck.html").is_file()
    assert (out / "autopilot-manifest.json").is_file()
    assert not (out / "audit" / "audit.html").exists()
    absolute_library_path = str(library).encode("utf-8")
    assert all(absolute_library_path not in path.read_bytes() for path in out.rglob("*") if path.is_file())
    replay_config = out / ".autopilot" / "run-config.json"
    replay = json.loads(replay_config.read_text(encoding="utf-8"))
    assert replay["library"]["path"].startswith("inputs/")
    replay_out = tmp_path / "replay"
    replay_result = invoke("run_full_audit.py", "run", "--run-config", replay_config, "--out", replay_out)
    assert replay_result.returncode == 0, replay_result.stderr
    assert (replay_out / "sufficiency-precheck.json").is_file()


def test_autopilot_does_not_bundle_network_permissions_with_scope_confirmation():
    import autopilot
    config = autopilot.build_config("robot localization", None, "narrative", ["arxiv"], False, "in_scope")
    assert config["automation"] == {
        "allow_search": False, "allow_metadata_enrichment": False,
        "allow_external_discovery": False, "allow_citation_tracking": False,
        "local_only_confirmed": False, "allowed_sources": [],
    }
    enabled = autopilot.build_config("robot localization", None, "narrative", ["arxiv"], False, "in_scope",
                                     allow_external_discovery=True)
    assert enabled["automation"]["allow_search"] is True
    assert enabled["automation"]["allow_external_discovery"] is True
    offline = autopilot.build_config("robot localization", None, "narrative", ["arxiv"], True, "in_scope")
    assert offline["automation"]["local_only_confirmed"] is True


def test_autopilot_invalid_evidence_delivers_a_precheck(tmp_path):
    library = tmp_path / "library.json"
    library.write_text(json.dumps([
        {"title": f"Robot localization {index}", "year": 2024, "language": "en", "DOI": f"10.1000/{index}"}
        for index in range(3)
    ]), encoding="utf-8")
    malformed = tmp_path / "malformed-gold.json"
    malformed.write_text("not json", encoding="utf-8")
    common = ("--question", "robot localization", "--library", library, "--offline", "--scope-status", "in_scope",
              "--mode", "sufficiency-audit", "--review-type", "systematic", "--time-start", "2020", "--time-end", "2026",
              "--languages", "en", "--output-language", "en")
    for evidence, out_name in ((tmp_path / "missing-gold.json", "missing"), (malformed, "malformed")):
        out = tmp_path / out_name
        result = invoke("autopilot.py", *common, "--gold", evidence, "--out", out)
        assert result.returncode == 0, result.stderr
        precheck = json.loads((out / "sufficiency-precheck.json").read_text(encoding="utf-8"))
        assert precheck["audit_status"] == "not_started"


def test_systematic_overview_with_evidence_gaps_is_exploratory_only():
    from run_audit import _result_overview
    overview = _result_overview({
        "context": {"review_type": "系统综述"},
        "indicator_register": [{"subproject": "B1", "project_name": "饱和度", "meets_standard": "not_assessable",
                                "evidence_status": "not_assessable", "description_and_action": "需要人工筛选记录"}],
    })
    assert "尚不能作充分性判断" in overview


def test_query_compiler_uses_source_specific_syntax():
    from query_compiler import compile_query_plan
    plan = compile_query_plan("robot localization", ["arxiv", "europepmc", "crossref"])
    queries = {row["sources"][0]: row["query"] for row in plan["queries"]}
    assert queries["arxiv"].startswith('all:"')
    assert "TITLE:" in queries["europepmc"]
    assert queries["crossref"] == "robot localization"
