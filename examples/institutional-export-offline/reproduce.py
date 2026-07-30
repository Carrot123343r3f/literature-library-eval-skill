"""Cross-platform runner and acceptance check for this example."""
import json, os, pathlib, subprocess, sys

example = pathlib.Path(__file__).resolve().parent
repo = example.parents[1]
env = {**os.environ, "PYTHONUTF8": "1"}
subprocess.run([sys.executable, repo / "scripts" / "import_source_snapshots.py", "--manifest", example / "institutional-exports.json", "--out", example / "outputs" / "institutional-snapshot.json"], check=True, env=env)
subprocess.run([sys.executable, repo / "scripts" / "run_audit.py", "--run-config", example / "run-config.json", "--out", example / "outputs" / "audit"], check=True, env=env)
a3 = json.loads((example / "outputs" / "audit" / "audit.json").read_text(encoding="utf-8"))["coverage"]["a3"]
assert a3["status"] == "estimated_lower_bound" and a3["deduplicated_candidate_lower_bound"] == 3
print("Success: institutional exports are in the audit; A3 lower bound = 3. Next: create a 10–20 paper independent must-include set, run forward/backward citation tracking, and save each query's fields/date/filters.")
