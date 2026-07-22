#!/usr/bin/env python3
"""Literature-library evaluation report generator (model X: A-F six dimensions, 22 sub-items; umbrella adds A4/C5/F7 → 25)."""
import argparse, datetime as dt, hashlib, html, json, pathlib, re, shutil, sys
from collections import Counter
from math import log

try:
    from evidence_isolation import inspect_manifest
    from stable_ids import doi as canonical_doi, stable_ids
except ImportError:  # pragma: no cover - package-style fallback
    from scripts.evidence_isolation import inspect_manifest
    from scripts.stable_ids import doi as canonical_doi, stable_ids

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

# English → Chinese review type normalization
REVIEW_TYPE_MAP = {
    "narrative": "叙事综述",
    "systematic": "系统综述",
    "scoping": "范围综述",
    "rapid": "快速综述",
    "umbrella": "伞式综述",
}

def normalize_review_type(rt):
    """Normalize review type to Chinese enum. Returns Chinese value if already Chinese,
    maps English canonical names, or returns as-is with a warning for unknown values."""
    if not rt:
        return rt
    if rt in REVIEW_THRESHOLDS:
        return rt
    mapped = REVIEW_TYPE_MAP.get(rt.lower() if isinstance(rt, str) else rt)
    if mapped:
        return mapped
    # Unknown value — return as-is (schema validation catches these at config load)
    return rt

def resolve_thresholds(context):
    """Merge review-type defaults into context.standards (user overrides win)."""
    ctx = dict(context) if context else {}
    s = dict(ctx.get("standards", {}))
    rt = normalize_review_type(ctx.get("review_type", ""))
    ctx["review_type"] = rt  # normalize in-place so umbrella detection works
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
                 "topic_min_sources": 2, "topic_source_top_share_warning": 0.80,
                 "viewpoint_min_classified_fraction": 0.50,
                 "viewpoint_max_dominant_share": 0.90,
                 "viewpoint_min_counterevidence": 3}.items():
        if k not in s: s[k] = v
    ctx["standards"] = s
    return ctx

def doi(value):
    return canonical_doi(value)

def ids(row):
    return stable_ids(row)

def title(row):
    return re.sub(r"[^\w]", "", str(row.get("title") or "").casefold())

def load_items(path):
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("items", [])

def load_snapshot(path):
    with open(path, encoding="utf-8-sig") as fh:
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
    """A2 recall at the item level — same logic as A1 benchmark().

    Each gold item that shares any stable ID with any hit => matched.
    This avoids double-counting when one item has multiple identifiers.
    """
    if gold is None or hits is None:
        return {"status": "not_assessable", "recall": None, "note": "Supply both gold set and executed query-hit snapshot."}
    hit_ids = set().union(*(ids(x) for x in hits if isinstance(x, dict)))
    gold_items_with_ids = [g for g in gold if isinstance(g, dict) and ids(g)]
    total = len(gold_items_with_ids)
    if total == 0:
        return {"status": "not_assessable", "recall": None,
                "note": "Gold set lacks usable stable identifiers (DOI, OpenAlex, arXiv, PMID, or PMCID)."}
    matched = sum(1 for g in gold_items_with_ids if ids(g) & hit_ids)
    return {"status": "measured", "total": total, "matched": matched,
            "recall": round(matched / total, 3),
            "missing_ids": sorted(set().union(*(ids(g) for g in gold_items_with_ids if not (ids(g) & hit_ids)))),
            "note": "Item-level match (any shared stable ID → matched). Consistent with A1 method. An executed zero-result query is measured recall 0, not unavailable evidence."}

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


def load_evidence_manifest(path):
    if not path:
        return None
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None

def health(library, standards=None, dedup_log_provided=False, dedup_log_depth="missing", decision_log_provided=False, taxonomy=None):
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
    decision_links = sum(bool(x.get("decision") or x.get("inclusion_reason") or x.get("screening_status")) for x in library)
    flags = sum(bool(x.get("retracted") or x.get("corrected") or x.get("expression_of_concern")) for x in library)
    core_min = float(standards.get("f_core_metadata_rate", 0.95))
    abstract_min = float(standards.get("f_abstract_rate", 0.80))
    access_min = float(standards.get("f_access_rate", 0.80))
    provenance_min = float(standards.get("f_provenance_rate", 0.95))
    has_fuzzy_dupes = sum(v > 1 for v in title_year.values()) > 0
    f4_version = "pass" if dedup_log_provided else "not_assessable"
    # F5: decision-log provides screening trail; without it provenance-rate-only is a lower bound
    provenance_rate = provenance / n if n else None
    if decision_log_provided:
        f5_verdict = "pass" if n and provenance_rate and provenance_rate >= provenance_min else "fail"
        f5_note = "来源谱系 + 纳入/排除决定均可追溯"
        # ── Descriptive listing risk diagnostic ──
        if not taxonomy:
            f5_note += '。未提供主题分类（taxonomy）——库的纳入决定未按主题分组，后续综述存在"逐篇流水账"风险（descriptive listing），建议引入主题框架以支撑批判性综合'
    else:
        # provenance-only → not enough for "pass"
        f5_verdict = "warning" if n and provenance_rate and provenance_rate >= provenance_min else "fail"
        f5_note = f"仅来源字段可追溯（谱系率 {round(provenance_rate,3) if provenance_rate else '—'}）。未提供 decision-log——纳入/排除理由不可追溯。"
        if decision_links and n and decision_links / n >= 0.5:
            f5_note += f" 库内有 {decision_links}/{n} 条含 decision/screening_status 字段——可作为部分证据。"
        if not taxonomy:
            f5_note += '。未提供主题分类（taxonomy）——库的纳入决定未按主题分组，后续综述存在"逐篇流水账"风险（descriptive listing），建议引入主题框架以支撑批判性综合'
    checks = {"F_metadata_composite": "pass" if all(fields.get(k) is not None and fields[k] >= core_min
              for k in ("title", "creators", "date", "publicationTitle", "DOI"))
              and (fields.get("abstractNote") is None or fields["abstractNote"] >= abstract_min) else "fail",
              "F4_exact_duplicates": "pass" if not sum(v > 1 for v in dois.values()) else "fail",
              "F4_version_decisions": f4_version,
              "F3_access": "pass" if n and access_union / n >= access_min else "warning",
              "F5_provenance": f5_verdict if n and provenance_rate and provenance_rate >= provenance_min else ("fail" if n else "not_assessable"),
              "F6_corrections": "not_assessable"}
    return {"status": "measured" if n else "not_assessable", "records": n, "field_completeness": fields, "checks": checks,
            "duplicate_doi_groups": sum(v > 1 for v in dois.values()),
            "duplicate_title_year_groups": sum(v > 1 for v in title_year.values()),
            "attachment_rate": round(has_attachment / n, 3) if n else None,
            "open_link_rate": round(has_oa / n, 3) if n else None,
            "access_union_rate": round(access_union / n, 3) if n else None,
            "provenance_rate": round(provenance / n, 3) if n else None, "correction_flag_records": flags,
            "decision_link_rate": round(decision_links / n, 3) if n else None,
            "decision_log_provided": decision_log_provided,
            "dedup_log_depth": dedup_log_depth,
            "f5_note": f5_note,
            "note": "F3=v 附件或开放链接任一可用的记录比例；两率分列展示以避免重复计数。版本族等价性、访问权限和更正状态需专项来源核验。F5 需 decision-log 以追溯纳入/排除理由。"}

def stability(context):
    rounds = context.get("search_rounds", [])
    # Only rounds with screened_complete or explicit screening bypass count for convergence.
    # discovery_only rounds are excluded from GGR/DRR verdicts — candidates != inclusions.
    screened_rounds = [x for x in rounds if x.get("screening_status") != "discovery_only"]
    any_discovery_only = any(x.get("screening_status") == "discovery_only" for x in rounds)
    any_automated_screening = any(x.get("screening_status") == "automated-screening" for x in rounds)
    rates = [round((x.get("screened_inclusions", 0) if x.get("screening_status") == "automated-screening"
                    else x.get("included_high", 0)) / x["core_before"], 4)
             for x in screened_rounds if isinstance(x.get("core_before"), (int, float)) and x["core_before"] > 0]
    discovery_candidates_count = sum(x.get("discovery_candidates", 0) for x in rounds
                                     if x.get("screening_status") == "discovery_only")
    pathway_records = context.get("independent_pathways") or context.get("source_marginal_yields", [])
    paths = set(context.get("planned_pathways", []))
    done = {x.get("pathway") for x in pathway_records if x.get("completed")}
    if not done:
        done = {x.get("pathway") for x in rounds if x.get("completed")}
    complete = round(len(paths & done) / len(paths), 3) if paths else None
    standards = context.get("standards", {})
    threshold = float(standards.get("b_ggr_threshold", 0.02))
    yield_threshold = float(standards.get("b_drr_threshold", 0.05))
    # Only human-screened yields can contribute to a final DRR conclusion.
    yields = [x.get("yield") for x in pathway_records
              if isinstance(x.get("yield"), (int, float))
              and x.get("screening_status") not in ("discovery_only", "automated-screening")]
    automated_pathways = [x for x in pathway_records
                           if x.get("screening_status") == "automated-screening"
                           and isinstance(x.get("yield"), (int, float))]
    iv_passed = context.get("independent_validation_passed")
    evidence_integrity = context.get("evidence_integrity", {})
    run_log = context.get("run_log_complete")
    run_log_depth = context.get("run_log_depth", "missing")
    has_enough_screened = len(screened_rounds) >= 2
    validation_independent = not evidence_integrity.get("a2_b3_shared_validation", False)
    converged = (has_enough_screened and all(x < threshold for x in rates[-2:]) and complete == 1.0
                 and iv_passed is True and validation_independent
                 and bool(yields) and all(x < yield_threshold for x in yields))
    # Evidence tier and result are separate.  Automated screening may produce a
    # direct threshold result, but source-level routes never substitute for the
    # independent pathways required by B2.
    if any_discovery_only and not has_enough_screened:
        b1_verdict = "not_assessable"
        b2_verdict = "not_assessable"
    else:
        b1_verdict = "pass" if len(rates) >= 2 and all(x < threshold for x in rates[-2:]) else ("not_assessable" if len(rates) < 2 else "fail")
        b2_verdict = ("warning" if any_automated_screening and len(automated_pathways) >= 2
                      else "pass" if yields and all(x < yield_threshold for x in yields)
                      else "not_assessable" if not yields else "fail")
    # In the automated tier, a shared A3 snapshot does not erase the displayed
    # source-level diagnostic; it does prohibit using it as evidence of final
    # DRR convergence.  In measured mode the same overlap remains disqualifying.
    if evidence_integrity.get("a3_b2_overlap") and not any_automated_screening:
        b2_verdict = "not_assessable"
    checks = {"B1_ggr": b1_verdict,
              "B3_pathway_completion": "pass" if complete == 1.0 else "not_assessable" if complete is None else "fail",
              "B2_drr": b2_verdict,
              "F1_query_traceability": "pass" if run_log is True
              else "fail" if run_log is False else "not_assessable",
              "B3_independent_validation": "not_assessable" if evidence_integrity.get("a2_b3_shared_validation")
              else ("pass" if iv_passed is True else "fail" if iv_passed is False else "not_assessable")}
    result = {"status": "discovery_only" if any_discovery_only and not has_enough_screened
              else "automated-screening" if any_automated_screening
              else ("measured" if rounds else "not_assessable"),
              "high_confidence_new_rates": rates, "discovery_candidates_total": discovery_candidates_count,
              "pathway_completion": complete, "source_marginal_yields": yields,
              "automated_pathway_yields": automated_pathways,
              "thresholds": {"new_rate": threshold, "marginal_yield": yield_threshold}, "checks": checks,
              "independent_validation_passed": iv_passed,
              "verdict": "趋稳" if converged and all(x == "pass" for x in checks.values())
              else "不可证明" if "not_assessable" in checks.values() else "未稳定"}
    if any_discovery_only and not has_enough_screened:
        result["note"] = "B 维处于候选发现阶段——discovery candidates 不等于纳入项。GGR/DRR 不可评估直至完成筛选。"
    elif any_automated_screening:
        result["note"] = "B1 为 AI 自动初筛后的首轮增长率：可用于定位仍在扩张的检索策略，但不是人工确认的饱和结论；B2/B3 仍需独立路径和验证。"
    if evidence_integrity.get("a3_b2_overlap"):
        result["note"] = (result.get("note", "") + " A3 快照与 B2 路径共享证据来源；B2 不作独立边际收益结论。 ").strip()
    if evidence_integrity.get("a2_b3_shared_validation"):
        result["note"] = (result.get("note", "") + " A2 与 B3 复用验证集；B3 独立验证不可证明。 ").strip()
    return result

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

    # ── Author concentration (diagnostic only, not a separate indicator) ──
    author_counts = Counter()
    for item in library:
        creators = item.get("creators", [])
        if isinstance(creators, list):
            for c in creators:
                if isinstance(c, dict):
                    name = (c.get("name") or f"{c.get('firstName','')} {c.get('lastName','')}").strip()
                elif isinstance(c, str):
                    name = c.strip()
                else:
                    continue
                if name:
                    author_counts[name] += 1
    author_values = [v for v in author_counts.values() if v >= 2]  # 只统计出现≥2次的作者
    author_n = sum(author_values); author_k = len(author_values)
    author_concentration = None
    if author_n and author_k >= 3:
        top_author_share = max(author_values) / author_n if author_n else None
        # Author Gini
        author_gini = sum(abs(a - b) for a in author_values for b in author_values) / (2 * author_k * author_n)
        author_concentration = {
            "unique_authors": len(author_counts),
            "authors_with_2plus": author_k,
            "top_author": author_counts.most_common(1)[0][0] if author_counts else "",
            "top_author_count": author_counts.most_common(1)[0][1] if author_counts else 0,
            "top_author_share": round(top_author_share, 3) if top_author_share else None,
            "author_gini": round(author_gini, 3),
        }
        # 单一作者/课题组统治：top author share > 0.25 时提示
        if top_author_share and top_author_share > 0.25:
            author_concentration["note"] = (
                f"单一作者 '{author_counts.most_common(1)[0][0]}' 占文献库 {top_author_share*100:.1f}%——"
                "可能存在课题组偏倚，建议检查是否过度依赖单一研究群体的视角。"
            )

    return {"status": "measured", "counts": dict(counts), "top_source_share": round(max(values) / n, 3),
            "cv": round(cv, 3), "gini": round(gini, 3), "shannon": round(entropy, 3),
            "normalized_shannon": round(normalized_entropy, 3), "limits": limits, "flags": flags,
            "high_shannon_note": high_shannon_note,
            "author_concentration": author_concentration,
            "checks": {"C2_source_balance": "warning" if flags else "pass"}}

