#!/usr/bin/env python3
"""Run a low-friction first-pass literature audit with safe, resumable defaults."""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import subprocess
import sys

try:
    from query_compiler import compile_query_plan
    from import_library import load as load_library
except ImportError:
    from scripts.query_compiler import compile_query_plan
    from scripts.import_library import load as load_library


DEFAULT_SOURCES = ["openalex", "arxiv", "crossref", "europepmc"]


def build_context(question, terms):
    return {"research_question": question, "keywords": terms,
            "search_decomposition": {"object": {"term": ""}, "technology": {"term": ""},
                                      "performance": {"term": ""}, "context": {"term": ""},
                                      "source": "autopilot_question_only"}}


def build_config(question, library, review_type, sources, offline, scope_status,
                 *, allow_metadata_enrichment=False, allow_external_discovery=False,
                 allow_citation_tracking=False, time_start=None, time_end=None,
                 languages=None, output_language="zh-CN"):
    """Build an explicit-permission config; scope confirmation never grants network access."""
    if offline:
        allow_metadata_enrichment = allow_external_discovery = allow_citation_tracking = False
    allow_search = any((allow_metadata_enrichment, allow_external_discovery, allow_citation_tracking))
    config = {"schema_version": "1.0",
            "project": {"research_question": question, "review_type": review_type,
                        "scope_status": scope_status,
                        "time_range": {"start": time_start, "end": time_end},
                        "languages": languages or [],
                        "scope_rationale": "explicit autopilot scope confirmation" if scope_status == "in_scope" else "autopilot draft; scope not confirmed"},
            "library": {"provided": bool(library), "path": pathlib.Path(library).name if library else None, "format": "json" if library else None},
            "automation": {"allow_search": allow_search, "allow_metadata_enrichment": allow_metadata_enrichment,
                            "allow_external_discovery": allow_external_discovery, "allow_citation_tracking": allow_citation_tracking,
                            "local_only_confirmed": offline, "allowed_sources": sources if allow_search else []},
            "output": {"language": output_language, "formats": ["html", "json"]}}
    if allow_search:
        config["quality"] = {"active_screen_budget": 100}
    return config


def write_onboarding(out, question, plan, sources):
    """Write a safe first-run handoff when scope has not been confirmed yet."""
    query_count = len(plan.get("queries", [])) if isinstance(plan, dict) else 0
    command = "python scripts/autopilot.py --question " + json.dumps(question, ensure_ascii=False) + " --scope-status in_scope --out first-pass"
    if sources:
        command += " --sources " + json.dumps(",".join(sources), ensure_ascii=False)
    page = f"""<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Literature audit: start here</title>
<body><main style=\"max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif\">
<h1>Start your literature audit</h1>
<p>Your question has been saved and a {query_count}-query starter plan was created. No A–F conclusion was produced because the engineering scope has not yet been confirmed.</p>
<h2>Question</h2><p>{html.escape(question)}</p>
<h2>Next step</h2><p>If this is an engineering review question within this skill's scope, run:</p>
<pre>{html.escape(command)}</pre>
<p>You may add <code>--library path/to/library.json</code> now or later. Without a library, the first confirmed run creates an empty starter library and reports only what is currently assessable.</p>
<h2>Why this pause exists</h2><p>It prevents an automated draft from silently deciding that an out-of-scope question deserves a full evidence verdict.</p>
</main></body></html>"""
    (out / "onboarding.html").write_text(page, encoding="utf-8")


