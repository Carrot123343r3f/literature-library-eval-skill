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
            sources.setdefault(name, []).extend(result.get("items", []))
    if not sources and isinstance(data.get("sources"), dict):
        sources = {name: value.get("items", []) for name, value in data["sources"].items()}
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
    source_ids = {name: set().union(*(ids(x) for x in rows if isinstance(x, dict))) for name, rows in sources.items()}
    union = set().union(*source_ids.values())
    if not union:
        return {"status": "not_assessable", "note": "Candidate snapshots contain no stable identifiers."}
    overlaps = {"|".join(pair): len(source_ids[pair[0]] & source_ids[pair[1]])
                for pair in __import__('itertools').combinations(sorted(source_ids), 2)}
    return {"status": "estimated_lower_bound", "deduplicated_candidate_lower_bound": len(union),
            "source_unique_identifier_counts": {k: len(v) for k, v in source_ids.items()}, "pairwise_overlaps": overlaps,
            "note": "This is a multi-source identifier lower bound, not Recall or a capture–recapture estimate."}


def health(library):
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
    return {"status": "measured" if n else "not_assessable", "records": n, "field_completeness": fields,
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
    threshold = float(context.get("new_rate_threshold", 0.02)); yield_threshold = float(context.get("marginal_yield_threshold", 0.05))
    yields = [x.get("yield") for x in context.get("source_marginal_yields", []) if isinstance(x.get("yield"), (int, float))]
    converged = len(rates) >= 2 and all(x < threshold for x in rates[-2:]) and complete == 1.0 and context.get("independent_validation_passed") is True and bool(yields) and all(x < yield_threshold for x in yields)
    return {"status": "measured" if rounds else "not_assessable", "high_confidence_new_rates": rates, "pathway_completion": complete,
            "independent_validation_passed": context.get("independent_validation_passed") is True, "source_marginal_yields": yields,
            "verdict": "趋于稳定（仅限声明范围）" if converged else "未证明稳定"}


def currency(context):
    raw = context.get("last_successful_search", {})
    raw = {"unspecified": raw} if isinstance(raw, list) else raw
    dates = {}
    for source, value in raw.items():
        try: dates[source] = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except (TypeError, ValueError): pass
    today = dt.date.today()
    return {"status": "measured" if dates else "not_assessable", "sources": {k: {"date": v.isoformat(), "days_since": (today-v).days} for k, v in dates.items()},
            "note": "Report every successful source date; a recent source does not hide stale or failed sources."}


def structure(library, context):
    taxonomy = context.get("taxonomy", [])
    mapped = []
    for row in taxonomy:
        expected = row.get("expected", True)
        count = row.get("high_confidence_records")
        confidence = row.get("classification_confidence")
        status = "gap" if expected and not count else "covered" if count else "out_of_scope"
        mapped.append({"name": row.get("name", "unnamed"), "expected": expected, "records": count,
                       "classification_confidence": confidence, "status": status})
    source_counts = Counter(str(x.get("source") or x.get("source_database") or "unknown") for x in library)
    n = len(library); shares = [x / n for x in source_counts.values()] if n else []
    entropy = -sum(p * log(p) for p in shares if p)
    return {"status": "measured" if taxonomy or library else "not_assessable", "taxonomy": mapped,
            "uncovered_expected_strata": [x["name"] for x in mapped if x["status"] == "gap"],
            "source_dependence": {"counts": dict(source_counts), "top_source_share": round(max(shares), 3) if shares else None,
                                  "shannon_entropy": round(entropy, 3) if shares else None},
            "note": "Taxonomy must describe engineering conditions, methods, metrics or applications; concentration is descriptive, not a quality verdict."}


def evidence(library, context):
    required = set(context.get("engineering_evidence_types_required", []))
    present = {str(x.get("engineering_evidence_type") or x.get("evidence_type")) for x in library if x.get("engineering_evidence_type") or x.get("evidence_type")}
    flags = {"preprint": sum(bool(x.get("is_preprint")) for x in library),
             "retraction_or_correction_flags": sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library),
             "code_or_data_links": sum(bool(x.get("code_url") or x.get("data_url")) for x in library),
             "missing_conditions": sum(not bool(x.get("operating_conditions") or x.get("test_conditions")) for x in library)}
    return {"status": "screening" if library else "not_assessable", "required_evidence_types": sorted(required),
            "present_evidence_types": sorted(present), "missing_required_types": sorted(required - present), "credibility_flags": flags,
            "note": "This is engineering evidence screening. It does not determine causal validity, benchmark fairness, code reproducibility or version equivalence."}


def artifacts(paths):
    return {name: {"provided": bool(value), "path": value} for name, value in paths.items()}


def write(report, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [("A1 基准集召回", report["coverage"]["a1"].get("recall"), report["coverage"]["a1"]["status"]),
            ("A2 查询灵敏度", report["coverage"]["a2"].get("recall"), report["coverage"]["a2"]["status"]),
            ("A3 候选下界", report["coverage"]["a3"].get("deduplicated_candidate_lower_bound"), report["coverage"]["a3"]["status"]),
            ("B 检索趋稳", report["stability"].get("verdict"), report["stability"]["status"]),
            ("C 未覆盖工程关键层", ", ".join(report["structure"].get("uncovered_expected_strata", [])) or "—", report["structure"]["status"]),
            ("D 缺失工程证据类型", ", ".join(report["evidence"].get("missing_required_types", [])) or "—", report["evidence"]["status"]),
            ("E 来源级新鲜度", report["currency"].get("sources"), report["currency"]["status"]),
            ("F 库健康", report["library_health"].get("records"), report["library_health"]["status"])]
    table = "\n".join(f"| {a} | {b if b is not None else '—'} | {c} |" for a,b,c in rows)
    missing = [name for name, meta in report["artifacts"].items() if not meta["provided"]]
    md = "# 工程文献库审计报告\n\n" + report["summary"] + "\n\n| 项目 | 结果 | 证据状态 |\n| --- | --- | --- |\n" + table
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
    report = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "library_health": health(load_items(a.library)),
              "coverage": {"a1": benchmark(load_items(a.library), load_items(a.benchmark) if a.benchmark else []),
                           "a2": a2(load_items(a.gold) if a.gold else None, load_items(a.query_hits) if a.query_hits else None),
                           "a3": a3(load_snapshot(a.candidate_snapshots) if a.candidate_snapshots else {})},
              "stability": stability(context), "structure": structure(load_items(a.library), context), "evidence": evidence(load_items(a.library), context), "currency": currency(context),
              "artifacts": artifacts({"query-plan": a.query_plan, "source-snapshot": a.source_snapshot, "decision-log": a.decision_log, "deduplication-log": a.deduplication_log, "run-log": a.run_log}),
              "summary": "本报告只将稳定标识符匹配和已保存过程记录标为可复跑证据。",
              "limitations": ["A3 下界不是 Recall；任何区间都需要另行声明模型假设。", "工程适用性、版本等价性、研究设计和更正状态需要人工或专门来源核验。", "未提供的运行产物会明确标为缺失。"]}
    write(report, pathlib.Path(a.out))

if __name__ == "__main__": main()