def topic_balance(context):
    standards = context.get("standards", {})
    raw = context.get("taxonomy", [])
    # ── Validate taxonomy entries before processing ──
    taxonomy_errors = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            taxonomy_errors.append(f"taxonomy[{i}]: not an object")
            continue
        if not isinstance(r.get("high_confidence_records"), (int, float)):
            taxonomy_errors.append(
                f"taxonomy[{i}] '{r.get('name','?')}': "
                "high_confidence_records must be numeric, got "
                f"{type(r.get('high_confidence_records')).__name__}"
            )
        elif isinstance(r.get("high_confidence_records"), (int, float)) and r["high_confidence_records"] < 0:
            taxonomy_errors.append(
                f"taxonomy[{i}] '{r.get('name','?')}': "
                f"high_confidence_records cannot be negative, got {r['high_confidence_records']}"
            )
        if r.get("target_share") is not None:
            if not isinstance(r["target_share"], (int, float)):
                taxonomy_errors.append(
                    f"taxonomy[{i}] '{r.get('name','?')}': "
                    "target_share must be numeric"
                )
            elif r["target_share"] < 0:
                taxonomy_errors.append(
                    f"taxonomy[{i}] '{r.get('name','?')}': "
                    f"target_share cannot be negative, got {r['target_share']}"
                )
    topics = [{"name": r.get("name", "unnamed"), "expected": r.get("expected", True),
               "records": r.get("high_confidence_records"), "target_share": r.get("target_share"),
               "opposing_viewpoint": r.get("opposing_viewpoint")}
              for r in raw if isinstance(r, dict) and r.get("expected", True)]
    values = [int(x["records"] or 0) for x in topics]
    if taxonomy_errors:
        err_block = "; ".join(taxonomy_errors)
        return {"status": "measured" if topics else "not_assessable",
                "topic_counts": {x["name"]: 0 for x in topics},
                "top_topic_share": None, "cv": None, "gini": None, "normalized_shannon": None,
                "target_tvd": None, "flags": ["input_validation_error"],
                "cross_source_flags": [],
                "cross_reconciliation_errors": taxonomy_errors,
                "checks": {"C1_topic_balance": "not_assessable",
                           "C3_topic_source_balance": "not_assessable"},
                "note": f"Taxonomy validation failed: {err_block}"}
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
    cross_reconciliation_errors = list(taxonomy_errors)  # carry forward taxonomy validation errors
    if cross:
        # Validate cross table values
        for tname, counts in cross.items():
            if not isinstance(counts, dict):
                continue
            for src, cnt in counts.items():
                if not isinstance(cnt, (int, float)):
                    cross_reconciliation_errors.append(
                        f"{tname}/{src}: 来源计数不是数字 (got {type(cnt).__name__})"
                    )
                elif cnt < 0:
                    cross_reconciliation_errors.append(
                        f"{tname}/{src}: 来源计数不可为负 ({cnt})"
                    )
        for topic in topics:
            tname = topic["name"]
            counts = cross.get(tname, {})
            if not isinstance(counts, dict):
                cross_flags.append(tname)
                if f"{tname}: topic_source_counts 值不是字典" not in cross_reconciliation_errors:
                    cross_reconciliation_errors.append(f"{tname}: topic_source_counts 值不是字典")
                continue
            total = sum(counts.values())
            taxonomy_records = int(topic["records"] or 0)
            if total == 0:
                cross_flags.append(tname)
            else:
                if total != taxonomy_records:
                    cross_reconciliation_errors.append(
                        f"{tname}: 来源计数合计 ({total}) ≠ taxonomy records ({taxonomy_records})——"
                        "交叉表覆盖不完整，C3 判断可能不可靠"
                    )
                too_few_sources = len(counts) < int(standards.get("topic_min_sources", 2))
                high_source_share = max(counts.values()) / total > float(standards.get("topic_source_top_share_warning", .80))
                if too_few_sources or high_source_share:
                    cross_flags.append(tname)
        # When most topics have reconciliation errors, C3 is not assessable
        if cross_reconciliation_errors and len(cross_reconciliation_errors) >= len(topics) * 0.5:
            cross_flags = [t["name"] for t in topics]  # all flagged

    # ── Contrasting viewpoints diagnostic ──
    opposing_warning = None
    has_opposing = [t for t in topics if t.get("opposing_viewpoint")]
    if has_opposing:
        opposing_names = [t["name"] for t in has_opposing]
        opposing_warning = (
            f"已标记 {len(opposing_names)} 个含对立/竞争观点的主题：{'、'.join(opposing_names)}。"
            "以下 C1 平衡仅反映数量分布——即使数值均衡，也应检查是否同时覆盖了议题的正反证据，"
            "避免 cherry-picking（只收录支持假设的文献）。这是对 C1 均衡判定的定性补充。"
        )

    return {"status": "measured", "topic_counts": {x["name"]: v for x, v in zip(topics, values)},
            "top_topic_share": round(max(values) / n, 3), "cv": round(cv, 3), "gini": round(gini, 3),
            "normalized_shannon": round(hn, 3), "target_tvd": round(tvd, 3) if tvd is not None else None,
            "flags": flags, "cross_source_flags": cross_flags,
            "cross_reconciliation_errors": cross_reconciliation_errors,
            "opposing_viewpoint_warning": opposing_warning,
            "checks": {"C1_topic_balance": "fail" if "empty_topic" in flags else "warning" if flags else "pass",
                       "C3_topic_source_balance": ("not_assessable" if cross_reconciliation_errors
                                                    else "warning" if cross_flags
                                                    else "pass" if cross
                                                    else "not_assessable")}}

