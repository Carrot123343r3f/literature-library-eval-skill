"""Public-input validation and safe rendering primitives shared by workflows."""
import datetime as dt
import json
import pathlib
import re


SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "api_key", "apikey", "authorization",
    "credential", "cookie",
)
SENSITIVE_VALUE_RE = re.compile(r"(?i)((?:api[_-]?key|token|secret|password|authorization|credential|cookie)\s*[=:]\s*)([^&\s,;]+)")
EMBEDDED_LOCAL_PATH_RE = re.compile(r"(?<![\w])(?:[A-Za-z]:[\\/]|/)[^\s\"']+")
ISO_LANGUAGE_CODES = {"all", "ar", "bn", "cs", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "hu", "id", "it", "ja", "ko", "nl", "no", "pl", "pt", "ro", "ru", "sv", "th", "tr", "uk", "ur", "vi", "zh"}

INDICATOR_VERDICTS = {"pass", "warning", "fail", "screening", "not_assessable"}
INDICATOR_EVIDENCE_STATUSES = {
    "measured", "estimated", "automated-screening",
    "manual-verification-required", "not_assessable",
}
EVIDENCE_STATUS_ALIASES = {
    "screening": "automated-screening",
    "discovery_only": "automated-screening",
    "candidate_discovery": "automated-screening",
    "partial_snapshot": "estimated",
    "estimated_lower_bound": "estimated",
    "warning (year_completeness < 50%)": "measured",
    "automated-screening (DOI-only)": "automated-screening",
    "estimated (open links only)": "estimated",
    "structured_no_decisions": "manual-verification-required",
    "provenance_only (no decision log)": "manual-verification-required",
}


def reconcile_indicator_evidence(verdict, evidence_status):
    """Apply the non-negotiable verdict/evidence semantics for one row."""
    if verdict == "not_assessable":
        return "not_assessable"
    return EVIDENCE_STATUS_ALIASES.get(evidence_status, evidence_status)


def indicator_evidence_qualifier(evidence_status):
    """Preserve a source-specific data state without polluting the core enum."""
    normalized = EVIDENCE_STATUS_ALIASES.get(evidence_status, evidence_status)
    return evidence_status if evidence_status != normalized else None


def validate_indicator_evidence(rows):
    """Return semantic-contract errors for indicator-register rows."""
    errors = []
    for row in rows:
        identifier = row.get("subproject", "<unknown>")
        verdict = row.get("meets_standard")
        evidence = row.get("evidence_status")
        if verdict not in INDICATOR_VERDICTS:
            errors.append(f"{identifier}: unsupported verdict {verdict!r}")
            continue
        if evidence not in INDICATOR_EVIDENCE_STATUSES:
            errors.append(f"{identifier}: unsupported evidence status {evidence!r}")
            continue
        if verdict == "not_assessable" and evidence != "not_assessable":
            errors.append(f"{identifier}: not_assessable verdict requires not_assessable evidence")
        elif verdict in {"pass", "warning", "fail"} and evidence == "not_assessable":
            errors.append(f"{identifier}: {verdict} verdict cannot use not_assessable evidence")
    return errors


def compact(value):
    """Convert a report cell to a safe, single-line Markdown-table value."""
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).replace("|", "／").replace("\n", " ")


def is_absolute_local_path(value):
    """Recognise Windows and POSIX absolute paths without resolving them."""
    return isinstance(value, str) and bool(re.match(r"^(?:[A-Za-z]:[\\/]|/|\\\\)", value.strip()))


def public_value(value, key=""):
    """Recursively redact secrets and absolute local paths before persistence."""
    key_lower = str(key).casefold()
    if any(part in key_lower for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): public_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [public_value(v, key) for v in value]
    if is_absolute_local_path(value):
        # PurePath follows the host OS. Use Windows parsing explicitly so a
        # Windows path is safely redacted when the audit runs on Linux CI.
        return pathlib.PureWindowsPath(value).name or "[LOCAL_PATH]"
    if isinstance(value, str):
        value = SENSITIVE_VALUE_RE.sub(r"\1[REDACTED]", value)
        return EMBEDDED_LOCAL_PATH_RE.sub("[LOCAL_PATH]", value)
    return value


