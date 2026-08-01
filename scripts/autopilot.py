#!/usr/bin/env python3
"""Run a low-friction first-pass literature audit with safe, resumable defaults."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
from audit_core.safe_paths import prepare_output_dir
import re
import subprocess
import sys

try:
    from query_compiler import compile_query_plan
    from import_library import load as load_library
    from audit_core.contracts import normalize_language_tag, public_value
    from run_audit import ids, scope_records, stable_record_ids
    from search_iterator import validate as validate_iterations
except ImportError:
    from scripts.query_compiler import compile_query_plan
    from scripts.import_library import load as load_library
    from scripts.audit_core.contracts import normalize_language_tag, public_value
    from scripts.run_audit import ids, scope_records, stable_record_ids
    from scripts.search_iterator import validate as validate_iterations


DEFAULT_SOURCES = ["openalex", "arxiv", "crossref", "europepmc"]


def build_context(question, terms):
    return {"research_question": question, "keywords": terms,
            "search_decomposition": {"object": {"term": ""}, "technology": {"term": ""},
                                      "performance": {"term": ""}, "context": {"term": ""},
                                      "source": "autopilot_question_only"}}


def build_config(question, library, review_type, sources, offline, scope_status,
                 *, allow_metadata_enrichment=False, allow_external_discovery=False,
                 allow_citation_tracking=False, time_start=None, time_end=None,
                 languages=None, output_language="zh-CN", evidence_inputs=None):
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
            "library": {"provided": bool(library), "path": str(library) if library and not pathlib.Path(library).is_absolute() else (pathlib.Path(library).name if library else None), "format": pathlib.Path(library).suffix.lstrip(".").lower() if library else None},
            "automation": {"allow_search": allow_search, "allow_metadata_enrichment": allow_metadata_enrichment,
                            "allow_external_discovery": allow_external_discovery, "allow_citation_tracking": allow_citation_tracking,
                            "local_only_confirmed": offline, "allowed_sources": sources if allow_search else []},
            "output": {"language": output_language, "formats": ["html", "json"]}}
    if allow_search:
        config["quality"] = {"active_screen_budget": 100}
    if evidence_inputs:
        config["evidence_inputs"] = evidence_inputs
    return config


def bundle_input(path, bundle_dir, label):
    """Create a movable, path-free input copy and return its config-relative name."""
    try:
        source = pathlib.Path(path)
        suffix = source.suffix.lower()
        raw = source.read_bytes()
        if suffix == ".json":
            raw = json.dumps(public_value(json.loads(raw.decode("utf-8"))), ensure_ascii=False, indent=2).encode("utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    digest = __import__("hashlib").sha256(raw).hexdigest()
    destination = bundle_dir / f"{label}__{digest[:12]}{suffix}"
    if not destination.exists():
        destination.write_bytes(raw)
    return f"inputs/{destination.name}", {"sha256": digest, "filename": destination.name, "redacted_json": suffix == ".json"}


def write_onboarding(out, question, plan, sources, output_language="zh-CN"):
    """Write a safe, localized first-run handoff when scope is uncertain."""
    query_count = len(plan.get("queries", [])) if isinstance(plan, dict) else 0
    command = "python scripts/autopilot.py --question " + json.dumps(question, ensure_ascii=False) + " --scope-status in_scope --out first-pass"
    if sources:
        command += " --sources " + json.dumps(",".join(sources), ensure_ascii=False)
    if str(output_language).lower().startswith("en"):
        page = f"""<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Literature audit: start here</title>
