#!/usr/bin/env python3
"""Create Markdown, HTML and JSON audit reports from normalized library inputs.

This is deliberately conservative: unavailable evidence is reported as unavailable,
not converted into a score.
"""
import argparse
import datetime as dt
import html
import json
import pathlib
import re
from collections import Counter
from math import log


def doi(value):
    match = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return match.group(1).rstrip(".,;:)]}").lower() if match else ""


def ids(row):
    found = set()
    for key in ("DOI", "doi", "extra"):
        value = doi(row.get(key))
        if value:
            found.add("doi:" + value)
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"), ("arxiv", "arxiv"), ("arXiv", "arxiv")):
        if row.get(key):
            found.add(prefix + ":" + str(row[key]).casefold())
    raw_id = str(row.get("id") or "")
    raw_doi = doi(raw_id)
    if raw_doi:
        found.add("doi:" + raw_doi)
    elif raw_id.startswith(("pmid:", "arxiv:", "openalex:")):
        found.add(raw_id.casefold())
    return found


def title(row):
    return re.sub(r"[^\w]", "", str(row.get("title") or "").casefold())


def load(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("items", [])


def benchmark(library, benchmark):
    lib_ids = set().union(*(ids(x) for x in library)) if library else set()
    lib_titles = {title(x) for x in library if title(x)}
    stable = [x for x in benchmark if isinstance(x, dict) and ids(x)]
    uncertain = [x for x in benchmark if not isinstance(x, dict) or not ids(x)]
    matched = sum(bool(ids(x) & lib_ids) for x in stable)
    candidates = [str(x if isinstance(x, str) else x.get("title", "")) for x in uncertain
                  if title(x if isinstance(x, dict) else {"title": x}) in lib_titles]
    return {"status": "measured" if stable else "not_assessable", "total": len(stable), "matched": matched,
            "recall": round(matched / len(stable), 3) if stable else None,
            "manual_title_candidates": candidates}


def health(library):
    n = len(library)
    fields = {key: round(sum(bool(str(x.get(key) or "").strip()) for x in library) / n, 3) if n else None
              for key in ("title", "creators", "date", "publicationTitle", "abstractNote", "DOI", "url")}
    doi_groups = Counter(next(iter(ids(x)), "") for x in library if ids(x))
    title_groups = Counter((title(x), str(x.get("date") or "")[:4]) for x in library if title(x))
    fulltext = sum(bool(x.get("attachments") or x.get("fulltext_url") or x.get("open_access_url")) for x in library)
    provenance = sum(bool(x.get("source") or x.get("source_database") or x.get("collection")) for x in library)
    alerts = sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library)
    return {"status": "measured", "records": n, "field_completeness": fields,
            "duplicate_doi_groups": sum(v > 1 for v in doi_groups.values()),
            "duplicate_title_year_groups": sum(v > 1 for v in title_groups.values()),
            "fulltext_or_link_rate": round(fulltext / n, 3) if n else None,
            "provenance_rate": round(provenance / n, 3) if n else None,
            "correction_alert_records": alerts,
            "note": "版本族、访问许可与撤稿状态需由来源解析或人工/模型复核。"}


