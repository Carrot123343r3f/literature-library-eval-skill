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
    assert (out / "audit" / "audit.html").is_file()
    assert (out / "next-actions.json").is_file()
    state = json.loads((out / "workflow-state.json").read_text(encoding="utf-8"))
    assert state["steps"]["citation_seed_plan"] == "complete"
    assert state["steps"]["audit"] == "complete"

    resumed = run(run_config, out, "--resume")
    assert resumed.returncode == 0, resumed.stderr
    state = json.loads((out / "workflow-state.json").read_text(encoding="utf-8"))
    assert state["steps"]["audit"] == "reused"


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