<body><main style=\"max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif\">
<h1>Start your literature audit</h1>
<p>Your question has been saved and a {query_count}-query starter plan was created. No A–F conclusion was produced because the engineering scope has not yet been confirmed.</p>
<h2>Question</h2><p>{html.escape(question)}</p>
<h2>Next step</h2><p>If this is an engineering review question within this skill's scope, run:</p>
<pre>{html.escape(command)}</pre>
<p>You may add <code>--library path/to/library.{{json,csv,ris,bib}}</code> now or later. Without a library, the first confirmed run delivers a search-preparation plan and does not start an A–F audit.</p>
<h2>Why this pause exists</h2><p>It prevents an automated draft from silently deciding that an out-of-scope question deserves a full evidence verdict.</p>
</main></body></html>"""
        (out / "onboarding.html").write_text(page, encoding="utf-8")
        return
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献库审计：从这里开始</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>开始文献库审计</h1>
<p>已保存你的研究问题，并生成 {query_count} 条起步检索式。由于尚未确认该问题是否属于本 skill 的工程研究范围，本次没有生成 A–F 结论。</p>
<h2>研究问题</h2><p>{html.escape(question)}</p>
<h2>下一步</h2><p>如果这是本 skill 适用范围内的工程综述问题，请运行：</p>
<pre>{html.escape(command)}</pre>
<p>现在或之后均可补充 <code>--library path/to/library.{{json,csv,ris,bib}}</code>。未提供文献库时，首次确认范围后的运行只交付检索准备计划，不会启动 A–F 审计。</p>
<h2>为何暂停</h2><p>此步骤避免自动化系统在范围不明时，擅自对超出适用范围的问题给出完整证据结论。</p>
</main></body></html>"""
    (out / "onboarding.html").write_text(page, encoding="utf-8")


def write_out_of_scope_notice(out, question, output_language="zh-CN"):
    """Stop without suggesting an out-of-scope question be reclassified."""
    if str(output_language).lower().startswith("en"):
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Outside this skill's scope</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif"><h1>Outside this skill's scope</h1>
<p>This question is explicitly marked out of scope, so no search plan or A–F audit was started.</p><h2>Question</h2><p>{html.escape(question)}</p>
<p>Reclassify the scope only if the original project scope changes; this page is not a review-readiness conclusion.</p></main></body></html>"""
        (out / "out-of-scope.html").write_text(page, encoding="utf-8")
        return
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>超出本 skill 的适用范围</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif"><h1>超出本 skill 的适用范围</h1>
<p>该问题已被明确标记为超出范围，因此不会启动检索计划或 A–F 审计。</p><h2>研究问题</h2><p>{html.escape(question)}</p>
<p>只有原始项目范围实际发生变化时，才应重新分类；本页不构成综述准备度结论。</p></main></body></html>"""
    (out / "out-of-scope.html").write_text(page, encoding="utf-8")


def write_search_preparation(out, question, plan, output_language="zh-CN"):
    """Deliver a useful, plainly labelled output when no library exists yet."""
    queries = plan.get("queries", []) if isinstance(plan, dict) else []
    examples = "".join(f"<li>{html.escape(str(row.get('query', '')))}</li>" for row in queries[:3])
    if str(output_language).lower().startswith("en"):
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Search preparation plan</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif"><h1>Search preparation plan</h1>
<p>No library was supplied. This is not an A-F audit and cannot judge review sufficiency.</p><h2>Research question</h2><p>{html.escape(question)}</p>
<h2>Three next steps</h2><ol><li>Export or build a library (JSON, CSV, RIS, or BibTeX).</li><li>Set review type, time and language boundaries.</li><li>Record source, date, and query for every search; candidates are not included studies.</li></ol>
<h2>Starter queries</h2><ul>{examples or '<li>Add core terms before generating queries.</li>'}</ul></main></body></html>"""
        (out / "search-preparation.html").write_text(page, encoding="utf-8")
        return
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>检索准备计划</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>检索准备计划（尚未开始文献库审计）</h1>
<p>尚未提供文献库。本页不包含 A–F 评估，也不能判断文献库能否支撑综述。</p>
<h2>研究问题</h2><p>{html.escape(question)}</p>
<h2>建议先完成的三件事</h2><ol><li>导出或建立文献库（JSON、CSV、RIS 或 BibTeX）。</li><li>确认综述类型与时间/语言边界。</li><li>记录每次检索的来源、日期和检索式；候选不等于已纳入文献。</li></ol>
<h2>起步检索式</h2><ul>{examples or '<li>请补充核心术语后生成检索式。</li>'}</ul>
</main></body></html>"""
    (out / "search-preparation.html").write_text(page, encoding="utf-8")


