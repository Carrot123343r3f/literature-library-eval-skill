#!/usr/bin/env python3
"""Guided, resumable orchestration for import → collect → screen → audit → actions."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def signature(args):
    values = {key: str(value) for key, value in vars(args).items() if key not in {"out", "resume", "force", "command"} and value}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()


def state_path(out): return out / "workflow-state.json"


def load_state(out, run_signature, resume, force):
    if resume and state_path(out).is_file() and not force:
        old = json.loads(state_path(out).read_text(encoding="utf-8"))
        if old.get("run_signature") == run_signature: return old.get("steps", {})
        raise SystemExit("ERROR: inputs changed since the saved workflow. Re-run without --resume or use --force.")
    return {}


def write_state(out, steps, run_signature, message=""):
    payload = {"schema_version": "1.1", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "run_signature": run_signature, "steps": steps, "message": message}
    state_path(out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(command, steps, name, out, run_signature, outputs, resume):
    if resume and steps.get(name) == "complete" and all(path.is_file() for path in outputs):
        steps[name] = "reused"; write_state(out, steps, run_signature); return
    try:
        subprocess.run(command, check=True); steps[name] = "complete"; write_state(out, steps, run_signature)
    except subprocess.CalledProcessError as exc:
        steps[name] = "failed"; write_state(out, steps, run_signature, f"{name} failed with exit code {exc.returncode}"); raise SystemExit(exc.returncode)


def script(name): return str(ROOT / name)


def init_config_v2(args):
    """Create a user-confirmed config with online enrichment enabled by default."""
    question = input("Research question/title: ").strip()
    review_type = input("Review type [narrative/systematic/scoping/rapid/umbrella] (default narrative): ").strip() or "narrative"
    library = input("Library path (optional; can be imported later): ").strip()
    allow = input("Allow AI to enrich metadata online? [Y/n]: ").strip().lower() not in {"n", "no"}
    discover = input("Allow online discovery of new candidate papers? [y/N]: ").strip().lower() in {"y", "yes"}
    local_only = input("Run fully locally? [y/N]: ").strip().lower() in {"y", "yes"}
    if local_only:
        allow = False; discover = False
    sources = [item.strip().lower() for item in input("Allowed sources (comma-separated, default openalex): ").split(",") if item.strip()] if allow else []
    if allow and not sources:
        sources = ["openalex"]
    authorized = [item.strip().lower() for item in input("Sources with a preconfigured legal login/connector (comma-separated, optional): ").split(",") if item.strip()] if allow else []
    config = {"schema_version": "1.0", "project": {"research_question": question, "review_type": review_type, "scope_status": "scope_uncertain"},
              "library": {"provided": bool(library), "path": library or None, "format": "json" if library.endswith(".json") else None},
              "automation": {"allow_search": allow, "allow_metadata_enrichment": allow, "allow_external_discovery": discover,
                             "local_only_confirmed": local_only, "allowed_sources": sources, "authorized_sources": authorized},
              "output": {"language": "zh-CN", "formats": ["html", "md", "json"]}}
    pathlib.Path(args.out).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def init_config(args):
    question = input("研究问题/题目：").strip(); review_type = input("综述类型 [narrative/systematic/scoping/rapid/umbrella]：").strip() or "narrative"
    library = input("文献库路径（可留空，后续导入）：").strip(); allow = input("允许联网检索？[y/N]：").strip().lower() in {"y", "yes"}
    sources = [item.strip() for item in input("允许来源（逗号分隔）：").split(",") if item.strip()] if allow else []
    config = {"schema_version": "1.0", "project": {"research_question": question, "review_type": review_type, "scope_status": "scope_uncertain"}, "library": {"provided": bool(library), "path": library or None, "format": "json" if library.endswith(".json") else None}, "automation": {"allow_search": allow, "allowed_sources": sources or (["openalex", "crossref", "arxiv"] if allow else [])}, "output": {"language": "zh-CN", "formats": ["html", "md", "json"]}}
    pathlib.Path(args.out).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init"); init.add_argument("--out", required=True)
    status = sub.add_parser("status"); status.add_argument("--out", required=True)
    execute = sub.add_parser("run"); execute.add_argument("--run-config", required=True); execute.add_argument("--out", required=True); execute.add_argument("--library")
    for name in ("context", "benchmark", "gold", "query-hits", "source-snapshot", "screening-decisions", "deduplication-log", "screening-summary"): execute.add_argument("--" + name)
    execute.add_argument("--query-plan"); execute.add_argument("--collect", action="store_true"); execute.add_argument("--citation-seed"); execute.add_argument("--resume", action="store_true"); execute.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "init": return init_config_v2(args)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.command == "status": print(state_path(out).read_text(encoding="utf-8") if state_path(out).exists() else "No workflow state yet."); return
    run_signature = signature(args); steps = load_state(out, run_signature, args.resume, args.force)
    config = json.loads(pathlib.Path(args.run_config).read_text(encoding="utf-8")); library = pathlib.Path(args.library or config.get("library", {}).get("path") or "")
    if not library.is_file(): raise SystemExit("ERROR: provide an existing --library or library.path in run-config.")
    canonical = library
    if library.suffix.lower() != ".json":
        imported = out / "import"; run([sys.executable, script("import_library.py"), "--input", str(library), "--out", str(imported)], steps, "import", out, run_signature, [imported / "library.json", imported / "import-preview.json"], args.resume); canonical = imported / "library.json"
        config["library"] = {"provided": True, "path": str(canonical), "format": "json", "normalization_required": False}; resolved = out / "resolved-run-config.json"; resolved.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"); args.run_config = str(resolved)
    automation = config.get("automation") or {}
    if automation.get("allow_search") is True and automation.get("allow_metadata_enrichment", True) is True and not automation.get("local_only_confirmed", False):
        enrichment = out / "enrichment"
        run([sys.executable, script("enrich_library_metadata.py"), "--library", str(canonical), "--run-config", args.run_config, "--out", str(enrichment)], steps, "metadata_enrichment", out, run_signature, [enrichment / "library-enriched.json", enrichment / "metadata-enrichment.json"], args.resume)
        canonical = enrichment / "library-enriched.json"
    if args.collect:
        if not args.query_plan: raise SystemExit("ERROR: --collect requires --query-plan.")
        collection = out / "collection"; run([sys.executable, script("collect_open_sources.py"), "--run-config", args.run_config, "--plan", args.query_plan, "--out", str(collection)], steps, "collection", out, run_signature, [collection / "source-snapshot.json"], args.resume)
        normalized = out / "normalization"; run([sys.executable, script("normalize_candidates.py"), "--snapshot", str(collection / "source-snapshot.json"), "--out", str(normalized)], steps, "normalization", out, run_signature, [normalized / "candidates.json", normalized / "deduplication-log.json"], args.resume)
        args.source_snapshot = args.source_snapshot or str(collection / "source-snapshot.json"); args.deduplication_log = args.deduplication_log or str(normalized / "deduplication-log.json")
        screen = out / "screening"; run([sys.executable, script("screen_candidates.py"), "--candidates", str(normalized / "candidates.json"), "--out", str(screen)], steps, "screening_template", out, run_signature, [screen / "screening-decisions.json"], args.resume)
    if args.screening_decisions:
        candidates = out / "normalization" / "candidates.json"
        if not candidates.is_file(): raise SystemExit("ERROR: screening decisions require normalized candidates from --collect.")
        summary = out / "screening"; run([sys.executable, script("summarize_screening.py"), "--candidates", str(candidates), "--decisions", args.screening_decisions, "--out", str(summary)], steps, "screening_summary", out, run_signature, [summary / "screening-summary.json"], args.resume); args.screening_summary = args.screening_summary or str(summary / "screening-summary.json")
    if args.citation_seed:
        citations = out / "citations"; run([sys.executable, script("citation_candidates.py"), "--seed", args.citation_seed, "--run-config", args.run_config, "--out", str(citations)], steps, "citation_discovery", out, run_signature, [citations / "citation-candidates.json", citations / "manifest.json"], args.resume)
    audit = out / "audit"; command = [sys.executable, script("run_audit.py"), "--library", str(canonical), "--out", str(audit), "--run-config", args.run_config]
    for flag, value in (("--context", args.context), ("--benchmark", args.benchmark), ("--gold", args.gold), ("--query-hits", args.query_hits), ("--candidate-snapshots", args.source_snapshot), ("--decision-log", args.screening_decisions), ("--deduplication-log", args.deduplication_log), ("--search-meta", args.screening_summary)):
        if value: command.extend([flag, value])
    run(command, steps, "audit", out, run_signature, [audit / "audit.json", audit / "audit.html"], args.resume)
    run([sys.executable, script("next_actions.py"), "--audit", str(audit / "audit.json"), "--out", str(out)], steps, "actions", out, run_signature, [out / "next-actions.json"], args.resume)


if __name__ == "__main__": main()
