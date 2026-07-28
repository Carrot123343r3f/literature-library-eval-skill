#!/usr/bin/env python3
"""Run V2 design-aware paper evidence evaluation."""
import argparse
import datetime as dt
import json
import pathlib
import sys

from paper_evaluation.contracts import clean, load_items
from paper_evaluation.evaluation import add_contribution, evaluate_record, recommend
from paper_evaluation.external import ExternalSearchError, enrich_openalex_record, normalize_openalex, require_openalex_authorization, search_openalex, without_library_duplicates
from artifact_manifest import write_manifest
from audit_core.rendering import render_markdown_html
from audit_core.contracts import validate_run_config


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
        title = clean(row["title"]).replace("|", "\\|")
        safe_basis = clean(basis).replace("|", "\\|")
        lines.append(f"| {i} | {title} | {row.get('year') or '—'} | {row['eligibility']['verdict']} | {row['method_appraisal']['overall']} | {safe_basis} |")
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
    return markdown, render_markdown_html(markdown, title="单篇文献证据评价 V2")


def validate_configuration(config, context):
    if not isinstance(config, dict):
        raise ValueError("run-config must be a JSON object")
    # v1 configs use the shared strict contract; the paper module retains a
    # small legacy adapter for pre-v1 local ranking fixtures.
    if "schema_version" in config:
        config_errors = validate_run_config(config)
        if config_errors:
            raise ValueError("invalid run-config: " + "; ".join(config_errors))
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
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--library", help="JSON library array or object with items[].")
    source.add_argument("--paper", help="One paper JSON object; convenient local-first mode.")
    p.add_argument("--context", required=True); p.add_argument("--run-config", required=True); p.add_argument("--out", required=True)
    p.add_argument("--external-candidates", help="Reproducible saved candidate snapshot; otherwise an authorized OpenAlex search is required.")
    p.add_argument("--external-search", action="store_true", help="Allow live OpenAlex candidate discovery in addition to metadata enrichment.")
    p.add_argument("--offline", action="store_true", help="Disable all live lookups; must be chosen explicitly for a fully local run.")
    p.add_argument("--top-n", type=int, default=20)
    a = p.parse_args()
    if not 1 <= a.top_n <= 100: p.error("--top-n must be between 1 and 100")
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    artifacts = {"library": a.library or a.paper, "context": a.context, "run-config": a.run_config, "external-candidates": a.external_candidates}
    step_status = {"input_validation": "pending", "library_evaluation": "pending", "external_discovery": "pending", "report": "pending"}
    try:
        if a.paper:
            raw_paper = json.loads(pathlib.Path(a.paper).read_text(encoding="utf-8"))
            if not isinstance(raw_paper, dict):
                raise ValueError("--paper must point to one JSON object, not an array.")
            library = [raw_paper]; input_mode = "single-paper"
        else:
            library = load_items(a.library); input_mode = "library"
        context = json.loads(pathlib.Path(a.context).read_text(encoding="utf-8")); config = json.loads(pathlib.Path(a.run_config).read_text(encoding="utf-8"))
        validate_configuration(config, context)
        enrichment_log = {"source": "none", "status": "not_requested"}
        automation = config.get("automation") or {}
        if a.paper and not a.offline and automation.get("allow_search") is True and automation.get("allow_metadata_enrichment", False) is True:
            key = require_openalex_authorization(config)
            library[0], enrichment_log = enrich_openalex_record(library[0], key)
        configured_scope = ((config.get("paper_evaluation") or {}).get("scope"))
        if configured_scope and not context.get("paper_evaluation_scope"):
            context["paper_evaluation_scope"] = configured_scope
        step_status["input_validation"] = "complete"
        library_rows = add_contribution([evaluate_record(item, context, config) for item in library if isinstance(item, dict)])
        step_status["library_evaluation"] = "complete"
        if a.external_candidates:
            candidates, search_log = load_items(a.external_candidates), {"source": "provided_snapshot", "status": "complete"}
        elif a.paper and not a.external_search:
            candidates, search_log = [], {"source": "single_paper_metadata_only", "status": "skipped", "reason": "candidate discovery requires --external-search"}
        else:
            if (config.get("automation") or {}).get("allow_external_discovery", False) is not True:
                raise ExternalSearchError("External candidate discovery requires explicit automation.allow_external_discovery=true.")
            key = require_openalex_authorization(config)
            question = clean((config.get("project") or {}).get("research_question") or context.get("research_question"))
            if not question: raise ExternalSearchError("External search requires project.research_question.")
            works, search_log = search_openalex(question, key, max(50, a.top_n * 3)); candidates = [normalize_openalex(work) for work in works]
        candidates = without_library_duplicates(candidates, library)
        external = recommend([evaluate_record(item, context, config, external=True) for item in candidates if isinstance(item, dict)], library_rows)
        step_status["external_discovery"] = "complete"
        report = {"schema_version": "2.0", "module": "paper-evidence-evaluation", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "input_mode": input_mode,
                  "search_log": search_log, "metadata_enrichment": enrichment_log, "library_record_count": len(library_rows), "external_candidate_count": len(external),
                  "papers": library_rows, "external_candidates": external,
                  "reading_priority_top": sort_rows([row for row in library_rows if row['reading_priority']['score'] is not None], ["reading_priority", "score"])[:a.top_n],
                  "core_support_top": sort_rows(library_rows, ["review_contribution", "rank_signal"])[:a.top_n],
                  "external_candidate_top": sort_rows(external, ["recommendation", "rank_signal"])[:a.top_n]}
        markdown, html = render(report)
        (out / "paper-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "paper-evaluation.html").write_text(html, encoding="utf-8")
        (out / "external-search-snapshot.json").write_text(json.dumps({"search_log": search_log, "candidates": candidates}, ensure_ascii=False, indent=2), encoding="utf-8")
        step_status["report"] = "complete"
        report["manifest"] = write_manifest(out, "paper-evidence-evaluation", "2.0", artifacts, step_status)
        (out / "paper-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Evaluated {len(library_rows)} library papers and {len(external)} external candidates. HTML report created: paper-evaluation.html")
    except (ValueError, ExternalSearchError) as exc:
        step_status = {key: ("failed" if value == "pending" else value) for key, value in step_status.items()}
        write_manifest(out, "paper-evidence-evaluation", "2.0", artifacts, step_status)
        (out / "paper-evaluation-error.json").write_text(json.dumps({"module": "paper-evidence-evaluation", "status": "error", "message": "evaluation_failed", "error_type": type(exc).__name__}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("ERROR: online paper evaluation is unavailable. Check automation.allow_external_discovery and OPENALEX_API_KEY configuration.", file=sys.stderr); raise SystemExit(2)


if __name__ == "__main__": main()
