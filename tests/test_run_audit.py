import json
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    out = pathlib.Path(temp) / "out"
    args = [sys.executable, str(root / "scripts" / "run_audit.py"), "--library", str(root / "tests" / "library.json"), "--benchmark", str(root / "tests" / "benchmark.json"), "--gold", str(root / "tests" / "gold.json"), "--query-hits", str(root / "tests" / "zero-hits.json"), "--candidate-snapshots", str(root / "tests" / "snapshot.json"), "--context", str(root / "tests" / "context.json"), "--out", str(out)]
    subprocess.run(args, check=True)
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert audit["coverage"]["a1"]["recall"] == 0.5
    assert audit["coverage"]["a2"]["status"] == "measured"
    assert audit["coverage"]["a2"]["recall"] == 0.0
    assert audit["coverage"]["a3"]["deduplicated_candidate_lower_bound"] == 3
    assert audit["structure"]["uncovered_expected_strata"] == ["low-light"]
    assert audit["evidence"]["missing_required_types"] == ["field-test"]
    assert (out / "audit.md").exists() and (out / "audit.html").exists()
print("run_audit tests passed")
