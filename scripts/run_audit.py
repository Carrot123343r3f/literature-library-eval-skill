#!/usr/bin/env python3
"""Generate a conservative, reproducible engineering literature-library audit."""
import argparse
import datetime as dt
import html
import json
import pathlib
import re
from collections import Counter
from math import log


def doi(value):
    m = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return m.group(1).rstrip(".,;:)]}").lower() if m else ""


def ids(row):
    found = set()
    for key in ("DOI", "doi", "extra", "id"):
        value = doi(row.get(key))
        if value:
            found.add("doi:" + value)
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"), ("PMCID", "pmcid"),
                        ("arxiv", "arxiv"), ("arXiv", "arxiv"), ("openalex_id", "openalex")):
        if row.get(key):
            found.add(prefix + ":" + str(row[key]).casefold())
    raw = str(row.get("id") or "").casefold()
    if raw.startswith(("pmid:", "pmcid:", "arxiv:", "openalex:")):
        found.add(raw)
    if row.get("source") == "arxiv" and raw:
        found.add("arxiv:" + raw)
    return found


def title(row):
    return re.sub(r"[^\w]", "", str(row.get("title") or "").casefold())


def load_items(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("items", [])


def load_snapshot(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    sources = {}
    for query in data.get("queries", []):
        for name, result in query.get("sources", {}).items():
            bucket = sources.setdefault(name, {"items": [], "statuses": []})
            bucket["items"].extend(result.get("items", []))
            bucket["statuses"].append(result.get("status", "unknown"))
    if not sources and isinstance(data.get("sources"), dict):
        sources = {name: {"items": value.get("items", []), "statuses": [value.get("status", "unknown")]} for name, value in data["sources"].items()}
    return sources


def benchmark(library, base):
    lib_ids = set().union(*(ids(x) for x in library)) if library else set()
    stable = [x for x in base if isinstance(x, dict) and ids(x)]
    uncertain = [x for x in base if not isinstance(x, dict) or not ids(x)]
    candidates = [str(x if isinstance(x, str) else x.get("title", "")) for x in uncertain
                  if title(x if isinstance(x, dict) else {"title": x}) in {title(y) for y in library}]
    matched_ids = set().union(*(ids(x) & lib_ids for x in stable)) if stable else set()
    return {"status": "measured" if stable else "not_assessable", "total": len(stable),
            "matched": sum(bool(ids(x) & lib_ids) for x in stable),
            "recall": round(sum(bool(ids(x) & lib_ids) for x in stable) / len(stable), 3) if stable else None,
            "missing_ids": sorted(set().union(*(ids(x) for x in stable)) - lib_ids) if stable else [],
            "manual_title_candidates": candidates,
            "note": "Only stable identifiers contribute to measured recall."}


def a2(gold, hits):
    if gold is None or hits is None:
        return {"status": "not_assessable", "recall": None, "note": "Supply both gold set and executed query-hit snapshot."}
    gold_ids = set().union(*(ids(x) for x in gold if isinstance(x, dict)))
    hit_ids = set().union(*(ids(x) for x in hits if isinstance(x, dict)))
    if not gold_ids:
        return {"status": "not_assessable", "recall": None, "note": "Gold set lacks stable identifiers."}
    matched = gold_ids & hit_ids
    return {"status": "measured", "total": len(gold_ids), "matched": len(matched),
            "recall": round(len(matched) / len(gold_ids), 3), "missing_ids": sorted(gold_ids - hit_ids),
            "note": "An executed zero-result query is measured recall 0, not unavailable evidence."}


def a3(sources):
    if not sources or len(sources) < 2:
        return {"status": "not_assessable", "note": "Supply deduplicable snapshots from at least two sources for a candidate lower bound."}
    incomplete = sorted(name for name, meta in sources.items() if any(status != "complete" for status in meta.get("statuses", [])))
    source_ids = {name: set().union(*(ids(x) for x in meta.get("items", []) if isinstance(x, dict))) for name, meta in sources.items()}
    union = set().union(*source_ids.values())
    if not union:
        return {"status": "not_assessable", "note": "Candidate snapshots contain no stable identifiers."}
    overlaps = {"|".join(pair): len(source_ids[pair[0]] & source_ids[pair[1]])
                for pair in __import__('itertools').combinations(sorted(source_ids), 2)}
    result = {"status": "estimated_lower_bound" if not incomplete else "partial_snapshot", "deduplicated_candidate_lower_bound": len(union),
            "source_unique_identifier_counts": {k: len(v) for k, v in source_ids.items()}, "pairwise_overlaps": overlaps,
            "incomplete_sources": incomplete,
            "note": "This is a multi-source identifier lower bound, not Recall or a capture–recapture estimate."}
    if incomplete: result["note"] = "Source snapshots are incomplete; this provisional count must not support A3 coverage conclusions."
    return result


def health(library, standards=None):
    standards = standards or {}
    n = len(library)
    fields = {k: round(sum(bool(str(x.get(k) or "").strip()) for x in library) / n, 3) if n else None
              for k in ("title", "creators", "date", "publicationTitle", "abstractNote", "DOI", "url")}
    dois = Counter(doi(x.get("DOI") or x.get("doi") or x.get("id")) for x in library)
    dois.pop("", None)
    title_year = Counter((title(x), str(x.get("date") or "")[:4]) for x in library if title(x))
    attachments = sum(bool(x.get("attachments")) for x in library)
    oa_links = sum(bool(x.get("open_access_url") or x.get("fulltext_url")) for x in library)
    provenance = sum(bool(x.get("source") or x.get("source_database") or x.get("collection")) for x in library)
    flags = sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library)
    core_min = float(standards.get("f_core_metadata_rate", 0.95)); abstract_min = float(standards.get("f_abstract_rate", 0.80)); access_min = float(standards.get("f_access_rate", 0.80)); provenance_min = float(standards.get("f_provenance_rate", 0.95))
    checks = {"F5_metadata": "pass" if all(fields[k] is not None and fields[k] >= core_min for k in ("title", "creators", "date", "publicationTitle", "DOI")) and (fields["abstractNote"] is None or fields["abstractNote"] >= abstract_min) else "fail",
              "F6_exact_duplicates": "pass" if not sum(v > 1 for v in dois.values()) else "fail",
              "F6_version_decisions": "not_assessable", "F7_access": "pass" if n and (attachments + oa_links) / n >= access_min else "warning",
              "F4_provenance": "pass" if n and provenance / n >= provenance_min else "fail", "F8_corrections": "not_assessable"}
    return {"status": "measured" if n else "not_assessable", "records": n, "field_completeness": fields, "checks": checks,
            "duplicate_doi_groups": sum(v > 1 for v in dois.values()), "duplicate_title_year_groups": sum(v > 1 for v in title_year.values()),
            "attachment_rate": round(attachments / n, 3) if n else None, "open_link_rate": round(oa_links / n, 3) if n else None,
            "provenance_rate": round(provenance / n, 3) if n else None, "correction_flag_records": flags,
            "note": "Version-family equivalence, access permission and correction status require source checking or review."}


def stability(context):
    rounds = context.get("search_rounds", [])
    rates = [round(x["included_high"] / x["core_before"], 4) for x in rounds
             if isinstance(x.get("core_before"), (int, float)) and x["core_before"] > 0 and isinstance(x.get("included_high"), (int, float))]
    paths = set(context.get("planned_pathways", [])); done = {x.get("pathway") for x in rounds if x.get("completed")}
    complete = round(len(paths & done) / len(paths), 3) if paths else None
    standards = context.get("standards", {})
    threshold = float(standards.get("f_new_rate_threshold", context.get("new_rate_threshold", 0.02)))
    yield_threshold = float(standards.get("f_marginal_yield_threshold", context.get("marginal_yield_threshold", 0.05)))
    yields = [x.get("yield") for x in context.get("source_marginal_yields", []) if isinstance(x.get("yield"), (int, float))]
    converged = len(rates) >= 2 and all(x < threshold for x in rates[-2:]) and complete == 1.0 and context.get("independent_validation_passed") is True and bool(yields) and all(x < yield_threshold for x in yields)
    checks = {"F3_new_rate": "pass" if len(rates) >= 2 and all(x < threshold for x in rates[-2:]) else "not_assessable" if len(rates) < 2 else "fail",
              "F2_pathways": "pass" if complete == 1.0 else "not_assessable" if complete is None else "fail",
              "F3_marginal_yield": "pass" if yields and all(x < yield_threshold for x in yields) else "not_assessable" if not yields else "fail",
              "F1_query_traceability": "pass" if context.get("run_log_complete") is True else "not_assessable",
              "F3_independent_validation": "pass" if context.get("independent_validation_passed") is True else "not_assessable" if "independent_validation_passed" not in context else "fail"}
    return {"status": "measured" if rounds else "not_assessable", "high_confidence_new_rates": rates, "pathway_completion": complete,
            "independent_validation_passed": context.get("independent_validation_passed") is True, "source_marginal_yields": yields,
            "thresholds": {"new_rate": threshold, "marginal_yield": yield_threshold}, "checks": checks,
            "verdict": "趋于稳定（仅限声明范围）" if converged and all(x == "pass" for x in checks.values()) else "趋稳不可证明" if "not_assessable" in checks.values() else "未证明稳定"}


def currency(context):
    raw = context.get("last_successful_search", {})
    raw = {"unspecified": raw} if isinstance(raw, list) else raw
    dates = {}
    for source, value in raw.items():
        try: dates[source] = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except (TypeError, ValueError): pass
    today = dt.date.today()
    max_days = int(context.get("standards", {}).get("d_freshness_days", 90))
    sources = {k: {"date": v.isoformat(), "days_since": (today-v).days, "verdict": "pass" if (today-v).days <= max_days else "warning"} for k, v in dates.items()}
    planned = set(context.get("planned_sources", [])); missing = sorted(planned - set(dates))
    checks = {"D1_freshness": "pass" if sources and all(x["verdict"] == "pass" for x in sources.values()) else "warning" if sources else "not_assessable",
              "D2_source_window": "pass" if planned and not missing else "warning" if planned else "not_assessable",
              "D3_frontier_coverage": context.get("frontier_coverage_verdict", "not_assessable"),
              "D4_version_currency": context.get("version_currency_verdict", "not_assessable"), "D5_time_distribution": "not_assessable"}
    return {"status": "measured" if dates else "not_assessable", "freshness_threshold_days": max_days, "sources": sources, "missing_planned_sources": missing, "checks": checks,
            "note": "Report every successful source date; a recent source does not hide stale or failed sources."}


def structure(library, context):
    taxonomy = context.get("taxonomy", [])
    mapped = []
    standards = context.get("standards", {}); required = int(standards.get("b_min_records_per_critical_stratum", 1)); confidence_min = float(standards.get("b_min_classification_confidence", 0.80))
    for row in taxonomy:
        expected = row.get("expected", True)
        count = row.get("high_confidence_records")
        confidence = row.get("classification_confidence")
        status = "gap" if expected and (count or 0) < required else "covered" if count else "out_of_scope"
        mapped.append({"name": row.get("name", "unnamed"), "expected": expected, "records": count,
                       "classification_confidence": confidence, "status": status})
    source_counts = Counter(str(x.get("source") or x.get("source_database") or "unknown") for x in library)
    n = len(library); shares = [x / n for x in source_counts.values()] if n else []
    entropy = -sum(p * log(p) for p in shares if p)
    unclassified_rate = context.get("unclassified_rate")
    checks = {"B1_taxonomy": "pass" if taxonomy else "not_assessable", "B2_critical_strata": "pass" if taxonomy and not [x for x in mapped if x["status"] == "gap"] else "fail" if taxonomy else "not_assessable",
              "B3_classification": "pass" if all(x["classification_confidence"] is not None and x["classification_confidence"] >= confidence_min for x in mapped) and (unclassified_rate is None or unclassified_rate <= float(standards.get("b_max_unclassified_rate", 0.10))) else "warning" if taxonomy else "not_assessable", "B4_source_dependence": "warning" if shares and max(shares) > float(standards.get("b_source_dependence_warning", 0.80)) else "pass" if shares else "not_assessable", "B5_stratified_coverage": "not_assessable"}
    return {"status": "measured" if taxonomy or library else "not_assessable", "taxonomy": mapped, "checks": checks,
            "uncovered_expected_strata": [x["name"] for x in mapped if x["status"] == "gap"],
            "source_dependence": {"counts": dict(source_counts), "top_source_share": round(max(shares), 3) if shares else None,
                                  "shannon_entropy": round(entropy, 3) if shares else None},
            "note": "Taxonomy must describe engineering conditions, methods, metrics or applications; concentration is descriptive, not a quality verdict."}


def evidence(library, context):
    required = set(context.get("engineering_evidence_types_required", []))
    present = {str(x.get("engineering_evidence_type") or x.get("evidence_type")) for x in library if x.get("engineering_evidence_type") or x.get("evidence_type")}
    standards = context.get("standards", {}); field_rate = float(standards.get("c_required_field_rate", 0.80)); n = len(library)
    flags = {"preprint": sum(bool(x.get("is_preprint")) for x in library),
             "retraction_or_correction_flags": sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library),
             "code_or_data_links": sum(bool(x.get("code_url") or x.get("data_url")) for x in library),
             "missing_conditions": sum(not bool(x.get("operating_conditions") or x.get("test_conditions")) for x in library)}
    condition_rate = round(sum(bool(x.get("operating_conditions") or x.get("test_conditions")) for x in library) / n, 3) if n else None
    metric_rate = round(sum(bool(x.get("baseline") or x.get("performance_metrics")) for x in library) / n, 3) if n else None
    checks = {"C1_evidence_types": "pass" if not (required-present) else "fail", "C2_conditions": "pass" if condition_rate is not None and condition_rate >= field_rate else "warning", "C3_baselines_metrics": "pass" if metric_rate is not None and metric_rate >= field_rate else "warning",
              "C4_standards_data_versions": context.get("standards_data_versions_verdict", "not_assessable"), "C5_validation_strength": context.get("validation_strength_verdict", "not_assessable"), "C6_credibility_flags": context.get("credibility_flags_verdict", "not_assessable")}
    return {"status": "screening" if library else "not_assessable", "required_evidence_types": sorted(required), "checks": checks, "condition_rate": condition_rate, "baseline_or_metric_rate": metric_rate,
            "present_evidence_types": sorted(present), "missing_required_types": sorted(required - present), "credibility_flags": flags,
            "note": "This is engineering evidence screening. It does not determine causal validity, benchmark fairness, code reproducibility or version equivalence."}


