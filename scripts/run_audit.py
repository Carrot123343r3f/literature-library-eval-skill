#!/usr/bin/env python3
"""Literature-library evaluation report generator (model X: A-F six dimensions, 21 sub-items; umbrella adds A4/C4/F7 → 24)."""
import argparse, datetime as dt, hashlib, html, json, pathlib, re, shutil
from collections import Counter
from math import log

# Review-type → default thresholds (narrative / systematic / scoping / rapid / umbrella)
REVIEW_THRESHOLDS = {
    "叙事综述": {"a1_min_recall": 0.75, "a2_min_recall": 0.70, "f_access_rate": 0.60,
                 "f_provenance_rate": 0.85, "f_core_metadata_rate": 0.90, "f_abstract_rate": 0.80},
    "系统综述": {"a1_min_recall": 0.90, "a2_min_recall": 0.85, "f_access_rate": 0.80,
                 "f_provenance_rate": 0.95, "f_core_metadata_rate": 0.95, "f_abstract_rate": 0.85},
    "范围综述": {"a1_min_recall": 0.75, "a2_min_recall": 0.70, "f_access_rate": 0.60,
                 "f_provenance_rate": 0.85, "f_core_metadata_rate": 0.90, "f_abstract_rate": 0.80},
    "快速综述": {"a1_min_recall": 0.60, "a2_min_recall": 0.60, "f_access_rate": 0.50,
                 "f_provenance_rate": 0.70, "f_core_metadata_rate": 0.80, "f_abstract_rate": 0.70},
    "伞式综述": {"a1_min_recall": 0.90, "a2_min_recall": 0.80, "f_access_rate": 0.85,
                 "f_provenance_rate": 0.90, "f_core_metadata_rate": 0.90, "f_abstract_rate": 0.80},
}

def resolve_thresholds(context):
    """Merge review-type defaults into context.standards (user overrides win)."""
    ctx = dict(context) if context else {}
    s = dict(ctx.get("standards", {}))
    rt = ctx.get("review_type", "")
    defaults = REVIEW_THRESHOLDS.get(rt, {})
    for k, v in defaults.items():
        if k not in s: s[k] = v
    # inject profile freshness into D1 if not already set
    _, _, fresh_days = profile_defaults(ctx)
    if "d_freshness_days" not in s:
        s["d_freshness_days"] = fresh_days
    # non-RT defaults (balance/metric thresholds)
    for k, v in {"b_ggr_threshold": 0.02, "b_drr_threshold": 0.05,
                 "balance_top_share_warning": 0.80, "balance_cv_warning": 1.00,
                 "balance_gini_warning": 0.60, "balance_shannon_low_warning": 0.45,
                 "balance_shannon_high_warning": 0.95, "topic_top_share_warning": 0.70,
                 "topic_cv_warning": 0.80, "topic_gini_warning": 0.50,
                 "topic_shannon_low_warning": 0.55, "topic_target_tvd_warning": 0.25,
                 "topic_min_sources": 2, "topic_source_top_share_warning": 0.80}.items():
        if k not in s: s[k] = v
    ctx["standards"] = s
    return ctx

def doi(value):
    m = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return m.group(1).rstrip(".,;:)]}").lower() if m else ""

def ids(row):
    found = set()
    for key in ("DOI", "doi", "extra", "id"):
        value = doi(row.get(key))
        if value: found.add("doi:" + value)
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"), ("PMCID", "pmcid"),
                        ("arxiv", "arxiv"), ("arXiv", "arxiv"), ("openalex_id", "openalex")):
        if row.get(key): found.add(prefix + ":" + str(row[key]).casefold())
    raw = str(row.get("id") or "").casefold()
    if raw.startswith(("pmid:", "pmcid:", "arxiv:", "openalex:")): found.add(raw)
    if row.get("source") == "arxiv" and raw: found.add("arxiv:" + raw)
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
        sources = {name: {"items": value.get("items", []), "statuses": [value.get("status", "unknown")]}
                   for name, value in data["sources"].items()}
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
    if not gold_ids: return {"status": "not_assessable", "recall": None, "note": "Gold set lacks stable identifiers."}
    matched = gold_ids & hit_ids
    return {"status": "measured", "total": len(gold_ids), "matched": len(matched),
            "recall": round(len(matched) / len(gold_ids), 3), "missing_ids": sorted(gold_ids - hit_ids),
            "note": "An executed zero-result query is measured recall 0, not unavailable evidence."}

def a3(sources):
    if not sources or len(sources) < 2:
        return {"status": "not_assessable", "note": "Supply deduplicable snapshots from at least two sources."}
    incomplete = sorted(name for name, meta in sources.items()
                        if any(status != "complete" for status in meta.get("statuses", [])))
    source_ids = {name: set().union(*(ids(x) for x in meta.get("items", []) if isinstance(x, dict)))
                  for name, meta in sources.items()}
    union = set().union(*source_ids.values())
    if not union: return {"status": "not_assessable", "note": "Candidate snapshots contain no stable identifiers."}
    overlaps = {"|".join(pair): len(source_ids[pair[0]] & source_ids[pair[1]])
                for pair in __import__('itertools').combinations(sorted(source_ids), 2)}
    result = {"status": "estimated_lower_bound" if not incomplete else "partial_snapshot",
              "deduplicated_candidate_lower_bound": len(union),
              "source_unique_identifier_counts": {k: len(v) for k, v in source_ids.items()},
              "pairwise_overlaps": overlaps, "incomplete_sources": incomplete,
              "note": "Multi-source deduplicated lower bound; not Recall or capture-recapture."}
    if incomplete: result["note"] = "Source snapshots incomplete; provisional count must not support A3 conclusions."
    return result

def health(library, standards=None, dedup_log_provided=False, dedup_log_depth="missing"):
    standards = standards or {}
    n = len(library)
    fields = {k: round(sum(bool(str(x.get(k) or "").strip()) for x in library) / n, 3) if n else None
              for k in ("title", "creators", "date", "publicationTitle", "abstractNote", "DOI", "url")}
    dois = Counter(doi(x.get("DOI") or x.get("doi") or x.get("id")) for x in library)
    dois.pop("", None)
    title_year = Counter((title(x), str(x.get("date") or "")[:4]) for x in library if title(x))
    has_attachment = sum(bool(x.get("attachments")) for x in library)
    has_oa = sum(bool(x.get("open_access_url") or x.get("fulltext_url")) for x in library)
    access_union = sum(bool(x.get("attachments") or x.get("open_access_url") or x.get("fulltext_url")) for x in library)
    provenance = sum(bool(x.get("source") or x.get("source_database") or x.get("collection")) for x in library)
    flags = sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library)
    core_min = float(standards.get("f_core_metadata_rate", 0.95))
    abstract_min = float(standards.get("f_abstract_rate", 0.80))
    access_min = float(standards.get("f_access_rate", 0.80))
    provenance_min = float(standards.get("f_provenance_rate", 0.95))
    has_fuzzy_dupes = sum(v > 1 for v in title_year.values()) > 0
    f4_version = "pass" if dedup_log_provided else "not_assessable"
    checks = {"F_metadata_composite": "pass" if all(fields.get(k) is not None and fields[k] >= core_min
              for k in ("title", "creators", "date", "publicationTitle", "DOI"))
              and (fields.get("abstractNote") is None or fields["abstractNote"] >= abstract_min) else "fail",
              "F4_exact_duplicates": "pass" if not sum(v > 1 for v in dois.values()) else "fail",
              "F4_version_decisions": f4_version,
              "F3_access": "pass" if n and access_union / n >= access_min else "warning",
              "F5_provenance": "pass" if n and provenance / n >= provenance_min else "fail",
              "F6_corrections": "not_assessable"}
    return {"status": "measured" if n else "not_assessable", "records": n, "field_completeness": fields, "checks": checks,
            "duplicate_doi_groups": sum(v > 1 for v in dois.values()),
            "duplicate_title_year_groups": sum(v > 1 for v in title_year.values()),
            "attachment_rate": round(has_attachment / n, 3) if n else None,
            "open_link_rate": round(has_oa / n, 3) if n else None,
            "access_union_rate": round(access_union / n, 3) if n else None,
            "provenance_rate": round(provenance / n, 3) if n else None, "correction_flag_records": flags,
            "dedup_log_depth": dedup_log_depth,
            "note": "F3=v 附件或开放链接任一可用的记录比例；两率分列展示以避免重复计数。版本族等价性、访问权限和更正状态需专项来源核验。"}

