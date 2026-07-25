import json
import pathlib
import subprocess
import sys
import tempfile
import os

ROOT = pathlib.Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    library = root / "library.json"; context = root / "context.json"; config = root / "run-config.json"; candidates = root / "candidates.json"; out = root / "out"
    write(library, [
        {"title": "Strong unique robot localization paper", "DOI": "10.1/strong", "year": 2025, "cited_by_count": 50, "citation_normalized_percentile": 0.95, "study_type": "algorithm_ml", "topics": ["rare"], "evidence_roles": ["industrial_validation"], "source": "IEEE", "abstractNote": "robot localization", "open_access_url": "https://example.com", "method_appraisal": {"dataset_split": "pass", "baseline_fairness": "pass", "uncertainty_reporting": "pass", "ablation": "pass"}},
        {"title": "Common robot localization paper", "DOI": "10.1/common", "year": 2020, "cited_by_count": 100, "study_type": "algorithm_ml", "topics": ["common"], "source": "IEEE", "abstractNote": "robot localization"}
    ])
    write(context, {"ranking_keywords": ["robot", "localization"]})
    write(config, {"project": {"research_question": "robot localization"}, "automation": {"allow_search": True, "allowed_sources": ["openalex"]}})
    write(candidates, [
        {"title": "Already in library", "DOI": "10.1/strong"},
        {"title": "External robot localization gap paper", "DOI": "10.1/external", "year": 2025, "cited_by_count": 30, "citation_normalized_percentile": 0.8, "topics": ["new-gap"], "source": "OpenAlex", "abstract": "robot localization", "open_access_url": "https://example.com"}
    ])
    subprocess.run([sys.executable, str(ROOT / "scripts" / "rank_papers.py"), "--library", str(library), "--context", str(context), "--run-config", str(config), "--external-candidates", str(candidates), "--out", str(out)], check=True)
    report = json.loads((out / "paper-evaluation.json").read_text(encoding="utf-8"))
    assert report["reading_priority_top"][0]["title"] == "Strong unique robot localization paper"
    assert report["library_record_count"] == 2
    assert report["core_support_top"][0]["review_contribution"]["core_support_tier"] == "core"
    assert report["external_candidate_count"] == 1
    assert report["external_candidate_top"][0]["recommendation"]["status"] == "candidate_discovery"
    assert report["papers"][1]["reading_priority"]["label"] == "metadata_priority"
    assert (out / "paper-evaluation.html").exists()

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); library = root / "library.json"; context = root / "context.json"; config = root / "run-config.json"; out = root / "out"
    write(library, []); write(context, {"ranking_keywords": ["robot"]})
    write(config, {"project": {"research_question": "robot"}, "automation": {"allow_search": False, "allowed_sources": []}})
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "rank_papers.py"), "--library", str(library), "--context", str(context), "--run-config", str(config), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "allow_search" in result.stderr
    assert (out / "paper-evaluation-error.json").exists()

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); library = root / "library.json"; context = root / "context.json"; config = root / "run-config.json"; out = root / "out"
    write(library, []); write(context, {"ranking_keywords": ["robot"]})
    write(config, {"project": {"research_question": "robot"}, "automation": {"allow_search": True, "allowed_sources": ["openalex"]}})
    env = dict(os.environ); env.pop("OPENALEX_API_KEY", None)
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_paper_evaluation.py"), "--library", str(library), "--context", str(context), "--run-config", str(config), "--out", str(out)], capture_output=True, text=True, env=env)
    assert result.returncode == 2
    assert "OPENALEX_API_KEY" in result.stderr
    assert (out / "paper-evaluation-error.json").exists()

print("Paper ranking tests: PASSED")
