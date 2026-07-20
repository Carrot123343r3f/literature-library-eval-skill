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
    normalized = pathlib.Path(temp) / "normalized"
    subprocess.run([sys.executable, str(root / "scripts" / "normalize_candidates.py"), "--snapshot", str(root / "tests" / "snapshot.json"), "--out", str(normalized)], check=True)
    dedup = json.loads((normalized / "deduplication-log.json").read_text(encoding="utf-8"))
    assert len(dedup["exact_identifier_groups"]) == 3
    audit = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert audit["coverage"]["a1"]["recall"] == 0.5
    assert audit["coverage"]["a2"]["status"] == "measured"
    assert audit["coverage"]["a2"]["recall"] == 0.0
    assert audit["coverage"]["a3"]["deduplicated_candidate_lower_bound"] == 3
    assert "empty_topic" in audit["topic_balance"]["flags"]
    assert audit["balance"]["top_source_share"] == 0.5
    assert audit["recency"]["recent_share"] == 1.0
    assert (out / "audit.md").exists() and (out / "audit.html").exists()
    markdown = (out / "audit.md").read_text(encoding="utf-8")
    assert "| 维度 | 编号 | 评估项 | 标准 | 判定 | 当前值 | 证据状态 | 说明与行动 |" in markdown
    assert "| A 覆盖 | A1 |" in markdown
    assert "| B 饱和度 | B1 |" in markdown
    assert "| C 平衡 | C3 |" in markdown
    assert "| F 可用性 | F6 |" in markdown
    register = audit["indicator_register"]
    assert len(register) == 21
    assert {row["subproject"] for row in register} >= {"A1", "B1", "C1", "D1", "E1", "F6"}
print("run_audit tests passed")