def validate_run_config(rc):
    """Validate the shared v1.0 run-config contract without optional packages."""
    errors = []
    if not isinstance(rc, dict):
        return ["run-config must be a JSON object"]
    if rc.get("schema_version") != "1.0":
        errors.append(f"schema_version: expected '1.0', got {rc.get('schema_version')!r}")

    allowed_top = {"schema_version", "project", "library", "automation", "evidence_inputs",
                   "standards", "output", "paper_evaluation", "optimization", "quality",
                   "generated_by", "generated_at"}
    errors.extend(f"unknown top-level field: {key}" for key in sorted(set(rc) - allowed_top))
    for field in ("project", "library", "automation", "output"):
        if field not in rc:
            errors.append(f"Missing required top-level field: '{field}'")
        elif not isinstance(rc[field], dict):
            errors.append(f"'{field}' must be an object, got {type(rc[field]).__name__}")

    project = rc.get("project", {})
    if isinstance(project, dict):
        allowed_project = {"research_question", "review_type", "engineering_profile", "scope_status",
                           "scope_rationale", "time_range", "languages", "allowed_assessment_level"}
        errors.extend(f"unknown project field: {key}" for key in sorted(set(project) - allowed_project))
        question = project.get("research_question")
        if not isinstance(question, str) or not question.strip():
            errors.append("project.research_question is required (non-empty string)")
        review_type = project.get("review_type")
        valid_review_types = {"narrative", "systematic", "scoping", "rapid", "umbrella",
                              "叙事综述", "系统综述", "范围综述", "快速综述", "伞式综述"}
        if not isinstance(review_type, str) or not review_type:
            errors.append("project.review_type is required (non-empty string)")
        elif review_type not in valid_review_types:
            errors.append(f"project.review_type: must be one of {valid_review_types}, got {review_type!r}")
        scope_status = project.get("scope_status")
        valid_scope = {"in_scope", "cross_domain", "out_of_scope", "scope_uncertain"}
        if not isinstance(scope_status, str) or not scope_status:
            errors.append("project.scope_status is required (non-empty string)")
        elif scope_status not in valid_scope:
            errors.append(f"project.scope_status: must be one of {valid_scope}, got {scope_status!r}")
        level = project.get("allowed_assessment_level")
        if level and level not in {"full", "limited_metadata_only", "stop"}:
            errors.append(f"project.allowed_assessment_level is invalid: {level!r}")
        time_range = project.get("time_range")
        if time_range is not None:
            if not isinstance(time_range, dict):
                errors.append("project.time_range must be an object")
            else:
                start, end = time_range.get("start"), time_range.get("end")
                current_year = dt.date.today().year
                if start is not None and (not isinstance(start, int) or start < 1900 or start > current_year):
                    errors.append("project.time_range.start must be a year from 1900 through the current year")
                if end is not None and (not isinstance(end, int) or end < 1900 or end > current_year):
                    errors.append("project.time_range.end must be a year from 1900 through the current year")
                if isinstance(start, int) and isinstance(end, int) and start > end:
                    errors.append("project.time_range.start cannot be later than project.time_range.end")
        languages = project.get("languages")
        if languages is not None:
            if not isinstance(languages, list) or not languages:
                errors.append("project.languages must be a non-empty array")
            elif any(not isinstance(language, str) or language.casefold() not in ISO_LANGUAGE_CODES for language in languages):
                errors.append("project.languages must contain supported ISO language codes or 'all'")

    library = rc.get("library", {})
    if isinstance(library, dict):
        allowed_library = {"provided", "path", "format", "record_count", "normalization_required"}
        errors.extend(f"unknown library field: {key}" for key in sorted(set(library) - allowed_library))
        if not isinstance(library.get("provided"), bool):
            errors.append("library.provided is required and must be boolean")
        if library.get("provided") and not library.get("path"):
            errors.append("library.path is required when library.provided is true")
        if library.get("format") not in {"json", "csv", "ris", "bibtex", None}:
            errors.append("library.format: must be json, csv, ris, bibtex, or null")
    else:
        errors.append("library is required and must be an object")

    automation = rc.get("automation", {})
    if isinstance(automation, dict):
        allowed_automation = {"allow_search", "allow_metadata_enrichment", "allow_external_discovery",
                              "allow_citation_tracking", "local_only_confirmed", "allow_query_refinement",
                              "allowed_sources", "authorized_sources", "stop_conditions"}
        errors.extend(f"unknown automation field: {key}" for key in sorted(set(automation) - allowed_automation))
        if "allow_search" not in automation:
            errors.append("automation.allow_search is required")
        elif not isinstance(automation["allow_search"], bool):
            errors.append("automation.allow_search must be boolean")
        for permission in ("allow_metadata_enrichment", "allow_external_discovery", "allow_citation_tracking"):
            if permission in automation and not isinstance(automation[permission], bool):
                errors.append(f"automation.{permission} must be boolean")
        if automation.get("local_only_confirmed") is True and any(
                automation.get(permission) is True
                for permission in ("allow_search", "allow_metadata_enrichment", "allow_external_discovery", "allow_citation_tracking")):
            errors.append("automation.local_only_confirmed cannot coexist with online permissions")
        if automation.get("allow_search") is not True and any(
                automation.get(permission) is True
                for permission in ("allow_metadata_enrichment", "allow_external_discovery", "allow_citation_tracking")):
            errors.append("online capability permissions require automation.allow_search=true")
        allowed_sources = automation.get("allowed_sources", [])
        supported_sources = {"openalex", "crossref", "arxiv", "europepmc"}
        if "allowed_sources" not in automation:
            errors.append("automation.allowed_sources is required")
        elif not isinstance(allowed_sources, list):
            errors.append("automation.allowed_sources must be an array")
        elif any(not isinstance(source, str) or source.casefold() not in supported_sources for source in allowed_sources):
            errors.append("automation.allowed_sources contains an unsupported source")
    else:
        errors.append("automation is required and must be an object")

    evidence = rc.get("evidence_inputs", {})
    if evidence is not None:
        if not isinstance(evidence, dict):
            errors.append("evidence_inputs must be an object")
        else:
            allowed_evidence = {"benchmark", "gold", "query_log", "query_hits", "query_plan",
                                "source_snapshot", "screening_decisions", "deduplication_log",
                                "search_meta", "screening_summary", "search_iterations", "failed_sources"}
            errors.extend(f"unknown evidence_inputs field: {key}" for key in sorted(set(evidence) - allowed_evidence))
            for key, value in evidence.items():
                if key == "failed_sources":
                    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                        errors.append("evidence_inputs.failed_sources must be an array of strings")
                elif value is not None and not isinstance(value, str):
                    errors.append(f"evidence_inputs.{key} must be a string or null")

    standards = rc.get("standards", {})
    if isinstance(standards, dict):
        overrides = standards.get("user_overrides")
        if overrides is not None and not isinstance(overrides, dict):
            errors.append("standards.user_overrides must be an object")
        elif isinstance(overrides, dict):
            for key in ("b_ggr_threshold", "b_drr_threshold"):
                if key in overrides and (not isinstance(overrides[key], (int, float)) or isinstance(overrides[key], bool) or overrides[key] < 0):
                    errors.append(f"standards.user_overrides.{key} must be a non-negative number")
    output = rc.get("output", {})
    if not isinstance(output, dict):
        errors.append("output is required and must be an object")
    else:
        allowed_output = {"language", "formats", "include_standards_appendix"}
        errors.extend(f"unknown output field: {key}" for key in sorted(set(output) - allowed_output))
        formats = output.get("formats", ["html", "json"])
        if not isinstance(formats, list) or not formats or any(item not in {"html", "json"} for item in formats):
            errors.append("output.formats must contain only html and/or json; Markdown output is not supported")
        if "language" in output and not isinstance(output["language"], str):
            errors.append("output.language must be a string")
    return errors