def write_library_health(out, library, output_language="zh-CN", *, out_of_scope=False):
    """Provide a lightweight health check without claiming review sufficiency."""
    records = load_library(library)
    total = len(records)
    def rate(*keys):
        return (sum(bool(str(next((row.get(key) for key in keys if row.get(key)), "")).strip()) for row in records) / total) if total else 0
    if str(output_language).lower().startswith("en"):
        scope_notice = "This question is outside this skill's scope; this page is only a bibliographic health check." if out_of_scope else "This mode checks basic usability only; it does not establish recall, saturation, or review readiness."
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Library health check</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif"><h1>Library health check (not a sufficiency conclusion)</h1>
<p>{scope_notice}</p><ul><li>Readable records: {total}</li><li>Titles present: {rate('title'):.0%}</li><li>Years present: {rate('date', 'year', 'publication_year'):.0%}</li><li>Abstracts present: {rate('abstractNote', 'abstract'):.0%}</li><li>DOIs present: {rate('DOI', 'doi'):.0%}</li></ul></main></body></html>"""
        (out / "library-health.html").write_text(page, encoding="utf-8")
        return
    scope_notice = "该问题已明确超出本 skill 的适用范围；本页仅作题录健康检查。" if out_of_scope else "本模式只检查基础可用性；不对召回率、饱和度或文献库能否支撑综述作出结论。"
    next_step = "该问题超出本 skill 的适用范围；本 skill 不提供其充分性审计。只有项目范围实际改变后，才应重新分类。" if out_of_scope else "如需充分性审计，请明确综述类型，并运行 <code>--mode sufficiency-audit --review-type ...</code>。"
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>文献库健康检查</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>文献库健康检查（不是充分性审计）</h1>
<p>{scope_notice}</p>
<ul><li>可读取记录：{total}</li><li>标题完整率：{rate('title'):.0%}</li><li>年份完整率：{rate('date', 'year', 'publication_year'):.0%}</li><li>摘要完整率：{rate('abstractNote', 'abstract'):.0%}</li><li>DOI 完整率：{rate('DOI', 'doi'):.0%}</li></ul>
<p>{next_step}</p>
</main></body></html>"""
    (out / "library-health.html").write_text(page, encoding="utf-8")


def _question_terms(question):
    raw = [term.casefold() for term in re.findall(r"[\w-]+", question, flags=re.UNICODE)
           if len(term) >= 3 and term.casefold() not in {"what", "which", "does", "how", "with", "from", "this", "that", "research", "study", "研究", "如何", "什么", "哪些"}]
    # Common spelling variants are a recall aid only; they never prove topical
    # relevance by themselves.
    aliases = {"localization": {"localisation"}, "localisation": {"localization"},
               "robot": {"robotic"}, "robotic": {"robot"}}
    expanded = set(raw)
    for term in raw:
        expanded.update(aliases.get(term, set()))
    return expanded


def _load_records(path, label, errors):
    """Load a records/items JSON payload without allowing parser failures downstream."""
    try:
        payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is unreadable JSON: {exc}"); return []
    rows = payload if isinstance(payload, list) else payload.get("items", payload.get("records")) if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        errors.append(f"{label} must be a JSON records[]/items[] array"); return []
    return rows


def _load_json_object(path, label, errors):
    try:
        value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is unreadable JSON: {exc}"); return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object"); return {}
    return value


def _validate_relevance_review(path, errors):
    if not path:
        return False
    review = _load_json_object(path, "relevance review", errors)
    required = ("reviewer", "reviewed_at", "rule", "sample", "decision")
    if not all(isinstance(review.get(field), str) and review[field].strip() for field in required):
        errors.append("relevance review requires reviewer, reviewed_at, rule, sample, and decision")
        return False
    if review.get("decision") != "relevant":
        errors.append("relevance review decision must be 'relevant' to override lexical precheck")
        return False
    return True


