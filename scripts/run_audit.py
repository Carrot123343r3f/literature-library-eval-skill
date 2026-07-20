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


def write(report, out):
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", required=True); p.add_argument("--benchmark"); p.add_argument("--gold"); p.add_argument("--query-hits")
    p.add_argument("--candidate-snapshots", help="collector snapshot JSON from at least two sources")
    p.add_argument("--context", help="JSON with search rounds, pathways, taxonomy and source dates")
    p.add_argument("--query-plan"); p.add_argument("--source-snapshot"); p.add_argument("--decision-log"); p.add_argument("--deduplication-log"); p.add_argument("--run-log")
    p.add_argument("--out", required=True); a = p.parse_args()
    context = json.load(open(a.context, encoding="utf-8")) if a.context else {}
    library = load_items(a.library)
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "library_health": health(library, context.get("standards", {})),
              "coverage": {"a1": benchmark(load_items(a.library), load_items(a.benchmark) if a.benchmark else []),
                           "a2": a2(load_items(a.gold) if a.gold else None, load_items(a.query_hits) if a.query_hits else None),
                           "a3": a3(load_snapshot(a.candidate_snapshots) if a.candidate_snapshots else {})},
              "process": stability(context), "structure": structure(library, context), "evidence": evidence(library, context), "currency": currency(context), "influence": influence(library, context),
              "artifacts": artifacts({"query-plan": a.query_plan, "source-snapshot": a.source_snapshot, "decision-log": a.decision_log, "deduplication-log": a.deduplication_log, "run-log": a.run_log}),
              "summary": "本报告只将稳定标识符匹配和已保存过程记录标为可复跑证据。",
              "limitations": ["A3 下界不是 Recall；任何区间都需要另行声明模型假设。", "工程适用性、版本等价性、研究设计和更正状态需要人工或专门来源核验。", "未提供的运行产物会明确标为缺失。"]}
    write(report, pathlib.Path(a.out))

if __name__ == "__main__": main()