def viewpoint_balance(library, context):
    """Check whether a contested focal claim is represented from more than one side.

    This deliberately does not infer stance from generic positive/negative wording in
    titles: without an explicit claim that would manufacture a misleading result.
    Agents may supply ``viewpoint_framework`` after title/abstract classification;
    existing record-level stance labels are also accepted as a traceable fallback.
    """
    standards = context.get("standards", {})
    framework = context.get("viewpoint_framework", {})
    framework = framework if isinstance(framework, dict) else {}
    raw_counts = framework.get("counts", {})
    raw_counts = raw_counts if isinstance(raw_counts, dict) else {}
    aliases = {
        "supports_claim": ("supports_claim", "support", "supports", "positive", "for"),
        "challenges_claim": ("challenges_claim", "challenge", "challenges", "opposes", "negative", "against", "refutes"),
        "mixed_or_conditional": ("mixed_or_conditional", "mixed", "conditional", "inconclusive"),
        "unclassified": ("unclassified",),
    }
    counts = {}
    for target, names in aliases.items():
        value = next((raw_counts[name] for name in names if isinstance(raw_counts.get(name), (int, float))), None)
        counts[target] = max(0, int(value)) if value is not None else 0

    used_record_labels = False
    assessed_size = framework.get("records_assessed", len(library))
    assessed_size = int(assessed_size) if isinstance(assessed_size, (int, float)) and assessed_size >= 0 else len(library)
    if not any(counts.values()):
        for item in library:
            raw = item.get("viewpoint") or item.get("stance") or item.get("claim_direction")
            if not isinstance(raw, str):
                counts["unclassified"] += 1
                continue
            label = raw.strip().casefold().replace(" ", "_")
            matched = next((target for target, names in aliases.items() if label in names), "unclassified")
            counts[matched] += 1
            used_record_labels = True
        assessed_size = len(library)
    elif counts["unclassified"] == 0 and assessed_size:
        counts["unclassified"] = max(0, assessed_size - sum(counts.values()))

    classified = counts["supports_claim"] + counts["challenges_claim"] + counts["mixed_or_conditional"]
    total = classified + counts["unclassified"]
    classified_fraction = classified / total if total else 0.0
    directional = counts["supports_claim"] + counts["challenges_claim"]
    dominant_share = (max(counts["supports_claim"], counts["challenges_claim"]) / directional
                      if directional else None)
    min_fraction = float(standards.get("viewpoint_min_classified_fraction", .50))
    max_dominant = float(standards.get("viewpoint_max_dominant_share", .90))
    min_counter = int(standards.get("viewpoint_min_counterevidence", 3))
    claim = str(framework.get("claim") or "").strip()
    contested = framework.get("contested", True) is not False
    method = str(framework.get("classification_method") or "").strip()
    sample_verified = framework.get("sample_verified", framework.get("classification_sample_verified"))
    automatic = (not framework or not method or "ai" in method.casefold() or "自动" in method)
    if used_record_labels and not method:
        method = "库内 stance/viewpoint 标签汇总"
        automatic = False

    flags = []
    if not claim:
        flags.append("missing_focal_claim")
    if sum(counts.values()) > assessed_size:
        flags.append("count_exceeds_assessed")
    if classified_fraction < min_fraction:
        flags.append("insufficient_classification")
    if contested and directional == 0 and classified_fraction >= min_fraction:
        flags.append("no_directional_evidence")
    elif contested and directional and dominant_share is not None:
        minority = min(counts["supports_claim"], counts["challenges_claim"])
        if dominant_share > max_dominant or minority < min_counter:
            flags.append("one_sided_evidence")

    # A skew is a warning, not a failure: the underlying research may genuinely
    # converge. The required action is to search deliberately for counter-evidence.
    verdict = "warning" if flags else "pass"
    status = "automated-screening" if automatic else "measured"
    note = ("观点分类计数超过声明的被分类记录数；请核对去重范围和未分类计数。"
            if "count_exceeds_assessed" in flags else
            "未建立可审计的中心主张与立场分类；首轮应由 AI 对题名/摘要建立候选分类，并抽样核验。"
            if "missing_focal_claim" in flags else
            "立场分类覆盖不足；不能据此判断观点是否单边。"
            if "insufficient_classification" in flags else
            "支持与质疑证据失衡；应以反向术语、反例和失败条件补检。"
            if "one_sided_evidence" in flags else
            "已覆盖支持、质疑及条件性证据；仍应在写作中呈现适用边界。")
    return {"status": status, "claim": claim, "contested": contested, "counts": counts,
            "classified": classified, "total": total, "records_assessed": assessed_size,
            "classified_fraction": round(classified_fraction, 3),
            "dominant_share": round(dominant_share, 3) if dominant_share is not None else None,
            "thresholds": {"min_classified_fraction": min_fraction, "max_dominant_share": max_dominant,
                           "min_counterevidence": min_counter},
            "classification_method": method or "未记录", "sample_verified": sample_verified,
            "flags": flags, "note": note, "checks": {"C4_viewpoint_balance": verdict}}

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
    """Run umbrella-review-specific A4 / C5 / F7 checks. Keeps legacy c4 key internally."""
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

    # C5 — review coverage distribution (legacy internal key remains c4)
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
    configured_tiers = {str(x).strip().lower() for x in context.get("tier1_venues", [])}
    tiers = set(configured_tiers)
    aliases = context.get("tier1_venue_aliases", {})
    if isinstance(aliases, dict):
        for alias, canonical in aliases.items():
            tiers.update({str(alias).strip().lower(), str(canonical).strip().lower()})
    venues = [str(x.get("publicationTitle") or x.get("venue") or "").strip().lower() for x in library]
    tier_hits = sum(bool(v and v in tiers) for v in venues)
    rate = tier_hits / len(library) if library and tiers else None
    return {"status": "measured" if library else "not_assessable", "citation_records": len(citations),
            "citation_coverage_rate": round(len(citations) / len(library), 3) if library else None,
            "h_core": h if citations else None, "tier1_venues_configured": len(configured_tiers),
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

    integrity = ctx.get("evidence_integrity", {})
    if integrity.get("manifest_present"):
        lines.append("\n**证据隔离审计**：" + integrity.get("status", "not_assessable"))
        if integrity.get("a2_validation_independent") is False:
            lines.append("⚠ A2 验证集存在查询泄漏或开发集重叠，A2 已降级为 estimated。")
        if integrity.get("a2_b3_shared_validation"):
            lines.append("⚠ A2 与 B3 复用验证集，B3 独立验证不可证明。")
        if integrity.get("a3_b2_overlap"):
            lines.append("⚠ A3 多源快照与 B2 路径共享来源，B2 不作独立边际收益结论。")
        for warning in integrity.get("warnings", []):
            lines.append(f"- {warning}")

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
    # ── Search iteration summary ──
    iterations = ctx.get("search_iterations", [])
    if iterations:
        lines.append(f'\n**检索式迭代**：共 {len(iterations)} 轮（详见下方"检索迭代过程"节）。')
        best_dev = max((it.get("results", {}).get("dev_recall", 0) or 0) for it in iterations)
        best_val = max((it.get("results", {}).get("validation_recall", 0) or 0) for it in iterations)
        lines.append(f"最佳 dev_recall={best_dev:.3f}，最佳 validation_recall={best_val:.3f}。")
        indep_pathways = ctx.get("independent_pathways", [])
        if indep_pathways:
            pw_names = [p.get("pathway_id", p.get("type", "?")) for p in indep_pathways]
            lines.append(f"独立检索路径：{'、'.join(pw_names)}（宽/中/窄检索式不计入独立路径）。")
    lines.append(f"\n**证据状态**：实测=可复跑记录；估计=基于假设的区间或抽样；自动初筛=规则判定未人工核验；不可评估=缺少必要输入。")
    return "\n".join(lines)

def _search_iteration_section(report):
    """Generate the search strategy and iteration section.

    It renders for a first-round search record as well as a full iteration log. This
    keeps a user-provided q0 visible even when query refinement has not started.
    """
    ctx = report.get("context", {})
    iterations = ctx.get("search_iterations", [])
    versions = ctx.get("search_query_versions", [])
    if not isinstance(versions, list):
        versions = []
    if not versions:
        legacy_queries = ctx.get("queries", [])
        if isinstance(legacy_queries, list):
            versions = [dict(query, query_id=query.get("query_id") or f"q{index}")
                        for index, query in enumerate(legacy_queries)
                        if isinstance(query, dict) and query.get("query")]
        if not versions and isinstance(ctx.get("query_plan"), dict):
            versions = [{"query_id": f"q{index}", "origin": "未记录", "change_type": "initial",
                         "source": source, "query": query}
                        for index, (source, query) in enumerate(ctx["query_plan"].items())]
    initial_query = ctx.get("initial_query") or ctx.get("user_query")
    has_legacy_query = bool(ctx.get("queries") or ctx.get("query_plan"))
    if not iterations and not versions and not initial_query and not has_legacy_query:
        return ""

    lines = ["## 检索策略与迭代过程\n"]
    lines.append("本节保留检索式的起点、每轮原子修改、执行来源和结果；它用于复核策略，不把命中数本身当作检索充分性的证明。\n")

    # ── Query origin and version history ──
    if versions or initial_query:
        lines.append("### 检索式起点与版本\n")
        lines.append("| 版本 | 起点 | 改动类型 | 执行来源 | 日期 | 命中 | 状态 | 检索式 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        origin_labels = {"user_provided": "用户提供", "ai_generated": "AI 生成", "agent_refined": "AI 原子迭代"}
        rows = versions or [{"query_id": "q0", "origin": ctx.get("search_initial_query_origin", "user_provided"),
                             "query": initial_query, "change_type": "initial"}]
        for version in rows:
            if not isinstance(version, dict):
                continue
            query = str(version.get("query", "—")).replace("\n", " ").replace("|", "\\|")
            query = query.replace("`", "\\`")
            vid = version.get("query_id") or version.get("label") or "—"
            origin = origin_labels.get(version.get("origin"), version.get("origin") or "未记录")
            change = version.get("change_type") or "initial"
            source = version.get("source") or version.get("database") or "未记录"
            date = version.get("execution_date") or version.get("date") or "未记录"
            hits = version.get("hits", "—")
            status = version.get("status", "已记录")
            lines.append(f"| {vid} | {origin} | {change} | {source} | {date} | {hits} | {status} | `{query}` |")
        lines.append("")
        if ctx.get("search_initial_query_origin") == "user_provided":
            lines.append("q0 为用户提供的原始检索式；后续版本应仅在此基础上进行可解释的原子改动。\n")

        syntax_map = ctx.get("source_syntax_map", {})
        if isinstance(syntax_map, dict) and syntax_map:
            lines.append("### 来源与查询映射\n")
            lines.append("| 来源 | 执行映射 |")
            lines.append("| --- | --- |")
            for source, mapping in syntax_map.items():
                mapping_text = str(mapping).replace("|", "\\|")
                lines.append(f"| {source} | {mapping_text} |")
            lines.append("")

        dev_recall = ctx.get("_search_meta_dev_recall")
        val_recall = ctx.get("_search_meta_val_recall")
        if dev_recall is not None or val_recall is not None:
            dev_total = ctx.get("_search_meta_dev_total", "—")
            val_total = ctx.get("_search_meta_val_total", "—")
            val_source = ctx.get("search_validation_source") or "未提供独立验证集"
            dev_text = f"{float(dev_recall):.3f}（n={dev_total}）" if dev_recall is not None else "未记录"
            val_text = f"{float(val_recall):.3f}（n={val_total}）" if val_recall is not None else "未记录"
            lines.append(f"首轮诊断：dev_recall={dev_text}；validation_recall={val_text}；验证来源：{val_source}。\n")
            if isinstance(val_total, int) and val_total < 15:
                lines.append("⚠️ 留出验证集少于 15 篇，首轮 A2 的误差较大；应扩大候选锚点池后复评。\n")

    if not iterations:
        lines.append("### 过程状态\n")
        lines.append("当前仅记录了首轮检索/诊断，尚未提供逐轮优化日志。因此报告可以展示 q0 的执行情况，"
                     "但不能据此声称检索式已经完成优化或达到 A2 停止条件。\n")
        return "\n".join(lines)

    # ── PICO decomposition ──
    pico = ctx.get("search_decomposition", {})
    if pico:
        obj = pico.get("object", {}).get("term", "—")
        tech = pico.get("technology", {}).get("term", "—")
        perf = pico.get("performance", {}).get("term", "—")
        ctxt = pico.get("context", {}).get("term", "—")
        lines.append("### 工程 PICO 分解\n")
        lines.append("| 要素 | 提取 |")
        lines.append("| --- | --- |")
        lines.append(f"| 对象/系统 | {obj} |")
        lines.append(f"| 技术/方法 | {tech} |")
        lines.append(f"| 性能/指标 | {perf} |")
        lines.append(f"| 工况/场景 | {ctxt} |")
        supps = pico.get("supplements", [])
        if supps:
            for s in supps:
                lines.append(f"| 补充：{s.get('category','')} | {s.get('term','')} |")
        lines.append("")

    # ── Evidence sets ──
    gold_meta = ctx.get("gold_set_metadata", {})
    dev_size = len(ctx.get("dev_set", [])) or gold_meta.get("dev_set_size", 0)
    val_size = len(ctx.get("validation_set", [])) or gold_meta.get("validation_set_size", 0)
    has_indep_val = bool(val_size)
    if dev_size or val_size:
        lines.append("### 证据集\n")
        lines.append(f"- **开发集**（用于迭代反馈）：{dev_size} 篇")
        if has_indep_val:
            lines.append(f"- **独立验证集**（仅用于最终 A2 判定）：{val_size} 篇")
            overlap_ok = gold_meta.get("dev_validation_overlap_check")
            lines.append(f"- 开发集与验证集无重叠：{'✅ 已校验' if overlap_ok else '⚠ 未校验'}")
        else:
            lines.append("- **独立验证集**：未提供——A2 证据状态降级为 `estimated`（开发集=验证集复用）")
        lines.append("")

    # ── Iteration overview ──
    n_iter = len(iterations)
    last = iterations[-1]
    change_types = Counter(it.get("change_type", "?") for it in iterations)
    best_dev = max((it.get("results", {}).get("dev_recall", 0) or 0) for it in iterations)
    best_val = max((it.get("results", {}).get("validation_recall", 0) or 0) for it in iterations)
    total_disc = sum(it.get("results", {}).get("discovery_candidates", 0) or 0 for it in iterations)

    ct_labels = {"initial": "初始检索式", "add_synonym": "加同义词", "add_abbreviation": "加缩写",
                 "modify_field": "改字段限制", "add_source": "新增数据库", "add_exclusion": "加排除条件",
                 "remove_low_yield": "移除低效词"}
    changes_desc = [f"{ct_labels.get(ct, ct)}×{count}" for ct, count in sorted(change_types.items())]

    lines.append("### 迭代概览\n")
    lines.append(f"共 **{n_iter}** 轮检索迭代，改动类型：{'、'.join(changes_desc)}。")
    lines.append(f"开发集最佳召回：**{best_dev:.3f}**；验证集最佳召回：**{best_val:.3f}**。")
    lines.append(f"累计发现候选文献：{total_disc} 篇（需筛选确认）。")
    d_labels = {"a2_stop": "A2 已停止（检索式足够好）", "b_stop": "B 已停止（不再发现新纳入文献）",
                "continue": "继续迭代", "max_iterations": "达到最大轮数"}
    lines.append(f"最终决策：**{d_labels.get(last.get('decision',''), last.get('decision','—'))}**。")
    lines.append("")

    # ── Comparison table ──
    lines.append("### 迭代比较表\n")
    lines.append("| 轮次 | 改动类型 | 改动说明 | 来源 | 总命中 | 去重 | dev_recall | val_recall | 候选 | 决策 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    for it in iterations:
        iid = it.get("iteration_id", "?")
        ct = it.get("change_type", "?")
        desc = str(it.get("change_description", "—"))[:55]
        src = str(it.get("change_source", "—"))[:35]
        res = it.get("results", {})
        th = str(res.get("total_hits", "—"))
        dh = str(res.get("deduplicated_hits", "—"))
        dr = f"{res['dev_recall']:.3f}" if res.get("dev_recall") is not None else "—"
        vr = f"{res['validation_recall']:.3f}" if res.get("validation_recall") is not None else "—"
        dc = str(res.get("discovery_candidates", "—"))
        decision = it.get("decision", "—")
        lines.append(f"| {iid} | {ct} | {desc} | {src} | {th} | {dh} | {dr} | {vr} | {dc} | {decision} |")

    lines.append("")
    automatic_bundle = ctx.get("automatic_first_round", {})
    if automatic_bundle:
        lines.append("### 首轮检索分析\n")
        lines.append("本轮比较的是 q0 与明确记录的单一改动；它用于暴露术语或字段选择可能造成的差异，"
                     "不是最终的“最佳检索式”选择。候选文献仍需筛选，且同一数据库内的版本变体不构成 B2 的独立路径。")
        if automatic_bundle.get("description"):
            lines.append(f"自动诊断范围：{automatic_bundle['description']}")
        id_diag = ctx.get("_search_meta_id_diagnostics", {})
        if id_diag:
            lines.append(f"稳定 ID 诊断：{id_diag.get('records_with_stable_id', 0)}/{id_diag.get('records_total', 0)} 条开发/验证记录可参与自动匹配；"
                         f"匹配 {id_diag.get('matched_records', 0)} 条，缺少稳定 ID {id_diag.get('records_without_stable_id', 0)} 条。")
        lines.append("")

    # ── Per-iteration details ──
    lines.append("### 各轮检索式详情\n")
    for it in iterations:
        iid = it.get("iteration_id", "?")
        ct = it.get("change_type", "?")
        desc = it.get("change_description", "—")
        src = it.get("change_source", "—")
        parent = it.get("parent_iteration")
        lines.append(f"#### {iid}（{ct}）\n")
        if parent:
            lines.append(f"基于 **{parent}**；来源：{src}")
        else:
            lines.append(f"初始检索式；来源：{src}")
        lines.append(f"\n改动：{desc}\n")
        queries = it.get("queries", {})
        for pw_id, pw_queries in queries.items():
            if isinstance(pw_queries, dict):
                for ql, qs in pw_queries.items():
                    lines.append(f"- `{pw_id}` / {ql}: `{qs}`")
            else:
                lines.append(f"- `{pw_id}`: `{pw_queries}`")
        lines.append("")

    # ── Independent pathways ──
    indep_pw = ctx.get("independent_pathways", [])
    if indep_pw:
        lines.append("### 独立路径贡献\n")
        lines.append("| 路径 ID | 类型 | 候选数 | 筛选确认 | 净新增 | 收益率 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for pw in indep_pw:
            pid = pw.get("pathway_id", "?")
            ptype = pw.get("type", "?")
            cand = str(pw.get("candidates", "—"))
            scr = str(pw.get("screened_high_confidence", "—"))
            new = str(pw.get("new_high_confidence", "—"))
            yld = f"{pw['yield']:.3f}" if pw.get("yield") is not None else "—"
            status = pw.get("screening_status", "—")
            lines.append(f"| {pid} | {ptype} | {cand} | {scr} | {new} | {yld} | {status} |")
        lines.append("")

    # ── Stop condition note ──
    lines.append("### 停止条件说明\n")
    lines.append("- **A2 停止**（检索式已优化到足够好）：独立验证集召回达标 + 连续两轮无实质改善，或无更多可加的术语/来源。")
    lines.append("- **B 停止**（不再发现新的纳入文献）：GGR 收敛 + DRR 收敛 + 所有计划路径完成 + 独立验证未发现漏项。")
    lines.append("- **A2 停止 ≠ B 停止**：即使检索式能找回所有已知文献，也不代表结果中不存在新的高相关文献。两者需同时满足才可声称检索充分。")
    lines.append("")

    return "\n".join(lines)


def _writing_readiness_section(report):
    """Give narrative-review workset advice without turning it into a seventh score."""
    ctx = report.get("context", {})
    review_type = normalize_review_type(ctx.get("review_type", ""))
    records = report.get("health", {}).get("records", 0) or 0
    workset = ctx.get("writing_workset", {})
    if not isinstance(workset, dict):
        workset = {}
    threshold = int(ctx.get("writing_workset_large_library_threshold", 100))
    lines = ["## 综合分析：写作可用性与工作集建议\n"]
    lines.append("本节是跨维度的写作准备度建议，不新增评分，也不改变 A–F 的任何判定。"
                 "A–F 表现良好说明证据库有价值；它不自动说明该库可以不经整理就直接写成一篇结构清晰的综述。\n")
    if review_type != "叙事综述":
        lines.append("当前综述类型不是叙事综述。仍可按需建立写作工作集；本次不对其规模作专门建议。")
        return "\n".join(lines)
    core_count = workset.get("core_count")
    roles = workset.get("role_counts")
    if isinstance(core_count, int) and core_count > 0:
        lines.append(f"已声明写作工作集：**{core_count}** 篇。它应从完整证据库中按论证角色取用，而不是替代完整库。")
        if isinstance(roles, dict) and roles:
            lines.append("角色分布：" + "；".join(f"{key} {value}" for key, value in roles.items()) + "。")
        missing = [key for key in ("topic", "priority", "review_role", "synthesis_note")
                   if key not in set(workset.get("fields_confirmed", []))]
        if missing:
            lines.append("建议补齐工作集字段：" + "、".join(missing) + "，以便按主题组织论证而非逐篇罗列。")
    elif records >= threshold:
        lines.append(f"库含 **{records}** 篇记录，已超过叙事综述的默认“大库”提示线（{threshold} 篇），但尚未声明写作工作集。")
        lines.append("建议保留完整库作为证据池，同时另建一个可回溯的工作集：按主题、论证角色、优先级和综合笔记挑选核心/对照/方法/争议/前沿文献；不要为了变小而删除原库。")
    else:
        lines.append(f"库含 {records} 篇记录。规模本身不构成问题；在起草前仍建议用主题、论证角色、优先级和综合笔记建立可回溯的写作工作集。")
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

def _dimension_narrative(report):
    c, p, b, t, vbal, d, q, h = (report["coverage"], report["process"], report["balance"],
                                 report["topic_balance"], report["viewpoint_balance"], report["recency"], report["quality"],
                                 report["library_health"])
    lines = []
    a1_r = _fmt_pct(c["a1"].get("recall")); a1_h = _fmt_num(c["a1"].get("matched")); a1_t = _fmt_num(c["a1"].get("total"))
    a3_lb = _fmt_num(c["a3"].get("deduplicated_candidate_lower_bound"))
    lines.append(f"**A 覆盖**：基准集召回 {a1_r}（{a1_h}/{a1_t}），多源候选下界至少 {a3_lb} 篇——'至少有多少篇相关文献存在'，不是漏了多少。")
    rates = p.get("high_confidence_new_rates", [])
    ggr = ", ".join(f"{r:.3f}" for r in rates[-2:]) if len(rates) >= 2 else "缺数据"
    lines.append(f"**B 饱和度**：最后两轮 GGR={ggr}（阈值<{p.get('thresholds',{}).get('new_rate','—')}）；{p.get('verdict','—')}。")
    flags = t.get("flags", []); n_topics = len(t.get("topic_counts", {}))
    auth_note = ""
    author_conc = b.get("author_concentration", {})
    if author_conc and author_conc.get("note"):
        auth_note = f" 作者集中度：top-author {author_conc.get('top_author_share','—')}（{author_conc.get('top_author','')}: {author_conc.get('top_author_count','')}篇）。"
    elif author_conc and author_conc.get("top_author_share") is not None:
        auth_note = f" 作者集中度：top-author {author_conc.get('top_author_share','—')}（{author_conc.get('top_author','')}: {author_conc.get('top_author_count','')}篇）。"
    vc = vbal.get("counts", {})
    lines.append(f"**C 平衡**：{n_topics} 个预期主题，{'含空主题' if 'empty_topic' in flags else '全部有文献'}；来源集中度 {b.get('top_source_share','—')}（CV={_fmt_num(b.get('cv'))} Gini={_fmt_num(b.get('gini'))}）；观点为支持 {vc.get('supports_claim', 0)} / 质疑 {vc.get('challenges_claim', 0)} / 条件性 {vc.get('mixed_or_conditional', 0)}。{auth_note}")
    lines.append(f"**D 时效**：近 {d.get('window_years','—')} 年占比 {_fmt_pct(d.get('recent_share'))}（{d.get('recent_records','—')}/{d.get('dated_records','—')} 标有日期）；预印本 {d.get('preprint_records','—')} 条。")
    lines.append(f"**E 学术影响与来源背景**：h-core={_fmt_num(q.get('h_core'))}（{q.get('citation_records','—')} 条引用）；Tier-1 {_fmt_pct(q.get('tier1_rate'))}（{q.get('tier1_venues_configured','—')} venue）。仅作背景信号，不等于研究质量——真正的研究质量评估应使用与研究设计匹配的批判性评价工具。")
    fc = h.get("field_completeness", {})
    lines.append(f"**F 可用性**：核心元数据 {_fmt_pct(fc.get('title'))}；摘要 {_fmt_pct(fc.get('abstractNote'))}；DOI {_fmt_pct(fc.get('DOI'))}；全文获取率 {_fmt_pct(h.get('access_union_rate'))}（附件 {_fmt_pct(h.get('attachment_rate'))} / OA {_fmt_pct(h.get('open_link_rate'))}）；谱系率 {_fmt_pct(h.get('provenance_rate'))}。")
    return "\n\n".join(lines)

def _evidence_interpretation_section(rows):
    """Move evidence-tier caveats out of the decision table without hiding them."""
    automated = [row for row in rows if row[6] in ("automated-screening", "estimated", "partial_snapshot", "estimated_lower_bound")]
    if not automated:
        return ""
    labels = {"automated-screening": "AI 自动初筛", "estimated": "估计", "partial_snapshot": "部分快照", "estimated_lower_bound": "估计下界"}
    lines = ["## 证据状态说明\n",
             "总表的判定已按同一阈值直接给出；证据状态只说明结果可被多大程度复核，不改写通过、警示或不通过。\n",
             "| 指标 | 证据来源 | 如何升级 |",
             "| --- | --- | --- |"]
    for _, iid, name, _, verdict, _, status, _ in automated:
        if status == "automated-screening":
            upgrade = "人工抽样核验分类、筛选或锚点来源"
        elif status == "partial_snapshot":
            upgrade = "完成全部来源分页并固定去重快照"
        elif status == "estimated_lower_bound":
            upgrade = "保留来源、边界与去重规则；不可将下界当 Recall"
        else:
            upgrade = "补足原始记录和独立复算路径"
        lines.append(f"| {iid} {name}（{verdict}） | {labels.get(status, status)} | {upgrade} |")
    return "\n".join(lines)

def indicator_rows(report):
    """Generate indicator register rows from indicator-registry.json.

    The registry is the single source of truth for: indicator IDs, order,
    display names, dimension affiliation, and umbrella-only markers.
    Each indicator has a compute function that returns (verdict, current_value,
    evidence_status, description_and_action) from the report data.
    """
    c, p, b, t, vbal, d, q, h = (report["coverage"], report["process"], report["balance"],
                                 report["topic_balance"], report["viewpoint_balance"], report["recency"], report["quality"],
                                 report["library_health"])
    umb = report.get("umbrella", {})
    s = report.get("standards", {}); ctx = report.get("context", {})
    artifacts = report.get("artifacts", {})
    chk = lambda g, k: g.get("checks", {}).get(k, "not_assessable")
    is_umbrella = ctx.get("review_type") == "伞式综述"
    evidence_integrity = ctx.get("evidence_integrity", {})

    def tv(value, threshold):
        return threshold_verdict(value, threshold)

    # ── Shared data snapshots computed once ──
    data = {
        "a1r": c["a1"].get("recall"), "a1h": c["a1"].get("matched"), "a1t": c["a1"].get("total"),
        "a2r": c["a2"].get("recall"), "a3l": c["a3"].get("deduplicated_candidate_lower_bound"),
        "a3s": c["a3"].get("status") or "",
        "a1m": s.get("a1_min_recall"), "a2m": s.get("a2_min_recall"),
        "br": p.get("high_confidence_new_rates", []),
        "bv": p.get("verdict", "—"),
        "tc": t.get("topic_counts", {}), "tf": t.get("flags", []),
        "bs": b.get("top_source_share"), "bcv": b.get("cv"), "bg": b.get("gini"), "bsh": b.get("normalized_shannon"),
        "ds": d.get("recent_share"), "dy": d.get("window_years"),
        "d_status": d.get("status"), "d_rec": d.get("recent_records"),
        "d_dated": d.get("dated_records"), "d_comp": d.get("year_completeness"),
        "d_pre": d.get("preprint_records"),
        "dsrc": report.get("currency", {}).get("sources", {}),
        "qh": q.get("h_core"), "qt1": q.get("tier1_rate"),
        "fc": h.get("field_completeness", {}),
        "hdoi": h.get("duplicate_doi_groups", 0), "hty": h.get("duplicate_title_year_groups", 0),
        "hacc": h.get("access_union_rate"), "hpr": h.get("provenance_rate"),
        "hcr": h.get("correction_flag_records", 0),
        "ha_r": h.get("attachment_rate"), "ho_r": h.get("open_link_rate"),
        "mids": c["a1"].get("missing_ids", []),
        "a1_path": artifacts.get("benchmark", {}).get("path", ""),
        "a2_path": artifacts.get("gold", {}).get("path", ""),
        "author_conc": b.get("author_concentration", {}),
        "umbrella": umb,
    }

    # ── Indicator compute functions — one per indicator ID ──
    def _a1(d):
        a1m = d["a1m"]; a1r = d["a1r"]; mids = d["mids"]
        verdict = tv(a1r, a1m)
        return (verdict,
                f"{_fmt_pct(a1r)}（{_fmt_num(d['a1h'])}/{_fmt_num(d['a1t'])}）",
                c["a1"].get("status"),
                f"稳定 ID 匹配 {d['a1h']}/{d['a1t']}。{'存在漏项。' if mids else '未见漏项。'}")

    def _a2(d):
        a2m = d["a2m"]; a2r = d["a2r"]
        a2_dep = ("⚠ A2 非独立——Gold 与 A1 基准集复用；A1 和 A2 不能相互增强证据强度。"
                  if (d["a2_path"] and d["a2_path"] == d["a1_path"]) else "")
        if evidence_integrity.get("a2_validation_independent") is False:
            a2_dep += "⚠ evidence-manifest 显示 validation 集存在查询泄漏或重叠，A2 仅作 estimated。"
        zero_hit_note = "零命中=实测 0。" if a2r == 0 and c["a2"].get("status") == "measured" else ""
        verdict = tv(a2r, a2m)
        return (verdict,
                f"{_fmt_pct(a2r)}（{_fmt_num(c['a2'].get('matched'))}/{_fmt_num(c['a2'].get('total'))}）",
                c["a2"].get("status"),
                f"稳定 ID 匹配 {_fmt_num(c['a2'].get('matched'))}/{_fmt_num(c['a2'].get('total'))}。{a2_dep or zero_hit_note or '按当前 Gold 集计算。'}")

    def _a3(d):
        a3l = d["a3l"]; a3s = d["a3s"]
        src_names = ', '.join(c['a3'].get('source_unique_identifier_counts', {}).keys()) or '—'
        return ("screening" if a3l is not None else "not_assessable",
                f"至少 {_fmt_num(a3l)} 篇不重复候选（{src_names}）",
                "estimated" if a3s.startswith("estimated") else a3s,
                f"至少 {_fmt_num(a3l)} 篇——'至少有多少篇相关文献存在于这些来源中'。不是 Recall，也不是'漏了多少'。"
                f"{'来源不完整。' if a3s == 'partial_snapshot' else '来源完整。'}")

    def _b1(d):
        br = d["br"]
        cur = (', '.join(f'{r:.4f}' for r in br[-2:]) if len(br) >= 2
               else (f'首轮 {br[-1]:.4f}（需第2轮确认趋稳）' if len(br) == 1 else '—'))
        return (chk(p, "B1_ggr"), cur, p.get("status"),
                f"最后两轮 GGR 与阈值比较；{'已满足' if chk(p, 'B1_ggr') == 'pass' else '未满足或轮次不足'}。")

    def _b2(d):
        my = ctx.get('independent_pathways') or p.get('automated_pathway_yields', []) or p.get('source_marginal_yields', [])
        overlap_note = ("⚠ A3 快照与 B2 路径共享证据来源，B2 不作独立边际收益结论。"
                        if evidence_integrity.get("a3_b2_overlap") else "")
        evidence_status = "automated-screening" if p.get("status") == "automated-screening" else p.get("status")
        auto_values = [row.get('yield') for row in my if isinstance(row, dict) and isinstance(row.get('yield'), (int, float))]
        return (chk(p, "B2_drr"),
                f"{_fmt_num(len(my))} 条路径 | 初筛边际率 {auto_values or '—'}", evidence_status,
                ("来源级初筛已完成；仍缺独立的非关键词路径。" if evidence_status == "automated-screening"
                 else "独立路径边际率已按阈值比较。") + overlap_note)

    def _b3(d):
        bv = d["bv"]
        verdict = ("pass" if chk(p, "B3_pathway_completion") == "pass" and chk(p, "B3_independent_validation") == "pass"
                   else "fail" if chk(p, "B3_pathway_completion") == "fail" or chk(p, "B3_independent_validation") == "fail"
                   else "not_assessable")
        iv_label = ('通过' if p.get('independent_validation_passed') is True
                    else ('未通过' if p.get('independent_validation_passed') is False else '—'))
        evidence_status = "measured" if p.get("status") == "measured" else ("automated-screening" if p.get("status") == "automated-screening" else "not_assessable")
        return (verdict,
                f"路径 {_fmt_pct(p.get('pathway_completion'))} | 独立验证 {iv_label}",
                evidence_status,
                f"{bv}。{'路径与独立验证均已完成。' if verdict == 'pass' else '路径或独立验证尚未完成。' if verdict == 'fail' else '缺少路径或独立验证记录。'}")

    def _c1(d):
        tc = d["tc"]; tf = d["tf"]
        desc = (f"{'、'.join(f'{k}={v}篇' for k,v in (sorted(tc.items(), key=lambda x:-x[1]) if tc else []))}。"
                f"{'需补：' + ', '.join(k for k,v in tc.items() if v==0) if 'empty_topic' in tf else '各主题均有文献。'}")
        opp = t.get("opposing_viewpoint_warning")
        if opp: desc += " （" + opp + "）"
        return (chk(t, "C1_topic_balance"),
                f"{_fmt_num(len(tc))} 主题 | {'含空主题' if 'empty_topic' in tf else '无空主题'}",
                t.get("status"), desc)

    def _c2(d):
        bs = d["bs"]; author_conc = d["author_conc"]
        desc = (f"最大来源占比 {_fmt_pct(bs)}。"
                f"{'单一来源依赖——非质量问题但需说明索引偏差。' if bs and bs > b.get('limits',{}).get('top_share',0.80) else '来源分布合理。'}"
                f"{' ' + b.get('high_shannon_note','') if b.get('high_shannon_note') else ''}")
        if author_conc and author_conc.get("note"):
            desc += " " + author_conc["note"]
        return (chk(b, "C2_source_balance"),
                f"Top={_fmt_pct(bs)} | CV={_fmt_num(d['bcv'])} | Gini={_fmt_num(d['bg'])} | Hn={_fmt_num(d['bsh'])}",
                b.get("status"), desc)

    def _c3(d):
        cf = t.get('cross_source_flags')
        return (chk(t, "C3_topic_source_balance"),
                f"{'⚠ ' + str(len(cf)) + ' 主题来源不足' if cf else '—'}",
                t.get("status"),
                f"{'需补来源：' + ', '.join(cf) if cf else '未提供 topic_source_counts。' if not ctx.get('topic_source_counts') else '各主题有独立来源。'}")

    def _c4(d):
        counts = vbal.get("counts", {})
        support = counts.get("supports_claim", 0); challenge = counts.get("challenges_claim", 0)
        mixed = counts.get("mixed_or_conditional", 0); total = vbal.get("total", 0)
        return (chk(vbal, "C4_viewpoint_balance"),
                f"支持 {support} | 质疑 {challenge} | 条件性 {mixed}（已分 {vbal.get('classified', 0)}/{total}）",
                vbal.get("status"), vbal.get("note", "—"))

    def _d1(d):
        dsrc = d["dsrc"]
        fdays = report.get('currency', {}).get('freshness_threshold_days', '—')
        return (chk(d, "D1_search_freshness"),
                "; ".join(f"{k}:{v['days_since']}天" for k,v in dsrc.items()) if dsrc else "—",
                report.get("currency", {}).get("status", "not_assessable"),
                f"{len(dsrc)} 个来源有日期。"
                f"{'存在过期来源。' if chk(d,'D1_search_freshness')=='warning' else '来源在新鲜度窗口内。' if chk(d,'D1_search_freshness')=='pass' else '缺少可核验的检索日期。'}")

    def _d2(d):
        verdict = chk(d, "D2_recent_share")
        return (chk(d, "D2_recent_share"),
                f"{_fmt_pct(d['ds'])}（{_fmt_num(d.get('d_rec'))}/{_fmt_num(d.get('d_dated'))} 有日期）",
                d["d_status"],
                f"近 {d['dy']} 年占比 {_fmt_pct(d['ds'])}。阈值按 profile：AI/通信 3年40%、常规 5年35%、基础设施 7年30%。"
                f"{'低于阈值。' if verdict == 'warning' else '达标。' if verdict == 'pass' else '缺少可用年份数据。'}"
                f"年份字段完整率 {_fmt_pct(d.get('d_comp'))}；<50% 时 D2 自动降级为 warning。")

    def _d3(d):
        return (chk(d, "D3_frontier"),
                ctx.get("frontier_coverage_verdict", "—"), d["d_status"],
                "前沿覆盖需 context.frontier_coverage_verdict。近期发表不等于前沿覆盖。")

    def _d4(d):
        pre = d.get('d_pre', '—')
        return (chk(d, "D4_versions_preprints"),
                f"预印本 {_fmt_num(pre)} 条", d["d_status"],
                f"{_fmt_num(pre)} 条预印本。"
                f"{'未核验版本关系。' if chk(d,'D4_versions_preprints')=='not_assessable' else ''}")

    def _e1(d):
        qh = d["qh"]
        note = (f"h-core={_fmt_num(qh)}。仅背景信号——高被引不等于高质量，新论文拉低 h-core。"
                f"真正的研究质量评估应使用与研究设计匹配的批判性评价工具。")
        if q.get('citation_coverage_rate') is not None and q['citation_coverage_rate'] < 0.5:
            note += f" 注意仅 {_fmt_pct(q['citation_coverage_rate'])} 条目有引用数据。"
        return (chk(q, "E1_h_core"),
                f"h={_fmt_num(qh)}（{q.get('citation_records','—')} 条引用）",
                q.get("status"), note)

    def _e2(d):
        qt1 = d["qt1"]
        return (chk(q, "E2_tier1"),
                f"{_fmt_pct(qt1)}（{_fmt_num(q.get('tier1_records'))}/{_fmt_num(h.get('records'))} 条库内文献）",
                q.get("status"),
                f"已配置 {q.get('tier1_venues_configured','—')} 个 venue（支持 tier1_venue_aliases 规范化）。"
                f"{'未配置 tier1_venues。' if not q.get('tier1_venues_configured') else '当前仅为下界。'}")

    def _f1(d):
        if ctx.get('run_log_query_count'):
            info = f"run log {_fmt_pct(ctx.get('run_log_completeness'))} 完整（{ctx.get('run_log_valid_count','—')}/{ctx.get('run_log_query_count','—')} 条合格）"
        else:
            info = f"run log {'完整' if ctx.get('run_log_complete') else '缺失'}"
        evidence_status = "measured" if ctx.get("run_log_complete") is True else "not_assessable"
        return (chk(p, "F1_query_traceability"), info, evidence_status,
                f"{'建库时查询未保留——唯一过程阻断项。' if not ctx.get('run_log_complete') else '全部 ' + str(ctx.get('run_log_query_count','')) + ' 条查询均含必要字段。' if ctx.get('run_log_depth') in ('valid','valid_full') else ctx.get('run_log_valid_count','') + '/' + str(ctx.get('run_log_query_count','')) + ' 条查询完整，其余缺必要字段（需 source/query/fields/date）。'}")

    def _f2(d):
        fc_abs = d["fc"].get("abstractNote")
        abs_threshold = report['standards'].get('f_abstract_rate', .80)
        return ("pass" if fc_abs is not None and fc_abs >= abs_threshold else "fail",
                _fmt_pct(fc_abs), h.get("status"),
                f"摘要率 {_fmt_pct(fc_abs)}。"
                f"{'达标。' if (fc_abs or 0) >= abs_threshold else '低于阈值。'}")

    def _f3(d):
        hacc = d["hacc"]; access_threshold = report['standards'].get('f_access_rate', .80)
        return (chk(h, "F3_access"), _fmt_pct(hacc), h.get("status"),
                f"附件 {_fmt_pct(d['ha_r'])} | 开放链接 {_fmt_pct(d['ho_r'])} | 联合 {_fmt_pct(hacc)}。"
                f"{'达标。' if hacc and hacc >= access_threshold else '低于阈值。'}"
                f"联合=v 附件或开放链接任一可用的记录比例，避免同一记录双渠道重复计数。")

    def _f4(d):
        hdoi = d["hdoi"]; hty = d["hty"]
        info = f"DOI 重复 {_fmt_num(hdoi)} 组 | 题名候选 {_fmt_num(hty)} 组 | 深度 {h.get('dedup_log_depth','—')}"
        verdict = ("pass" if chk(h, "F4_exact_duplicates") == "pass" and chk(h, "F4_version_decisions") == "pass"
                   else "fail" if chk(h, "F4_exact_duplicates") == "fail" else "not_assessable")
        ver_note = (f"版本决定已保存（{h.get('dedup_log_depth','—')}）。" if chk(h, 'F4_version_decisions') == 'pass'
                    else "未提供结构化 dedup-log，版本候选待核验。")
        return (verdict, info, h.get("status"),
                f"DOI 重复 {_fmt_num(hdoi)} 组。{'存在未处理重复。' if hdoi > 0 else '无精确重复。'}"
                f"题名相似候选 {_fmt_num(hty)} 组（{ver_note}）")

    def _f5(d):
        hpr = d["hpr"]; f5n = h.get("f5_note", "")
        prov_threshold = report['standards'].get('f_provenance_rate', .95)
        return (chk(h, "F5_provenance"), _fmt_pct(hpr), h.get("status"),
                f5n if f5n else f"来源谱系率 {_fmt_pct(hpr)}。"
                f"{'达标。' if hpr and hpr >= prov_threshold else '低于阈值。'}")

    def _f6(d):
        hcr = d["hcr"]
        return (chk(h, "F6_corrections"), f"标记 {_fmt_num(hcr)} 条", h.get("status"),
                f"{_fmt_num(hcr)} 条标记。"
                f"{'未经专门来源核验。' if chk(h,'F6_corrections')=='not_assessable' else '已核验。'}")

    # ── Umbrella-only compute functions ──
    def _a4(d):
        a4_info = d["umbrella"].get("a4", {}) if d["umbrella"] else {}
        if not a4_info: return ("not_assessable", "—", "not_assessable", "伞式综述 A4 数据不可得")
        return (a4_info.get("verdict"),
                f"{_fmt_pct(a4_info.get('purity'))}（{_fmt_num(a4_info.get('survey_literature_count'))}/{_fmt_num(a4_info.get('total_library_size'))}）",
                a4_info.get("status"), a4_info.get("note", ""))

    def _c5(d):
        c4_info = d["umbrella"].get("c4", {}) if d["umbrella"] else {}
        if not c4_info: return ("not_assessable", "—", "not_assessable", "伞式综述 C5 数据不可得")
        mtd = c4_info.get("method_type_distribution", {})
        mtd_str = json.dumps(mtd, ensure_ascii=False) if mtd else "—"
        return (c4_info.get("verdict"),
                f"CCA={_fmt_num(c4_info.get('cca'))} | 方法类型: {mtd_str}",
                c4_info.get("status"), c4_info.get("note", ""))

    def _f7(d):
        f7_info = d["umbrella"].get("f7", {}) if d["umbrella"] else {}
        if not f7_info: return ("not_assessable", "—", "not_assessable", "伞式综述 F7 数据不可得")
        tool = f7_info.get("quality_assessment_tool", "—")
        return (f7_info.get("verdict"),
                f"全文 {_fmt_pct(f7_info.get('fulltext_readiness'))} | 工具 {tool}",
                f7_info.get("status"), f7_info.get("note", ""))

    # ── COMPUTE_FUNCTIONS: register each indicator ID to its compute func ──
    COMPUTE = {
        "A1": _a1, "A2": _a2, "A3": _a3,
        "B1": _b1, "B2": _b2, "B3": _b3,
        "C1": _c1, "C2": _c2, "C3": _c3, "C4": _c4,
        "D1": _d1, "D2": _d2, "D3": _d3, "D4": _d4,
        "E1": _e1, "E2": _e2,
        "F1": _f1, "F2": _f2, "F3": _f3, "F4": _f4, "F5": _f5, "F6": _f6,
        "A4": _a4, "C5": _c5, "F7": _f7,
    }

    # Standard texts (threshold descriptions) — also from registry when registry
    # defines display thresholds, but for now these are the human-readable
    # summaries that vary by indicator semantics.
    STANDARDS = {
        "A1": lambda d: f"阈值 ≥ {d['a1m']}" if d['a1m'] else "需配置 a1_min_recall",
        "A2": lambda d: f"阈值 ≥ {d['a2m']}" if d['a2m'] else "需配置 a2_min_recall",
        "A3": "至少两完整来源去重后的不重复候选数；只报告下界",
        "B1": lambda d: f"最后两轮均 < {p.get('thresholds',{}).get('new_rate','—')}" if len(d['br']) >= 2 else "/",
        "B2": lambda d: f"各路径均 < {p.get('thresholds',{}).get('marginal_yield','—')}" if len(p.get('source_marginal_yields',[])) >= 2 else "/",
        "B3": lambda d: "路径完成且独立验证通过" if p.get('independent_validation_passed') is not None else '/',
        "C1": "无空主题；Top≤0.70；CV≤0.80；Gini≤0.50；Shannon≥0.55",
        "C2": "Top≤0.80；CV≤1.00；Gini≤0.60；Shannon≥0.45",
        "C3": "每主题 ≥2 来源；单一来源 ≤0.80",
        "C4": lambda d: (f"分类覆盖≥{vbal.get('thresholds',{}).get('min_classified_fraction','—')}；"
                         f"单方≤{vbal.get('thresholds',{}).get('max_dominant_share','—')}；"
                         f"反方≥{vbal.get('thresholds',{}).get('min_counterevidence','—')}") if vbal.get('claim') else "先定义中心主张并完成观点分类",
        "D1": lambda d: f"各来源距检索 ≤ {report.get('currency',{}).get('freshness_threshold_days','—')} 天",
        "D2": lambda d: f"近 {d['dy'] or '—'} 年占比 ≥ {d.get('minimum_share','—')}",
        "D3": lambda d: "/" if not ctx.get("frontier_coverage_verdict") else "前沿窗口有独立检索/Gold set",
        "D4": lambda d: "/" if not ctx.get("version_currency_verdict") else "预印本-正式版关系已核验",
        "E1": "报告 h-index；仅背景信号",
        "E2": "按 profile 配置 venue 映射",
        "F1": lambda d: "/" if not ctx.get("run_log_complete") else "查询原文、字段、过滤器、日期、来源齐全",
        "F2": lambda d: f"≥ {report['standards'].get('f_abstract_rate', .80)}",
        "F3": lambda d: f"≥ {report['standards'].get('f_access_rate', .80)}",
        "F4": "DOI 精确重复=0；版本候选有决定",
        "F5": lambda d: f"≥ {report['standards'].get('f_provenance_rate', .95)}",
        "F6": lambda d: "/" if d["hcr"] == 0 else "关键记录有更正检查",
        "A4": lambda d: f"综述论文占比 ≥ {d['umbrella'].get('a4',{}).get('threshold','—')}" if d['umbrella'] else "/",
        "C5": lambda d: "/" if (not d['umbrella'] or d['umbrella'].get('c4',{}).get('verdict') == 'not_assessable') else "CCA ≤ 0.15 且子主题/方法类型无断层",
        "F7": lambda d: f"全文就绪 ≥ {d['umbrella'].get('f7',{}).get('threshold','—')}; 工具: {d['umbrella'].get('f7',{}).get('quality_assessment_tool','—')}" if d['umbrella'] else "/",
    }

    # ── Load registry and build rows in registry order ──
    script_dir = pathlib.Path(__file__).resolve().parent
    reg_path = script_dir.parent / "schemas" / "indicator-registry.json"
    try:
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        registry = {"indicators": [], "dimensions": {}}

    dim_names = {k: v.get("name", k) for k, v in registry.get("dimensions", {}).items()}

    rows = []
    for ind in registry.get("indicators", []):
        iid = ind["id"]
        # Skip umbrella-only indicators for non-umbrella reviews
        if ind.get("umbrella_only") and not is_umbrella:
            continue

        compute = COMPUTE.get(iid)
        if not compute:
            rows.append((dim_names.get(ind["dimension"], ind["dimension"]),
                         iid, ind["display_name"]["zh"],
                         "—", "not_assessable", "—", "not_assessable",
                         f"计算函数缺失——请在 COMPUTE 注册表中添加 '{iid}'"))
            continue

        # Resolve standard text
        std_entry = STANDARDS.get(iid, "")
        if callable(std_entry):
            std = std_entry(data)
        else:
            std = std_entry

        v, cur, ev, note = compute(data)
        dim_label = dim_names.get(ind["dimension"], ind["dimension"])
        rows.append((dim_label, iid, ind["display_name"]["zh"], std, v, compact(cur), ev, note))

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

    Naming: inputs/<label>__<sha256[:12]>.<ext> to avoid collisions.
    Absolute paths are NOT saved by default (privacy); opt-in via record_source_paths=True.
    """
    inputs_dir = out / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    # Try to detect git commit
    git_commit = None
    import subprocess as _sp
    try:
        git_commit = _sp.check_output(
            ["git", "-C", str(pathlib.Path(__file__).resolve().parent.parent),
             "rev-parse", "HEAD"], text=True, stderr=_sp.DEVNULL).strip()
    except Exception:
        pass
    import sys as _sys, platform as _pf
    script_hash = hash_file(pathlib.Path(__file__).resolve()) or "unknown"
    manifest = {
        "schema_version": "1.0",
        "generated_at": report.get("generated_at", ""),
        "run_audit_version": "model-x-2026-07-21",
        "git_commit": git_commit,
        "run_audit_sha256": script_hash,
        "python_version": _sys.version.split()[0],
        "platform": _pf.platform(),
        "review_type": report.get("context", {}).get("review_type", ""),
        "standards_applied": report.get("standards", {}),
        "record_source_paths": False,
        "input_files": {},
    }
    for label, src in sorted(artifact_paths.items()):
        entry = {"provided": bool(src)}
        if src and pathlib.Path(src).is_file():
            h = hash_file(src) or "unreadable"
            entry["sha256"] = h
            src_path = pathlib.Path(src)
            safe_prefix = f"{label}__{h[:12]}" if h != "unreadable" else label
            dst = inputs_dir / f"{safe_prefix}{src_path.suffix}"
            if not dst.exists() or hash_file(dst) != h:
                shutil.copy2(src, dst)
            entry["copied_to"] = str(dst.relative_to(out))
            entry["source_filename"] = src_path.name
        manifest["input_files"][label] = entry
    # Also record the library file
    lib_path = report.get("context", {}).get("library_path", "")
    if lib_path and pathlib.Path(lib_path).is_file():
        h = hash_file(lib_path) or "unreadable"
        entry = {"provided": True, "sha256": h, "source_filename": pathlib.Path(lib_path).name}
        safe_prefix = f"library__{h[:12]}" if h != "unreadable" else "library"
        dst = inputs_dir / f"{safe_prefix}{pathlib.Path(lib_path).suffix}"
        if not dst.exists() or hash_file(dst) != h:
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

    # ── Pre-compute all sections ──
    evidence_table = _input_evidence_table(report)
    method_narrative = _method_narrative(report)
    search_iteration_section = _search_iteration_section(report)
    writing_readiness_section = _writing_readiness_section(report)
    evidence_interpretation_section = _evidence_interpretation_section(rows)

    md = ["# 文献库评估报告\n"]
    # 1. 基本信息
    md.append("## 基本信息\n"); md.append("| 项目 | 值 |"); md.append("| --- | --- |")
    md.append(f"| 生成时间 | {gt} |"); md.append(f"| 评估对象 | {ln} |")
    md.append(f"| 文献库规模 | {h.get('records','—')} 篇 |"); md.append(f"| 综述类型 | {rt} |")
    md.append(f"| 工程领域 | {pr} |"); md.append(f"| 研究范围 | {sc} |")
    if a3l: md.append(f"| 全域参考 | OpenAlex 候选下界 {a3l} 篇 |")
    md.append("")
    # 2. 本次评估输入与证据状态
    if evidence_table:
        md.append(evidence_table)
        md.append("")
    # 3. 评估方法与过程
    md.append("## 评估方法与过程\n"); md.append(method_narrative); md.append("")
    # 3b. 检索迭代过程（有 search_iterations 时渲染）
    if search_iteration_section:
        md.append(search_iteration_section)
        md.append("")
    # 4. A–F 六维评估总表
    md.append("## A–F 六维评估总表\n")
    md.append("| 维度 | 编号 | 评估项 | 标准 | 判定 | 当前值 | 证据状态 | 说明与行动 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    md.append("\n".join("| " + " | ".join(compact(cell) for cell in row) + " |" for row in rows))
    md.append("")
    if evidence_interpretation_section:
        md.append(evidence_interpretation_section)
        md.append("")
    # 5. 各维度分析
    md.append("## 各维度分析\n"); md.append(_dimension_narrative(report)); md.append("")
    # 6. 改进建议
    md.append("## 改进建议\n"); md.append(_priority_actions(report)); md.append("")
    # 7. 跨维度写作建议
    md.append(writing_readiness_section); md.append("")
    # 8. 局限与声明
    md.append("## 局限与声明\n"); md.append("\n".join("- " + x for x in report["limitations"])); md.append("")
    (out / "audit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "audit.html").write_text("<html><meta charset='utf-8'><body><pre>" + html.escape("\n".join(md)) + "</pre></body></html>", encoding="utf-8")

def _validate_run_config(rc):
    """Lightweight schema validation without jsonschema dependency. Returns list of error strings."""
    errors = []
    if not isinstance(rc, dict):
        return ["run-config must be a JSON object"]
    if rc.get("schema_version") != "1.0":
        errors.append(f"schema_version: expected '1.0', got {rc.get('schema_version')!r}")

    # ── Required top-level fields ──
    for field in ("project", "library", "automation", "output"):
        if field not in rc:
            errors.append(f"Missing required top-level field: '{field}'")
        elif not isinstance(rc[field], dict):
            errors.append(f"'{field}' must be an object, got {type(rc[field]).__name__}")

    # project
    proj = rc.get("project", {})
    if isinstance(proj, dict):
        rq = proj.get("research_question")
        if not rq or not isinstance(rq, str) or not rq.strip():
            errors.append("project.research_question is required (non-empty string)")
        rt = proj.get("review_type")
        VALID_RT = {"narrative", "systematic", "scoping", "rapid", "umbrella",
                    "叙事综述", "系统综述", "范围综述", "快速综述", "伞式综述"}
        if not rt:
            errors.append("project.review_type is required")
        elif rt not in VALID_RT:
            errors.append(f"project.review_type: must be one of {VALID_RT}, got {rt!r}")
        ss = proj.get("scope_status")
        VALID_SS = {"in_scope", "cross_domain", "out_of_scope", "scope_uncertain"}
        if not ss:
            errors.append("project.scope_status is required")
        elif ss not in VALID_SS:
            errors.append(f"project.scope_status: must be one of {VALID_SS}, got {ss!r}")
        al = proj.get("allowed_assessment_level")
        VALID_AL = {"full", "limited_metadata_only", "stop"}
        if al and al not in VALID_AL:
            errors.append(f"project.allowed_assessment_level: must be one of {VALID_AL}, got {al!r}")
    # library
    lib = rc.get("library", {})
    if isinstance(lib, dict):
        if lib.get("provided") and not lib.get("path"):
            errors.append("library.path is required when library.provided is true")
        fmt = lib.get("format")
        VALID_FMT = {"json", None}
        if fmt is not None and fmt not in VALID_FMT:
            errors.append(f"library.format: v1.0 only supports {VALID_FMT}, got {fmt!r} (bibtex/csv/ris/zotero are roadmap items)")
    else:
        errors.append("library is required and must be an object")
    # automation
    auto = rc.get("automation", {})
    if isinstance(auto, dict):
        if "allow_search" not in auto:
            errors.append("automation.allow_search is required")
    else:
        errors.append("automation is required and must be an object")
    # standards
    stds = rc.get("standards", {})
    if isinstance(stds, dict):
        ov = stds.get("user_overrides")
        if ov is not None and not isinstance(ov, dict):
            errors.append("standards.user_overrides must be an object")
    # output
    out_cfg = rc.get("output", {})
    if not isinstance(out_cfg, dict):
        errors.append("output is required and must be an object")
    return errors

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-config", help="run-config.json (v1.0) — auto-resolves all other inputs")
    p.add_argument("--library"); p.add_argument("--benchmark"); p.add_argument("--gold")
    p.add_argument("--benchmark-evidence-status", choices=("measured", "estimated", "automated-screening"),
                   help="Evidence tier for --benchmark; automated first-run anchors must use automated-screening")
    p.add_argument("--query-hits"); p.add_argument("--candidate-snapshots"); p.add_argument("--context")
    p.add_argument("--query-plan"); p.add_argument("--source-snapshot"); p.add_argument("--decision-log")
    p.add_argument("--deduplication-log"); p.add_argument("--run-log"); p.add_argument("--search-meta",
                   help="search_meta.json from search_for_eval.py — auto-detected alongside --query-hits if omitted")
    p.add_argument("--evidence-manifest", help="evidence-manifest.json for dataset provenance and independence checks")
    p.add_argument("--out", required=True)
    p.add_argument("--allow-out-of-scope", action="store_true",
                   help="Force full A-F even when scope_status=out_of_scope (report will carry permanent caveats)")
    a = p.parse_args()

    # ── run-config mode: auto-resolve all inputs from run-config.json ──
    rc_base_dir = None
    rc_ctx_overrides = {}  # scope override flags, carried into final ctx
    if a.run_config:
        rc_path = pathlib.Path(a.run_config).resolve()
        if not rc_path.is_file():
            p.error(f"run-config file not found: {a.run_config}")
        rc_base_dir = rc_path.parent
        rc = json.loads(rc_path.read_text(encoding="utf-8-sig"))

        # ── schema validation ──
        rc_errors = _validate_run_config(rc)
        if rc_errors:
            print("run-config validation errors:", file=sys.stderr)
            for e in rc_errors:
                print(f"  - {e}", file=sys.stderr)
            # non-fatal for known fields; fatal for missing required fields
            fatal = any("required" in e.lower() or "must be" in e.lower() for e in rc_errors)
            if fatal:
                p.error("run-config has fatal validation errors (see above).")

        scope_status = rc.get("project", {}).get("scope_status", "scope_uncertain")
        allowed_level = rc.get("project", {}).get("allowed_assessment_level", "full")
        if scope_status in ("out_of_scope",) or allowed_level == "stop":
            if not a.allow_out_of_scope:
                print(f"ERROR: scope_status={scope_status}, allowed_assessment_level={allowed_level} — refusing to run full A-F.")
                print("  Use --allow-out-of-scope to force (report will carry permanent caveats),")
                print("  or use --mode metadata-health / --mode search-design for downgraded service.")
                p.exit(1)
            else:
                print("WARNING: scope_status=out_of_scope but --allow-out-of-scope active — continuing with permanent caveats in report.")
                rc_ctx_overrides["_scope_override_active"] = True

        # Resolve relative paths against the run-config directory
        rc_base = rc_base_dir
        def _resolve(path_str):
            if not path_str: return None
            pth = pathlib.Path(path_str)
            if pth.is_absolute(): return str(pth)
            resolved = (rc_base / pth).resolve()
            return str(resolved) if resolved.is_file() else str(pathlib.Path(path_str).resolve())

        lib_info = rc.get("library", {})
        if lib_info.get("provided") and lib_info.get("path") and not a.library:
            a.library = _resolve(lib_info["path"])

        ev = rc.get("evidence_inputs", {})
        if ev.get("benchmark") and not a.benchmark: a.benchmark = _resolve(ev["benchmark"])
        if ev.get("gold") and not a.gold: a.gold = _resolve(ev.get("gold"))
        if ev.get("query_log") and not a.run_log: a.run_log = _resolve(ev["query_log"])
        if ev.get("query_hits") and not a.query_hits: a.query_hits = _resolve(ev["query_hits"])
        if ev.get("source_snapshot") and not a.candidate_snapshots: a.candidate_snapshots = _resolve(ev["source_snapshot"])
        if ev.get("screening_decisions") and not a.decision_log: a.decision_log = _resolve(ev["screening_decisions"])
        if ev.get("deduplication_log") and not a.deduplication_log: a.deduplication_log = _resolve(ev["deduplication_log"])
        if ev.get("evidence_manifest") and not a.evidence_manifest: a.evidence_manifest = _resolve(ev["evidence_manifest"])

        if not a.context:
            ctx_from_rc = {
                "review_type": rc.get("project", {}).get("review_type", ""),
                "profile": (rc.get("project", {}).get("engineering_profile", [None]) or [None])[0] if rc.get("project", {}).get("engineering_profile") else "",
                "year_start": (rc.get("project", {}).get("time_range") or {}).get("start"),
                "year_end": (rc.get("project", {}).get("time_range") or {}).get("end"),
                "languages": rc.get("project", {}).get("languages", []),
                "scope_status": scope_status,
                "viewpoint_framework": (rc.get("assessment_context", {}) or {}).get("viewpoint_framework", {}),
            }
            user_stds = rc.get("standards", {}).get("user_overrides", {})
            confirmed = rc.get("standards", {}).get("confirmed_by_user", False)
            if user_stds:
                ctx_from_rc["standards"] = dict(user_stds)
            ctx_from_rc.setdefault("standards", {})["confirmed_by_user"] = confirmed
            # write as resolved-config for manifest
            resolved_dir = pathlib.Path(a.out) / ".tmp"
            resolved_dir.mkdir(parents=True, exist_ok=True)
            ctx_file = resolved_dir / "resolved-config.json"
            ctx_file.write_text(json.dumps(ctx_from_rc, ensure_ascii=False, indent=2), encoding="utf-8")
            a.context = str(ctx_file)

    if not a.library:
        p.error("--library is required (or provide --run-config with library.path)")
    ctx = json.load(open(a.context, encoding="utf-8-sig")) if a.context else {}
    # Carry forward scope override flag from run-config parsing
    for k, v in rc_ctx_overrides.items():
        ctx.setdefault(k, v)
    ctx.setdefault("library_path", a.library)
    ctx = resolve_thresholds(ctx)
    # ── Unified scope guard (covers both run-config and direct CLI paths) ──
    scope_status = ctx.get("scope_status", "")
    if scope_status == "out_of_scope" and not a.allow_out_of_scope:
        print(f"ERROR: scope_status=out_of_scope — refusing to run full A-F.")
        print("  Use --allow-out-of-scope to force (report will carry permanent caveats),")
        print("  or provide a library within the supported engineering scope.")
        p.exit(1)
    if scope_status == "out_of_scope":
        print("WARNING: scope_status=out_of_scope — --allow-out-of-scope active. Report will carry permanent caveats.")
    # ── Consume search_meta.json if present and merge search iterations / evidence status ──
    search_meta_path = a.search_meta
    if not search_meta_path:
        # Try to auto-detect search_meta.json alongside query-hits
        if a.query_hits:
            qh_dir = pathlib.Path(a.query_hits).parent
            sm_candidate = qh_dir / "search_meta.json"
            if sm_candidate.is_file():
                search_meta_path = str(sm_candidate)
    if search_meta_path:
        try:
            sm = json.loads(pathlib.Path(search_meta_path).read_text(encoding="utf-8-sig"))
            # Merge search_rounds only if not already provided via context
            if "search_rounds" not in ctx or not ctx["search_rounds"]:
                ctx["search_rounds"] = sm.get("search_rounds", ctx.get("search_rounds", []))
            if "source_marginal_yields" not in ctx or not ctx["source_marginal_yields"]:
                ctx["source_marginal_yields"] = sm.get("source_marginal_yields", [])
            if "planned_pathways" not in ctx or not ctx["planned_pathways"]:
                ctx["planned_pathways"] = sm.get("planned_pathways", [])
            if "independent_pathways" not in ctx or not ctx["independent_pathways"]:
                ctx["independent_pathways"] = sm.get("independent_pathways", [])
            # Preserve q0 and first-round execution for the user-facing strategy
            # section, even before the iterative refinement log exists.
            if not ctx.get("search_query_versions"):
                ctx["search_query_versions"] = sm.get("query_versions") or sm.get("queries", [])
            if not ctx.get("search_iterations"):
                ctx["search_iterations"] = sm.get("search_iterations", [])
            if not ctx.get("search_initial_query_origin"):
                ctx["search_initial_query_origin"] = sm.get("initial_query_origin", "")
            if not ctx.get("source_syntax_map"):
                ctx["source_syntax_map"] = sm.get("source_syntax_map", {})
            if not ctx.get("search_validation_source"):
                ctx["search_validation_source"] = sm.get("validation_source", "")
            # Consume dev/val recall for A2 evidence status
            a2_meta = sm.get("a2", {})
            dev_recall = sm.get("dev_recall")
            val_recall = sm.get("validation_recall")
            ctx["_search_meta_a2_evidence"] = sm.get("a2_evidence_status", "")
            ctx["_search_meta_dev_recall"] = dev_recall
            ctx["_search_meta_val_recall"] = val_recall
            ctx["_search_meta_val_total"] = sm.get("validation_recall_total", 0)
            ctx["_search_meta_dev_total"] = sm.get("dev_recall_total", 0)
            ctx["_search_meta_id_diagnostics"] = sm.get("a2", {}).get("validation_id_diagnostics") or sm.get("a2", {}).get("dev_id_diagnostics", {})
        except (json.JSONDecodeError, OSError):
            pass
    # Check query_hits for failed sources — downgrade A2 status if any query failed
    a2_query_failed = False
    if a.query_hits:
        qh_path = pathlib.Path(a.query_hits)
        if qh_path.is_file():
            try:
                qh_data = json.loads(qh_path.read_text(encoding="utf-8-sig"))
                if isinstance(qh_data, list):
                    # query-hits.json is a flat list of hit records
                    pass
                elif isinstance(qh_data, dict):
                    queries_info = qh_data.get("queries", qh_data.get("query_log", []))
                    a2_query_failed = any(
                        isinstance(q, dict) and q.get("status") == "failed"
                        for q in queries_info
                    )
            except (json.JSONDecodeError, OSError):
                pass
    evidence_manifest = load_evidence_manifest(a.evidence_manifest)
    evidence_integrity = inspect_manifest(evidence_manifest, a.evidence_manifest)
    ctx["evidence_integrity"] = evidence_integrity
    lib = load_items(a.library)
    cov = {"a1": benchmark(load_items(a.library), load_items(a.benchmark) if a.benchmark else []),
           "a2": a2(load_items(a.gold) if a.gold else None, load_items(a.query_hits) if a.query_hits else None),
           "a3": a3(load_snapshot(a.candidate_snapshots) if a.candidate_snapshots else {})}
    if a.benchmark_evidence_status and cov["a1"].get("status") == "measured":
        cov["a1"]["status"] = a.benchmark_evidence_status
        if a.benchmark_evidence_status != "measured":
            cov["a1"]["note"] = (cov["a1"].get("note", "") +
                                  " Benchmark was assembled by automated first-run screening; it requires provenance and relevance review before becoming measured.").strip()
    # ── Evidence status from search_meta ──
    if a2_query_failed and cov["a2"].get("status") == "measured":
        cov["a2"]["status"] = "partial_snapshot"
        cov["a2"]["note"] = (cov["a2"].get("note", "") + " At least one source query failed — A2 recall may underestimate true sensitivity.").strip()
    # Downgrade A2 to estimated when no independent validation set
    search_meta_a2_ev = ctx.get("_search_meta_a2_evidence", "")
    has_val_set = ctx.get("_search_meta_val_total", 0) > 0
    if search_meta_a2_ev == "estimated" and cov["a2"].get("status") == "measured":
        cov["a2"]["status"] = "estimated"
        cov["a2"]["note"] = (cov["a2"].get("note", "") + " No independent validation set — A2 may be overestimated (dev=val reuse).").strip()
    # When search_for_eval supplied an independent validation result, it is the
    # A2 primary value. Do not silently report the dev/gold recall instead.
    if (ctx.get("_search_meta_val_total", 0) > 0 and
            ctx.get("_search_meta_val_recall") is not None):
        val_total = int(ctx["_search_meta_val_total"])
        val_recall = float(ctx["_search_meta_val_recall"])
        cov["a2"]["total"] = val_total
        cov["a2"]["matched"] = round(val_recall * val_total)
        cov["a2"]["recall"] = val_recall
        cov["a2"]["status"] = "automated-screening" if search_meta_a2_ev == "automated-screening" else "measured"
        cov["a2"]["note"] = (cov["a2"].get("note", "") +
                              " A2 主值来自 search_meta 的 validation_recall，而非 dev/gold recall。"
                              + (" 该验证集为自动留出，尚未形成独立实测。" if search_meta_a2_ev == "automated-screening" else "")).strip()
    id_diagnostics = ctx.get("_search_meta_id_diagnostics", {})
    if id_diagnostics.get("records_without_stable_id"):
        cov["a2"]["note"] = (cov["a2"].get("note", "") +
                              f" {id_diagnostics['records_without_stable_id']} 条开发/验证记录缺少可用稳定 ID；可补 DOI、OpenAlex、arXiv、PMID 或 PMCID，标题相似仅供人工核验。").strip()
    if evidence_integrity.get("a2_validation_independent") is False and cov["a2"].get("status") == "measured":
        cov["a2"]["status"] = "estimated"
        cov["a2"]["note"] = (cov["a2"].get("note", "") + " Evidence manifest shows validation leakage or overlap; A2 is procedurally non-independent.").strip()
    # F1: parse run-log BEFORE stability() so F1_query_traceability can use the result
    if a.run_log:
        rp = pathlib.Path(a.run_log)
        if rp.is_file():
            try:
                content = rp.read_text(encoding="utf-8")
                if content.strip():
                    data = json.loads(content)
                    queries = data.get("queries", data.get("query_log", []))
                    if queries and isinstance(queries, list):
                        REQUIRED = {"source", "query", "fields", "date"}
                        PREFERRED = {"filters", "result_count", "completion_status"}
                        valid_count = sum(1 for q in queries if isinstance(q, dict) and REQUIRED <= set(q.keys()))
                        preferred_count = sum(1 for q in queries if isinstance(q, dict) and PREFERRED <= set(q.keys()))
                        total_count = len(queries)
                        completeness = round(valid_count / total_count, 3) if total_count else None
                        ctx["run_log_query_count"] = total_count
                        ctx["run_log_valid_count"] = valid_count
                        ctx["run_log_completeness"] = completeness
                        ctx["run_log_complete"] = valid_count == total_count and total_count > 0
                        ctx["run_log_depth"] = ("valid_full" if preferred_count == total_count and total_count > 0
                                                else "valid" if valid_count == total_count
                                                else "partial" if valid_count > 0
                                                else "shallow")
                    else:
                        ctx["run_log_complete"] = False
                        ctx["run_log_depth"] = "shallow"
            except (OSError, json.JSONDecodeError):
                ctx["run_log_complete"] = False
                ctx["run_log_depth"] = "unparseable"
    proc = stability(ctx); bal = balance(lib, ctx.get("standards", {}))
    tbal = topic_balance(ctx); vbal = viewpoint_balance(lib, ctx); cur = currency(ctx); rec = recency(lib, ctx)
    # F4: verify dedup-log exists, is parseable, and contains structured decisions.
    # dedup_log_ok only True when: structured sections exist AND all fuzzy/version candidates
    # have actual decisions (merge/retain_both/exclude/manual_review_required).
    # "No pending candidates" is a valid conclusion (scan completed, nothing ambiguous) → pass.
    # "manual_review_required" is a PENDING state — not a resolved decision.
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
                    if pending:
                        # manual_review_required is NOT a resolved decision
                        RESOLVED = {"merge", "retain_both", "exclude"}
                        all_resolved = all(
                            c.get("decision") in RESOLVED
                            for c in pending
                        )
                        dedup_log_depth = "structured_decisions" if all_resolved else "structured_no_decisions"
                        dedup_log_ok = all_resolved  # only when all pending have resolved decisions
                    else:
                        # Scan completed, zero ambiguous candidates → pass
                        dedup_log_depth = "structured_decisions"
                        dedup_log_ok = True
                else:
                    dedup_log_depth = "parseable_but_shallow"
            except (json.JSONDecodeError, OSError):
                dedup_log_depth = "unparseable"
    # F5: check decision-log for screening trail
    decision_log_ok = False
    if a.decision_log:
        dp = pathlib.Path(a.decision_log)
        if dp.is_file():
            try:
                data = json.loads(dp.read_text(encoding="utf-8"))
                # decision-log should have decisions array with inclusion/exclusion/reason entries
                decisions = data.get("decisions", data.get("screening_log", []))
                if isinstance(decisions, list) and len(decisions) > 0:
                    has_reasons = any(isinstance(d, dict) and d.get("reason") for d in decisions)
                    decision_log_ok = has_reasons
            except (json.JSONDecodeError, OSError):
                pass
    libh = health(lib, ctx.get("standards", {}), dedup_log_provided=dedup_log_ok,
                  dedup_log_depth=dedup_log_depth, decision_log_provided=decision_log_ok,
                  taxonomy=ctx.get("taxonomy"))
    libh["dedup_log_depth"] = dedup_log_depth
    qual = quality(lib, ctx)
    # umbrella-specific A4/C5/F7 (requires libh to exist first)
    umb = umbrella_checks(lib, ctx, libh) if ctx.get("review_type") == "伞式综述" else {"a4": None, "c4": None, "f7": None}
    gt = dt.datetime.now(dt.timezone.utc).isoformat(); gts = gt[:19].replace("T", " ")
    rt = ctx.get("review_type", "未指定"); prf = ctx.get("profile", "未指定")
    bf = []
    if tbal.get("checks", {}).get("C1_topic_balance") == "fail": bf.append("C1 存在空主题")
    if vbal.get("checks", {}).get("C4_viewpoint_balance") == "warning": bf.append("C4 观点偏斜或分类不足")
    if libh.get("checks", {}).get("F4_exact_duplicates") == "fail": bf.append("F4 存在未处理重复")
    # F_metadata_composite 不在 22 子项 register 内，
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
            "本评估报告沿用文献库准备度的通用框架，仅对综述层面的 A4（综述类型确认）/C5（综述间覆盖分布）/F7（质量评估就绪度）做初筛诊断。"
            "**本报告不能代替**：① AMSTAR-2 的 16 项逐条评分；② ROBIS 偏倚风险评估；③ 综述间结论冲突的实质分析。"
            "**强烈建议在完成文献库评估后，由领域专家对纳入综述进行独立的方法学质量审查。**"
        )
        summary += umbrella_disclaimer
    report = {"generated_at": gt, "standards": ctx.get("standards", {}), "context": ctx,
            "library_health": libh, "coverage": cov, "process": proc, "balance": bal,
              "topic_balance": tbal, "viewpoint_balance": vbal, "currency": cur, "recency": rec, "quality": qual,
              "umbrella": umb,
              "artifacts": artifacts({"query-plan": a.query_plan, "query-hits": a.query_hits,
                                      "search-meta": search_meta_path, "source-snapshot": a.source_snapshot or a.candidate_snapshots,
                                      "decision-log": a.decision_log, "deduplication-log": a.deduplication_log,
                                      "evidence-manifest": a.evidence_manifest, "run-log": a.run_log}),
              "summary": summary,
              "limitations": ["本报告中的各项阈值均为基于工程文献计量经验的参考值，旨在辅助识别可能的风险信号，不等于文献库质量的绝对标准。pass/warning/fail 是自动化诊断提示，不是质量裁决，所有结论均应结合具体研究问题和领域惯例做人工判断。",
                              "A3 下界不是 Recall；区间需另行声明模型假设。",
                              "主题平衡、版本等价性、研究设计和更正状态需人工或专门来源核验。",
                              "h-core 和 Tier-1 仅作诊断背景，不等于综述质量。",
                              "未提供的运行产物会明确标为缺失。"]}
    if rt == "伞式综述":
        report["limitations"].extend([
            "伞式综述专用子项 A4（综述类型确认）基于标题关键词自动分类，仅初筛——需人工抽样核验 review/survey 论文的实际类型。",
            "伞式综述专用子项 C5 的 CCA 计算需要纳入综述的原始研究引用列表，超出自动范围；方法类型分布为标题 keyword 推断，不做最终分类。",
            "伞式综述专用子项 F7 仅报告就绪度——AMSTAR-2 的 16 项评分和 ROBIS 偏倚风险评估需人工或专用工具完成，本报告不代替实际质量评估。"
        ])
    write(report, pathlib.Path(a.out),
          artifact_paths={k: v for k, v in {
                         "library": a.library,
                         "benchmark": a.benchmark,
                         "gold": a.gold,
                         "query-hits": a.query_hits,
                         "search-meta": search_meta_path,
                         "candidate-snapshots": a.candidate_snapshots,
                         "query-plan": a.query_plan,
                         "source-snapshot": a.source_snapshot or a.candidate_snapshots,
                         "decision-log": a.decision_log,
                         "deduplication-log": a.deduplication_log,
                         "evidence-manifest": a.evidence_manifest,
                         "run-log": a.run_log,
                         "context": a.context}.items() if v is not None})


if __name__ == "__main__":
    main()
