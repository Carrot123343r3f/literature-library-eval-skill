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
    library = root / "library.json"; config = root / "run-config.json"; out = root / "out"
    rows = [{"title": "A paper without DOI", "abstract": "metadata only"}]
    write(library, rows)
    write(config, {"project": {"research_question": "metadata"}, "automation": {"allow_search": False, "allow_metadata_enrichment": False, "allowed_sources": []}})
    subprocess.run([sys.executable, str(ROOT / "scripts" / "enrich_library_metadata.py"), "--library", str(library), "--run-config", str(config), "--out", str(out)], check=True)
    report = json.loads((out / "metadata-enrichment.json").read_text(encoding="utf-8"))
    assert report["status"] == "disabled_by_user"
    assert json.loads((out / "library-enriched.json").read_text(encoding="utf-8")) == rows

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    library = root / "library.json"; config = root / "run-config.json"; out = root / "out"
    write(library, [{"title": "A paper without DOI", "abstract": "metadata only"}])
    write(config, {"project": {"research_question": "metadata"}, "automation": {"allow_search": True, "allow_metadata_enrichment": True, "allowed_sources": ["openalex"]}})
    env = dict(os.environ); env.pop("OPENALEX_API_KEY", None)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "enrich_library_metadata.py"), "--library", str(library), "--run-config", str(config), "--out", str(out)], check=True, env=env)
    report = json.loads((out / "metadata-enrichment.json").read_text(encoding="utf-8"))
    assert report["status"] == "unavailable"
    assert (out / "library-enriched.json").exists()

print("Metadata enrichment tests: PASSED")
