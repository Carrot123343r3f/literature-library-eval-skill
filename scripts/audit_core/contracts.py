"""Public-input validation and safe rendering primitives shared by workflows."""
import json
import pathlib
import re


SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "api_key", "apikey", "authorization",
    "credential",
)


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
        return pathlib.PurePath(value).name or "[LOCAL_PATH]"
    return value


def validate_run_config(rc):
    """Validate the shared v1.0 run-config contract without optional packages."""
    errors = []
    if not isinstance(rc, dict):
        return ["run-config must be a JSON object"]
    if rc.get("schema_version") != "1.0":
        errors.append(f"schema_version: expected '1.0', got {rc.get('schema_version')!r}")

    for field in ("project", "library", "automation", "output"):
        if field not in rc:
            errors.append(f"Missing required top-level field: '{field}'")
        elif not isinstance(rc[field], dict):
            errors.append(f"'{field}' must be an object, got {type(rc[field]).__name__}")

    project = rc.get("project", {})
    if isinstance(project, dict):
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

    library = rc.get("library", {})
    if isinstance(library, dict):
        if not isinstance(library.get("provided"), bool):
            errors.append("library.provided is required and must be boolean")
        if library.get("provided") and not library.get("path"):
            errors.append("library.path is required when library.provided is true")
        if library.get("format") not in {"json", None}:
            errors.append("library.format: v1.0 only supports json")
    else:
        errors.append("library is required and must be an object")

    automation = rc.get("automation", {})
    if isinstance(automation, dict):
        if "allow_search" not in automation:
            errors.append("automation.allow_search is required")
        elif not isinstance(automation["allow_search"], bool):
            errors.append("automation.allow_search must be boolean")
        if "allowed_sources" in automation and not isinstance(automation["allowed_sources"], list):
            errors.append("automation.allowed_sources must be an array")
    else:
        errors.append("automation is required and must be an object")

    standards = rc.get("standards", {})
    if isinstance(standards, dict):
        overrides = standards.get("user_overrides")
        if overrides is not None and not isinstance(overrides, dict):
            errors.append("standards.user_overrides must be an object")
        elif isinstance(overrides, dict):
            for key in ("b_ggr_threshold", "b_drr_threshold"):
                if key in overrides and (not isinstance(overrides[key], (int, float)) or isinstance(overrides[key], bool) or overrides[key] < 0):
                    errors.append(f"standards.user_overrides.{key} must be a non-negative number")
    if not isinstance(rc.get("output", {}), dict):
        errors.append("output is required and must be an object")
    return errors