def stability(context):
    rounds = context.get("search_rounds", [])
    rates = [round(x["included_high"] / x["core_before"], 4) for x in rounds
             if isinstance(x.get("core_before"), (int, float)) and x["core_before"] > 0
             and isinstance(x.get("included_high"), (int, float))]
    paths = set(context.get("planned_pathways", []))
    done = {x.get("pathway") for x in rounds if x.get("completed")}
    complete = round(len(paths & done) / len(paths), 3) if paths else None
    standards = context.get("standards", {})
    threshold = float(standards.get("b_ggr_threshold", 0.02))
    yield_threshold = float(standards.get("b_drr_threshold", 0.05))
    yields = [x.get("yield") for x in context.get("source_marginal_yields", [])
              if isinstance(x.get("yield"), (int, float))]
    iv_passed = context.get("independent_validation_passed")
    run_log = context.get("run_log_complete")
    run_log_depth = context.get("run_log_depth", "missing")
    converged = (len(rates) >= 2 and all(x < threshold for x in rates[-2:]) and complete == 1.0
                 and iv_passed is True
                 and bool(yields) and all(x < yield_threshold for x in yields))
    checks = {"B1_ggr": "pass" if len(rates) >= 2 and all(x < threshold for x in rates[-2:])
              else "not_assessable" if len(rates) < 2 else "fail",
              "B3_pathway_completion": "pass" if complete == 1.0 else "not_assessable" if complete is None else "fail",
              "B2_drr": "pass" if yields and all(x < yield_threshold for x in yields)
              else "not_assessable" if not yields else "fail",
              "F1_query_traceability": "pass" if run_log is True
              else "fail" if run_log is False else "not_assessable",
              "B3_independent_validation": "pass" if iv_passed is True
              else "fail" if iv_passed is False else "not_assessable"}
    return {"status": "measured" if rounds else "not_assessable", "high_confidence_new_rates": rates,
            "pathway_completion": complete, "source_marginal_yields": yields,
            "thresholds": {"new_rate": threshold, "marginal_yield": yield_threshold}, "checks": checks,
            "independent_validation_passed": iv_passed,
            "verdict": "趋稳" if converged and all(x == "pass" for x in checks.values())
            else "不可证明" if "not_assessable" in checks.values() else "未稳定"}

def currency(context):
    raw = context.get("last_successful_search", {})
    raw = {"unspecified": raw} if isinstance(raw, list) else raw
    dates = {}
    for source, value in raw.items():
        try: dates[source] = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except (TypeError, ValueError): pass
    today = dt.date.today()
    max_days = int(context.get("standards", {}).get("d_freshness_days", 90))
    sources = {k: {"date": v.isoformat(), "days_since": (today - v).days,
               "verdict": "pass" if (today - v).days <= max_days else "warning"}
               for k, v in dates.items()}
    planned = set(context.get("planned_sources", []))
    missing = sorted(planned - set(dates))
    checks = {"D1_freshness": "pass" if sources and all(x["verdict"] == "pass" for x in sources.values())
              else "warning" if sources else "not_assessable"}
    return {"status": "measured" if dates else "not_assessable", "freshness_threshold_days": max_days,
            "sources": sources, "missing_planned_sources": missing, "checks": checks,
            "note": "Report every successful source date."}

def artifacts(paths):
    result = {name: {"provided": bool(value), "path": value} for name, value in paths.items()}
    result["provided_with_paths"] = {k: v["path"] for k, v in result.items() if v["provided"]}
    return result

def balance(library, standards=None):
    standards = standards or {}
    counts = Counter(str(x.get("source") or x.get("source_database") or "unknown") for x in library)
    values = list(counts.values()); n = sum(values); k = len(values)
    if not n or not k: return {"status": "not_assessable", "checks": {"C2_source_balance": "not_assessable"}}
    mean = n / k
    cv = (sum((x - mean) ** 2 for x in values) / k) ** 0.5 / mean if mean else None
    gini = sum(abs(a - b) for a in values for b in values) / (2 * k * n)
    entropy = -sum((x / n) * log(x / n) for x in values if x)
    normalized_entropy = entropy / log(k) if k > 1 else 0.0
    limits = {"top_share": float(standards.get("balance_top_share_warning", 0.80)),
              "cv": float(standards.get("balance_cv_warning", 1.00)),
              "gini": float(standards.get("balance_gini_warning", 0.60)),
              "shannon_low": float(standards.get("balance_shannon_low_warning", 0.45)),
              "shannon_high": float(standards.get("balance_shannon_high_warning", 0.95))}
    flags = []
    if max(values) / n > limits["top_share"]: flags.append("top_source_share")
    if cv > limits["cv"]: flags.append("cv")
    if gini > limits["gini"]: flags.append("gini")
    if normalized_entropy < limits["shannon_low"]: flags.append("shannon_low")
    # 高 Shannon 仅作说明性信号（碎片化风险），不触发自动警示
    high_shannon_note = None
    if k >= 3 and normalized_entropy > limits["shannon_high"]:
        high_shannon_note = f"Hn={normalized_entropy:.3f}>{limits['shannon_high']}，来源高度碎片化——建议检查是否混入异质数据库或非相关来源，不代表平衡性不合格"
    return {"status": "measured", "counts": dict(counts), "top_source_share": round(max(values) / n, 3),
            "cv": round(cv, 3), "gini": round(gini, 3), "shannon": round(entropy, 3),
            "normalized_shannon": round(normalized_entropy, 3), "limits": limits, "flags": flags,
            "high_shannon_note": high_shannon_note,
            "checks": {"C2_source_balance": "warning" if flags else "pass"}}

def topic_balance(context):
    standards = context.get("standards", {})
    raw = context.get("taxonomy", [])
    topics = [{"name": r.get("name", "unnamed"), "expected": r.get("expected", True),
               "records": r.get("high_confidence_records"), "target_share": r.get("target_share")}
              for r in raw if isinstance(r, dict) and r.get("expected", True)]
    values = [int(x["records"] or 0) for x in topics]
    if not topics:
        return {"status": "not_assessable",
                "checks": {"C1_topic_balance": "not_assessable", "C3_topic_source_balance": "not_assessable"}}
    n, k = sum(values), len(values)
    if n == 0:
        return {"status": "measured", "topic_counts": {x["name"]: 0 for x in topics},
                "top_topic_share": None, "cv": None, "gini": None, "normalized_shannon": None,
                "target_tvd": None, "flags": ["empty_topic"], "cross_source_flags": [],
                "checks": {"C1_topic_balance": "fail", "C3_topic_source_balance": "not_assessable"}}
    mean = n / k
    cv = (sum((x - mean) ** 2 for x in values) / k) ** .5 / mean
    gini = sum(abs(a - b) for a in values for b in values) / (2 * k * n)
    h = -sum((x / n) * log(x / n) for x in values if x); hn = h / log(k) if k > 1 else 0.0
    limits = {"top_share": float(standards.get("topic_top_share_warning", .70)),
              "cv": float(standards.get("topic_cv_warning", .80)),
              "gini": float(standards.get("topic_gini_warning", .50)),
              "shannon_low": float(standards.get("topic_shannon_low_warning", .55)),
              "tvd": float(standards.get("topic_target_tvd_warning", .25))}
    flags = ["empty_topic"] if any(x == 0 for x in values) else []
    if max(values) / n > limits["top_share"]: flags.append("top_topic_share")
    if cv > limits["cv"]: flags.append("cv")
    if gini > limits["gini"]: flags.append("gini")
    if hn < limits["shannon_low"]: flags.append("shannon_low")
    targets = [x.get("target_share") for x in topics]
    tvd = None
    if all(isinstance(x, (int, float)) for x in targets) and sum(targets) > 0:
        target_sum = sum(targets)
        tvd = .5 * sum(abs(value / n - target / target_sum) for value, target in zip(values, targets))
        if tvd > limits["tvd"]: flags.append("target_distribution")
    cross = context.get("topic_source_counts", {})
    cross_flags = []
    if cross:
        for topic in topics:
            counts = cross.get(topic["name"], {})
            total = sum(counts.values()) if isinstance(counts, dict) else 0
            if total and (len(counts) < int(standards.get("topic_min_sources", 2))
                          or max(counts.values()) / total > float(standards.get("topic_source_top_share_warning", .80))):
                cross_flags.append(topic["name"])
            elif not total: cross_flags.append(topic["name"])
    return {"status": "measured", "topic_counts": {x["name"]: v for x, v in zip(topics, values)},
            "top_topic_share": round(max(values) / n, 3), "cv": round(cv, 3), "gini": round(gini, 3),
            "normalized_shannon": round(hn, 3), "target_tvd": round(tvd, 3) if tvd is not None else None,
            "flags": flags, "cross_source_flags": cross_flags,
            "checks": {"C1_topic_balance": "fail" if "empty_topic" in flags else "warning" if flags else "pass",
                       "C3_topic_source_balance": "warning" if cross_flags else "pass" if cross else "not_assessable"}}

# Controlled profile IDs → (recency_years, min_share, freshness_days)
PROFILES = {
    "computer_ai": (3, .40, 30),
    "electronics_communications": (3, .40, 30),
    "mechanical_manufacturing": (5, .35, 90),
    "materials_chemical": (5, .35, 90),
    "biomedical_engineering": (5, .35, 90),
    "civil_infrastructure": (7, .30, 180),
    "energy_environment": (7, .30, 180),
    "aerospace_transportation": (7, .30, 180),
}

