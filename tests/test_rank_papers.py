import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    library = root / "library.json"; context = root / "context.json"; config = root / "run-config.json"; candidates = root / "candidates.json"; out = root / "out"
    write(library, [
        {"title": "Strong unique paper", "DOI": "10.1/strong", "year": 2025, "cited_by_count": 50, "publicationTitle": "Journal", "peer_reviewed": True, "method_evidence_score": 0.9, "relevance_score": 0.9, "topics": ["rare"], "source": "IEEE", "abstractNote": "a", "open_access_url": "https://example.com"},
        {"title": "Common paper", "DOI": "10.1/common", "year": 2020, "cited_by_count": 100, "publicationTitle": "Journal", "peer_reviewed": True, "method_evidence_score": 0.7, "relevance_score": 0.8, "topics": ["common"], "source": "IEEE", "abstractNote": "a", "open_access_url": "https://example.com"}
    ])
    write(context, {"ranking_keywords": ["robot", "localization"]})
    write(config, {"project": {"research_question": "robot localization"}, "automation": {"allow_search": True, "allowed_sources": ["openalex"]}})
    write(candidates, [
        {"title": "Already in library", "DOI": "10.1/strong"},
        {"title": "External gap paper", "DOI": "10.1/external", "year": 2025, "cited_by_count": 30, "publicationTitle": "Journal", "peer_reviewed": True, "relevance_score": 0.95, "topics": ["new-gap"], "source": "OpenAlex", "abstract": "robot localization", "open_access_url": "https://example.com"}
    ])
    subprocess.run([sys.executable, str(ROOT / "scripts" / "rank_papers.py"), "--library", str(library), "--context", str(context), "--run-config", str(config), "--external-candidates", str(candidates), "--out", str(out)], check=True)
    report = json.loads((out / "paper-ranking.json").read_text(encoding="utf-8"))
    assert report["library_top_quality"][0]["title"] == "Strong unique paper"
    assert report["library_core_support"][0]["title"] == "Strong unique paper"
    assert report["external_candidate_count"] == 1
    assert report["external_recommendations"][0]["recommendation_status"] == "candidate_discovery"
    assert (out / "paper-ranking.html").exists()

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp); library = root / "library.json"; context = root / "context.json"; config = root / "run-config.json"; out = root / "out"
    write(library, []); write(context, {"ranking_keywords": ["robot"]})
    write(config, {"project": {"research_question": "robot"}, "automation": {"allow_search": False, "allowed_sources": []}})
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "rank_papers.py"), "--library", str(library), "--context", str(context), "--run-config", str(config), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "allow_search" in result.stderr
    assert (out / "paper-ranking-error.json").exists()

print("Paper ranking tests: PASSED")
