#!/usr/bin/env python3
"""Run a low-friction first-pass literature audit with safe, resumable defaults."""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

try:
    from query_compiler import compile_query_plan
except ImportError:
    from scripts.query_compiler import compile_query_plan


DEFAULT_SOURCES = ["openalex", "arxiv", "crossref", "europepmc"]


def build_context(question, terms):
    return {"research_question": question, "keywords": terms,
            "search_decomposition": {"object": {"term": ""}, "technology": {"term": ""},
                                      "performance": {"term": ""}, "context": {"term": ""},
                                      "source": "autopilot_question_only"}}


def build_config(question, library, review_type, sources, offline):
    config = {"schema_version": "1.0",
            "project": {"research_question": question, "review_type": review_type,
                        "scope_status": "in_scope", "scope_rationale": "user_invoked_autopilot"},
            "library": {"provided": True, "path": pathlib.Path(library).name, "format": "json"},
            "automation": {"allow_search": not offline, "allow_metadata_enrichment": False,
                            "allow_external_discovery": not offline, "allow_citation_tracking": False,
                            "local_only_confirmed": offline, "allowed_sources": [] if offline else sources},
            "output": {"language": "zh-CN", "formats": ["html", "json"]}}
    if not offline:
        config["quality"] = {"active_screen_budget": 100}
    return config


def run(args):
    out = pathlib.Path(args.out); control = out / ".autopilot"; control.mkdir(parents=True, exist_ok=True)
    sources = [x.strip().casefold() for x in args.sources.split(",") if x.strip()] if not args.offline else []
    plan = compile_query_plan(args.question, sources or ["arxiv"])
    terms = plan["queries"][0].get("terms", []) if plan["queries"] else []
    config_path = control / "run-config.json"; context_path = control / "context.json"; plan_path = control / "query-plan.json"
    config_path.write_text(json.dumps(build_config(args.question, args.library, args.review_type, sources, args.offline), ensure_ascii=False, indent=2), encoding="utf-8")
    context_path.write_text(json.dumps(build_context(args.question, terms), ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [sys.executable, str(pathlib.Path(__file__).with_name("run_full_audit.py")), "run",
               "--run-config", str(config_path), "--library", str(pathlib.Path(args.library).resolve()),
               "--context", str(context_path), "--out", str(out)]
    if not args.offline:
        command += ["--collect", "--query-plan", str(plan_path), "--active-screen-budget", str(args.screen_budget)]
    subprocess.run(command, check=True)
    candidates = out / "normalization" / "candidates.json"
    if candidates.is_file():
        triage = out / "screening" / "auto-triage.json"
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("auto_triage.py")),
                        "--candidates", str(candidates), "--question", args.question, "--out", str(triage)], check=True)
    (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "offline" if args.offline else "multi-source", "sources_requested": sources, "question": args.question, "human_gates": ["scope", "screening", "final_inclusion"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True); parser.add_argument("--library", required=True); parser.add_argument("--out", required=True)
    parser.add_argument("--review-type", default="narrative", choices=("narrative", "systematic", "scoping", "rapid", "umbrella"))
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES)); parser.add_argument("--offline", action="store_true")
    parser.add_argument("--screen-budget", type=int, default=100)
    args = parser.parse_args()
    if args.screen_budget < 1: parser.error("--screen-budget must be positive")
    try: run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc: parser.error(str(exc))


if __name__ == "__main__": main()