def parse_date(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def stability(context):
    rounds = context.get("search_rounds", [])
    if not rounds:
        return {"status": "not_assessable", "note": "Supply search-round logs with included_high and core_before."}
    rates = []
    for row in rounds:
        before = row.get("core_before")
        added = row.get("included_high")
        if isinstance(before, (int, float)) and before > 0 and isinstance(added, (int, float)):
            rates.append(round(added / before, 4))
    paths = context.get("planned_pathways", [])
    done = {x.get("pathway") for x in rounds if x.get("completed")}
    complete = round(len(set(paths) & done) / len(set(paths)), 3) if paths else None
    validation_passed = context.get("independent_validation_passed") is True
    yields = [x.get("yield") for x in context.get("source_marginal_yields", [])
              if isinstance(x.get("yield"), (int, float))]
    yields_low = bool(yields) and all(x < 0.05 for x in yields)
    converged = len(rates) >= 2 and all(x < 0.02 for x in rates[-2:]) and complete == 1.0 and validation_passed and yields_low
    return {"status": "measured" if rates else "not_assessable", "high_confidence_new_rates": rates,
            "pathway_completion": complete, "independent_validation_passed": validation_passed,
            "source_marginal_yields": yields, "converged_signal": converged,
            "verdict": "趋于稳定（仅限声明范围）" if converged else "未证明稳定",
            "note": "需要独立验证集、引文路径和新来源收益共同支持，不以单一 GGR/DRR 下结论。"}


def structure(library, context):
    taxonomy = context.get("taxonomy", [])
    mapped = []
    for row in taxonomy:
        count = row.get("high_confidence_records")
        expected = row.get("expected", True)
        mapped.append({"name": row.get("name", "unnamed"), "expected": expected, "records": count,
                       "status": "gap" if expected and not count else "covered" if count else "out_of_scope"})
    venues = Counter(str(x.get("publicationTitle") or x.get("venue") or "unknown") for x in library)
    n = len(library)
    shares = [v / n for v in venues.values()] if n else []
    entropy = -sum(p * log(p) for p in shares if p)
    return {"status": "measured" if taxonomy or n else "not_assessable", "taxonomy": mapped,
            "uncovered_expected_strata": [x["name"] for x in mapped if x["status"] == "gap"],
            "venue_concentration": {"top_venue_share": round(max(shares), 3) if shares else None,
                                    "shannon_entropy": round(entropy, 3) if shares else None,
                                    "note": "集中度是描述，不等于偏差或低质量。"},
            "note": "分类必须保留规则、置信度和未分类项；均匀不是普遍目标。"}


def evidence(library, context):
    n = len(library)
    requested = set(context.get("evidence_types_required", []))
    present = {str(x.get("evidence_type")) for x in library if x.get("evidence_type")}
    citations = [x.get("cited_by_count") for x in library if isinstance(x.get("cited_by_count"), (int, float))]
    flags = {"retracted": sum(bool(x.get("retracted")) for x in library),
             "corrected": sum(bool(x.get("corrected")) for x in library),
             "preprint": sum(bool(x.get("is_preprint")) for x in library),
             "code_or_data": sum(bool(x.get("code_url") or x.get("data_url")) for x in library)}
    return {"status": "screening" if n else "not_assessable",
            "required_evidence_types": sorted(requested), "present_evidence_types": sorted(present),
            "missing_required_types": sorted(requested - present),
            "citation_context": {"count_available": len(citations), "median": sorted(citations)[len(citations)//2] if citations else None,
                                 "note": "Citation counts are not field- or age-normalized and are not quality scores."},
            "credibility_flags": flags,
            "note": "Research design validity, risk of bias and version equivalence require full-text review or a dedicated screening model."}


def currency(library, context):
    today = dt.date.today()
    dates = [parse_date(x) for x in context.get("last_successful_search", [])]
    dates = [x for x in dates if x]
    years = [int(m.group(1)) for x in library if (m := re.search(r"(19|20)\d{2}", str(x.get("date") or "")))]
    window = int(context.get("recent_years", 2))
    recent = sum(y >= today.year - window + 1 for y in years)
    return {"status": "measured" if dates or years else "not_assessable",
            "last_successful_search": max(dates).isoformat() if dates else None,
            "days_since_last_successful_search": (today - max(dates)).days if dates else None,
            "publication_window_years": window, "publication_recent_share": round(recent / len(years), 3) if years else None,
            "note": "出版年份分布需按领域 profile 解读；检索新鲜度比近期论文占比更直接。"}


def a2(gold, query_hits):
    if not gold or not query_hits:
        return {"status": "not_assessable", "recall": None}
    gold_ids = set().union(*(ids(x) for x in gold if isinstance(x, dict)))
    hit_ids = set().union(*(ids(x) for x in query_hits if isinstance(x, dict)))
    if not gold_ids:
        return {"status": "not_assessable", "recall": None}
    return {"status": "measured", "total": len(gold_ids), "matched": len(gold_ids & hit_ids),
            "recall": round(len(gold_ids & hit_ids) / len(gold_ids), 3),
            "missing_ids": sorted(gold_ids - hit_ids)}


def write_reports(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        ("A1 基准集召回", report["coverage"]["a1"].get("recall"), report["coverage"]["a1"]["status"]),
        ("A2 检索策略灵敏度", report["coverage"]["a2"].get("recall"), report["coverage"]["a2"]["status"]),
        ("B 检索趋稳", report["stability"].get("verdict"), report["stability"]["status"]),
        ("C 未覆盖关键层", ", ".join(report["structure"].get("uncovered_expected_strata", [])) or "—", report["structure"]["status"]),
        ("D 证据适用性", ", ".join(report["evidence"].get("missing_required_types", [])) or "未见缺口", report["evidence"]["status"]),
        ("E 距最近成功检索天数", report["currency"].get("days_since_last_successful_search"), report["currency"]["status"]),
        ("库记录数", report["library_health"]["records"], "measured"),
    ]
    table = "\n".join(f"| {name} | {value if value is not None else '—'} | {status} |" for name, value, status in rows)
    md = "# 文献库自动审计报告\n\n" + report["summary"] + "\n\n| 指标 | 结果 | 证据状态 |\n| --- | --- | --- |\n" + table
    md += "\n\n## 局限\n\n" + "\n".join("- " + x for x in report["limitations"])
    (output / "audit.md").write_text(md + "\n", encoding="utf-8")
    page = "<html><meta charset='utf-8'><title>Literature audit</title><body><pre>" + html.escape(md) + "</pre></body></html>"
    (output / "audit.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", required=True)
    parser.add_argument("--benchmark")
    parser.add_argument("--gold")
    parser.add_argument("--query-hits")
    parser.add_argument("--context", help="optional JSON: search rounds, pathways, taxonomy, evidence requirements, search dates")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    library = load(args.library)
    base = load(args.benchmark) if args.benchmark else []
    gold = load(args.gold) if args.gold else []
    hits = load(args.query_hits) if args.query_hits else []
    context = {}
    if args.context:
        with open(args.context, encoding="utf-8") as fh:
            context = json.load(fh)
    a1 = benchmark(library, base)
    a2_result = a2(gold, hits)
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "library_health": health(library),
              "coverage": {"a1": a1, "a2": a2_result,
                           "a3": {"status": "not_assessable", "note": "Supply multi-source, deduplicated snapshots to estimate candidate coverage."}},
              "stability": stability(context), "structure": structure(library, context),
              "evidence": evidence(library, context), "currency": currency(library, context),
              "summary": "该报告由可复跑输入生成；只有稳定标识符匹配的覆盖指标被标为实测。",
              "limitations": ["A3 需要多源去重与已声明纳入范围，不能从库规模或单库结果推导。",
                              "自动相关性判别、研究设计质量和版本等价性应保留决策日志与置信度。",
                              "B–F 中没有输入数据的项目将标为不可评估，而非自动评分。"]}
    write_reports(report, pathlib.Path(args.out))


if __name__ == "__main__":
    main()
