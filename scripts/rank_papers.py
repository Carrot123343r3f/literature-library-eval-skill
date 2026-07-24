#!/usr/bin/env python3
"""Rank library papers and externally discovered candidates with explicit evidence limits."""
import argparse
import datetime as dt
import json
import math
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


WEIGHTS = {
    "relevance": 0.30,
    "method_evidence": 0.25,
    "credibility": 0.15,
    "impact": 0.10,
    "recency": 0.10,
    "usability": 0.10,
}
SUPPORT_WEIGHTS = {"quality": 0.45, "topic_uniqueness": 0.25,
                   "source_diversity": 0.15, "evidence_role": 0.15}
RECOMMENDATION_WEIGHTS = {"quality": 0.55, "relevance": 0.25, "gap": 0.20}


class ExternalSearchError(RuntimeError):
    """An external top-20 must not be silently fabricated when search fails."""


def items(path):
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    raise ValueError(f"{path} must be a JSON array or an object with items[].")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def stable_ids(record):
    found = set()
    for key in ("DOI", "doi"):
        value = clean(record.get(key)).lower().replace("https://doi.org/", "")
        if value:
            found.add("doi:" + value)
    for key in ("openalex_id", "id"):
        value = clean(record.get(key))
        if value.startswith("https://openalex.org/"):
            found.add("openalex:" + value.rsplit("/", 1)[-1].lower())
    value = clean(record.get("arxiv") or record.get("arXiv"))
    if value:
        found.add("arxiv:" + value.lower())
    return found


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bounded(value):
    value = number(value)
    return None if value is None else max(0.0, min(1.0, value))


def year(record):
    value = record.get("year") or record.get("publication_year") or record.get("date")
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return int(match.group(0)) if match else None


