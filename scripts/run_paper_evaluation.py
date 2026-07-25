#!/usr/bin/env python3
"""Run V2 design-aware paper evidence evaluation."""
import argparse
import datetime as dt
import json
import pathlib
import sys

from paper_evaluation.contracts import clean, load_items
from paper_evaluation.evaluation import add_contribution, evaluate_record, recommend
from paper_evaluation.external import ExternalSearchError, normalize_openalex, require_openalex_authorization, search_openalex, without_library_duplicates
from artifact_manifest import write_manifest


def sort_rows(rows, path):
    def key(row):
        value = row
        for part in path: value = value.get(part, {}) if isinstance(value, dict) else {}
        return value if isinstance(value, (int, float)) else -1
    return sorted(rows, key=key, reverse=True)


def md_table(rows, kind):
    lines = ["| 排名 | 文章 | 年份 | 资格 | 方法学 | 排序依据 |", "| --- | --- | --- | --- | --- | --- |"]
    for i, row in enumerate(rows, 1):
        if kind == "reading": basis = row["reading_priority"]["label"] + f" ({row['reading_priority']['score']})"
        elif kind == "core": basis = row["review_contribution"]["core_support_tier"] + ": " + ", ".join(row["review_contribution"]["unique_roles"] + row["review_contribution"]["topic_gap_if_removed"])
        else: basis = "候选发现；新增主题：" + ", ".join(row["recommendation"]["new_topics"])
        lines.append(f"| {i} | {clean(row['title']).replace('|','\\|')} | {row.get('year') or '—'} | {row['eligibility']['verdict']} | {row['method_appraisal']['overall']} | {clean(basis).replace('|','\\|')} |")
    return "\n".join(lines)


def render(report):
    md = ["# 单篇文献证据评价 V2", "", "## 结论", "",
          f"库内评估 {report['library_record_count']} 篇；外部候选 {report['external_candidate_count']} 篇。",
          "本报告将资格、方法学、可复核性、完整性、影响信号和库内贡献分开呈现；不输出单一“文章质量总分”。", "",
          "## 优先精读 Top 20", "", md_table(report['reading_priority_top'], "reading"), "",
          "## 核心证据骨架 Top 20", "", md_table(report['core_support_top'], "core"), "",
          "## 建议补库候选 Top 20", "", md_table(report['external_candidate_top'], "external"), "",
          "## 证据边界", "",
          "- `metadata_priority` 仅用于元数据层阅读排序，不是高质量判定。",
          "- `candidate_discovery` 的外部论文尚未筛选，不能记入正式库或检索饱和度。",
          "- 方法学评价按研究类型路由；缺少全文级证据时为 `not_assessable`，不以零分替代。",
          "- 期刊、会议与原始引用数仅作为背景信号；不构成单篇质量裁决。"]
    markdown = "\n".join(md) + "\n"
    from run_audit import _report_html
    return markdown, _report_html(markdown)


def validate_configuration(config, context):
    project = config.get("project")
    automation = config.get("automation")
    if not isinstance(project, dict) or not clean(project.get("research_question")):
        raise ValueError("run-config.project.research_question is required for paper evaluation.")
    if not isinstance(automation, dict) or not isinstance(automation.get("allow_search"), bool):
        raise ValueError("run-config.automation.allow_search must be boolean.")
    if not isinstance(context, dict):
        raise ValueError("context must be a JSON object.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", required=True); p.add_argument("--context", required=True); p.add_argument("--run-config", required=True); p.add_argument("--out", required=True)
    p.add_argument("--external-candidates", help="Reproducible saved candidate snapshot; otherwise an authorized OpenAlex search is required.")
    p.add_argument("--top-n", type=int, default=20)
    a = p.parse_args()
    if not 1 <= a.top_n <= 100: p.error("--top-n must be between 1 and 100")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    artifacts = {"library": a.library, "context": a.context, "run-config": a.run_config, "external-candidates": a.external_candidates}
    step_status = {"input_validation": "pending", "library_evaluation": "pending", "external_discovery": "pending", "report": "pending"}
    try:
        library = load_items(a.library); context = json.loads(pathlib.Path(a.context).read_text(encoding="utf-8")); config = json.loads(pathlib.Path(a.run_config).read_text(encoding="utf-8"))
        validate_configuration(config, context)
        configured_scope = ((config.get("paper_evaluation") or {}).get("scope"))
        if configured_scope and not context.get("paper_evaluation_scope"):
            context["paper_evaluation_scope"] = configured_scope
        step_status["input_validation"] = "complete"
        library_rows = add_contribution([evaluate_record(item, context, config) for item in library if isinstance(item, dict)])
        step_status["library_evaluation"] = "complete"
        if a.external_candidates:
            candidates, search_log = load_items(a.external_candidates), {"source": "provided_snapshot", "status": "complete"}
        else:
            key = require_openalex_authorization(config)
            question = clean((config.get("project") or {}).get("research_question") or context.get("research_question"))
            if not question: raise ExternalSearchError("External search requires project.research_question.")
            works, search_log = search_openalex(question, key, max(50, a.top_n * 3)); candidates = [normalize_openalex(work) for work in works]
        candidates = without_library_duplicates(candidates, library)
        external = recommend([evaluate_record(item, context, config, external=True) for item in candidates if isinstance(item, dict)], library_rows)
        step_status["external_discovery"] = "complete"
        report = {"schema_version": "2.0", "module": "paper-evidence-evaluation", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "search_log": search_log, "library_record_count": len(library_rows), "external_candidate_count": len(external),
                  "papers": library_rows, "external_candidates": external,
                  "reading_priority_top": sort_rows([row for row in library_rows if row['reading_priority']['score'] is not None], ["reading_priority", "score"])[:a.top_n],
                  "core_support_top": sort_rows(library_rows, ["review_contribution", "rank_signal"])[:a.top_n],
                  "external_candidate_top": sort_rows(external, ["recommendation", "rank_signal"])[:a.top_n]}
        markdown, html = render(report)
        (out / "paper-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "paper-evaluation.md").write_text(markdown, encoding="utf-8")
        (out / "paper-evaluation.html").write_text(html, encoding="utf-8")
        (out / "external-search-snapshot.json").write_text(json.dumps({"search_log": search_log, "candidates": candidates}, ensure_ascii=False, indent=2), encoding="utf-8")
        step_status["report"] = "complete"
        report["manifest"] = write_manifest(out, "paper-evidence-evaluation", "2.0", artifacts, step_status)
        (out / "paper-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Evaluated {len(library_rows)} library papers and {len(external)} external candidates.")
    except (ValueError, ExternalSearchError) as exc:
        step_status = {key: ("failed" if value == "pending" else value) for key, value in step_status.items()}
        write_manifest(out, "paper-evidence-evaluation", "2.0", artifacts, step_status)
        (out / "paper-evaluation-error.json").write_text(json.dumps({"module": "paper-evidence-evaluation", "status": "error", "message": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__": main()