def write_search_preparation(out, question, plan):
    """Deliver a useful, plainly labelled output when no library exists yet."""
    queries = plan.get("queries", []) if isinstance(plan, dict) else []
    examples = "".join(f"<li>{html.escape(str(row.get('query', '')))}</li>" for row in queries[:3])
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>检索准备计划</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>检索准备计划（尚未开始文献库审计）</h1>
<p>尚未提供文献库。本页不包含 A–F 评估，也不能判断文献库能否支撑综述。</p>
<h2>研究问题</h2><p>{html.escape(question)}</p>
<h2>建议先完成的三件事</h2><ol><li>导出或建立文献库（JSON、CSV、RIS 或 BibTeX）。</li><li>确认综述类型与时间/语言边界。</li><li>记录每次检索的来源、日期和检索式；候选不等于已纳入文献。</li></ol>
<h2>起步检索式</h2><ul>{examples or '<li>请补充核心术语后生成检索式。</li>'}</ul>
</main></body></html>"""
    (out / "search-preparation.html").write_text(page, encoding="utf-8")


def write_library_health(out, library):
    """Provide a lightweight health check without claiming review sufficiency."""
    records = load_library(library)
    total = len(records)
    def rate(*keys):
        return (sum(bool(str(next((row.get(key) for key in keys if row.get(key)), "")).strip()) for row in records) / total) if total else 0
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献库健康检查</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>文献库健康检查（不是充分性审计）</h1>
<p>本模式只检查基础可用性；不对召回率、饱和度或文献库能否支撑综述作出结论。</p>
<ul><li>可读取记录：{total}</li><li>标题完整率：{rate('title'):.0%}</li><li>年份完整率：{rate('date', 'year', 'publication_year'):.0%}</li><li>摘要完整率：{rate('abstractNote', 'abstract'):.0%}</li><li>DOI 完整率：{rate('DOI', 'doi'):.0%}</li></ul>
<p>如需充分性审计，请明确综述类型，并运行 <code>--mode sufficiency-audit --review-type ...</code>。</p>
</main></body></html>"""
    (out / "library-health.html").write_text(page, encoding="utf-8")


def audit_readiness(library):
    """Keep an explicit audit request from becoming an empty A-F report."""
    records = load_library(library)
    total = len(records)
    titled = sum(bool(row.get("title")) for row in records)
    dated = sum(bool(row.get("year")) for row in records)
    reasons = []
    if total < 3:
        reasons.append("at least 3 imported records")
    if total and titled / total < 0.8:
        reasons.append("titles for at least 80% of records")
    if total and dated / total < 0.8:
        reasons.append("years for at least 80% of records")
    return records, reasons