def abstract_from_openalex(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    words = [""] * (max((max(pos) for pos in value.values() if pos), default=-1) + 1)
    for token, positions in value.items():
        for position in positions or []:
            if isinstance(position, int) and 0 <= position < len(words):
                words[position] = token
    return " ".join(words)


def text_of(record):
    return " ".join(clean(record.get(k)) for k in ("title", "abstractNote", "abstract", "keywords", "topic", "topics", "tags"))


def query_terms(context, config):
    values = list(context.get("ranking_keywords") or context.get("keywords") or [])
    pico = context.get("search_decomposition") or context.get("pico") or {}
    if isinstance(pico, dict):
        for key in ("object", "technology", "performance", "context"):
            item = pico.get(key, "")
            values.append(item.get("term", "") if isinstance(item, dict) else item)
    question = ((config.get("project") or {}).get("research_question") or context.get("research_question") or "")
    values.append(question)
    tokens = []
    for value in values:
        tokens.extend(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", clean(value).lower()))
    return sorted(set(tokens))


def relevance(record, terms, external=False):
    explicit = bounded(record.get("relevance_score"))
    if explicit is not None:
        return explicit, "provided"
    if not terms:
        return (0.60, "search_matched_baseline") if external else (None, "missing_scope_terms")
    haystack = text_of(record).lower()
    matched = sum(term in haystack for term in terms)
    if matched:
        return round(matched / len(terms), 3), "lexical_overlap"
    return (0.60, "search_matched_baseline") if external else (0.0, "lexical_overlap")


def method_evidence(record):
    value = record.get("method_evidence_score")
    if value is None and isinstance(record.get("quality_assessment"), dict):
        value = record["quality_assessment"].get("method_evidence_score")
    value = bounded(value)
    return value, "fulltext_assessed" if value is not None else "not_assessed"


def credibility(record):
    if record.get("retracted") or record.get("expression_of_concern"):
        return 0.0, "retraction_or_concern"
    explicit = bounded(record.get("credibility_score"))
    if explicit is not None:
        return explicit, "provided"
    if record.get("peer_reviewed") is True:
        return 1.0, "peer_reviewed_flag"
    if clean(record.get("publicationTitle") or record.get("venue")):
        return 0.60, "venue_metadata_only"
    return None, "missing"


def impact(record, now_year):
    cited = number(record.get("cited_by_count"))
    published = year(record)
    if cited is None or published is None:
        return None, "missing"
    annual = max(0.0, cited) / max(1, now_year - published + 1)
    return round(min(1.0, math.log1p(annual) / math.log1p(50)), 3), "age_normalized_citations"


def recency(record, now_year, window=3):
    published = year(record)
    if published is None:
        return None, "missing"
    age = max(0, now_year - published)
    return round(max(0.0, 1 - age / max(1, window * 2)), 3), f"{window}_year_window"


def usability(record):
    checks = [bool(stable_ids(record)), bool(clean(record.get("abstractNote") or record.get("abstract"))),
              bool(record.get("attachments") or record.get("open_access_url") or record.get("fulltext_url"))]
    return round(sum(checks) / len(checks), 3), "identifier_abstract_access"


def weighted(parts, weights):
    available = {key: value for key, value in parts.items() if value is not None}
    if not available:
        return None
    scale = sum(weights[key] for key in available)
    return round(sum(available[key] * weights[key] for key in available) / scale * 100, 1)


def topics(record):
    value = record.get("topics") or record.get("topic") or record.get("tags") or []
    if isinstance(value, str):
        return [clean(value)] if clean(value) else []
    return [clean(x) for x in value if clean(x)] if isinstance(value, list) else []


def score_record(record, context, config, external=False, now_year=None):
    now_year = now_year or dt.date.today().year
    terms = query_terms(context, config)
    r, r_status = relevance(record, terms, external)
    m, m_status = method_evidence(record)
    c, c_status = credibility(record)
    i, i_status = impact(record, now_year)
    recent, recent_status = recency(record, now_year)
    u, u_status = usability(record)
    components = {"relevance": r, "method_evidence": m, "credibility": c,
                  "impact": i, "recency": recent, "usability": u}
    score = weighted(components, WEIGHTS)
    evidence = "fulltext_assessed" if m is not None else "metadata_only"
    return {
        "title": clean(record.get("title")) or "Untitled",
        "year": year(record), "doi": clean(record.get("DOI") or record.get("doi")),
        "openalex_id": clean(record.get("openalex_id") or record.get("id")),
        "source": clean(record.get("source") or record.get("source_database")),
        "venue": clean(record.get("publicationTitle") or record.get("venue")),
        "citation_count": int(number(record.get("cited_by_count")) or 0),
        "topics": topics(record), "quality_score": score, "evidence_status": evidence,
        "evidence_role_score": bounded(record.get("evidence_role_score")),
        "components": components,
        "component_evidence": {"relevance": r_status, "method_evidence": m_status,
                                "credibility": c_status, "impact": i_status,
                                "recency": recent_status, "usability": u_status},
        "limitations": (["未提供全文方法学评价；方法与证据强度未计入总分。"] if m is None else [])
    }


def add_support_scores(ranked):
    topic_counts = {}
    source_counts = {}
    for row in ranked:
        for topic in row["topics"]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if row["source"]:
            source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
    for row in ranked:
        uniqueness = max((1 / topic_counts[t] for t in row["topics"]), default=None)
        diversity = 1 / source_counts[row["source"]] if row["source"] else None
        role = bounded(row.get("evidence_role_score"))
        parts = {"quality": (row["quality_score"] / 100 if row["quality_score"] is not None else None),
                 "topic_uniqueness": uniqueness, "source_diversity": diversity, "evidence_role": role}
        row["core_support_score"] = weighted(parts, SUPPORT_WEIGHTS)
        row["core_support_components"] = parts
        if uniqueness is None:
            row["limitations"].append("未提供文章级主题标签，核心支撑排序无法评估主题填补价值。")
    return ranked


def recommend(external_rows, library_rows):
    covered_topics = {topic for row in library_rows for topic in row["topics"]}
    for row in external_rows:
        gap = (sum(topic not in covered_topics for topic in row["topics"]) / len(row["topics"]) if row["topics"] else None)
        parts = {"quality": row["quality_score"] / 100 if row["quality_score"] is not None else None,
                 "relevance": row["components"]["relevance"], "gap": gap}
        row["inclusion_priority_score"] = weighted(parts, RECOMMENDATION_WEIGHTS)
        row["inclusion_priority_components"] = parts
        row["recommendation_status"] = "candidate_discovery"
        row["limitations"].append("外部检索候选尚未经过纳入/排除筛选，不得视为已纳入文献。")
    return external_rows


def authorized(config):
    automation = config.get("automation") or {}
    if automation.get("allow_search") is not True:
        raise ExternalSearchError("External ranking requires automation.allow_search=true.")
    sources = automation.get("allowed_sources")
    if sources is not None and "openalex" not in {str(x).lower() for x in sources}:
        raise ExternalSearchError("OpenAlex is not authorized by automation.allowed_sources.")


def query_for(config, context):
    question = clean((config.get("project") or {}).get("research_question") or context.get("research_question"))
    if not question:
        question = " ".join(context.get("ranking_keywords") or context.get("keywords") or [])
    if not question:
        raise ExternalSearchError("External ranking needs project.research_question or context.ranking_keywords.")
    return question


def openalex_search(query, limit):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per-page": limit, "sort": "cited_by_count:desc"})
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ExternalSearchError(f"OpenAlex search failed: {exc}") from exc
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ExternalSearchError("OpenAlex returned no usable result list.")
    return [{"title": work.get("title"), "DOI": clean(work.get("doi")).replace("https://doi.org/", ""),
             "openalex_id": work.get("id"), "publication_year": work.get("publication_year"),
             "cited_by_count": work.get("cited_by_count"), "publicationTitle": clean((work.get("primary_location") or {}).get("source", {}).get("display_name")),
             "open_access_url": (work.get("open_access") or {}).get("oa_url"),
             "abstract": abstract_from_openalex(work.get("abstract_inverted_index")), "source": "openalex"}
            for work in results]


def remove_library_duplicates(candidates, library):
    ids = set().union(*(stable_ids(row) for row in library)) if library else set()
    titles = {norm(row.get("title")) for row in library if norm(row.get("title"))}
    result, seen = [], set()
    for row in candidates:
        key = next(iter(stable_ids(row)), "") or norm(row.get("title"))
        if not key or key in seen or stable_ids(row) & ids or norm(row.get("title")) in titles:
            continue
        seen.add(key); result.append(row)
    return result


def cell(value):
    return clean(value).replace("|", "\\|")


def table(rows, score_key):
    lines = ["| 排名 | 文章 | 年份 | 分数 | 证据等级 | 关键依据 |", "| --- | --- | --- | --- | --- | --- |"]
    for index, row in enumerate(rows, 1):
        component_key = {"quality_score": "components", "core_support_score": "core_support_components",
                         "inclusion_priority_score": "inclusion_priority_components"}[score_key]
        parts = row.get(component_key, {})
        evidence = ", ".join(f"{key}={value:.2f}" for key, value in parts.items() if isinstance(value, (int, float))) or "缺少可评分证据"
        lines.append(f"| {index} | {cell(row['title'])} | {row.get('year') or '—'} | {row.get(score_key) if row.get(score_key) is not None else '—'} | {row.get('evidence_status')} | {cell(evidence)} |")
    return "\n".join(lines)


def render(report):
    top_quality = report["library_top_quality"]
    core = report["library_core_support"]
    external = report["external_recommendations"]
    md = ["# 单篇文献价值评估与补库建议", "",
          "## 结论", "",
          f"库内共评估 {report['library_record_count']} 篇；外部候选去重后 {report['external_candidate_count']} 篇。",
          "单篇质量、核心支撑和补库优先级是不同排序，均不能替代人工纳入决定。", "",
          "## 库内 Top 20：单篇质量", "", table(top_quality, "quality_score"), "",
          "## 库内 Top 20：核心支撑", "", table(core, "core_support_score"), "",
          "## 外部 Top 20：建议补库候选", "", table(external, "inclusion_priority_score"), "",
          "## 评分口径与边界", "",
          "- 单篇质量权重：研究问题匹配度 30%、方法与证据 25%、可信度 15%、年龄归一化影响力 10%、时效 10%、可用性 10%。缺失维度不以零替代，已按可用维度重新归一化。",
          "- 核心支撑衡量该论文对当前库的边际贡献：主题独特性、来源多样性和证据角色；它不是引用量排名。",
          "- 外部候选仅是候选发现层。没有通过标题/摘要/全文筛选前，不能作为正式纳入项或饱和度证据。",
          "- 只有元数据时，方法与证据强度未评分，结果必须按 metadata_only 解读。"]
    markdown = "\n".join(md) + "\n"
    from run_audit import _report_html
    return markdown, _report_html(markdown)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--run-config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--external-candidates", help="Saved external candidate snapshot; skips network only because evidence is supplied.")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.top_n <= 100:
        parser.error("--top-n must be between 1 and 100")
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    try:
        library, context = items(args.library), json.loads(pathlib.Path(args.context).read_text(encoding="utf-8"))
        config = json.loads(pathlib.Path(args.run_config).read_text(encoding="utf-8"))
        library_rows = [score_record(row, context, config) for row in library if isinstance(row, dict)]
        add_support_scores(library_rows)
        if args.external_candidates:
            candidates = items(args.external_candidates)
            external_source = "provided_snapshot"
        else:
            authorized(config)
            query = query_for(config, context)
            candidates = openalex_search(query, max(50, args.top_n * 3))
            external_source = "openalex_live"
        candidates = remove_library_duplicates(candidates, library)
        external_rows = [score_record(row, context, config, external=True) for row in candidates if isinstance(row, dict)]
        recommend(external_rows, library_rows)
        library_quality = sorted(library_rows, key=lambda row: (row["quality_score"] is not None, row["quality_score"] or -1), reverse=True)[:args.top_n]
        core = sorted(library_rows, key=lambda row: (row["core_support_score"] is not None, row["core_support_score"] or -1), reverse=True)[:args.top_n]
        recommendations = sorted(external_rows, key=lambda row: (row["inclusion_priority_score"] is not None, row["inclusion_priority_score"] or -1), reverse=True)[:args.top_n]
        report = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                  "module": "paper-value-ranking", "external_source": external_source,
                  "weights": {"quality": WEIGHTS, "core_support": SUPPORT_WEIGHTS, "recommendation": RECOMMENDATION_WEIGHTS},
                  "library_record_count": len(library_rows), "external_candidate_count": len(external_rows),
                  "library_top_quality": library_quality, "library_core_support": core, "external_recommendations": recommendations}
        markdown, rendered = render(report)
        (out / "paper-ranking.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "paper-ranking.md").write_text(markdown, encoding="utf-8")
        (out / "paper-ranking.html").write_text(rendered, encoding="utf-8")
        print(f"Ranked {len(library_rows)} library records and {len(external_rows)} external candidates.")
    except (ValueError, ExternalSearchError) as exc:
        error = {"module": "paper-value-ranking", "status": "error", "message": str(exc)}
        (out / "paper-ranking-error.json").write_text(json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