def validate_audit_evidence(evidence_inputs, context, review_type, relevance_review=None):
    """Validate all evidence contracts before an A-F subprocess is allowed to run."""
    errors = []
    required = {"gold": "an independent gold/validation set", "query_hits": "query hits for A2",
                "query_log": "a reproducible query log", "screening_decisions": "human screening decisions",
                "search_iterations": "validated search iterations", "independent_pathways": "documented independent search pathways"}
    for key, label in required.items():
        if not evidence_inputs.get(key) or not pathlib.Path(evidence_inputs[key]).is_file():
            errors.append(label)
    gold = _load_records(evidence_inputs["gold"], "Gold set", errors) if evidence_inputs.get("gold") else []
    hits = _load_records(evidence_inputs["query_hits"], "Query hits", errors) if evidence_inputs.get("query_hits") else []
    scoped_gold, gold_scope = scope_records(gold, context)
    scoped_hits, hits_scope = scope_records(hits, context)
    if gold and not scoped_gold:
        errors.append("Gold set has no records inside the declared time/language boundary")
    if hits and not scoped_hits:
        errors.append("Query hits have no records inside the declared time/language boundary")
    if scoped_gold and not stable_record_ids(scoped_gold):
        errors.append("Gold set needs at least one stable identifier after scope filtering")
    hit_ids = stable_record_ids(scoped_hits)
    log = _load_json_object(evidence_inputs["query_log"], "Query log", errors) if evidence_inputs.get("query_log") else {}
    queries = log.get("queries", log.get("query_log", []))
    if not isinstance(queries, list) or not queries or any(not isinstance(row, dict) or not {"source", "query", "fields", "date"} <= set(row) for row in queries):
        errors.append("Query log needs non-empty queries[] with source/query/fields/date")
    decisions_doc = _load_json_object(evidence_inputs["screening_decisions"], "Screening decisions", errors) if evidence_inputs.get("screening_decisions") else {}
    decisions = decisions_doc.get("decisions", decisions_doc.get("screening_log", []))
    if not isinstance(decisions, list) or not decisions or any(not isinstance(row, dict) or row.get("decision") not in {"include", "exclude"} or not str(row.get("reason") or "").strip() for row in decisions):
        errors.append("Screening decisions need include/exclude decisions with reasons")
    else:
        decision_ids = []
        for row in decisions:
            candidate_ids = ids({"id": row.get("candidate_id")})
            if len(candidate_ids) != 1:
                errors.append("Screening decisions need one stable candidate_id per decision")
                continue
            decision_ids.append(next(iter(candidate_ids)))
        if len(decision_ids) != len(set(decision_ids)):
            errors.append("Screening decisions contain duplicate candidate_id values")
        if hit_ids and (set(decision_ids) - hit_ids):
            errors.append("Screening decisions reference candidate_id values outside query hits")
        if hit_ids and not hit_ids <= set(decision_ids):
            errors.append("Screening decisions must cover every stable-ID query hit before a full audit")
    iterations = _load_json_object(evidence_inputs["search_iterations"], "Search iterations", errors) if evidence_inputs.get("search_iterations") else {}
    iteration_errors, _warnings = validate_iterations(iterations) if iterations else (["missing"], [])
    if iteration_errors:
        errors.append("Search iterations invalid: " + "; ".join(iteration_errors[:3]))
    heldout = iterations.get("heldout_test_set", []) if isinstance(iterations, dict) else []
    scoped_heldout, _heldout_scope = scope_records(heldout, context)
    if not scoped_heldout:
        errors.append("Search iterations need a heldout_test_set inside the declared boundary")
    if scoped_gold and stable_record_ids(scoped_gold) != stable_record_ids(scoped_heldout):
        errors.append("Gold set and heldout_test_set must have identical stable-ID sets")
    pathways = _load_records(evidence_inputs["independent_pathways"], "Independent pathways", errors) if evidence_inputs.get("independent_pathways") else []
    minimum = {"systematic": 4, "umbrella": 5, "scoping": 3, "narrative": 3, "rapid": 2}.get(review_type, 3)
    valid_types = {"db_boolean", "backward_citation", "forward_citation", "related_articles", "standards_guidelines"}
    valid_paths = [row for row in pathways if isinstance(row, dict) and isinstance(row.get("pathway_id"), str)
                   and row.get("type") in valid_types and row.get("completed") is True
                   and row.get("screening_status") == "screened_complete"
                   and isinstance(row.get("yield"), (int, float))]
    if len(valid_paths) < minimum:
        errors.append(f"Independent pathways need {minimum} completed, screened paths with type and yield")
    else:
        pathway_ids = [row["pathway_id"].strip() for row in valid_paths]
        pathway_types = [row["type"] for row in valid_paths]
        if any(not value for value in pathway_ids) or len(pathway_ids) != len(set(pathway_ids)):
            errors.append("Independent pathways need unique, non-empty pathway_id values")
        if len(pathway_types) != len(set(pathway_types)):
            errors.append("Independent pathways need distinct pathway types; repeated types are not independent")
        screened_decision_ids = set(decision_ids) if 'decision_ids' in locals() else set()
        for pathway in valid_paths:
            raw_candidates = pathway.get("candidate_ids")
            raw_screened = pathway.get("screened_candidate_ids")
            if not isinstance(raw_candidates, list) or not raw_candidates or not isinstance(raw_screened, list):
                errors.append("Each independent pathway needs candidate_ids and screened_candidate_ids for auditable screening coverage")
                continue
            def canonical(values):
                resolved = []
                for value in values:
                    value_ids = ids({"id": value})
                    if len(value_ids) != 1:
                        return None
                    resolved.append(next(iter(value_ids)))
                return resolved
            candidate_ids = canonical(raw_candidates)
            screened_ids = canonical(raw_screened)
            if candidate_ids is None or screened_ids is None or len(candidate_ids) != len(set(candidate_ids)) or len(screened_ids) != len(set(screened_ids)):
                errors.append("Each pathway candidate_ids and screened_candidate_ids must contain unique stable identifiers")
                continue
            candidate_set, screened_set = set(candidate_ids), set(screened_ids)
            if candidate_set - hit_ids:
                errors.append("Independent pathway candidate_ids must belong to query hits")
            if candidate_set - screened_decision_ids:
                errors.append("Independent pathway candidates need corresponding human screening decisions")
            if screened_set != candidate_set:
                errors.append("Independent pathway screening coverage is incomplete or includes candidates outside that pathway")
    review_ok = _validate_relevance_review(relevance_review, errors)
    return errors, {"gold": gold_scope, "query_hits": hits_scope,
                    "heldout": _heldout_scope, "relevance_reviewed": review_ok}


