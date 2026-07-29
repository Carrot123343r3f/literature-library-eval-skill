#!/usr/bin/env python3
"""Guided, resumable orchestration for import → collect → screen → audit → actions."""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys

try:
    from scripts.lle_core.contracts import validate_run_config_contract, validate_stage_contract
    from scripts.lle_core.runtime import WorkflowContext
    from scripts.lle_core.state_machine import can_advance
except ImportError:  # direct execution with scripts/ on sys.path
    from lle_core.contracts import validate_run_config_contract, validate_stage_contract
    from lle_core.runtime import WorkflowContext
    from lle_core.state_machine import can_advance

ROOT = pathlib.Path(__file__).resolve().parent
SUPPORTED_SOURCES = {"openalex", "crossref", "arxiv", "europepmc"}


def signature(args):
    values = {}
    for key, value in vars(args).items():
        if key in {"out", "resume", "force", "command"} or not value: continue
        path = pathlib.Path(str(value))
        values[key] = {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} if path.is_file() else str(value)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


def state_path(out): return out / "workflow-state.json"


def load_state(out, run_signature, resume, force):
    if resume and state_path(out).is_file() and not force:
        old = json.loads(state_path(out).read_text(encoding="utf-8"))
        if old.get("run_signature") == run_signature: return old.get("steps", {})
        raise SystemExit("ERROR: inputs changed since the saved workflow. Re-run without --resume or use --force.")
    return {}


