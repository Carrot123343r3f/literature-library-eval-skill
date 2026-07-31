"""Workflow input/output contracts.

This layer is deliberately stricter than individual scripts: a node may run
only when its declared inputs exist, and it may be marked complete only after
its declared artifacts have been produced.
"""
from __future__ import annotations

import pathlib

try:
    from audit_core.contracts import validate_run_config as _validate_run_config
except ImportError:  # pragma: no cover - direct package execution
    from ..audit_core.contracts import validate_run_config as _validate_run_config


STAGE_CONTRACTS = {
    "optimization_contract": {"inputs": ("optimization-run/run.json",), "outputs": ("run.json",), "human_gate": False, "optional": True},
    "config_validated": {"inputs": ("run-config.json",), "outputs": ("resolved-run-config.json",), "human_gate": True, "optional": True},
    "import": {"inputs": ("library-source",), "outputs": ("import/library.json", "import/import-preview.json"), "human_gate": False},
    "metadata_enrichment": {"inputs": ("library.json", "run-config.json"), "outputs": ("enrichment/library-enriched.json", "enrichment/metadata-enrichment.json"), "human_gate": False},
    "collection": {"inputs": ("run-config.json", "query-plan.json"), "outputs": ("collection/source-snapshot.json",), "human_gate": False},
    "normalization": {"inputs": ("collection/source-snapshot.json",), "outputs": ("normalization/candidates.json", "normalization/deduplication-log.json"), "human_gate": False},
    "screening_template": {"inputs": ("normalization/candidates.json",), "outputs": ("screening/screening-decisions.json", "screening/screening-template.csv", "screening/screening-workbench.html"), "human_gate": True},
    "screening_summary": {"inputs": ("screening-decisions.json",), "outputs": ("screening/screening-summary.json",), "human_gate": True},
    "active_screen_queue": {"inputs": ("normalization/candidates.json",), "outputs": ("screening/active-screen-queue.json",), "human_gate": True},
    "citation_seed_plan": {"inputs": ("library.json",), "outputs": ("citations/citation-seeds.json",), "human_gate": False},
    "citation_discovery": {"inputs": ("citation-seed", "run-config.json"), "outputs": ("citations/citation-candidates.json", "citations/manifest.json"), "human_gate": False},
    "audit": {"inputs": ("library.json", "run-config.json"), "outputs": ("audit/audit.json", "audit/audit.html"), "human_gate": False},
    "actions": {"inputs": ("audit/audit.json",), "outputs": ("actions/next-actions.json",), "human_gate": False},
}


def validate_run_config_contract(config):
    """Return human-readable errors for the canonical run-config contract."""
    return list(_validate_run_config(config))


def validate_stage_outputs(root, stage, outputs):
    """Validate declared outputs and reject paths outside the run root."""
    root = pathlib.Path(root).resolve()
    errors = []
    for output in outputs:
        path = pathlib.Path(output).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{stage}: output escapes workflow root: {output}")
            continue
        if not path.is_file():
            errors.append(f"{stage}: missing output: {path.relative_to(root)}")
    return errors


def validate_stage_inputs(stage, inputs):
    """Validate concrete input paths before a node starts.

    Inputs may live outside the run directory (for example a user library or
    the separate optimization workspace); only their existence is enforced.
    """
    errors = []
    for item in inputs:
        if item is None:
            continue
        path = pathlib.Path(item)
        if not path.is_file():
            errors.append(f"{stage}: missing input: {path}")
    return errors


def validate_stage_contract(root, stage, outputs):
    contract = STAGE_CONTRACTS.get(stage)
    if not contract:
        return []
    errors = validate_stage_outputs(root, stage, outputs)
    root = pathlib.Path(root).resolve()
    expected = {pathlib.PurePosixPath(item).as_posix() for item in contract.get("outputs", ())}
    actual = set()
    for item in outputs:
        try:
            actual.add(pathlib.PurePosixPath(pathlib.Path(item).resolve().relative_to(root)).as_posix())
        except ValueError:
            # validate_stage_outputs already reports this escape.
            pass
    if not contract.get("optional") and expected != actual:
        errors.append(f"{stage}: declared outputs do not match contract; expected {sorted(expected)}, got {sorted(actual)}")
    return errors