def profile_defaults(context):
    """Resolve profile defaults from controlled ID, with text fallback and standards override."""
    profile = str(context.get("profile", "")).lower()
    standards = context.get("standards", {})
    # 1. prefer recency_years / recency_min_share / d_freshness_days from standards
    # 2. else controlled profile ID
    # 3. else text heuristic fallback (legacy compatibility)
    years = standards.get("recency_years")
    share = standards.get("recency_min_share")
    fresh_days = standards.get("d_freshness_days")
    if years is not None and share is not None:
        return int(years), float(share), int(fresh_days or PROFILES.get("mechanical_manufacturing", (5, .35, 90))[2])
    # controlled ID lookup
    for pid, (y, s, d) in PROFILES.items():
        if pid in profile or profile == pid:
            return y, s, int(fresh_days or d)
    # text heuristic fallback
    fast = any(x in profile for x in ("computer", "ai", "software", "electronic", "communication"))
    slow = any(x in profile for x in ("civil", "energy", "infrastructure", "aerospace", "transport"))
    defaults = (3, .40) if fast else (7, .30) if slow else (5, .35)
    return defaults[0], defaults[1], int(fresh_days or (30 if fast else 180 if slow else 90))

def recency(library, context):
    years, minimum, _freshness = profile_defaults(context)
    current_year = dt.date.today().year; parsed = []
    total_records = len(library)
    for item in library:
        try: parsed.append(int(str(item.get("date") or "")[:4]))
        except ValueError: pass
    recent = sum(y >= current_year - years + 1 for y in parsed)
    share = recent / len(parsed) if parsed else None
    year_completeness = len(parsed) / total_records if total_records else None
    preprints = sum(bool(x.get("is_preprint")) for x in library)
    d2_passes = share is not None and share >= minimum
    d2_verdict = ("warning" if not d2_passes and share is not None
                  else "not_assessable" if share is None else "pass")
    # Degrade to warning when year completeness < 50% — numerator hides missing data
    if d2_verdict == "pass" and year_completeness is not None and year_completeness < 0.50:
        d2_verdict = "warning"
    checks = {"D1_search_freshness": currency(context)["checks"]["D1_freshness"],
              "D2_recent_share": d2_verdict,
              "D3_frontier": context.get("frontier_coverage_verdict", "not_assessable"),
              "D4_versions_preprints": context.get("version_currency_verdict", "not_assessable")}
    return {"status": "measured" if parsed else "not_assessable", "window_years": years,
            "minimum_share": minimum, "dated_records": len(parsed), "recent_records": recent,
            "recent_share": round(share, 3) if share is not None else None,
            "year_completeness": round(year_completeness, 3) if year_completeness is not None else None,
            "preprint_records": preprints, "checks": checks}

def umbrella_checks(library, context, lib_health):
    """Run umbrella-review-specific A4 / C4 / F7 checks. Returns dict with a4, c4, f7."""
    standards = context.get("standards", {})
    n = len(library) if library else 0
    rt = context.get("review_type", "")
    if rt != "伞式综述":
        return {"a4": None, "c4": None, "f7": None}

    # A4 — library type purity: are these survey/review papers, not primary studies?
    SURVEY_PATTERNS = ["survey", "review", "comprehensive review", "systematic review",
                       "meta-analysis", "scoping review", "umbrella review",
                       "综述", "进展", "回顾", "元分析", "荟萃分析"]
    survey_count = 0
    for item in library:
        title = str(item.get("title", "")).lower()
        pub_type = str(item.get("itemType", item.get("type", ""))).lower()
        matched = any(p in title for p in SURVEY_PATTERNS) or ("review" in pub_type)
        if matched:
            survey_count += 1
    purity = round(survey_count / n, 3) if n else None
    purity_min = float(standards.get("umbrella_library_type_purity", 0.90))
    a4 = {"status": "measured" if n else "not_assessable",
          "survey_literature_count": survey_count, "total_library_size": n,
          "purity": purity,
          "threshold": purity_min,
          "verdict": "pass" if purity is not None and purity >= purity_min else "fail" if purity is not None else "not_assessable",
          "note": "伞式综述的库内文献应为已发表的综述论文。自动分类基于 title 关键词匹配 - 仅初筛，需人工抽样核验。"}

    # C4 — review coverage distribution
    # This needs survey metadata: sub-topics, method types, search windows
    # Auto-detect method types from titles
    method_counts = Counter()
    for item in library:
        title = str(item.get("title", "")).lower()
        if "systematic review" in title or "系统综述" in title: method_counts["系统综述"] += 1
        elif "meta-analysis" in title or "元分析" in title or "荟萃分析" in title: method_counts["元分析"] += 1
        elif "scoping review" in title or "范围综述" in title or "scoping" in title: method_counts["范围综述"] += 1
        elif "umbrella review" in title or "伞式综述" in title: method_counts["伞式综述"] += 1
        elif any(p in title for p in ["survey", "review", "综述", "回顾", "进展"]): method_counts["叙事/一般综述"] += 1
    # CCA calculation requires primary-study lists per review — not automatable
    cca = context.get("umbrella_cca")
    c4 = {"status": "not_assessable", "method_type_distribution": dict(method_counts) if method_counts else None,
          "cca": cca, "cca_threshold": 0.15,
          "verdict": "not_assessable",
          "note": "方法类型分布为自动初筛（从标题推断）。CCA 需纳入综述的原始研究列表，超出自动范围。若 CCA 不可得则标 not_assessable。"}
    if cca is not None:
        c4["verdict"] = "warning" if cca > 0.15 else "pass"
        c4["status"] = "estimated"
        c4["note"] = f"CCA={cca:.3f}。{'重叠较高，需解释原因。' if cca > 0.15 else '重叠在可接受范围内。'}方法类型分布为自动初筛。"

    # F7 — quality assessment readiness
    access_union_rate = lib_health.get("access_union_rate") if lib_health else None
    f7_access_threshold = float(standards.get("f_access_rate", 0.85))
    tool = context.get("quality_assessment_tool", "")
    f7 = {"status": "screening", "fulltext_readiness": access_union_rate,
          "threshold": f7_access_threshold,
          "quality_assessment_tool": tool or "未指定",
          "verdict": "not_assessable",
          "note": "AMSTAR-2/ROBIS 评估超出自动范围。F7 仅报告就绪度（全文获取率是否支持质量评估），不代替实际质量评分。"}
    if access_union_rate is not None:
        if access_union_rate >= f7_access_threshold:
            f7["verdict"] = "pass"
            f7["note"] = f"全文就绪度达标（{access_union_rate*100:.1f}%）。{'已指定评估工具：' + tool if tool else '请选定 AMSTAR-2 或 ROBIS 作为质量评估工具。'}AMSTAR-2/ROBIS 需人工完成。"
        else:
            f7["verdict"] = "fail"
            f7["note"] = f"全文就绪度不足（{access_union_rate*100:.1f}% < {f7_access_threshold*100:.0f}%）。需要更多全文才能对纳入综述开展 AMSTAR-2/ROBIS 评估。"

    return {"a4": a4, "c4": c4, "f7": f7}

def quality(library, context):
    citations = sorted([int(x.get("cited_by_count")) for x in library
                        if isinstance(x.get("cited_by_count"), (int, float))], reverse=True)
    h = max((idx for idx, value in enumerate(citations, 1) if value >= idx), default=0)
    tiers = {str(x).strip().lower() for x in context.get("tier1_venues", [])}
    venues = [str(x.get("publicationTitle") or x.get("venue") or "").strip().lower() for x in library]
    tier_hits = sum(bool(v and v in tiers) for v in venues)
    rate = tier_hits / len(library) if library and tiers else None
    return {"status": "measured" if library else "not_assessable", "citation_records": len(citations),
            "h_core": h if citations else None, "tier1_venues_configured": len(tiers),
            "tier1_records": tier_hits if tiers else None,
            "tier1_rate": round(rate, 3) if rate is not None else None,
            "checks": {"E1_h_core": "screening" if citations else "not_assessable",
                       "E2_tier1": "screening" if tiers else "not_assessable"}}

def compact(value):
    if value is None or value == "": return "—"
    if isinstance(value, float): return f"{value:.3f}"
    if isinstance(value, (list, dict)): return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).replace("|", "／").replace("\n", " ")