def write_state(out, steps, run_signature, message=""):
    path = state_path(out)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if existing.get("schema_version") == "2.0":
        merged_steps = dict(existing.get("steps") or {})
        merged_steps.update(steps)
        existing.update({"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                         "run_signature": run_signature, "steps": merged_steps, "message": message})
        payload = existing
    else:
        payload = {"schema_version": "1.1", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "run_signature": run_signature, "steps": steps, "message": message}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


STEP_STAGES = {
    "optimization_contract": "config_validated", "import": "library_ready",
    "metadata_enrichment": "library_ready", "collection": "collection_ready",
    "normalization": "collection_ready", "screening_template": "screening_ready",
    "citation_seed_plan": "library_ready",
    "active_screen_queue": "screening_ready", "screening_summary": "screening_ready",
    "citation_discovery": "collection_ready", "audit": "audit_ready", "actions": "completed",
}


def sync_kernel_state(out, steps, run_signature, name, outputs=None, failed=None):
    """Mirror legacy step state into the architecture kernel and artifact ledger."""
    context = WorkflowContext.open(out, run_signature, resume=True, force=True)
    context.state.steps.update(steps)
    if failed:
        context.fail(name, failed)
        return
    output_paths = [pathlib.Path(item) for item in (outputs or [])]
    # The optimization workspace is an external, validated input. It is not
    # copied into the audit run and therefore must not enter its artifact tree.
    if name == "optimization_contract":
        context.state.steps[name] = "complete"
        context.persist()
        return
    errors = validate_stage_contract(out, name, output_paths)
    if errors:
        context.fail(name, "; ".join(errors))
        raise SystemExit("ERROR: " + "; ".join(errors))
    context.complete_step(name, output_paths)
    target = STEP_STAGES.get(name)
    if target and can_advance(context.state.stage, target):
        context.advance(target)


def run(command, steps, name, out, run_signature, outputs, resume):
    if resume and steps.get(name) in {"complete", "reused"} and all(path.is_file() for path in outputs):
        steps[name] = "reused"; write_state(out, steps, run_signature); sync_kernel_state(out, steps, run_signature, name, outputs); return
    try:
        subprocess.run(command, check=True)
        errors = [] if name == "optimization_contract" else validate_stage_contract(out, name, [pathlib.Path(item) for item in outputs])
        if errors:
            steps[name] = "failed"; write_state(out, steps, run_signature, "; ".join(errors)); sync_kernel_state(out, steps, run_signature, name, failed="; ".join(errors)); raise SystemExit("ERROR: " + "; ".join(errors))
        steps[name] = "complete"; write_state(out, steps, run_signature); sync_kernel_state(out, steps, run_signature, name, outputs)
    except subprocess.CalledProcessError as exc:
        message = f"{name} failed with exit code {exc.returncode}"
        steps[name] = "failed"; write_state(out, steps, run_signature, message); sync_kernel_state(out, steps, run_signature, name, failed=message); raise SystemExit(exc.returncode)


def script(name): return str(ROOT / name)


def init_config_v2(args):
    """Create a local-first config in one three-question intake round."""
    question = input("Research question/title: ").strip()
    scope_answer = input("Is this an engineering review question within this skill's scope? [y/n/uncertain]: ").strip().lower()
    scope_status = {"y": "in_scope", "yes": "in_scope", "n": "out_of_scope", "no": "out_of_scope"}.get(scope_answer, "scope_uncertain")
    library = input("Library path (optional; can be imported later): ").strip()
    config = {"schema_version": "1.0", "project": {"research_question": question, "review_type": "narrative",
              "scope_status": scope_status,
              "scope_rationale": "confirmed during guided initialization" if scope_status != "scope_uncertain" else "user did not confirm engineering scope"},
              "library": {"provided": bool(library), "path": library or None, "format": "json" if library.endswith(".json") else None},
              "automation": {"allow_search": False, "allow_metadata_enrichment": False, "allow_external_discovery": False, "allow_citation_tracking": False,
                             "local_only_confirmed": False, "allowed_sources": [], "authorized_sources": []},
              "output": {"language": "zh-CN", "formats": ["html", "json"]}}
    pathlib.Path(args.out).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Created a local-first config. Review type defaults to narrative; online permissions stay disabled until explicitly enabled.")


def configure_permissions(args):
    """Record later, explicit permission choices without exposing run-config JSON."""
    path = pathlib.Path(args.run_config)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot parse run-config: {exc}")
    if not isinstance(config, dict):
        raise SystemExit("ERROR: run-config must be an object")
    errors = validate_run_config_contract(config)
    if errors:
        raise SystemExit("ERROR: invalid run-config:\n- " + "\n- ".join(errors))
    automation = config["automation"]
    enabled = [label for key, label in (
        ("allow_metadata_enrichment", "metadata enrichment"),
        ("allow_external_discovery", "external discovery"),
        ("allow_citation_tracking", "citation tracking"),
    ) if automation.get(key) is True]
    source_summary = ", ".join(automation.get("allowed_sources", [])) or "none"
    print("Current permissions: fully-local confirmed=" + ("yes" if automation.get("local_only_confirmed") else "no") +
          "; enabled=" + (", ".join(enabled) if enabled else "none") + "; sources=" + source_summary)
    local_only = input("Confirm fully local execution (disable all online capabilities)? [y/N]: ").strip().lower() in {"y", "yes"}
    if local_only:
        metadata = discovery = citations = False
        sources = authorized = []
    else:
        metadata = input("Allow online metadata enrichment? [y/N]: ").strip().lower() in {"y", "yes"}
        discovery = input("Allow online discovery of new candidate papers? [y/N]: ").strip().lower() in {"y", "yes"}
        citations = input("Allow online citation tracking? [y/N]: ").strip().lower() in {"y", "yes"}
        if any((metadata, discovery, citations)):
            sources = [item.strip().lower() for item in input("Allowed sources (default openalex,arxiv,crossref,europepmc): ").split(",") if item.strip()]
            sources = sources or ["openalex", "arxiv", "crossref", "europepmc"]
            unknown = sorted(set(sources) - SUPPORTED_SOURCES)
            if unknown:
                raise SystemExit(f"ERROR: unsupported source(s): {', '.join(unknown)}")
            authorized = [item.strip().lower() for item in input("Sources with a preconfigured legal login/connector (optional): ").split(",") if item.strip()]
        else:
            sources = authorized = []
    automation.update({"allow_search": any((metadata, discovery, citations)),
                       "allow_metadata_enrichment": metadata, "allow_external_discovery": discovery,
                       "allow_citation_tracking": citations, "local_only_confirmed": local_only,
                       "allowed_sources": sources, "authorized_sources": authorized})
    errors = validate_run_config_contract(config)
    if errors:
        raise SystemExit("ERROR: invalid permission configuration:\n- " + "\n- ".join(errors))
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print("Saved explicit local/online permission choices to run-config.")
    if discovery:
        print("Next step: run the audit with --collect --query-plan <query-plan.json> to discover candidates.")


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--out", required=True)
    permissions = sub.add_parser("configure-permissions"); permissions.add_argument("--run-config", required=True)
    status = sub.add_parser("status"); status.add_argument("--out", required=True)
    execute = sub.add_parser("run"); execute.add_argument("--run-config", required=True); execute.add_argument("--out", required=True); execute.add_argument("--library")
    for name in ("context", "benchmark", "gold", "query-hits", "run-log", "source-snapshot", "screening-decisions", "deduplication-log", "screening-summary", "search-meta", "search-iterations", "independent-pathways", "relevance-review"): execute.add_argument("--" + name)
    execute.add_argument("--query-plan"); execute.add_argument("--optimization-run", help="optimization.py workspace to validate before audit"); execute.add_argument("--active-screen-budget", type=int, help="generate a prioritized human-screening queue after normalization"); execute.add_argument("--collect", action="store_true"); execute.add_argument("--citation-seed"); execute.add_argument("--resume", action="store_true"); execute.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "init": return init_config_v2(args)
    if args.command == "configure-permissions": return configure_permissions(args)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.command == "status": print(state_path(out).read_text(encoding="utf-8") if state_path(out).exists() else "No workflow state yet."); return
    run_signature = signature(args); steps = load_state(out, run_signature, args.resume, args.force)
    try:
        config = json.loads(pathlib.Path(args.run_config).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: cannot parse run-config: {exc}")
    config_errors = validate_run_config_contract(config)
    if config_errors:
        raise SystemExit("ERROR: invalid run-config:\n- " + "\n- ".join(config_errors))
    kernel = WorkflowContext.open(out, run_signature, resume=args.resume, force=args.force)
    kernel.state.steps["config_validated"] = "complete"
    if kernel.state.stage == "created":
        kernel.advance("config_validated")
    else:
        kernel.persist()
    configured_library = config.get("library", {}).get("path")
    if args.library:
        library = pathlib.Path(args.library)
    elif configured_library:
        config_base = pathlib.Path(args.run_config).resolve().parent
        configured_path = pathlib.Path(configured_library)
        library = configured_path if configured_path.is_absolute() else config_base / configured_path
    else:
        library = pathlib.Path("")
    if not library.is_file(): raise SystemExit("ERROR: provide an existing --library or library.path in run-config.")
    # Shared product gate: a self-reported allowed_assessment_level must never
    # bypass the same evidence qualification used by the low-friction entry.
    try:
        from autopilot import audit_readiness
        project = config.get("project", {})
        scope_context = {"review_type": project.get("review_type", ""),
                         "year_start": (project.get("time_range") or {}).get("start"),
                         "year_end": (project.get("time_range") or {}).get("end"),
                         "languages": project.get("languages", []),
                         "scope_status": project.get("scope_status", "")}
        evidence = {"gold": args.gold, "query_hits": args.query_hits, "query_log": args.run_log,
                    "screening_decisions": args.screening_decisions, "search_iterations": args.search_iterations,
                    "independent_pathways": args.independent_pathways}
        _, readiness_errors, _scope_matrix = audit_readiness(library, project.get("research_question", ""), scope_context, evidence, args.relevance_review)
        if readiness_errors:
            raise SystemExit("ERROR: sufficiency audit preflight failed:\n- " + "\n- ".join(readiness_errors))
    except ImportError as exc:
        raise SystemExit(f"ERROR: shared audit preflight is unavailable: {exc}")
    canonical = library
    if library.suffix.lower() != ".json":
        imported = out / "import"; run([sys.executable, script("import_library.py"), "--input", str(library), "--out", str(imported)], steps, "import", out, run_signature, [imported / "library.json", imported / "import-preview.json"], args.resume); canonical = imported / "library.json"
        config["library"] = {"provided": True, "path": str(canonical), "format": "json", "normalization_required": False}; resolved = out / "resolved-run-config.json"; resolved.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"); args.run_config = str(resolved)
    automation = config.get("automation") or {}
    optimization_run = args.optimization_run or (config.get("optimization") or {}).get("run_root")
    if optimization_run:
        optimization_gate = [sys.executable, script("optimization.py"), "validate", "--run", optimization_run, "--strict"]
        run(optimization_gate, steps, "optimization_contract", out, run_signature, [pathlib.Path(optimization_run) / "run.json"], args.resume)
    if automation.get("allow_search") is True and automation.get("allow_metadata_enrichment", False) is True and not automation.get("local_only_confirmed", False):
        enrichment = out / "enrichment"
        run([sys.executable, script("enrich_library_metadata.py"), "--library", str(canonical), "--run-config", args.run_config, "--out", str(enrichment)], steps, "metadata_enrichment", out, run_signature, [enrichment / "library-enriched.json", enrichment / "metadata-enrichment.json"], args.resume)
        canonical = enrichment / "library-enriched.json"
    if args.collect:
        if automation.get("allow_search") is not True or automation.get("allow_external_discovery") is not True: raise SystemExit("ERROR: --collect requires automation.allow_search=true and automation.allow_external_discovery=true.")
        if not args.query_plan: raise SystemExit("ERROR: --collect requires --query-plan.")
        collection = out / "collection"; collect_command = [sys.executable, script("collect_open_sources.py"), "--run-config", args.run_config, "--plan", args.query_plan, "--out", str(collection / "source-snapshot.json")]
        if args.resume: collect_command.append("--resume")
        run(collect_command, steps, "collection", out, run_signature, [collection / "source-snapshot.json"], args.resume)
        normalized = out / "normalization"; run([sys.executable, script("normalize_candidates.py"), "--snapshot", str(collection / "source-snapshot.json"), "--out", str(normalized)], steps, "normalization", out, run_signature, [normalized / "candidates.json", normalized / "deduplication-log.json"], args.resume)
        args.source_snapshot = args.source_snapshot or str(collection / "source-snapshot.json"); args.deduplication_log = args.deduplication_log or str(normalized / "deduplication-log.json")
        screen = out / "screening"; run([sys.executable, script("screen_candidates.py"), "--candidates", str(normalized / "candidates.json"), "--out", str(screen)], steps, "screening_template", out, run_signature, [screen / "screening-decisions.json", screen / "screening-template.csv", screen / "screening-workbench.html"], args.resume)
    quality = config.get("quality") or {}
    active_budget = args.active_screen_budget if args.active_screen_budget is not None else quality.get("active_screen_budget")
    if active_budget is not None:
        normalized_candidates = out / "normalization" / "candidates.json"
        if not normalized_candidates.is_file():
            raise SystemExit("ERROR: active screening queue requires normalized candidates from --collect.")
        queue_out = out / "screening" / "active-screen-queue.json"
        run([sys.executable, script("quality_optimization.py"), "screen-queue", "--candidates", str(normalized_candidates), "--out", str(queue_out), "--budget", str(active_budget)], steps, "active_screen_queue", out, run_signature, [queue_out], args.resume)
    if args.screening_decisions:
        candidates = out / "normalization" / "candidates.json"
        if candidates.is_file():
            summary = out / "screening"; run([sys.executable, script("summarize_screening.py"), "--candidates", str(candidates), "--decisions", args.screening_decisions, "--out", str(summary)], steps, "screening_summary", out, run_signature, [summary / "screening-summary.json"], args.resume); args.screening_summary = args.screening_summary or str(summary / "screening-summary.json")
    # Citation expansion is a built-in candidate-discovery path.  A user seed
    # is preferred, but a deterministic plan is created from the library and
    # first-round candidates when no seed was supplied.
    citations = out / "citations"; citation_candidates = out / "normalization" / "candidates.json"
    seed_command = [sys.executable, script("citation_seed_plan.py"), "--library", str(canonical), "--out", str(citations / "citation-seeds.json")]
    if citation_candidates.is_file(): seed_command.extend(["--candidates", str(citation_candidates)])
    if args.citation_seed: seed_command.extend(["--user-seed", args.citation_seed])
    run(seed_command, steps, "citation_seed_plan", out, run_signature, [citations / "citation-seeds.json"], args.resume)
    if automation.get("allow_search") is True and automation.get("allow_citation_tracking") is True:
        run([sys.executable, script("citation_candidates.py"), "--seed", str(citations / "citation-seeds.json"), "--run-config", args.run_config, "--out", str(citations)], steps, "citation_discovery", out, run_signature, [citations / "citation-candidates.json", citations / "manifest.json"], args.resume)
    audit = out / "audit"; command = [sys.executable, script("run_audit.py"), "--library", str(canonical), "--out", str(audit), "--run-config", args.run_config,
                                        "--citation-seed-plan", str(citations / "citation-seeds.json")]
    discovered_citations = citations / "citation-candidates.json"
    if discovered_citations.is_file():
        command.extend(["--citation-discovery", str(discovered_citations)])
    for flag, value in (("--context", args.context), ("--benchmark", args.benchmark), ("--gold", args.gold), ("--query-hits", args.query_hits), ("--run-log", args.run_log), ("--candidate-snapshots", args.source_snapshot), ("--decision-log", args.screening_decisions), ("--deduplication-log", args.deduplication_log), ("--screening-summary", args.screening_summary), ("--search-meta", args.search_meta), ("--search-iterations", args.search_iterations)):
        if value: command.extend([flag, value])
    run(command, steps, "audit", out, run_signature, [audit / "audit.json", audit / "audit.html"], args.resume)
    run([sys.executable, script("next_actions.py"), "--audit", str(audit / "audit.json"), "--out", str(out)], steps, "actions", out, run_signature, [out / "next-actions.json"], args.resume)


if __name__ == "__main__": main()