def audit_readiness(library, question, context, evidence_inputs=None, relevance_review=None):
    """Keep an explicit audit request from becoming an empty A-F report."""
    records, scope = scope_records(load_library(library), context)
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
    terms = _question_terms(question)
    matches = sum(any(term in (str(row.get("title", "")) + " " + str(row.get("abstractNote", ""))).casefold()
                      for term in terms) for row in records)
    minimum_match_share = 0.20
    evidence_errors, evidence_scope = validate_audit_evidence(evidence_inputs or {}, context, context.get("review_type", ""), relevance_review)
    evidence_scope["library"] = scope
    if terms and total and matches / total < minimum_match_share and not evidence_scope["relevance_reviewed"]:
        reasons.append(f"topical relevance precheck: at least {minimum_match_share:.0%} of scoped records must match research-question terms, or supply a documented relevance review")
    reasons.extend(evidence_errors)
    if scope["unknown_language_records"] and context.get("languages") and "all" not in {normalize_language_tag(x) for x in context["languages"]}:
        reasons.append("language metadata is missing for scoped-library candidates; enrich it, document a manual boundary review, or use all")
    return records, reasons, evidence_scope


def validate_audit_boundaries(args):
    current_year = dt.date.today().year
    if args.time_start is None or args.time_end is None:
        return "--time-start and --time-end"
    if not 1900 <= args.time_start <= current_year or not 1900 <= args.time_end <= current_year:
        return "time boundaries from 1900 through the current year"
    if args.time_start > args.time_end:
        return "a time start that is not later than the time end"
    languages = [item.strip() for item in (args.languages or "").split(",") if item.strip()]
    if not languages or any(normalize_language_tag(item) is None for item in languages):
        return "supported ISO language or BCP-47 tags (or all) in --languages"
    return None


def write_sufficiency_precheck(out, reasons, output_language="zh-CN"):
    items = "".join(f"<li>{html.escape(reason)}</li>" for reason in reasons)
    if str(output_language).lower().startswith("en"):
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Sufficiency-audit precheck</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif"><h1>Sufficiency audit not started</h1>
<p>The requested audit lacks the minimum auditable evidence. This page is a precheck, not an A-F report.</p><h2>Minimum inputs still needed</h2><ul>{items}</ul>
<p>Recall and saturation need reproducible search logs, independent validation, screened decisions, and independent pathways.</p></main></body></html>"""
        (out / "sufficiency-precheck.html").write_text(page, encoding="utf-8")
        return
    page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>充分性审计预检查</title>
<body><main style="max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif">
<h1>充分性审计尚未开始</h1>
<p>你已请求充分性审计，但文献库尚未达到最小可审计输入。为避免生成大部分不可评估的 A–F 报告，本次仅交付预检查结果。</p>
<h2>最低需要补齐</h2><ul>{items}</ul>
<h2>之后仍需要的审计证据</h2><p>检索日志、独立验证集、人工筛选决定和独立检索路径用于判断覆盖与饱和度；缺少它们时不会宣称“检索充分”。</p>
</main></body></html>"""
    (out / "sufficiency-precheck.html").write_text(page, encoding="utf-8")


