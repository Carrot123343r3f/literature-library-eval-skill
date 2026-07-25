#!/usr/bin/env python3
"""Guided, resumable orchestration for import → collect → screen → audit → actions."""
import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys


def write_state(out, steps, message=""):
    state = {"schema_version": "1.0", "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "steps": steps, "message": message}
    (out / "workflow-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run(command, steps, name, out):
    try:
        subprocess.run(command, check=True); steps[name] = "complete"; write_state(out, steps)
    except subprocess.CalledProcessError as exc:
        steps[name] = "failed"; write_state(out, steps, f"{name} failed with exit code {exc.returncode}")
        raise SystemExit(exc.returncode)


def init_config(args):
    question = input("研究问题/题目：").strip(); review_type = input("综述类型 [narrative/systematic/scoping/rapid/umbrella]：").strip() or "narrative"
    library = input("文献库路径（可留空，后续导入）：").strip(); allow = input("允许联网检索？[y/N]：").strip().lower() in {"y", "yes"}
    sources = [item.strip() for item in input("允许来源（逗号分隔，默认 openalex,crossref,arxiv）：").split(",") if item.strip()] if allow else []
    config = {"schema_version": "1.0", "project": {"research_question": question, "review_type": review_type, "scope_status": "scope_uncertain"},
              "library": {"provided": bool(library), "path": library or None, "format": "json" if library.endswith(".json") else None},
              "automation": {"allow_search": allow, "allowed_sources": sources or (["openalex", "crossref", "arxiv"] if allow else [])},
              "output": {"language": "zh-CN", "formats": ["html", "md", "json"]}}
    pathlib.Path(args.out).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {args.out}. Review scope_status before a full A–F audit.")


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Ask only essential questions and create run-config.json"); init.add_argument("--out", required=True)
    status = sub.add_parser("status", help="Show resumable workflow state"); status.add_argument("--out", required=True)
    execute = sub.add_parser("run", help="Run local import/audit steps and persist recovery state")
    execute.add_argument("--run-config", required=True); execute.add_argument("--out", required=True); execute.add_argument("--library")
    execute.add_argument("--context"); execute.add_argument("--benchmark"); execute.add_argument("--gold"); execute.add_argument("--query-hits"); execute.add_argument("--source-snapshot")
    execute.add_argument("--screening-decisions"); execute.add_argument("--deduplication-log")
    execute.add_argument("--query-plan", help="Persisted multi-source query plan; used only with --collect")
    execute.add_argument("--collect", action="store_true", help="Run authorized multi-source collection and normalization")
    execute.add_argument("--citation-seed", help="Optional library subset for authorized backward/forward citation discovery")
    args = parser.parse_args()
    if args.command == "init": return init_config(args)
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.command == "status":
        state = out / "workflow-state.json"; print(state.read_text(encoding="utf-8") if state.exists() else "No workflow state yet. Run `init` then `run`."); return
    config = json.loads(pathlib.Path(args.run_config).read_text(encoding="utf-8")); library = args.library or config.get("library", {}).get("path")
    if not library: raise SystemExit("ERROR: provide --library or library.path in run-config.")
    steps = {"import": "skipped", "audit": "pending", "actions": "pending"}; canonical = pathlib.Path(library)
    if canonical.suffix.lower() != ".json":
        imported = out / "import"; run([sys.executable, "scripts/import_library.py", "--input", str(canonical), "--out", str(imported)], steps, "import", out); canonical = imported / "library.json"
        config["library"] = {"provided": True, "path": str(canonical), "format": "json", "normalization_required": False}
        resolved_config = out / "resolved-run-config.json"; resolved_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        args.run_config = str(resolved_config)
    if args.collect:
        if not args.query_plan: raise SystemExit("ERROR: --collect requires --query-plan.")
        collection = out / "collection"; steps["collection"] = "pending"; write_state(out, steps)
        run([sys.executable, "scripts/collect_open_sources.py", "--run-config", args.run_config, "--plan", args.query_plan, "--out", str(collection)], steps, "collection", out)
        normalization = out / "normalization"; steps["normalization"] = "pending"; write_state(out, steps)
        run([sys.executable, "scripts/normalize_candidates.py", "--snapshot", str(collection / "source-snapshot.json"), "--out", str(normalization)], steps, "normalization", out)
        args.source_snapshot = args.source_snapshot or str(collection / "source-snapshot.json")
        args.deduplication_log = args.deduplication_log or str(normalization / "deduplication-log.json")
        screening = out / "screening"; steps["screening_template"] = "pending"; write_state(out, steps)
        run([sys.executable, "scripts/screen_candidates.py", "--candidates", str(normalization / "candidates.json"), "--out", str(screening)], steps, "screening_template", out)
    if args.citation_seed:
        citations = out / "citations"; steps["citation_discovery"] = "pending"; write_state(out, steps)
        run([sys.executable, "scripts/citation_candidates.py", "--seed", args.citation_seed, "--run-config", args.run_config, "--out", str(citations)], steps, "citation_discovery", out)
    audit_out = out / "audit"; context = args.context or ""
    command = [sys.executable, "scripts/run_audit.py", "--library", str(canonical), "--out", str(audit_out), "--run-config", args.run_config]
    for flag, value in (("--context", context), ("--benchmark", args.benchmark), ("--gold", args.gold), ("--query-hits", args.query_hits), ("--candidate-snapshots", args.source_snapshot), ("--decision-log", args.screening_decisions), ("--deduplication-log", args.deduplication_log)):
        if value: command.extend([flag, value])
    run(command, steps, "audit", out)
    run([sys.executable, "scripts/next_actions.py", "--audit", str(audit_out / "audit.json"), "--out", str(out)], steps, "actions", out)
    print(f"Complete. Open {audit_out / 'audit.html'} and {out / 'next-actions.json'}.")


if __name__ == "__main__": main()