def validate_context(context):
    """Validate typed, conclusion-bearing context claims.

    Extra descriptive fields remain allowed, but claims used by the audit must
    be well formed. Their provenance is verified by the calling workflow.
    """
    if not isinstance(context, dict):
        return ["context must be a JSON object"]
    errors = []
    for field in ("scope_status", "review_type", "profile"):
        if field in context and context[field] is not None and not isinstance(context[field], str):
            errors.append(f"context.{field} must be a string")
    for field in ("search_rounds", "independent_pathways", "source_marginal_yields", "planned_pathways"):
        if field in context and not isinstance(context[field], list):
            errors.append(f"context.{field} must be an array")
    for field in ("independent_validation_passed", "run_log_complete"):
        if field in context and not isinstance(context[field], bool):
            errors.append(f"context.{field} must be boolean when supplied")
    if "standards" in context and not isinstance(context["standards"], dict):
        errors.append("context.standards must be an object")
    if "output_language" in context and not isinstance(context["output_language"], str):
        errors.append("context.output_language must be a string")
    metadata = context.get("gold_set_metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("context.gold_set_metadata must be an object")
    elif isinstance(metadata, dict):
        for field in ("validation_set_source", "independence_rationale", "validation_set_frozen_at"):
            if field in metadata and not isinstance(metadata[field], str):
                errors.append(f"context.gold_set_metadata.{field} must be a string")
        for field in ("dev_validation_overlap_check", "validation_set_frozen"):
            if field in metadata and not isinstance(metadata[field], bool):
                errors.append(f"context.gold_set_metadata.{field} must be boolean")
    return errors