def _input_evidence_table(report):
    """Generate the input evidence status table placed at the top of the report."""
    ctx = report.get("context", {})
    artifacts = report.get("artifacts", {})
    libh = report.get("library_health", {})
    standards = report.get("standards", {})

    def yn(p): return "是" if p else "否"

    # Determine input states
    lib_provided = bool(libh.get("records"))
    benchmark_provided = bool(artifacts.get("benchmark", {}).get("provided"))
    gold_provided = bool(artifacts.get("gold", {}).get("provided"))
    run_log_provided = bool(artifacts.get("run-log", {}).get("provided"))
    run_log_depth = ctx.get("run_log_depth", "missing")
    run_log_valid = "schema 合格" if run_log_depth in ("valid", "valid_full") else ("字段不全" if run_log_depth == "shallow" else "否")
    screening_decisions = ctx.get("search_rounds", [])
    screening_status = "discovery_only" if any(r.get("screening_status") == "discovery_only" for r in screening_decisions) else ("完整" if screening_decisions else "否")
    dedup_provided = bool(artifacts.get("deduplication-log", {}).get("provided"))
    dedup_depth = libh.get("dedup_log_depth", "missing")
    dedup_valid = "决策完整" if dedup_depth == "structured_decisions" else ("有候选无决策" if dedup_depth == "structured_no_decisions" else "否")
    snap_provided = bool(artifacts.get("candidate-snapshots", {}).get("provided") or artifacts.get("source-snapshot", {}).get("provided"))

    # A2 independence check
    a1_path = artifacts.get("benchmark", {}).get("path", "")
    a2_path = artifacts.get("gold", {}).get("path", "")
    gold_independence = "独立于 A1" if (a2_path and a2_path != a1_path) else ("与 A1 复用" if gold_provided else "—")

    lines = ["## 本次评估输入与证据状态\n"]
    lines.append("| 输入工件 | 是否提供 | 是否有效 | 支撑的指标 | 缺失影响 |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.append(f"| 规范化文献库 | {yn(lib_provided)} | 有效（{libh.get('records','—')} 篇） | C–F、部分 A/B | 无库不能做正式评估 |")
    lines.append(f"| A1 基准集 | {yn(benchmark_provided)} | 有稳定 ID | A1 | A1 不可评估 |")
    lines.append(f"| A2 Gold 集 | {yn(gold_provided)} | {gold_independence} | A2 | {'A2 降低证据强度' if gold_independence == '与 A1 复用' else 'A2 不可评估' if not gold_provided else '—'} |")
    lines.append(f"| 查询日志 (run-log) | {yn(run_log_provided)} | {run_log_valid} | F1、A2 | 检索不可复跑 |")
    lines.append(f"| 筛选决定 | {yn(bool(screening_decisions))} | {screening_status} | B | B 不可判饱和 |")
    lines.append(f"| 去重日志 (dedup-log) | {yn(dedup_provided)} | {dedup_valid} | F4 | 版本处理待核验 |")
    lines.append(f"| A3 多源快照 | {yn(snap_provided)} | — | A3 | A3 不可评估 |")
    d3_has = bool(ctx.get("frontier_coverage_verdict"))
    lines.append(f"| 前沿检索证据 | {yn(d3_has)} | — | D3 | D3 不可评估（默认） |")
    d4_has = bool(ctx.get("version_currency_verdict"))
    lines.append(f"| 版本核验记录 | {yn(d4_has)} | — | D4 | D4 不可评估（默认） |")
    return "\n".join(lines)

def _standards_appendix(report):
    """Generate an appendix showing which standards were actually applied and their source."""
    ctx = report.get("context", {})
    s = report.get("standards", {})
    rt = ctx.get("review_type", "未指定")
    pr = ctx.get("profile", "未指定")
    user_overrides = ctx.get("standards", {}).get("user_overrides", {})

    def src(k, default_val):
        ov = user_overrides.get(k) if isinstance(user_overrides, dict) else None
        if ov is not None: return ("user_override", True)
        return ("review_type_default" if k in ("a1_min_recall", "a2_min_recall", "f_access_rate", "f_provenance_rate", "f_core_metadata_rate", "f_abstract_rate") else "profile_default", False)

    def row(code, label, default_val, override_val):
        sr, over = src(code, default_val)
        applied = override_val if override_val is not None else default_val
        return f"| {label} | {code} | {default_val} | {applied} | {sr} | {'是' if over else '否'} |"

    lines = ["## 本次采用标准\n"]
    lines.append("| 评估项 | 编号 | 默认值 | 本次采用值 | 来源 | 用户覆盖？ |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    lines.append(row("a1_min_recall", "基准集召回率", _fmt_pct(s.get("a1_min_recall")), _fmt_pct(s.get("a1_min_recall"))))
    lines.append(row("a2_min_recall", "检索式灵敏度", _fmt_pct(s.get("a2_min_recall")), _fmt_pct(s.get("a2_min_recall"))))
    lines.append(row("b_ggr_threshold", "GGR 阈值", _fmt_num(s.get("b_ggr_threshold")), _fmt_num(s.get("b_ggr_threshold"))))
    lines.append(row("b_drr_threshold", "DRR 阈值", _fmt_num(s.get("b_drr_threshold")), _fmt_num(s.get("b_drr_threshold"))))
    lines.append(row("topic_top_share_warning", "主题 Top-share", _fmt_num(s.get("topic_top_share_warning")), _fmt_num(s.get("topic_top_share_warning"))))
    lines.append(row("balance_top_share_warning", "来源 Top-share", _fmt_num(s.get("balance_top_share_warning")), _fmt_num(s.get("balance_top_share_warning"))))
    lines.append(row("recency_years", "D2 近年窗口", f"{s.get('recency_years','—')} 年 / ≥ {_fmt_pct(s.get('recency_min_share'))}", f"{s.get('recency_years','—')} 年 / ≥ {_fmt_pct(s.get('recency_min_share'))}"))
    lines.append(row("d_freshness_days", "来源新鲜度", f"{s.get('d_freshness_days','—')} 天", f"{s.get('d_freshness_days','—')} 天"))
    lines.append(row("f_abstract_rate", "摘要覆盖率", _fmt_pct(s.get("f_abstract_rate")), _fmt_pct(s.get("f_abstract_rate"))))
    lines.append(row("f_access_rate", "全文获取率", _fmt_pct(s.get("f_access_rate")), _fmt_pct(s.get("f_access_rate"))))
    lines.append(row("f_provenance_rate", "来源可追溯", _fmt_pct(s.get("f_provenance_rate")), _fmt_pct(s.get("f_provenance_rate"))))
    lines.append(row("f_core_metadata_rate", "核心元数据率", _fmt_pct(s.get("f_core_metadata_rate")), _fmt_pct(s.get("f_core_metadata_rate"))))
    lines.append("")
    lines.append("> 来源说明：`profile_default` = 工程领域默认值；`review_type_default` = 综述类型默认值；`user_override` = 用户指定值。")
    lines.append("> 完整标准说明书见 `references/user-standards-guide.md`。")
    return "\n".join(lines)

def threshold_verdict(value, threshold):
    if value is None or threshold is None: return "not_assessable"
    return "pass" if value >= threshold else "fail"

def _fmt_pct(val):
    return f"{val*100:.1f}%" if val is not None else "—"

def _fmt_num(val):
    return str(val) if val is not None else "—"

# ── report sections ─────────────────────────────────────────────
def _method_narrative(report):
    """Expose implicit agent work: keywords, benchmark method, data sources, taxonomy."""
    ctx = report.get("context", {}); lines = []
    keywords = ctx.get("keywords", []); queries = ctx.get("queries", [])
    plan_queries = ctx.get("query_plan", {})
    if keywords: lines.append(f"**检索关键词**：{'、'.join(keywords)}")
    if queries:
        lines.append("**检索式**：")
        for q in queries:
            if isinstance(q, dict):
                lines.append(f"- {q.get('source','')}: `{q.get('query','')}`（{q.get('date','')}，结果 {q.get('hits','—')} 条）")
            else: lines.append(f"- {q}")
    elif isinstance(plan_queries, dict):
        for src, q in plan_queries.items(): lines.append(f"- {src}: `{q}`")
    if not keywords and not queries and not plan_queries:
        lines.append("**检索关键词**：未记录（建库时未保留 query-plan.json，检索不可复跑）")

    bm_method = ctx.get("benchmark_method", ""); bm_source = ctx.get("benchmark_source", "")
    bm_size = report["coverage"]["a1"].get("total", 0); bm_note = ctx.get("benchmark_note", "")
    if bm_method or bm_source:
        lines.append(f"\n**A1 基准集构建**：{bm_method}")
        lines.append(f"**基准集来源**：{bm_source}，共 {bm_size} 篇。{bm_note}")
    else:
        lines.append(f"\n**A1 基准集**：共 {bm_size} 篇稳定标识符条目。" + ("来源未记录。" if not bm_source else ""))

    gs_method = ctx.get("gold_set_method", ""); gs_size = report["coverage"]["a2"].get("total", 0)
    if gs_method: lines.append(f"**A2 Gold set 构建**：{gs_method}（共 {gs_size} 篇）")
    elif gs_size: lines.append(f"**A2 Gold set**：共 {gs_size} 篇")
    # Warn when gold set reuses A1 benchmark — A1 and A2 become non-independent
    a2_note = report["coverage"]["a2"].get("note", "")
    if "reuses" in a2_note.lower() or "gold" in a2_note.lower():
        lines.append(f"**A2 独立性**：⚠ {a2_note}")
    elif "title" in a2_note.lower():
        lines.append(f"**A2 匹配方式**：{a2_note}")

    sources = ctx.get("search_sources", ctx.get("planned_sources", []))
    sources_used = list(report.get("currency", {}).get("sources", {}).keys())
    all_srcs = sources or sources_used
    if all_srcs:
        lines.append(f"\n**数据来源**：{'、'.join(all_srcs)}")
        failed = ctx.get("failed_sources", [])
        if failed: lines.append(f"（检索失败：{'、'.join(failed)}）")
        incomplete = report["coverage"]["a3"].get("incomplete_sources", [])
        if incomplete: lines.append(f"（快照不完整：{'、'.join(incomplete)}）")

    lines.append(f"\n**A3 覆盖估计**：{report['coverage']['a3'].get('note','')}")
    taxonomy = ctx.get("taxonomy", [])
    if taxonomy:
        names = [t.get("name", "?") for t in taxonomy if isinstance(t, dict)]
        lines.append(f"\n**分类体系**：{len(taxonomy)} 个主题（{'、'.join(names)}）")
    cls_method = ctx.get("classification_method", "")
    cls_sample = ctx.get("classification_sample_verified")
    if cls_method or cls_sample is not None:
        parts = []
        if cls_method: parts.append(cls_method)
        if cls_sample is not None: parts.append(f"抽查校验 {cls_sample} 条")
        lines.append(f"**C1 分类方法**：{'；'.join(parts)}（注：C1 数值从外部分类计数计算，未经脚本独立分类）")
    lines.append(f"\n**证据状态**：实测=可复跑记录；估计=基于假设的区间或抽样；自动初筛=规则判定未人工核验；不可评估=缺少必要输入。")
    return "\n".join(lines)

def _priority_actions(report):
    blocking, rec = [], []
    for row in report.get("indicator_register", []):
        v = row.get("meets_standard", "")
        if v == "fail": blocking.append(f"- **{row['subproject']} {row['project_name']}**：{row.get('description_and_action','')}")
        elif v == "warning": rec.append(f"- {row['subproject']} {row['project_name']}：{row.get('description_and_action','')}")
    parts = []
    if blocking: parts.append("### 阻断项\n\n" + "\n".join(blocking))
    if rec: parts.append("### 建议改进\n\n" + "\n".join(rec))
    ctx = report.get("context", {})
    pa = ctx.get("potential_additions", [])
    if pa:
        lines = "\n".join(f"- {t}" for t in pa[:15])
        discovery_ggr = ctx.get("first_round_discovery_ggr", "—")
        head = f"### 潜在新增文献（Discovery 候选率={discovery_ggr}，筛选确认后可复评 B 饱和度）\n\n"
        parts.append(head + lines + (f"\n\n（共 {len(pa)} 篇候选，完整列表见 potential_additions.json）" if len(pa) > 15 else ""))
    return "\n\n".join(parts) if parts else "未检测到阻断或警示项。"

def _top_actions(report):
    """Extract the top 3 highest-priority actions for the report header."""
    blocking, rec = [], []
    for row in report.get("indicator_register", []):
        v = row.get("meets_standard", "")
        if v == "fail": blocking.append(row)
        elif v == "warning": rec.append(row)

    lines = []
    # Blocking items first
    for r in blocking[:2]:
        lines.append(f"1. **🔴 {r['subproject']} {r['project_name']}**：{r.get('description_and_action','')}")
    # Top warning if fewer than 3 blocking
    for r in rec[:3 - len(blocking)]:
        lines.append(f"{len(lines)+1}. **🟡 {r['subproject']} {r['project_name']}**：{r.get('description_and_action','')}")
    if not lines:
        lines.append("1. 未检测到阻断或警示项。查看完整总表确认是否有需人工核验的 `not_assessable` 项。")
    return "\n".join(lines)

def _dimension_narrative(report):
    c, p, b, t, d, q, h = (report["coverage"], report["process"], report["balance"],
                           report["topic_balance"], report["recency"], report["quality"],
                           report["library_health"])
    lines = []
    a1_r = _fmt_pct(c["a1"].get("recall")); a1_h = _fmt_num(c["a1"].get("matched")); a1_t = _fmt_num(c["a1"].get("total"))
    a3_lb = _fmt_num(c["a3"].get("deduplicated_candidate_lower_bound"))
    lines.append(f"**A 覆盖**：基准集召回 {a1_r}（{a1_h}/{a1_t}），多源候选下界 {a3_lb} 篇。")
    rates = p.get("high_confidence_new_rates", [])
    ggr = ", ".join(f"{r:.3f}" for r in rates[-2:]) if len(rates) >= 2 else "缺数据"
    lines.append(f"**B 饱和度**：最后两轮 GGR={ggr}（阈值<{p.get('thresholds',{}).get('new_rate','—')}）；{p.get('verdict','—')}。")
    flags = t.get("flags", []); n_topics = len(t.get("topic_counts", {}))
    lines.append(f"**C 平衡**：{n_topics} 个预期主题，{'含空主题' if 'empty_topic' in flags else '全部有文献'}；来源集中度 {b.get('top_source_share','—')}（CV={_fmt_num(b.get('cv'))} Gini={_fmt_num(b.get('gini'))}）。")
    lines.append(f"**D 时效**：近 {d.get('window_years','—')} 年占比 {_fmt_pct(d.get('recent_share'))}（{d.get('recent_records','—')}/{d.get('dated_records','—')} 标有日期）；预印本 {d.get('preprint_records','—')} 条。")
    lines.append(f"**E 学术影响**：h-core={_fmt_num(q.get('h_core'))}（{q.get('citation_records','—')} 条引用）；Tier-1 {_fmt_pct(q.get('tier1_rate'))}（{q.get('tier1_venues_configured','—')} venue）。仅作背景信号，不等于研究质量——真正的研究质量评估应使用与研究设计匹配的批判性评价工具。")
    fc = h.get("field_completeness", {})
    lines.append(f"**F 可用性**：核心元数据 {_fmt_pct(fc.get('title'))}；摘要 {_fmt_pct(fc.get('abstractNote'))}；DOI {_fmt_pct(fc.get('DOI'))}；全文获取率 {_fmt_pct(h.get('access_union_rate'))}（附件 {_fmt_pct(h.get('attachment_rate'))} / OA {_fmt_pct(h.get('open_link_rate'))}）；谱系率 {_fmt_pct(h.get('provenance_rate'))}。")
    return "\n\n".join(lines)

def indicator_rows(report):
    c, p, b, t, d, q, h = (report["coverage"], report["process"], report["balance"],
                           report["topic_balance"], report["recency"], report["quality"],
                           report["library_health"])
    umb = report.get("umbrella", {})
    s = report.get("standards", {}); ctx = report.get("context", {})
    a1m = s.get("a1_min_recall"); a2m = s.get("a2_min_recall")
    chk = lambda g, k: g.get("checks", {}).get(k, "not_assessable")
    rows = []
    def add(dim, code, name, std, v, cur, ev, note):
        rows.append((dim, code, name, std, v, compact(cur), ev, note))

    a1r = c["a1"].get("recall"); a1h = c["a1"].get("matched"); a1t = c["a1"].get("total")
    a2r = c["a2"].get("recall"); a3l = c["a3"].get("deduplicated_candidate_lower_bound")
    a3s = c["a3"].get("status"); br = p.get("high_confidence_new_rates", [])
    bv = p.get("verdict", "—"); tc = t.get("topic_counts", {}); tf = t.get("flags", [])
    bs = b.get("top_source_share"); bcv = b.get("cv"); bg = b.get("gini"); bsh = b.get("normalized_shannon")
    ds = d.get("recent_share"); dy = d.get("window_years"); dsrc = report.get("currency", {}).get("sources", {})
    qh = q.get("h_core"); qt1 = q.get("tier1_rate")
    fc = h.get("field_completeness", {}); hdoi = h.get("duplicate_doi_groups", 0)
    hty = h.get("duplicate_title_year_groups", 0)
    hacc = h.get("access_union_rate")
    hpr = h.get("provenance_rate"); hcr = h.get("correction_flag_records", 0)
    ha_r = h.get("attachment_rate"); ho_r = h.get("open_link_rate")
    mids = c["a1"].get("missing_ids", [])

    add("A 覆盖", "A1", "基准集召回率", f"阈值 ≥ {a1m}" if a1m else "需配置 a1_min_recall",
        threshold_verdict(a1r, a1m), f"{_fmt_pct(a1r)}（{_fmt_num(a1h)}/{_fmt_num(a1t)}）",
        c["a1"].get("status"),
        f"A1 高只说明找回了锚点，不等于主题无遗漏。实测 {a1h}/{a1t}（{_fmt_pct(a1r)}）。{'漏项：' + ', '.join(mids[:5]) if mids else '无稳定 ID 漏项。'}")

    # A2 independence note
    a1_path = report.get("artifacts", {}).get("benchmark", {}).get("path", "")
    a2_path = report.get("artifacts", {}).get("gold", {}).get("path", "")
    a2_dep = "⚠ A2 非独立——Gold 与 A1 基准集复用；A1 和 A2 不能相互增强证据强度。" if (a2_path and a2_path == a1_path) else ""
    add("A 覆盖", "A2", "检索式灵敏度", f"阈值 ≥ {a2m}" if a2m else "需配置 a2_min_recall",
        threshold_verdict(a2r, a2m), f"{_fmt_pct(a2r)}（{_fmt_num(c['a2'].get('matched'))}/{_fmt_num(c['a2'].get('total'))}）",
        c["a2"].get("status"),
        f"A2 高只说明检索式能找回 Gold，不等于 Gold 足够代表问题。{a2_dep}实测 {_fmt_pct(a2r)}。{'零命中=实测 0。' if a2r == 0 and c['a2'].get('status') == 'measured' else ''}")

    add("A 覆盖", "A3", "多源候选下界", "至少两完整来源；只报告下界",
        "pass" if a3s == "estimated_lower_bound" else "not_assessable",
        f"下界 {_fmt_num(a3l)} 篇（{', '.join(c['a3'].get('source_unique_identifier_counts',{}).keys()) or '—'}）",
        "estimated" if a3s.startswith("estimated") else a3s,
        f"多源去重下界 {_fmt_num(a3l)} 篇。{'来源不完整。' if a3s == 'partial_snapshot' else '来源完整。'}不是召回率。")

    b1_cur = (', '.join(f'{r:.4f}' for r in br[-2:]) if len(br) >= 2
              else (f'首轮 {br[-1]:.4f}（需第2轮确认趋稳）' if len(br) == 1 else '—'))
    add("B 饱和度", "B1", "核心库增长率 GGR",
        f"最后两轮均 < {p.get('thresholds',{}).get('new_rate','—')}" if len(br) >= 2 else "/",
        chk(p, "B1_ggr"),
        b1_cur, p.get("status"),
        f"B 趋稳仅在筛选决策真实、路径独立且多轮完成时才成立。GGR={', '.join(f'{r:.4f}' for r in br[-2:]) if len(br)>=2 else ('首轮 '+f'{br[-1]:.4f}'+'，需第2轮确认' if len(br)==1 else '需要至少两轮 search round')}。高置信新增/核心库。")

    add("B 饱和度", "B2", "新增路径发现率 DRR",
        f"各路径均 < {p.get('thresholds',{}).get('marginal_yield','—')}" if len(p.get('source_marginal_yields',[])) >= 2 else "/",
        chk(p, "B2_drr"),
        f"{_fmt_num(len(p.get('source_marginal_yields',[])))} 条路径", p.get("status"),
        f"DRR 只有在筛选确认后才有意义——发现候选不等于纳入项。边际收益：{p.get('source_marginal_yields','—')}。新路径高置信文献/候选量。")

    add("B 饱和度", "B3", "饱和过程证据",
        "路径完成且独立验证通过" if p.get('independent_validation_passed') is not None else '/',
        "pass" if chk(p, "B3_pathway_completion") == "pass" and chk(p, "B3_independent_validation") == "pass"
        else "fail" if chk(p, "B3_pathway_completion") == "fail" or chk(p, "B3_independent_validation") == "fail"
        else "not_assessable",
        f"路径 {_fmt_pct(p.get('pathway_completion'))} | 独立验证 {'通过' if p.get('independent_validation_passed') is True else ('未通过' if p.get('independent_validation_passed') is False else '—')}",
        p.get("status"), f"结论：**{bv}**。仅低 GGR/DRR 不够——需路径完成+独立验证+筛选真实同时成立。")

    add("C 平衡", "C1", "主题覆盖与偏斜",
        "无空主题；Top≤0.70；CV≤0.80；Gini≤0.50；Shannon≥0.55", chk(t, "C1_topic_balance"),
        f"{_fmt_num(len(tc))} 主题 | {'含空主题' if 'empty_topic' in tf else '无空主题'}", t.get("status"),
        f"{'、'.join(f'{k}={v}篇' for k,v in (sorted(tc.items(), key=lambda x:-x[1]) if tc else []))}。{'需补：' + ', '.join(k for k,v in tc.items() if v==0) if 'empty_topic' in tf else '各主题均有文献。'}")

    add("C 平衡", "C2", "来源集中度", "Top≤0.80；CV≤1.00；Gini≤0.60；Shannon≥0.45",
        chk(b, "C2_source_balance"),
        f"Top={_fmt_pct(bs)} | CV={_fmt_num(bcv)} | Gini={_fmt_num(bg)} | Hn={_fmt_num(bsh)}", b.get("status"),
        f"最大来源占比 {_fmt_pct(bs)}。{'单一来源依赖——非质量问题但需说明索引偏差。' if bs and bs > b.get('limits',{}).get('top_share',0.80) else '来源分布合理。'}{' ' + b.get('high_shannon_note','') if b.get('high_shannon_note') else ''}")

    add("C 平衡", "C3", "主题-来源交叉", "每主题 ≥2 来源；单一来源 ≤0.80",
        chk(t, "C3_topic_source_balance"),
        f"{'⚠ ' + str(len(t.get('cross_source_flags',[]))) + ' 主题来源不足' if t.get('cross_source_flags') else '—'}",
        t.get("status"),
        f"{'需补来源：' + ', '.join(t.get('cross_source_flags',[])) if t.get('cross_source_flags') else '未提供 topic_source_counts。' if not ctx.get('topic_source_counts') else '各主题有独立来源。'}")

    add("D 时效", "D1", "来源新鲜度",
        f"各来源距检索 ≤ {report.get('currency',{}).get('freshness_threshold_days','—')} 天",
        chk(d, "D1_search_freshness"),
        "; ".join(f"{k}:{v['days_since']}天" for k,v in dsrc.items()) if dsrc else "—",
        report.get("currency", {}).get("status", "not_assessable"),
        f"{len(dsrc)} 个来源有日期。{'存在过期来源。' if chk(d,'D1_search_freshness')=='warning' else '来源在新鲜度窗口内。'}")

    add("D 时效", "D2", "近年文献比例",
        f"近 {dy or '—'} 年占比 ≥ {d.get('minimum_share','—')}", chk(d, "D2_recent_share"),
        f"{_fmt_pct(ds)}（{_fmt_num(d.get('recent_records'))}/{_fmt_num(d.get('dated_records'))} 有日期）", d.get("status"),
        f"近 {dy} 年占比 {_fmt_pct(ds)}。阈值按 profile：AI/通信 3年40%、常规 5年35%、基础设施 7年30%。{'低于阈值。' if chk(d,'D2_recent_share')=='warning' else '达标。'}年份字段完整率 {_fmt_pct(d.get('year_completeness'))}；<50% 时 D2 自动降级为 warning。")

    add("D 时效", "D3", "前沿覆盖",
        "/" if not ctx.get("frontier_coverage_verdict") else "前沿窗口有独立检索/Gold set",
        chk(d, "D3_frontier"), ctx.get("frontier_coverage_verdict", "—"), d.get("status"),
        "前沿覆盖需 context.frontier_coverage_verdict。近期发表不等于前沿覆盖。")

    add("D 时效", "D4", "版本区分",
        "/" if not ctx.get("version_currency_verdict") else "预印本-正式版关系已核验",
        chk(d, "D4_versions_preprints"), f"预印本 {d.get('preprint_records','—')} 条", d.get("status"),
        f"{d.get('preprint_records','—')} 条预印本。{'未核验版本关系。' if chk(d,'D4_versions_preprints')=='not_assessable' else ''}")

    e1n = f"h-core={_fmt_num(qh)}。仅背景信号——高被引不等于高质量，新论文拉低 h-core。真正的研究质量评估应使用与研究设计匹配的批判性评价工具。"
    if q.get('citation_records') and h.get('records') and q['citation_records'] < h['records'] * 0.5:
        e1n += f" 注意仅 {_fmt_pct(q['citation_records']/h['records'])} 条目有引用数据。"
    add("E 学术影响", "E1", "h-core", "报告 h-index；仅背景信号", chk(q, "E1_h_core"),
        f"h={_fmt_num(qh)}（{q.get('citation_records','—')} 条引用）", q.get("status"), e1n)

    add("E 学术影响", "E2", "Tier-1 覆盖", "按 profile 配置 venue 映射", chk(q, "E2_tier1"),
        f"{_fmt_pct(qt1)}（{_fmt_num(q.get('tier1_records'))}/{_fmt_num(q.get('tier1_venues_configured'))} venue）", q.get("status"),
        f"已配置 {q.get('tier1_venues_configured','—')} 个 venue。{'未配置 tier1_venues。' if not q.get('tier1_venues_configured') else '当前仅为下界。'}")

    run_log_info = f"run log {'完整' if ctx.get('run_log_complete') else '缺失'}（{ctx.get('run_log_depth','无')}）"
    add("F 可用性", "F1", "检索可复跑",
        "/" if not ctx.get("run_log_complete") else "查询原文、字段、过滤器、日期、来源齐全",
        chk(p, "F1_query_traceability"), run_log_info, p.get("status"),
        f"{'建库时查询未保留——唯一过程阻断项。' if not ctx.get('run_log_complete') else '查询日志完整（source+query+fields+date+filters+result_count）。' if ctx.get('run_log_depth') == 'valid_full' else '查询日志包含 source+query+fields+date 字段。建议补充 filters/result_count/completion_status。' if ctx.get('run_log_depth') == 'valid' else 'run log 存在但缺少必要字段（需 source/query/fields/date）。'}")

    add("F 可用性", "F2", "摘要覆盖率", f"≥ {report['standards'].get('f_abstract_rate', .80)}",
        "pass" if fc.get("abstractNote") is not None and fc["abstractNote"] >= report["standards"].get("f_abstract_rate", .80) else "fail",
        _fmt_pct(fc.get("abstractNote")), h.get("status"),
        f"摘要率 {_fmt_pct(fc.get('abstractNote'))}。{'达标。' if (fc.get('abstractNote') or 0) >= report['standards'].get('f_abstract_rate',.80) else '低于阈值。'}")

    add("F 可用性", "F3", "全文获取率", f"≥ {report['standards'].get('f_access_rate', .80)}",
        chk(h, "F3_access"), _fmt_pct(hacc), h.get("status"),
        f"附件 {_fmt_pct(ha_r)} | 开放链接 {_fmt_pct(ho_r)} | 联合 {_fmt_pct(hacc)}。{'达标。' if hacc and hacc >= report['standards'].get('f_access_rate',.80) else '低于阈值。'}联合=v 附件或开放链接任一可用的记录比例，避免同一记录双渠道重复计数。")

    dedup_info = f"DOI 重复 {_fmt_num(hdoi)} 组 | 题名候选 {_fmt_num(hty)} 组 | 深度 {h.get('dedup_log_depth','—')}"
    dedup_verdict = "pass" if chk(h, "F4_exact_duplicates") == "pass" and chk(h, "F4_version_decisions") == "pass" else "fail" if chk(h, "F4_exact_duplicates") == "fail" else "not_assessable"
    add("F 可用性", "F4", "去重与版本", "DOI 精确重复=0；版本候选有决定",
        dedup_verdict, dedup_info, h.get("status"),
        f"DOI 重复 {_fmt_num(hdoi)} 组。{'存在未处理重复。' if hdoi > 0 else '无精确重复。'}题名相似候选 {_fmt_num(hty)} 组（{'版本决定已保存（' + dedup_log_depth + '）。' if chk(h,'F4_version_decisions')=='pass' else '未提供结构化 dedup-log，版本候选待核验。'}）")

    add("F 可用性", "F5", "来源可追溯", f"≥ {report['standards'].get('f_provenance_rate', .95)}",
        chk(h, "F5_provenance"), _fmt_pct(hpr), h.get("status"),
        f"来源谱系率 {_fmt_pct(hpr)}。{'达标。' if hpr and hpr >= report['standards'].get('f_provenance_rate',.95) else '低于阈值。'}")

    add("F 可用性", "F6", "撤稿更正核查",
        "/" if hcr == 0 else "关键记录有更正检查",
        chk(h, "F6_corrections"), f"标记 {_fmt_num(hcr)} 条", h.get("status"),
        f"{_fmt_num(hcr)} 条标记。{'未经专门来源核验。' if chk(h,'F6_corrections')=='not_assessable' else '已核验。'}")

    # ── Umbrella-only A4 / C4 / F7 rows ──
    is_umbrella = ctx.get("review_type") == "伞式综述"

    a4 = umb.get("a4") if umb else None
    if is_umbrella and a4:
        add("A 覆盖", "A4", "综述类型确认",
            f"综述论文占比 ≥ {a4.get('threshold','—')}",
            a4.get("verdict"), f"{_fmt_pct(a4.get('purity'))}（{_fmt_num(a4.get('survey_literature_count'))}/{_fmt_num(a4.get('total_library_size'))}）",
            a4.get("status"), a4.get("note", ""))

    c4 = umb.get("c4") if umb else None
    if is_umbrella and c4:
        mtd = c4.get("method_type_distribution", {})
        mtd_str = json.dumps(mtd, ensure_ascii=False) if mtd else "—"
        add("C 平衡", "C4", "综述间覆盖分布",
            "/" if c4.get("verdict") == "not_assessable" else "CCA ≤ 0.15 且子主题/方法类型无断层",
            c4.get("verdict"), f"CCA={_fmt_num(c4.get('cca'))} | 方法类型: {mtd_str}",
            c4.get("status"), c4.get("note", ""))

    f7 = umb.get("f7") if umb else None
    if is_umbrella and f7:
        add("F 可用性", "F7", "综述质量评估就绪度",
            f"全文就绪 ≥ {f7.get('threshold','—')}; 工具: {f7.get('quality_assessment_tool','—')}",
            f7.get("verdict"), f"全文 {_fmt_pct(f7.get('fulltext_readiness'))} | 工具 {f7.get('quality_assessment_tool','—')}",
            f7.get("status"), f7.get("note", ""))
    # ── end umbrella-only rows ──

    return rows

def hash_file(path):
    """Return sha256 hex digest of a file, or None if unreadable."""
    try:
        data = pathlib.Path(path).read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        return None

def copy_inputs_and_manifest(report, artifact_paths, out):
    """Copy input artifacts into out/inputs/ and write manifest.json.

    artifact_paths: dict of {label: path_or_None}
    """
    inputs_dir = out / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "1.0",
        "generated_at": report.get("generated_at", ""),
        "run_audit_version": "model-x-2026-07-21",
        "review_type": report.get("context", {}).get("review_type", ""),
        "standards_applied": report.get("standards", {}),
        "input_files": {},
    }
    for label, src in sorted(artifact_paths.items()):
        entry = {"provided": bool(src)}
        if src and pathlib.Path(src).is_file():
            entry["original_path"] = str(src)
            entry["sha256"] = hash_file(src) or "unreadable"
            dst = inputs_dir / pathlib.Path(src).name
            if not dst.exists() or hash_file(dst) != entry["sha256"]:
                shutil.copy2(src, dst)
            entry["copied_to"] = str(dst.relative_to(out))
        manifest["input_files"][label] = entry
    # Also record the library file
    lib_path = report.get("context", {}).get("library_path", "")
    if lib_path and pathlib.Path(lib_path).is_file():
        entry = {"provided": True, "original_path": lib_path, "sha256": hash_file(lib_path) or "unreadable"}
        dst = inputs_dir / pathlib.Path(lib_path).name
        if not dst.exists() or hash_file(dst) != entry["sha256"]:
            shutil.copy2(lib_path, dst)
        entry["copied_to"] = str(dst.relative_to(out))
        manifest["input_files"]["library"] = entry
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest

def write(report, out, artifact_paths=None):
    out.mkdir(parents=True, exist_ok=True)
    ctx = report.get("context", {}); h = report["library_health"]
    rows = indicator_rows(report)
    report["indicator_register"] = [
        {"parent_dimension": d, "subproject": c, "project_name": n,
         "standard": s, "meets_standard": v, "current_status": cur,
         "evidence_status": e, "description_and_action": note}
        for d, c, n, s, v, cur, e, note in rows]

    # Copy inputs and generate manifest
    if artifact_paths:
        copy_inputs_and_manifest(report, artifact_paths, out)
        report["manifest"] = json.loads((out / "manifest.json").read_text(encoding="utf-8"))

    (out / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    gt = report.get("generated_at", "")[:19].replace("T", " ")
    ln = ctx.get("library_name", ctx.get("library_path", "未指定"))
    rt = ctx.get("review_type", "未指定"); pr = ctx.get("profile", "未指定")
    sc = ctx.get("scope", f"{ctx.get('year_start','—')}–{ctx.get('year_end','—')}")
    a3l = report["coverage"]["a3"].get("deduplicated_candidate_lower_bound")

    # ── Input evidence status table (top of report) ──
    evidence_table = _input_evidence_table(report)
    # ── Standards appendix ──
    standards_appendix = _standards_appendix(report)

    md = ["# 文献库评估报告\n"]
    # Input evidence status + standards appendix before the main content
    if evidence_table:
        md.append(evidence_table)
        md.append("")
    # ── High-priority actions (top 3) ──
    top_actions = _top_actions(report)
    if top_actions:
        md.append("## 优先级行动\n")
        md.append(top_actions)
        md.append("")

    md.append("## 基本信息\n"); md.append("| 项目 | 值 |"); md.append("| --- | --- |")
    md.append(f"| 生成时间 | {gt} |"); md.append(f"| 评估对象 | {ln} |")
    md.append(f"| 文献库规模 | {h.get('records','—')} 篇 |"); md.append(f"| 综述类型 | {rt} |")
    md.append(f"| 工程领域 | {pr} |"); md.append(f"| 研究范围 | {sc} |")
    if a3l: md.append(f"| 全域参考 | OpenAlex 候选下界 {a3l} 篇 |")
    md.append("")
    md.append("## 综合判断\n"); md.append(report["summary"]); md.append("")
    md.append("## 评估方法与过程\n"); md.append(_method_narrative(report)); md.append("")
    md.append("## A–F 六维评估总表\n")
    md.append("| 维度 | 编号 | 评估项 | 标准 | 判定 | 当前值 | 证据状态 | 说明与行动 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    md.append("\n".join("| " + " | ".join(compact(cell) for cell in row) + " |" for row in rows))
    md.append("")
    md.append("## 各维度分析\n"); md.append(_dimension_narrative(report)); md.append("")
    md.append("## 改进建议\n"); md.append(_priority_actions(report)); md.append("")
    md.append("## 局限与声明\n"); md.append("\n".join("- " + x for x in report["limitations"])); md.append("")
    if standards_appendix:
        md.append(standards_appendix)
        md.append("")
    (out / "audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "audit.html").write_text("<html><meta charset='utf-8'><body><pre>" + html.escape("\n".join(md)) + "</pre></body></html>", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--library", required=True); p.add_argument("--benchmark"); p.add_argument("--gold")
    p.add_argument("--query-hits"); p.add_argument("--candidate-snapshots"); p.add_argument("--context")
    p.add_argument("--query-plan"); p.add_argument("--source-snapshot"); p.add_argument("--decision-log")
    p.add_argument("--deduplication-log"); p.add_argument("--run-log"); p.add_argument("--out", required=True)
    a = p.parse_args()
    ctx = json.load(open(a.context, encoding="utf-8")) if a.context else {}
    ctx.setdefault("library_path", a.library)
    ctx = resolve_thresholds(ctx)
    lib = load_items(a.library)
    cov = {"a1": benchmark(load_items(a.library), load_items(a.benchmark) if a.benchmark else []),
           "a2": a2(load_items(a.gold) if a.gold else None, load_items(a.query_hits) if a.query_hits else None),
           "a3": a3(load_snapshot(a.candidate_snapshots) if a.candidate_snapshots else {})}
    proc = stability(ctx); bal = balance(lib, ctx.get("standards", {}))
    tbal = topic_balance(ctx); cur = currency(ctx); rec = recency(lib, ctx)
    # F4: verify dedup-log exists, is parseable, and contains structured decisions.
    # dedup_log_ok only True when: structured sections exist AND all fuzzy/version candidates
    # have actual decisions (merge/retain_both/exclude/manual_review_required).
    # Without decisions → F4_version_decisions remains not_assessable or warning.
    dedup_log_ok = False
    dedup_log_depth = "missing"
    if a.deduplication_log:
        dp = pathlib.Path(a.deduplication_log)
        if dp.exists():
            try:
                data = json.loads(dp.read_text(encoding="utf-8"))
                has_exact = bool(data.get("exact_identifier_groups"))
                has_uncertain = bool(data.get("uncertain_title_year_candidates"))
                has_version = bool(data.get("possible_version_families"))
                if has_exact or has_uncertain or has_version:
                    uncertain = data.get("uncertain_title_year_candidates", [])
                    version_fams = data.get("possible_version_families", [])
                    pending = uncertain + version_fams
                    all_decided = all(
                        c.get("decision") in ("merge", "retain_both", "exclude", "manual_review_required")
                        for c in pending
                    ) if pending else True
                    dedup_log_depth = "structured_decisions" if all_decided else "structured_no_decisions"
                    # Only consider the log "ok" when decisions actually exist
                    dedup_log_ok = all_decided and pending
                else:
                    dedup_log_depth = "parseable_but_shallow"
            except (json.JSONDecodeError, OSError):
                dedup_log_depth = "unparseable"
    libh = health(lib, ctx.get("standards", {}), dedup_log_provided=dedup_log_ok, dedup_log_depth=dedup_log_depth)
    libh["dedup_log_depth"] = dedup_log_depth
    qual = quality(lib, ctx)
    # F1: verify run-log structure — requires query text, source, fields, date at minimum
    if a.run_log:
        rp = pathlib.Path(a.run_log)
        if rp.is_file():
            try:
                content = rp.read_text(encoding="utf-8")
                if content.strip():
                    data = json.loads(content)
                    queries = data.get("queries", data.get("query_log", []))
                    # Minimal schema: source, query, fields, date
                    # Preferred: filters, result_count, completion_status (check separately for depth)
                    REQUIRED = {"source", "query", "fields", "date"}
                    PREFERRED = {"filters", "result_count", "completion_status"}
                    has_valid = any(
                        isinstance(q, dict) and REQUIRED <= set(q.keys())
                        for q in (queries if isinstance(queries, list) else [])
                    ) if queries else False
                    has_preferred = any(
                        isinstance(q, dict) and PREFERRED <= set(q.keys())
                        for q in (queries if isinstance(queries, list) else [])
                    ) if queries else False
                    ctx["run_log_complete"] = has_valid
                    ctx["run_log_depth"] = "valid_full" if has_preferred else "valid" if has_valid else "shallow"
            except (OSError, json.JSONDecodeError):
                ctx["run_log_complete"] = False
                ctx["run_log_depth"] = "unparseable"
    # umbrella-specific A4/C4/F7 (requires libh to exist first)
    umb = umbrella_checks(lib, ctx, libh) if ctx.get("review_type") == "伞式综述" else {"a4": None, "c4": None, "f7": None}
    gt = dt.datetime.now(dt.timezone.utc).isoformat(); gts = gt[:19].replace("T", " ")
    rt = ctx.get("review_type", "未指定"); prf = ctx.get("profile", "未指定")
    bf = []
    if tbal.get("checks", {}).get("C1_topic_balance") == "fail": bf.append("C1 存在空主题")
    if libh.get("checks", {}).get("F4_exact_duplicates") == "fail": bf.append("F4 存在未处理重复")
    # F_metadata_composite 不在 21 子项 register 内，
    # 不作为阻断列入 summary——诊断在"各维度分析"F 段呈现，与 register 的 priority_actions 一致
    if libh.get("field_completeness", {}).get("abstractNote") is not None and libh["field_completeness"]["abstractNote"] < float(ctx.get("standards", {}).get("f_abstract_rate", 0.80)): bf.append("F2 摘要覆盖率不足")
    summary = f"评估完成（{gts}）。库规模 {libh.get('records','—')} 篇，综述类型 {rt}，工程领域 {prf}。"
    if bf: summary += f"\n\n**阻断项**：{'；'.join(bf)}。解决后方可声称库准备完毕。"
    else: summary += " 未检测到阻断项。"
    summary += f"\n\nA1 基准集召回 {_fmt_pct(cov['a1'].get('recall'))}（{_fmt_num(cov['a1'].get('matched'))}/{_fmt_num(cov['a1'].get('total'))}），"
    summary += f"A3 多源下界 {_fmt_num(cov['a3'].get('deduplicated_candidate_lower_bound'))} 篇，"
    summary += f"B 饱和度 {proc.get('verdict','—')}，C 主题平衡 {'含空主题' if 'empty_topic' in tbal.get('flags',[]) else '正常'}，"
    summary += f"D 近年占比 {_fmt_pct(rec.get('recent_share'))}，E h-core={_fmt_num(qual.get('h_core'))}，"
    summary += f"F 摘要覆盖 {_fmt_pct(libh.get('field_completeness',{}).get('abstractNote'))}。"
    summary += " 各维度不合成总分；\"不可评估\"不是失败。"
    # Umbrella disclaimer
    if rt == "伞式综述":
        umbrella_disclaimer = (
            "\n\n> ⚠️ **伞式综述方法学提示**：伞式综述有独立的方法学标准（AMSTAR-2、ROBIS、综述间重叠分析）。"
            "本评估报告沿用文献库准备度的通用框架，仅对综述层面的 A4（综述类型确认）/C4（综述间覆盖分布）/F7（质量评估就绪度）做初筛诊断。"
            "**本报告不能代替**：① AMSTAR-2 的 16 项逐条评分；② ROBIS 偏倚风险评估；③ 综述间结论冲突的实质分析。"
            "**强烈建议在完成文献库评估后，由领域专家对纳入综述进行独立的方法学质量审查。**"
        )
        summary += umbrella_disclaimer
    report = {"generated_at": gt, "standards": ctx.get("standards", {}), "context": ctx,
              "library_health": libh, "coverage": cov, "process": proc, "balance": bal,
              "topic_balance": tbal, "currency": cur, "recency": rec, "quality": qual,
              "umbrella": umb,
              "artifacts": artifacts({"query-plan": a.query_plan, "source-snapshot": a.source_snapshot,
                                      "decision-log": a.decision_log, "deduplication-log": a.deduplication_log,
                                      "run-log": a.run_log}),
              "summary": summary,
              "limitations": ["本报告中的各项阈值均为基于工程文献计量经验的参考值，旨在辅助识别可能的风险信号，不等于文献库质量的绝对标准。pass/warning/fail 是自动化诊断提示，不是质量裁决，所有结论均应结合具体研究问题和领域惯例做人工判断。",
                              "A3 下界不是 Recall；区间需另行声明模型假设。",
                              "主题平衡、版本等价性、研究设计和更正状态需人工或专门来源核验。",
                              "h-core 和 Tier-1 仅作诊断背景，不等于综述质量。",
                              "未提供的运行产物会明确标为缺失。"]}
    if rt == "伞式综述":
        report["limitations"].extend([
            "伞式综述专用子项 A4（综述类型确认）基于标题关键词自动分类，仅初筛——需人工抽样核验 review/survey 论文的实际类型。",
            "伞式综述专用子项 C4 的 CCA 计算需要纳入综述的原始研究引用列表，超出自动范围；方法类型分布为标题 keyword 推断，不做最终分类。",
            "伞式综述专用子项 F7 仅报告就绪度——AMSTAR-2 的 16 项评分和 ROBIS 偏倚风险评估需人工或专用工具完成，本报告不代替实际质量评估。"
        ])
    write(report, pathlib.Path(a.out),
          artifact_paths={"library": a.library,
                         "benchmark": a.benchmark,
                         "gold": a.gold,
                         "query-hits": a.query_hits,
                         "candidate-snapshots": a.candidate_snapshots,
                         "query-plan": a.query_plan,
                         "source-snapshot": a.source_snapshot,
                         "decision-log": a.decision_log,
                         "deduplication-log": a.deduplication_log,
                         "run-log": a.run_log,
                         "context": a.context})

if __name__ == "__main__": main()
