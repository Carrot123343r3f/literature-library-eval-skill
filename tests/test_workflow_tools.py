"""Regression tests for the guided workflow's offline human-factor artifacts."""
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def invoke(script, *args):
    subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)], check=True)


with tempfile.TemporaryDirectory() as temp:
    root = pathlib.Path(temp)
    csv_input = root / "library.csv"; imported = root / "import"; screening = root / "screening"; actions = root / "actions"
    csv_input.write_text("title,doi,year,abstract\nExample paper,10.1000/example,2025,Example abstract\n", encoding="utf-8")
    invoke("import_library.py", "--input", csv_input, "--out", imported)
    library = json.loads((imported / "library.json").read_text(encoding="utf-8"))
    assert library[0]["DOI"] == "10.1000/example"
    invoke("screen_candidates.py", "--candidates", imported / "library.json", "--out", screening)
    template = json.loads((screening / "screening-decisions.json").read_text(encoding="utf-8"))
    assert template["status"] == "template" and template["decisions"][0]["decision"] == "pending"
    audit = {"indicator_register": [{"subproject": "A2", "meets_standard": "not_assessable", "description_and_action": "missing validation evidence"}]}
    audit_path = root / "audit.json"; audit_path.write_text(json.dumps(audit), encoding="utf-8")
    invoke("next_actions.py", "--audit", audit_path, "--out", actions)
    result = json.loads((actions / "next-actions.json").read_text(encoding="utf-8"))
    assert result["actions"][0]["indicator"] == "A2"

print("Workflow tool tests: PASSED")
