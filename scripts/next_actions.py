#!/usr/bin/env python3
"""Turn an audit into a concise, recoverable user action plan."""
import argparse
import json
import pathlib


RECOVERY = {
    "A2": ("提供独立验证集或执行已授权检索", "Gold/validation set、query-hits.json 或 search_meta.json"),
    "A3": ("执行至少两个已授权来源的快照采集", "query-plan.json 与 source-snapshot.json"),
    "B1": ("完成两轮独立路径的人工筛选", "含 screened_complete 的 search_rounds"),
    "B2": ("记录各路径筛选后的新增量", "source_marginal_yields 与去重规则"),
    "B3": ("完成计划中的独立检索路径", "planned_pathways 和完成记录"),
    "F2": ("补齐题名、年份、摘要等核心元数据", "重新导入或补全 library.json"),
    "F1": ("补全可复跑的检索日志", "每条含 source、query、fields、date"),
    "F4": ("处理版本族与模糊去重队列", "deduplication-log.json 的明确决定"),
    "F5": ("记录纳入/排除理由", "screening-decisions.json"),
}


def build(audit):
    actions = []
    for row in audit.get("indicator_register", []):
        verdict = row.get("meets_standard")
        if verdict not in {"fail", "warning", "not_assessable"}: continue
        code = row.get("subproject", "")
        action, needed = RECOVERY.get(code, (row.get("description_and_action", "人工复核该指标。"), "见审计输入与证据记录"))
        actions.append({"indicator": code, "severity": verdict, "action": action, "needed": needed,
                        "why": row.get("description_and_action", "")})
    priority = {"fail": 0, "not_assessable": 1, "warning": 2}
    return {"schema_version": "1.0", "status": "action_required" if actions else "ready_for_human_review",
            "actions": sorted(actions, key=lambda item: (priority[item["severity"]], item["indicator"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--audit", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); audit = json.loads(pathlib.Path(args.audit).read_text(encoding="utf-8")); result = build(audit)
    output = pathlib.Path(args.out); output.mkdir(parents=True, exist_ok=True)
    (output / "next-actions.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {len(result['actions'])} recoverable action(s).")


if __name__ == "__main__": main()