def run(args):
    out = prepare_output_dir(args.out, force=args.force)
    control = out / ".autopilot"; control.mkdir(exist_ok=True)
    print("[1/3] Preparing the first-run plan...", flush=True)
    sources = [x.strip().casefold() for x in args.sources.split(",") if x.strip()] if not args.offline else []
    plan = compile_query_plan(args.question, sources or ["arxiv"])
    terms = plan["queries"][0].get("terms", []) if plan["queries"] else []
    config_path = control / "run-config.json"; context_path = control / "context.json"; plan_path = control / "query-plan.json"; bundle_dir = control / "inputs"; bundle_dir.mkdir(exist_ok=True)
    evidence_inputs = {key: value for key, value in {
        "gold": args.gold, "query_hits": args.query_hits, "query_log": args.query_log,
        "screening_decisions": args.screening_decisions, "search_iterations": args.search_iterations,
        "independent_pathways": args.independent_pathways, "relevance_review": args.relevance_review,
    }.items() if value}
    bundle_manifest = {}
    library_reference = None
    if args.library:
        bundled_library = bundle_input(args.library, bundle_dir, "library")
        if bundled_library:
            library_reference, bundle_manifest["library"] = bundled_library
    bundled_evidence = {}
    for key, value in evidence_inputs.items():
        bundled = bundle_input(value, bundle_dir, key.replace("_", "-"))
        if bundled:
            bundled_evidence[key], bundle_manifest[key] = bundled
    context = build_context(args.question, terms)
    context.update({"review_type": args.review_type, "year_start": args.time_start, "year_end": args.time_end,
                    "languages": [item.strip() for item in (args.languages or "").split(",") if item.strip()],
                    "output_language": args.output_language or "zh-CN", "scope_status": args.scope_status})
    if args.independent_pathways:
        try:
            pathways = json.loads(pathlib.Path(args.independent_pathways).read_text(encoding="utf-8"))
            context["independent_pathways"] = pathways if isinstance(pathways, list) else pathways.get("items", [])
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise ValueError(f"invalid --independent-pathways: {exc}")
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    bundled_evidence["context"] = "context.json"
    config_path.write_text(json.dumps(build_config(
        args.question, library_reference, args.review_type, sources, args.offline, args.scope_status,
        allow_metadata_enrichment=args.allow_metadata_enrichment,
        allow_external_discovery=args.allow_external_discovery,
        allow_citation_tracking=args.allow_citation_tracking, time_start=args.time_start,
        time_end=args.time_end, languages=[item.strip() for item in (args.languages or "").split(",") if item.strip()],
        output_language=args.output_language or "zh-CN", evidence_inputs=bundled_evidence), ensure_ascii=False, indent=2), encoding="utf-8")
    (control / "input-bundle-manifest.json").write_text(json.dumps(bundle_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    output_language = args.output_language or "zh-CN"
    if args.scope_status == "scope_uncertain":
        write_onboarding(out, args.question, plan, sources, output_language)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "needs_scope_confirmation", "sources_requested": sources, "question": args.question, "scope_status": args.scope_status, "human_gates": ["scope"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    if args.scope_status == "out_of_scope":
        if args.library:
            write_library_health(out, pathlib.Path(args.library).resolve(), output_language, out_of_scope=True)
            manifest = {"schema_version": "1.0", "mode": "out_of_scope_library_health", "audit_status": "not_started", "question": args.question, "scope_status": args.scope_status}
        else:
            write_out_of_scope_notice(out, args.question, output_language)
            manifest = {"schema_version": "1.0", "mode": "out_of_scope", "audit_status": "not_started", "question": args.question, "scope_status": args.scope_status}
        (out / "autopilot-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] Delivered an out-of-scope bibliographic health check." if args.library else "[2/3] Delivered an out-of-scope stop notice.", flush=True)
        return
    mode = args.mode
    if mode == "auto":
        mode = "library-health" if args.library else "search-preparation"
    if mode == "search-preparation":
        write_search_preparation(out, args.question, plan, args.output_language or "zh-CN")
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "search_preparation", "audit_status": "not_started", "question": args.question}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] No library supplied: delivered a search-preparation plan, not an audit.", flush=True)
        return
    if not args.library:
        raise ValueError("library-health and sufficiency-audit require --library; use search-preparation without one.")
    library = pathlib.Path(args.library).resolve()
    if mode == "library-health":
        write_library_health(out, library, args.output_language or "zh-CN")
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "library_health", "audit_status": "not_started", "question": args.question}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] Delivered a library-health check, not a sufficiency audit.", flush=True)
        return
    missing = []
    if not args.review_type: missing.append("--review-type")
    boundary_error = validate_audit_boundaries(args)
    if boundary_error: missing.append(boundary_error)
    if not args.output_language: missing.append("--output-language")
    if missing:
        raise ValueError("sufficiency-audit requires explicit confirmation of " + ", ".join(missing) + ".")
    _, readiness_gaps, scope_matrix = audit_readiness(library, args.question, context, evidence_inputs, args.relevance_review)
    if readiness_gaps:
        write_sufficiency_precheck(out, readiness_gaps, args.output_language or "zh-CN")
        precheck = {"schema_version": "1.0", "mode": "sufficiency_precheck",
                    "audit_status": "not_started", "completion": "precheck_delivered",
                    "exit_code_contract": 0, "question": args.question,
                    "missing_minimum_inputs": readiness_gaps, "scope_matrix": scope_matrix}
        (out / "sufficiency-precheck.json").write_text(json.dumps(precheck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "autopilot-manifest.json").write_text(json.dumps(precheck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("[2/3] Delivered a sufficiency precheck; the A-F audit was not started.", flush=True)
        return
    print("[2/3] Running the sufficiency audit; missing evidence will remain explicit.", flush=True)
    command = [sys.executable, str(pathlib.Path(__file__).with_name("run_full_audit.py")), "run",
               "--run-config", str(config_path), "--out", str(out)]
    if args.allow_external_discovery and not args.offline:
        command += ["--collect", "--query-plan", str(plan_path), "--active-screen-budget", str(args.screen_budget)]
    # The child accepts only this autopilot-owned control directory; it never
    # receives blanket overwrite authority for user output files.
    command.append("--allow-autopilot-control-dir")
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
    parser.add_argument("--force", action="store_true", help="explicitly allow replacing an existing autopilot output directory")
    parser.add_argument("--mode", default="auto", choices=("auto", "search-preparation", "library-health", "sufficiency-audit"),
                        help="Search preparation and library health do not produce A-F sufficiency conclusions.")
    parser.add_argument("--review-type", choices=("narrative", "systematic", "scoping", "rapid", "umbrella"))
    parser.add_argument("--time-start", type=int, help="Explicit start year required for sufficiency-audit.")
    parser.add_argument("--time-end", type=int, help="Explicit end year required for sufficiency-audit.")
    parser.add_argument("--languages", help="Comma-separated language boundary required for sufficiency-audit.")
    parser.add_argument("--output-language", choices=("zh-CN", "en"), help="Explicit report language required for sufficiency-audit.")
    parser.add_argument("--gold", help="Independent gold/validation set required before an A-F audit can start.")
    parser.add_argument("--query-hits", help="Scope-filterable query-hit records required to calculate A2.")
    parser.add_argument("--query-log", help="Reproducible query log required before an A-F audit can start.")
    parser.add_argument("--screening-decisions", help="Human screening decisions required before an A-F audit can start.")
    parser.add_argument("--search-iterations", help="Validated development/held-out iteration record required for A2 independence.")
    parser.add_argument("--independent-pathways", help="JSON list of documented independent search pathways required before an A-F audit can start.")
    parser.add_argument("--relevance-review", help="JSON reviewer/date/rule/sample/decision record required to override lexical relevance precheck.")
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