def write_sufficiency_precheck(out, reasons):
    items = "".join(f"<li>{html.escape(reason)}</li>" for reason in reasons)
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>充分性审计预检查</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>充分性审计尚未开始</h1>
<p>你已请求充分性审计，但文献库尚未达到最小可审计输入。为避免生成大部分不可评估的 A–F 报告，本次仅交付预检查结果。</p>
<h2>最低需要补齐</h2><ul>{items}</ul>
<h2>之后仍需要的审计证据</h2><p>检索日志、独立验证集、人工筛选决定和独立检索路径用于判断覆盖与饱和度；缺少它们时不会宣称“检索充分”。</p>
</main></body></html>"""
    (out / "sufficiency-precheck.html").write_text(page, encoding="utf-8")


def run(args):
    out = pathlib.Path(args.out); control = out / ".autopilot"; control.mkdir(parents=True, exist_ok=True)
    print("[1/3] Preparing the first-run plan...", flush=True)
    sources = [x.strip().casefold() for x in args.sources.split(",") if x.strip()] if not args.offline else []
    plan = compile_query_plan(args.question, sources or ["arxiv"])
    terms = plan["queries"][0].get("terms", []) if plan["queries"] else []
    config_path = control / "run-config.json"; context_path = control / "context.json"; plan_path = control / "query-plan.json"
    config_path.write_text(json.dumps(build_config(
        args.question, args.library, args.review_type, sources, args.offline, args.scope_status,
        allow_metadata_enrichment=args.allow_metadata_enrichment,
        allow_external_discovery=args.allow_external_discovery,
        allow_citation_tracking=args.allow_citation_tracking, time_start=args.time_start,
        time_end=args.time_end, languages=[item.strip() for item in (args.languages or "").split(",") if item.strip()],
        output_language=args.output_language or "zh-CN"), ensure_ascii=False, indent=2), encoding="utf-8")
    context_path.write_text(json.dumps(build_context(args.question, terms), ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.scope_status not in {"in_scope", "cross_domain"}:
        write_onboarding(out, args.question, plan, sources)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "needs_scope_confirmation", "sources_requested": sources, "question": args.question, "scope_status": args.scope_status, "human_gates": ["scope"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    mode = args.mode
    if mode == "auto":
        mode = "library-health" if args.library else "search-preparation"
    if mode == "search-preparation":
        write_search_preparation(out, args.question, plan)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "search_preparation", "audit_status": "not_started", "question": args.question}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] No library supplied: delivered a search-preparation plan, not an audit.", flush=True)
        return
    if not args.library:
        raise ValueError("library-health and sufficiency-audit require --library; use search-preparation without one.")
    library = pathlib.Path(args.library).resolve()
    if mode == "library-health":
        write_library_health(out, library)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "library_health", "audit_status": "not_started", "question": args.question}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] Delivered a library-health check, not a sufficiency audit.", flush=True)
        return
    missing = []
    if not args.review_type: missing.append("--review-type")
    if args.time_start is None or args.time_end is None: missing.append("--time-start and --time-end")
    if not args.languages: missing.append("--languages")
    if not args.output_language: missing.append("--output-language")
    if missing:
        raise ValueError("sufficiency-audit requires explicit confirmation of " + ", ".join(missing) + ".")
    _, readiness_gaps = audit_readiness(library)
    if readiness_gaps:
        write_sufficiency_precheck(out, readiness_gaps)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "sufficiency_precheck", "audit_status": "not_started", "question": args.question, "missing_minimum_inputs": readiness_gaps}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] Delivered a sufficiency precheck; the A-F audit was not started.", flush=True)
        return
    print("[2/3] Running the sufficiency audit; missing evidence will remain explicit.", flush=True)
    command = [sys.executable, str(pathlib.Path(__file__).with_name("run_full_audit.py")), "run",
               "--run-config", str(config_path), "--library", str(library),
               "--context", str(context_path), "--out", str(out)]
    if args.allow_external_discovery and not args.offline:
        command += ["--collect", "--query-plan", str(plan_path), "--active-screen-budget", str(args.screen_budget)]
    subprocess.run(command, check=True)
    candidates = out / "normalization" / "candidates.json"
    if candidates.is_file():
        triage = out / "screening" / "auto-triage.json"
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("auto_triage.py")),
                        "--candidates", str(candidates), "--question", args.question, "--out", str(triage)], check=True)
    (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": mode, "sources_requested": sources if not args.offline else [], "question": args.question, "scope_status": args.scope_status, "human_gates": ["scope", "standards", "screening", "final_inclusion"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[3/3] Sufficiency audit complete.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True); parser.add_argument("--library"); parser.add_argument("--out", required=True)
    parser.add_argument("--mode", default="auto", choices=("auto", "search-preparation", "library-health", "sufficiency-audit"),
                        help="Search preparation and library health do not produce A-F sufficiency conclusions.")
    parser.add_argument("--review-type", choices=("narrative", "systematic", "scoping", "rapid", "umbrella"))
    parser.add_argument("--time-start", type=int, help="Explicit start year required for sufficiency-audit.")
    parser.add_argument("--time-end", type=int, help="Explicit end year required for sufficiency-audit.")
    parser.add_argument("--languages", help="Comma-separated language boundary required for sufficiency-audit.")
    parser.add_argument("--output-language", choices=("zh-CN", "en"), help="Explicit report language required for sufficiency-audit.")
    parser.add_argument("--scope-status", default="scope_uncertain", choices=("in_scope", "cross_domain", "out_of_scope", "scope_uncertain"),
                        help="Explicit scope decision. Full A-F execution requires in_scope or cross_domain; default is a safe draft state.")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES)); parser.add_argument("--offline", action="store_true",
                        help="Disable all online capabilities (the default is already local-only).")
    parser.add_argument("--allow-metadata-enrichment", action="store_true", help="Explicitly allow online metadata enrichment.")
    parser.add_argument("--allow-external-discovery", action="store_true", help="Explicitly allow online discovery of candidate papers.")
    parser.add_argument("--allow-citation-tracking", action="store_true", help="Explicitly allow online citation candidate discovery.")
    parser.add_argument("--screen-budget", type=int, default=100)
    args = parser.parse_args()
    if args.screen_budget < 1: parser.error("--screen-budget must be positive")
    if args.offline and any((args.allow_metadata_enrichment, args.allow_external_discovery, args.allow_citation_tracking)):
        parser.error("--offline cannot be combined with an --allow-* online capability")
    try: run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc: parser.error(str(exc))


if __name__ == "__main__": main()
