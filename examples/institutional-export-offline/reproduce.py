"""Cross-platform runner and acceptance check for this example."""
import json, os, pathlib, subprocess, sys

example = pathlib.Path(__file__).resolve().parent
repo = example.parents[1]
env = {**os.environ, "PYTHONUTF8": "1"}
out = example / ".local-output"
# This fixture owns .local-output; force makes repeated teaching/CI runs
# reproducible without changing the fail-closed policy for user-selected paths.
subprocess.run([sys.executable, repo / "scripts" / "import_source_snapshots.py", "--manifest", example / "institutional-exports.json", "--out", out / "institutional-snapshot.json", "--force"], check=True, env=env)
subprocess.run([sys.executable, repo / "scripts" / "run_audit.py", "--run-config", example / "run-config.json", "--out", out / "audit", "--force"], check=True, env=env)
audit = json.loads((out / "audit" / "audit.json").read_text(encoding="utf-8"))
a3 = audit["coverage"]["a3"]
snapshot = json.loads((out / "institutional-snapshot.json").read_text(encoding="utf-8"))
sources = snapshot["queries"][0]["sources"]
assert a3["status"] == "estimated_lower_bound" and a3["deduplicated_candidate_lower_bound"] == 3
assert set(sources) == {"ieee_xplore", "scopus"} and all(item["complete"] for item in sources.values())
assert all(item["provenance"].get("query") and item["provenance"].get("sha256") for item in sources.values())
assert audit["coverage"]["a1"]["status"] == audit["coverage"]["a2"]["status"] == "not_assessable"
assert audit["process"]["status"] == "not_assessable" and audit["process"]["checks"]["F1_query_traceability"] in {"not_assessable", "fail"}
print("Success: institutional exports are in the audit; A3 lower bound = 3. Next: create a 10–20 paper independent must-include set, run forward/backward citation tracking, and save each query's fields/date/filters.")
