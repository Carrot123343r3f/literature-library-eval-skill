import datetime as dt
import math
import re

from .contracts import ELIGIBILITY, VERDICTS, clean, list_value, stable_ids, text, year

ROUTERS = {
    "algorithm_ml": ["dataset_split", "baseline_fairness", "uncertainty_reporting", "ablation"],
    "system_software": ["workload_representativeness", "environment_reporting", "baseline_fairness", "repeatability"],
    "hardware_materials": ["sample_or_repeat_count", "instrument_calibration", "uncertainty_reporting", "control_condition"],
    "field_observational": ["sampling_bias", "confounding", "measurement_validity", "external_validity"],
    "benchmark_dataset": ["data_provenance", "annotation_quality", "split_leakage", "license_and_version"],
    "review_guideline": ["search_transparency", "eligibility_criteria", "bias_assessment", "synthesis_method"],
    "qualitative_mixed": ["question_method_fit", "sampling_or_saturation", "analysis_chain", "integration"],
}


def bounded(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def scope_terms(context, config):
    scope = context.get("paper_evaluation_scope") or {}
    values = []
    for key in ("object", "technology", "performance", "context"):
        values.extend(list_value(scope.get(key)))
    values.extend(list_value(context.get("ranking_keywords") or context.get("keywords")))
    question = (config.get("project") or {}).get("research_question") or context.get("research_question") or ""
    values.append(question)
    return [term.lower() for value in values for term in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", clean(value))]


def route(record):
    declared = clean(record.get("study_type"))
    if declared in ROUTERS:
        return declared, "declared"
    haystack = text(record).lower()
    hints = {"algorithm_ml": ("dataset", "neural", "model", "algorithm"), "system_software": ("system", "workload", "latency"),
             "hardware_materials": ("material", "specimen", "calibration"), "field_observational": ("field", "survey", "case study"),
             "benchmark_dataset": ("dataset", "benchmark", "corpus"), "review_guideline": ("systematic review", "guideline", "standard"),
             "qualitative_mixed": ("interview", "qualitative", "mixed methods")}
    hits = [(kind, sum(token in haystack for token in tokens)) for kind, tokens in hints.items()]
    kind, count = max(hits, key=lambda item: item[1])
    return (kind, "inferred_low_confidence") if count else ("unclassified", "not_assessable")


def eligibility(record, terms):
    explicit = clean(record.get("eligibility_verdict"))
    if explicit in ELIGIBILITY:
        return {"verdict": explicit, "basis": "provided", "matched_terms": []}
    if not clean(record.get("title")):
        return {"verdict": "insufficient_metadata", "basis": "missing_title", "matched_terms": []}
    if not terms:
        return {"verdict": "possibly_eligible", "basis": "missing_scope_terms", "matched_terms": []}
    haystack = text(record).lower()
    matched = sorted({term for term in terms if term in haystack})
    ratio = len(matched) / len(set(terms))
    verdict = "eligible" if ratio >= .35 else "possibly_eligible" if matched else "out_of_scope"
    return {"verdict": verdict, "basis": "lexical_pre_screen", "matched_terms": matched}


def appraisal(record, study_type):
    fields = ROUTERS.get(study_type, [])
    supplied = record.get("method_appraisal") or record.get("quality_assessment") or {}
    if not isinstance(supplied, dict) or not fields:
        return {"router": study_type, "items": [], "overall": "not_assessable", "evidence_status": "metadata_only"}
    rows = []
    for field in fields:
        raw = supplied.get(field)
        if isinstance(raw, dict):
            verdict, evidence = clean(raw.get("verdict")), clean(raw.get("evidence"))
        else:
            verdict, evidence = clean(raw), ""
        verdict = verdict if verdict in VERDICTS else "not_assessable"
        rows.append({"id": field, "verdict": verdict, "evidence": evidence})
    values = [row["verdict"] for row in rows]
    overall = "fail" if "fail" in values else "concern" if "concern" in values else "pass" if values and all(v == "pass" for v in values) else "not_assessable"
    return {"router": study_type, "items": rows, "overall": overall, "evidence_status": "fulltext_assessed"}


def reproducibility(record):
    checks = {"fulltext_access": bool(record.get("attachments") or record.get("fulltext_url") or record.get("open_access_url")),
              "data_access": bool(record.get("data_url")), "code_access": bool(record.get("code_url")),
              "materials_or_protocol": bool(record.get("materials_url") or record.get("protocol_url")), "version_pinned": bool(stable_ids(record))}
    return {"checks": checks, "available_count": sum(checks.values()), "status": "metadata_checked"}


def integrity(record):
    if record.get("retracted"):
        verdict = "fail"
    elif record.get("expression_of_concern") or record.get("corrected"):
        verdict = "concern"
    else:
        verdict = "not_assessable"
    return {"verdict": verdict, "publication_status": clean(record.get("publication_status")), "version_identified": bool(stable_ids(record))}


def bibliometrics(record, now_year):
    percentile_raw = record.get("citation_normalized_percentile")
    if isinstance(percentile_raw, dict):
        percentile_raw = percentile_raw.get("value")
    percentile = bounded(percentile_raw)
    fwci = bounded(record.get("fwci"))
    cited = bounded(record.get("cited_by_count"))
    published = year(record)
    # Raw citations are preserved only as context; never used as a quality verdict.
    try:
        raw_citations = int(float(record.get("cited_by_count") or 0))
    except (TypeError, ValueError):
        raw_citations = 0
    return {"field_year_percentile": percentile, "fwci": fwci, "raw_citations": raw_citations,
            "publication_year": published, "snapshot_year": now_year, "status": "field_normalized" if percentile is not None or fwci is not None else "raw_only"}


def method_strength(appraisal_data):
    mapping = {"pass": 1.0, "concern": .45, "fail": 0.0}
    return mapping.get(appraisal_data["overall"])


def reading_priority(eligibility_data, appraisal_data, reproducibility_data, bibliometrics_data):
    if eligibility_data["verdict"] != "eligible":
        return {"label": "not_ranked", "score": None, "reason": "not_eligible", "components": {}}
    method = method_strength(appraisal_data)
    impact = bibliometrics_data["field_year_percentile"]
    reproducible = reproducibility_data["available_count"] / 5
    if method is None:
        # Metadata may guide reading order but may not be named quality.
        score = round((impact if impact is not None else 0.5) * .6 + reproducible * .4, 3)
        return {"label": "metadata_priority", "score": score, "reason": "method_not_fulltext_assessed",
                "components": {"impact_signal": round((impact if impact is not None else 0.5) * .6, 3),
                               "reproducibility_signal": round(reproducible * .4, 3),
                               "method_signal": None}, "confidence": "low"}
    score = round(method * .65 + reproducible * .20 + (impact if impact is not None else .5) * .15, 3)
    return {"label": "reading_priority", "score": score, "reason": "eligible_and_design_appraised",
            "components": {"method_signal": round(method * .65, 3),
                           "reproducibility_signal": round(reproducible * .20, 3),
                           "impact_signal": round((impact if impact is not None else .5) * .15, 3)},
            "confidence": "moderate" if impact is None else "higher"}


def evaluate_record(record, context, config, external=False, now_year=None):
    now_year = now_year or dt.date.today().year
    elig = eligibility(record, scope_terms(context, config))
    study_type, route_confidence = route(record)
    method = appraisal(record, study_type)
    repro = reproducibility(record)
    integ = integrity(record)
    biblio = bibliometrics(record, now_year)
    priority = reading_priority(elig, method, repro, biblio)
    roles = list_value(record.get("evidence_roles") or record.get("evidence_role"))
    return {"title": clean(record.get("title")) or "Untitled", "year": year(record), "doi": clean(record.get("DOI") or record.get("doi")),
            "openalex_id": clean(record.get("openalex_id") or record.get("id")), "source": clean(record.get("source") or record.get("source_database")),
            "topics": list_value(record.get("topics") or record.get("topic") or record.get("tags")), "evidence_roles": roles,
            "eligibility": elig, "study_type": study_type, "study_type_evidence": route_confidence,
            "method_appraisal": method, "reproducibility": repro, "integrity": integ, "bibliometric_signals": biblio,
            "reading_priority": priority, "external_candidate_status": "candidate_discovery" if external else None,
            "limitations": (["外部候选尚未经过正式筛选。"] if external else []) + (["未提供全文级方法学评价。"] if method["overall"] == "not_assessable" else [])}


def add_contribution(rows):
    topic_counts = {}; role_counts = {}; source_counts = {}
    for row in rows:
        for topic in row["topics"]: topic_counts[topic] = topic_counts.get(topic, 0) + 1
        for role in row["evidence_roles"]: role_counts[role] = role_counts.get(role, 0) + 1
        if row["source"]: source_counts[row["source"]] = source_counts.get(row["source"], 0) + 1
    for row in rows:
        unique_topics = [topic for topic in row["topics"] if topic_counts.get(topic) == 1]
        unique_roles = [role for role in row["evidence_roles"] if role_counts.get(role) == 1]
        source_unique = bool(row["source"] and source_counts.get(row["source"]) == 1)
        score = len(unique_topics) * 2 + len(unique_roles) * 3 + int(source_unique)
        if row["method_appraisal"]["overall"] == "pass": score += 1
        tier = "core" if score >= 4 else "supporting" if score else "not_assessable"
        row["review_contribution"] = {"topic_gap_if_removed": unique_topics, "unique_roles": unique_roles,
                                      "independent_source_support": source_unique, "substitutability": "low" if score >= 4 else "medium" if score else "unknown",
                                      "core_support_tier": tier, "rank_signal": score}
    return rows


def recommend(external, library):
    covered = {topic for row in library for topic in row["topics"]}
    for row in external:
        new_topics = [topic for topic in row["topics"] if topic not in covered]
        relevance = len(row["eligibility"]["matched_terms"])
        row["recommendation"] = {"status": "candidate_discovery", "new_topics": new_topics,
                                  "rank_signal": len(new_topics) * 3 + relevance,
                                  "screening_required": True}
    return external