def influence(library, context):
    n = len(library); citations = [x.get("cited_by_count") for x in library if isinstance(x.get("cited_by_count"), (int, float))]
    sources = Counter(str(x.get("source") or x.get("source_database") or "unknown") for x in library); shares = [v / n for v in sources.values()] if n else []
    rate = len(citations) / n if n else None; minimum = float(context.get("standards", {}).get("e_citation_data_rate", 0.80))
    checks = {"E1_citation_data": "pass" if rate is not None and rate >= minimum else "warning" if rate is not None else "not_assessable",
              "E2_influence_distribution": "screening" if citations else "not_assessable", "E3_knowledge_paths": context.get("knowledge_paths_verdict", "not_assessable"),
              "E4_channel_diversity": "warning" if shares and max(shares) > 0.80 else "pass" if shares else "not_assessable", "E5_authority_anchors": context.get("authority_anchors_verdict", "not_assessable")}
    return {"status": "screening" if n else "not_assessable", "citation_data_rate": round(rate, 3) if rate is not None else None,
            "citation_median": sorted(citations)[len(citations)//2] if citations else None, "source_distribution": dict(sources), "checks": checks,
            "note": "Citation and channel metrics are contextual diagnostics, never a research-quality score."}


def artifacts(paths):
    return {name: {"provided": bool(value), "path": value} for name, value in paths.items()}


def balance(library, standards=None):
    """Source balance diagnostics: dispersion is a search-risk signal, never quality."""
    standards = standards or {}
    counts = Counter(str(x.get("source") or x.get("source_database") or "unknown") for x in library)
    values = list(counts.values()); n = sum(values); k = len(values)
    if not n or not k:
        return {"status": "not_assessable", "checks": {"C1_critical_topics": "not_assessable", "C2_source_balance": "not_assessable"}}
    mean = n / k
    cv = (sum((x - mean) ** 2 for x in values) / k) ** 0.5 / mean if mean else None
    gini = sum(abs(a - b) for a in values for b in values) / (2 * k * n)
    entropy = -sum((x / n) * log(x / n) for x in values if x)
    normalized_entropy = entropy / log(k) if k > 1 else 0.0
    limits = {"top_share": float(standards.get("balance_top_share_warning", 0.80)), "cv": float(standards.get("balance_cv_warning", 1.00)), "gini": float(standards.get("balance_gini_warning", 0.60)), "shannon_low": float(standards.get("balance_shannon_low_warning", 0.45)), "shannon_high": float(standards.get("balance_shannon_high_warning", 0.95))}
    flags = []
    if max(values) / n > limits["top_share"]: flags.append("top_source_share")
    if cv > limits["cv"]: flags.append("cv")
    if gini > limits["gini"]: flags.append("gini")
    if normalized_entropy < limits["shannon_low"]: flags.append("shannon_low")
    if k >= 3 and normalized_entropy > limits["shannon_high"]: flags.append("shannon_high")
    return {"status": "measured", "counts": dict(counts), "top_source_share": round(max(values) / n, 3), "cv": round(cv, 3), "gini": round(gini, 3), "shannon": round(entropy, 3), "normalized_shannon": round(normalized_entropy, 3), "limits": limits, "flags": flags, "checks": {"C1_critical_topics": "not_assessable", "C2_source_balance": "warning" if flags else "pass"}}


def recency(library, context):
    profile = str(context.get("profile", "")).lower()
    fast = any(x in profile for x in ("computer", "ai", "software", "electronic", "communication"))
    slow = any(x in profile for x in ("civil", "energy", "infrastructure", "aerospace", "transport"))
    defaults = (3, .40) if fast else (7, .30) if slow else (5, .35)
    standards = context.get("standards", {}); years = int(standards.get("recency_years", defaults[0])); minimum = float(standards.get("recency_min_share", defaults[1]))
    current_year = dt.date.today().year; parsed = []
    for item in library:
        try: parsed.append(int(str(item.get("date") or "")[:4]))
        except ValueError: pass
    recent = sum(y >= current_year - years + 1 for y in parsed)
    share = recent / len(parsed) if parsed else None
    preprints = sum(bool(x.get("is_preprint")) for x in library)
    checks = {"D1_search_freshness": currency(context)["checks"]["D1_freshness"], "D2_recent_share": "pass" if share is not None and share >= minimum else "warning" if share is not None else "not_assessable", "D3_frontier": context.get("frontier_coverage_verdict", "not_assessable"), "D4_versions_preprints": context.get("version_currency_verdict", "not_assessable")}
    return {"status": "measured" if parsed else "not_assessable", "window_years": years, "minimum_share": minimum, "dated_records": len(parsed), "recent_records": recent, "recent_share": round(share, 3) if share is not None else None, "preprint_records": preprints, "checks": checks}


def quality(library, context):
    citations = sorted([int(x.get("cited_by_count")) for x in library if isinstance(x.get("cited_by_count"), (int, float))], reverse=True)
    h = max((idx for idx, value in enumerate(citations, 1) if value >= idx), default=0)
    tiers = {str(x).strip().lower() for x in context.get("tier1_venues", [])}
    venues = [str(x.get("publicationTitle") or x.get("venue") or "").strip().lower() for x in library]
    tier_hits = sum(bool(v and v in tiers) for v in venues)
    rate = tier_hits / len(library) if library and tiers else None
    return {"status": "measured" if library else "not_assessable", "citation_records": len(citations), "h_core": h if citations else None, "tier1_venues_configured": len(tiers), "tier1_records": tier_hits if tiers else None, "tier1_rate": round(rate, 3) if rate is not None else None, "checks": {"E1_h_core": "screening" if citations else "not_assessable", "E2_tier1": "screening" if tiers else "not_assessable"}}


def compact(value):
    """Make a measurement safe and readable inside a Markdown table cell."""
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    return text.replace("|", "／").replace("\n", " ")


def threshold_verdict(value, threshold):
    if value is None or threshold is None:
        return "not_assessable"
    return "pass" if value >= threshold else "fail"


def indicator_rows(report):
    """Return the single peer-level A1--F8 audit register used in every report."""
    readable_names = {
        "A1": "已知必纳入文献找回率", "A2": "检索式找回已知相关文献的能力", "A3": "多来源检索到的最少唯一候选数", "A4": "关键标准和核心文献是否找全",
        "B1": "工程问题的分类框架是否完整", "B2": "每个关键工程场景是否有文献", "B3": "文献分类结果是否可信", "B4": "是否过度依赖单一来源", "B5": "关键场景是否逐项验证找回率",
        "C1": "所需工程证据类型是否齐全", "C2": "文献是否说明适用工况", "C3": "文献是否给出可比的指标和基线", "C4": "标准、数据和软件版本是否明确", "C5": "验证是否足以支撑工程结论", "C6": "可信度风险是否已处理",
        "D1": "各检索来源是否仍是最新", "D2": "计划检索的来源是否全部完成", "D3": "新兴技术和新术语是否被覆盖", "D4": "是否使用了最新且正确的文献版本", "D5": "文献年代结构是否已被检查",
        "E1": "引用数据是否足够用于背景判断", "E2": "影响力是否由少数文献主导", "E3": "是否连到关键研究和技术路线", "E4": "是否过度依赖单一发表渠道", "E5": "领域标准和权威工作是否齐全",
        "F1": "检索过程能否被他人复跑", "F2": "计划的检索路径是否完成", "F3": "检索是否有趋于饱和的证据", "F4": "每篇纳入文献能否追溯来源和决定", "F5": "题录信息是否完整可用", "F6": "重复和不同版本是否已妥善处理", "F7": "全文、代码和数据是否有获取线索", "F8": "撤稿、更正和异常是否已核查"
    }
    c, b, s, e, d, i, p, h = (report["coverage"], report["coverage"].get("benchmark", {}),
                              report["structure"], report["evidence"], report["currency"],
                              report["influence"], report["process"], report["library_health"])
    standards = report.get("standards", {})
    a1_min = standards.get("a1_min_recall")
    a2_min = standards.get("a2_min_recall")
    checks = lambda group, key: group.get("checks", {}).get(key, "not_assessable")
    add = []
    def row(parent, sub, name, standard, verdict, current, evidence_state, note):
        add.append((parent, sub, readable_names.get(sub, name), standard, verdict, compact(current), evidence_state, note))

    row("A 覆盖验证", "A1", "稳定标识符基准集召回", f"配置阈值 ≥ {a1_min}" if a1_min is not None else "需在 context.standards 配置 a1_min_recall", threshold_verdict(c["a1"].get("recall"), a1_min), c["a1"].get("recall"), c["a1"].get("status"), "仅以 DOI、PMID 等稳定标识符匹配；未配置阈值时不作达标结论。")
    row("A 覆盖验证", "A2", "金标准查询灵敏度", f"配置阈值 ≥ {a2_min}" if a2_min is not None else "需在 context.standards 配置 a2_min_recall", threshold_verdict(c["a2"].get("recall"), a2_min), c["a2"].get("recall"), c["a2"].get("status"), "Gold set 必须有独立来源与纳入依据。")
    row("A 覆盖验证", "A3", "多源候选集下界", "至少两个来源且快照完整；仅报告下界", "pass" if c["a3"].get("status") == "estimated_lower_bound" else "not_assessable", c["a3"].get("deduplicated_candidate_lower_bound"), c["a3"].get("status"), "候选数下界不是 Recall，也不是饱和证明。")
    row("A 覆盖验证", "A4", "关键锚点命中", "配置关键锚点及命中阈值", "not_assessable", "未实现结构化输入", "not_assessable", "保留为显式审计项，避免以主观印象替代锚点检验。")

    row("B 范围结构", "B1", "范围分类体系", "提供与工程问题对应的 taxonomy", checks(s, "B1_taxonomy"), len(s.get("taxonomy", [])), s.get("status"), "分类应覆盖工况、方法、性能指标或应用场景。")
    row("B 范围结构", "B2", "关键层覆盖", f"每个预期关键层 ≥ {standards.get('b_min_records_per_critical_stratum', 1)} 条高置信记录", checks(s, "B2_critical_strata"), s.get("uncovered_expected_strata", []), s.get("status"), "列出的缺口是可执行补检索对象。")
    row("B 范围结构", "B3", "分类可靠性", f"置信度 ≥ {standards.get('b_min_classification_confidence', 0.80)}；未分类率 ≤ {standards.get('b_max_unclassified_rate', 0.10)}", checks(s, "B3_classification"), {"unclassified_rate": report.get("context", {}).get("unclassified_rate")}, s.get("status"), "分类置信度应来自已保存规则或人工复核抽样。")
    row("B 范围结构", "B4", "来源集中度", f"单一来源占比不应 > {standards.get('b_source_dependence_warning', 0.80)}", checks(s, "B4_source_dependence"), s.get("source_dependence", {}), s.get("status"), "集中度为风险信号，不是文献质量评分。")
    row("B 范围结构", "B5", "分层覆盖验证", "各层均有独立覆盖验证证据", checks(s, "B5_stratified_coverage"), "未提供分层验证输入", s.get("status"), "需把 A1/A2 或人工复核结果关联至各层。")

    row("C 工程证据适配", "C1", "工程证据类型", "所有必需 evidence type 均出现", checks(e, "C1_evidence_types"), {"missing": e.get("missing_required_types", [])}, e.get("status"), "例如仿真、台架、现场、标准测试或失效分析。")
    row("C 工程证据适配", "C2", "工况与边界条件", f"记录率 ≥ {standards.get('c_required_field_rate', 0.80)}", checks(e, "C2_conditions"), e.get("condition_rate"), e.get("status"), "不能仅以题名或摘要推断适用工况。")
    row("C 工程证据适配", "C3", "基线与性能指标", f"记录率 ≥ {standards.get('c_required_field_rate', 0.80)}", checks(e, "C3_baselines_metrics"), e.get("baseline_or_metric_rate"), e.get("status"), "需保留对比基线和可解释的性能指标。")
    row("C 工程证据适配", "C4", "标准、数据与版本", "已核验标准版本、数据版本和模型版本", checks(e, "C4_standards_data_versions"), "依赖 context 判定", e.get("status"), "版本信息缺失时不能声称可比。")
    row("C 工程证据适配", "C5", "验证强度", "按项目设定的验证层级完成核验", checks(e, "C5_validation_strength"), "依赖 context 判定", e.get("status"), "区分仿真、实验、现场与独立复现。")
    row("C 工程证据适配", "C6", "可信度标记", "预印本、撤稿、更正及代码/数据线索已核验", checks(e, "C6_credibility_flags"), e.get("credibility_flags", {}), e.get("status"), "标记是筛查线索，不等于对研究质量的裁决。")

    row("D 时效与技术演化", "D1", "检索新鲜度", f"每个来源距最近成功检索 ≤ {d.get('freshness_threshold_days')} 天", checks(d, "D1_freshness"), d.get("sources", {}), d.get("status"), "最近一个来源不能掩盖其他来源已过期。")
    row("D 时效与技术演化", "D2", "关键来源时间窗", "所有计划来源均有成功检索日期", checks(d, "D2_source_window"), d.get("missing_planned_sources", []), d.get("status"), "缺失来源应重跑或在报告中说明排除。")
    row("D 时效与技术演化", "D3", "前沿技术覆盖", "按项目定义前沿主题并保存核验结果", checks(d, "D3_frontier_coverage"), "依赖 context 判定", d.get("status"), "避免把近期发表时间误当作前沿覆盖。")
    row("D 时效与技术演化", "D4", "版本时效", "预印本、会议版与正式版关系已核验", checks(d, "D4_version_currency"), "依赖 context 判定", d.get("status"), "与 F6 的去重/版本决策相互引用。")
    row("D 时效与技术演化", "D5", "时间分布", "按研究问题定义必要历史与近期窗口", checks(d, "D5_time_distribution"), "未提供时间分布输入", d.get("status"), "不设置跨领域统一的发表年份配额。")

    row("E 学术影响与知识关联", "E1", "引用数据可得性", f"可得率 ≥ {standards.get('e_citation_data_rate', 0.80)}", checks(i, "E1_citation_data"), i.get("citation_data_rate"), i.get("status"), "引用数据只作诊断，不作为质量总分。")
    row("E 学术影响与知识关联", "E2", "影响力分布", "具备可解释的分布诊断", checks(i, "E2_influence_distribution"), {"median": i.get("citation_median")}, i.get("status"), "应防止单一高被引记录掩盖结构缺口。")
    row("E 学术影响与知识关联", "E3", "知识路径", "已保存关键方法、标准、应用之间的链接核验", checks(i, "E3_knowledge_paths"), "依赖 context 判定", i.get("status"), "适合工程技术路线、标准与应用关联。")
    row("E 学术影响与知识关联", "E4", "发表渠道多样性", "来源分布无未解释的单一依赖", checks(i, "E4_channel_diversity"), i.get("source_distribution", {}), i.get("status"), "渠道多样性不是强制配额。")
    row("E 学术影响与知识关联", "E5", "权威锚点", "项目定义的标准、指南或核心研究已核验", checks(i, "E5_authority_anchors"), "依赖 context 判定", i.get("status"), "不能以期刊名或引用数替代权威性判断。")

    row("F 过程合规、库健康与可追溯", "F1", "检索式与运行可追溯", "run log 完整且可定位检索式、日期、来源", checks(p, "F1_query_traceability"), "run_log_complete=" + str(report.get("context", {}).get("run_log_complete")), p.get("status"), "过程记录是审计证据，不是 A 的附属项。")
    row("F 过程合规、库健康与可追溯", "F2", "检索路径完成", "所有计划路径完成", checks(p, "F2_pathways"), p.get("pathway_completion"), p.get("status"), "未完成路径必须列入缺口或说明排除理由。")
    row("F 过程合规、库健康与可追溯", "F3", "趋稳证据", f"最后两轮高置信新增率 < {p.get('thresholds', {}).get('new_rate')}；边际收益 < {p.get('thresholds', {}).get('marginal_yield')}", checks(p, "F3_new_rate"), {"new_rates": p.get("high_confidence_new_rates"), "marginal_yields": p.get("source_marginal_yields")}, p.get("status"), "同时查看同名的边际收益与独立验证细项。")
    row("F 过程合规、库健康与可追溯", "F4", "纳入决策与来源谱系", f"来源谱系记录率 ≥ {standards.get('f_provenance_rate', 0.95)}", checks(h, "F4_provenance"), h.get("provenance_rate"), h.get("status"), "纳入、排除和来源应可回溯至原始记录。")
    row("F 过程合规、库健康与可追溯", "F5", "核心元数据完整性", f"核心字段 ≥ {standards.get('f_core_metadata_rate', 0.95)}；摘要 ≥ {standards.get('f_abstract_rate', 0.80)}", checks(h, "F5_metadata"), h.get("field_completeness", {}), h.get("status"), "标题、作者、日期、载体、标识符和摘要分别报告。")
    row("F 过程合规、库健康与可追溯", "F6", "去重与版本决策", "稳定标识符去重；版本族须有显式决策", checks(h, "F6_exact_duplicates"), {"duplicate_doi_groups": h.get("duplicate_doi_groups"), "duplicate_title_year_groups": h.get("duplicate_title_year_groups"), "version_decisions": checks(h, "F6_version_decisions")}, h.get("status"), "题名-年份相似项只进入待审队列，不自动合并。")
    row("F 过程合规、库健康与可追溯", "F7", "访问与复现线索", f"附件或开放链接率 ≥ {standards.get('f_access_rate', 0.80)}", checks(h, "F7_access"), {"attachment_rate": h.get("attachment_rate"), "open_link_rate": h.get("open_link_rate")}, h.get("status"), "可访问不等于已获授权或已经复现。")
    row("F 过程合规、库健康与可追溯", "F8", "撤稿、更正与异常处理", "已核验更正/撤稿状态并保存处置", checks(h, "F8_corrections"), h.get("correction_flag_records"), h.get("status"), "无专门来源核验时应如实标为不可判定。")
    return add


def write_legacy(report, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [("A1 基准集召回", report["coverage"]["a1"].get("recall"), report["coverage"]["a1"]["status"]),
            ("A2 查询灵敏度", report["coverage"]["a2"].get("recall"), report["coverage"]["a2"]["status"]),
            ("A3 候选下界", report["coverage"]["a3"].get("deduplicated_candidate_lower_bound"), report["coverage"]["a3"]["status"]),
            ("B 范围结构", ", ".join(report["structure"].get("uncovered_expected_strata", [])) or "—", report["structure"]["status"]),
            ("C 缺失工程证据类型", ", ".join(report["evidence"].get("missing_required_types", [])) or "—", report["evidence"]["status"]),
            ("D 来源级新鲜度", report["currency"].get("sources"), report["currency"]["status"]),
            ("E 引用数据可得率", report["influence"].get("citation_data_rate"), report["influence"]["status"]),
            ("F 过程与库健康", report["process"].get("verdict"), report["library_health"]["status"])]
    table = "\n".join(f"| {a} | {b if b is not None else '—'} | {c} |" for a,b,c in rows)
    missing = [name for name, meta in report["artifacts"].items() if not meta["provided"]]
    md = "# 工程文献库审计报告\n\n" + report["summary"] + "\n\n| 项目 | 结果 | 证据状态 |\n| --- | --- | --- |\n" + table
    detail_groups = [("B 范围结构", report["structure"].get("checks", {})), ("C 工程证据适用性", report["evidence"].get("checks", {})), ("D 时效与演化", report["currency"].get("checks", {})), ("E 影响与知识关联", report["influence"].get("checks", {})), ("F 过程规范", report["process"].get("checks", {})), ("F 库健康", report["library_health"].get("checks", {}))]
    md += "\n\n## B–F 细分判定\n\n| 维度 | 子项 | Verdict |\n| --- | --- | --- |\n" + "\n".join(f"| {group} | {key} | {value} |" for group, checks in detail_groups for key, value in checks.items())
    md += "\n\n## 审计产物\n\n" + ("缺失：" + "、".join(missing) if missing else "已提供全部运行产物。")
    md += "\n\n## 局限\n\n" + "\n".join("- " + x for x in report["limitations"])
    (out / "audit.md").write_text(md + "\n", encoding="utf-8")
    (out / "audit.html").write_text("<html><meta charset='utf-8'><body><pre>" + html.escape(md) + "</pre></body></html>", encoding="utf-8")


def indicator_rows_v2(report):
    c, p, b, d, q, h = report["coverage"], report["process"], report["balance"], report["recency"], report["quality"], report["library_health"]
    checks = lambda group, key: group.get("checks", {}).get(key, "not_assessable")
    rows = []
    def add(parent, code, name, standard, verdict, current, evidence, note):
        rows.append((parent, code, name, standard, verdict, compact(current), evidence, note))
    add("A 覆盖（Recall）", "A1", "已知必纳入文献找回率", "项目配置的基准集召回阈值", threshold_verdict(c["a1"].get("recall"), report["standards"].get("a1_min_recall")), c["a1"].get("recall"), c["a1"].get("status"), "稳定 ID 基准集召回。")
    add("A 覆盖（Recall）", "A2", "检索式找回已知相关文献的能力", "项目配置的 Gold-set 灵敏度阈值", threshold_verdict(c["a2"].get("recall"), report["standards"].get("a2_min_recall")), c["a2"].get("recall"), c["a2"].get("status"), "稳定 ID Gold set 灵敏度。")
    add("A 覆盖（Recall）", "A3", "多来源检索到的最少唯一候选数", "至少两完整来源；只报告下界", "pass" if c["a3"].get("status") == "estimated_lower_bound" else "not_assessable", c["a3"].get("deduplicated_candidate_lower_bound"), c["a3"].get("status"), "不是 Recall 或找全证明。")
    add("B 饱和度（GGR/DRR）", "B1", "核心库增长率（GGR）", f"最后两轮均 < {p.get('thresholds', {}).get('new_rate')}", checks(p, "F3_new_rate"), p.get("high_confidence_new_rates"), p.get("status"), "每轮高置信新增 / 该轮开始前核心库。")
    add("B 饱和度（GGR/DRR）", "B2", "新增路径发现率（DRR）", f"各新增路径均 < {p.get('thresholds', {}).get('marginal_yield')}", checks(p, "F3_marginal_yield"), p.get("source_marginal_yields"), p.get("status"), "新路径带来的此前未发现高置信文献 / 该路径候选。")
    add("B 饱和度（GGR/DRR）", "B3", "饱和结论的过程证据", "路径完成且独立验证通过", "pass" if checks(p, "F2_pathways") == "pass" and checks(p, "F3_independent_validation") == "pass" else "not_assessable", {"pathways": p.get("pathway_completion"), "independent_validation": p.get("independent_validation_passed")}, p.get("status"), "低 GGR/DRR 本身不足以证明饱和。")
    add("C 平衡（CV/Gini/Shannon）", "C1", "关键主题层是否平衡覆盖", "项目 taxonomy 的预期层均有记录", checks(report["structure"], "B2_critical_strata"), report["structure"].get("uncovered_expected_strata"), report["structure"].get("status"), "防止主题、方法或应用层出现空白。")
    add("C 平衡（CV/Gini/Shannon）", "C2", "来源分布是否过度集中或过度分散", "Top share≤0.80；CV≤1.00；Gini≤0.60；归一化 Shannon 0.45–0.95", checks(b, "C2_source_balance"), {"top_share": b.get("top_source_share"), "cv": b.get("cv"), "gini": b.get("gini"), "normalized_shannon": b.get("normalized_shannon"), "flags": b.get("flags")}, b.get("status"), "低 Shannon 表示集中；极高 Shannon 提示来源过度分散，均需解释。")
    add("D 时效性（Recency/前沿/预印本）", "D1", "检索来源是否足够新", f"每个来源距成功检索 ≤ {report['currency'].get('freshness_threshold_days')} 天", checks(d, "D1_search_freshness"), report["currency"].get("sources"), report["currency"].get("status"), "按来源逐项检查。")
    add("D 时效性（Recency/前沿/预印本）", "D2", "近年文献比例是否足够", f"近 {d.get('window_years')} 年占比 ≥ {d.get('minimum_share')}", checks(d, "D2_recent_share"), {"recent": d.get("recent_records"), "dated": d.get("dated_records"), "share": d.get("recent_share")}, d.get("status"), "AI/通信默认 3 年40%；常规工程 5 年35%；基础设施 7 年30%。")
    add("D 时效性（Recency/前沿/预印本）", "D3", "前沿主题是否专门检索和验证", "前沿窗口有独立检索/Gold-set 证据", checks(d, "D3_frontier"), "依赖 context 判定", d.get("status"), "近期发表不等于前沿覆盖。")
    add("D 时效性（Recency/前沿/预印本）", "D4", "预印本和正式版本是否已区分", "关键版本关系已核验", checks(d, "D4_versions_preprints"), {"preprint_records": d.get("preprint_records")}, d.get("status"), "预印本不是低质量，但不能与正式版重复计数。")
    add("E 质量（h-core/Tier-1）", "E1", "引用核心规模（h-core）", "报告 h-index；仅作质量背景", checks(q, "E1_h_core"), {"h_core": q.get("h_core"), "citation_records": q.get("citation_records")}, q.get("status"), "不把 h-core 当作综述充分性的总分。")
    add("E 质量（h-core/Tier-1）", "E2", "领域 Tier-1 文献覆盖", "使用 profile 配置的权威 venue 映射", checks(q, "E2_tier1"), {"tier1_records": q.get("tier1_records"), "tier1_rate": q.get("tier1_rate")}, q.get("status"), "未配置合法领域映射时不得判断。")
    add("F 可用性（摘要/PDF/去重）", "F1", "检索过程能否复跑", "查询原文、字段、日期、来源、过滤器齐全", checks(p, "F1_query_traceability"), report["context"].get("run_log_complete"), p.get("status"), "使所有审计量可追溯。")
    add("F 可用性（摘要/PDF/去重）", "F2", "摘要信息是否足够", f"摘要率 ≥ {report['standards'].get('f_abstract_rate', .80)}", "pass" if h.get("field_completeness", {}).get("abstractNote") is not None and h["field_completeness"]["abstractNote"] >= report["standards"].get("f_abstract_rate", .80) else "fail", h.get("field_completeness", {}).get("abstractNote"), h.get("status"), "支持自动初筛、分类和人工判断。")
    add("F 可用性（摘要/PDF/去重）", "F3", "PDF或开放全文是否可获得", f"附件或开放链接率 ≥ {report['standards'].get('f_access_rate', .80)}", checks(h, "F7_access"), {"attachment_rate": h.get("attachment_rate"), "open_link_rate": h.get("open_link_rate")}, h.get("status"), "可获得不代表已获授权。")
    add("F 可用性（摘要/PDF/去重）", "F4", "重复和版本是否已处理", "DOI 精确重复为 0；版本候选有决定", checks(h, "F6_exact_duplicates"), {"doi_duplicates": h.get("duplicate_doi_groups"), "title_year_candidates": h.get("duplicate_title_year_groups")}, h.get("status"), "相似题名不自动合并。")
    add("F 可用性（摘要/PDF/去重）", "F5", "纳入决定能否追溯", f"来源谱系率 ≥ {report['standards'].get('f_provenance_rate', .95)}", checks(h, "F4_provenance"), h.get("provenance_rate"), h.get("status"), "核心文献应可回溯来源和决定。")
    add("F 可用性（摘要/PDF/去重）", "F6", "撤稿和更正是否已核查", "关键记录有更正检查与处置", checks(h, "F8_corrections"), h.get("correction_flag_records"), h.get("status"), "无专门核验即不可评估。")
    return rows


def write(report, out):
    """Write the canonical A--F peer audit register in JSON, Markdown and HTML."""
    out.mkdir(parents=True, exist_ok=True)
    report["indicator_register"] = [
        {"parent_dimension": parent, "subproject": sub, "project_name": name,
         "standard": standard, "meets_standard": verdict, "current_status": current,
         "evidence_status": evidence_state, "description_and_action": note}
        for parent, sub, name, standard, verdict, current, evidence_state, note in indicator_rows_v2(report)
    ]
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    table = "\n".join(
        "| " + " | ".join(compact(cell) for cell in row) + " |"
        for row in indicator_rows_v2(report)
    )
    missing = [name for name, meta in report["artifacts"].items() if not meta["provided"]]
    artifacts_text = "缺失：" + "、".join(missing) if missing else "已提供全部运行产物。"
    md = "# 工程文献库审计报告\n\n" + report["summary"]
    md += "\n\n## A–F 平级审计总表\n\n"
    md += "| 母项目 | 子项目 | 项目名称 | 标准 | 是否达标 | 当前状态 | 证据状态 | 说明与行动 |\n"
    md += "| --- | --- | --- | --- | --- | --- | --- | --- |\n" + table
    md += "\n\n## 审计产物\n\n" + artifacts_text
    md += "\n\n## 局限\n\n" + "\n".join("- " + x for x in report["limitations"])
    (out / "audit.md").write_text(md + "\n", encoding="utf-8")
    (out / "audit.html").write_text("<html><meta charset='utf-8'><body><pre>" + html.escape(md) + "</pre></body></html>", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", required=True); p.add_argument("--benchmark"); p.add_argument("--gold"); p.add_argument("--query-hits")
    p.add_argument("--candidate-snapshots", help="collector snapshot JSON from at least two sources")
    p.add_argument("--context", help="JSON with search rounds, pathways, taxonomy and source dates")
    p.add_argument("--query-plan"); p.add_argument("--source-snapshot"); p.add_argument("--decision-log"); p.add_argument("--deduplication-log"); p.add_argument("--run-log")
    p.add_argument("--out", required=True); a = p.parse_args()
    context = json.load(open(a.context, encoding="utf-8")) if a.context else {}
    library = load_items(a.library)
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "standards": context.get("standards", {}), "context": context,
              "library_health": health(library, context.get("standards", {})),
              "coverage": {"a1": benchmark(load_items(a.library), load_items(a.benchmark) if a.benchmark else []),
                           "a2": a2(load_items(a.gold) if a.gold else None, load_items(a.query_hits) if a.query_hits else None),
                           "a3": a3(load_snapshot(a.candidate_snapshots) if a.candidate_snapshots else {})},
              "process": stability(context), "structure": structure(library, context), "balance": balance(library, context.get("standards", {})), "currency": currency(context), "recency": recency(library, context), "quality": quality(library, context),
              "artifacts": artifacts({"query-plan": a.query_plan, "source-snapshot": a.source_snapshot, "decision-log": a.decision_log, "deduplication-log": a.deduplication_log, "run-log": a.run_log}),
              "summary": "本报告只将稳定标识符匹配和已保存过程记录标为可复跑证据。",
              "limitations": ["A3 下界不是 Recall；任何区间都需要另行声明模型假设。", "工程适用性、版本等价性、研究设计和更正状态需要人工或专门来源核验。", "未提供的运行产物会明确标为缺失。"]}
    write(report, pathlib.Path(a.out))

if __name__ == "__main__": main()
