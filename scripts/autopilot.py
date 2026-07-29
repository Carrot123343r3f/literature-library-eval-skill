#!/usr/bin/env python3
"""Run a low-friction first-pass literature audit with safe, resumable defaults."""
from __future__ import annotations

import argparse
import html
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


def build_config(question, library, review_type, sources, offline, scope_status,
                 *, allow_metadata_enrichment=False, allow_external_discovery=False,
                 allow_citation_tracking=False):
    """Build an explicit-permission config; scope confirmation never grants network access."""
    if offline:
        allow_metadata_enrichment = allow_external_discovery = allow_citation_tracking = False
    allow_search = any((allow_metadata_enrichment, allow_external_discovery, allow_citation_tracking))
    config = {"schema_version": "1.0",
            "project": {"research_question": question, "review_type": review_type,
                        "scope_status": scope_status,
                        "scope_rationale": "explicit autopilot scope confirmation" if scope_status == "in_scope" else "autopilot draft; scope not confirmed"},
            "library": {"provided": True, "path": pathlib.Path(library).name if library else "starter-library.json", "format": "json"},
            "automation": {"allow_search": allow_search, "allow_metadata_enrichment": allow_metadata_enrichment,
                            "allow_external_discovery": allow_external_discovery, "allow_citation_tracking": allow_citation_tracking,
                            "local_only_confirmed": not allow_search, "allowed_sources": sources if allow_search else []},
            "output": {"language": "zh-CN", "formats": ["html", "json"]}}
    if allow_search:
        config["quality"] = {"active_screen_budget": 100}
    return config


def write_onboarding(out, question, plan, sources):
    """Write a safe first-run handoff when scope has not been confirmed yet."""
    query_count = len(plan.get("queries", [])) if isinstance(plan, dict) else 0
    command = "python scripts/autopilot.py --question " + json.dumps(question, ensure_ascii=False) + " --scope-status in_scope --out first-pass"
    if sources:
        command += " --sources " + json.dumps(",".join(sources), ensure_ascii=False)
    page = f"""<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><title>Literature audit: start here</title>
<body><main style=\"max-width:760px;margin:48px auto;font:16px/1.55 system-ui,sans-serif\">
<h1>Start your literature audit</h1>
<p>Your question has been saved and a {query_count}-query starter plan was created. No A–F conclusion was produced because the engineering scope has not yet been confirmed.</p>
<h2>Question</h2><p>{html.escape(question)}</p>
<h2>Next step</h2><p>If this is an engineering review question within this skill's scope, run:</p>
<pre>{html.escape(command)}</pre>
<p>You may add <code>--library path/to/library.json</code> now or later. Without a library, the first confirmed run creates an empty starter library and reports only what is currently assessable.</p>
<h2>Why this pause exists</h2><p>It prevents an automated draft from silently deciding that an out-of-scope question deserves a full evidence verdict.</p>
</main></body></html>"""
    (out / "onboarding.html").write_text(page, encoding="utf-8")


def run(args):
    out = pathlib.Path(args.out); control = out / ".autopilot"; control.mkdir(parents=True, exist_ok=True)
    sources = [x.strip().casefold() for x in args.sources.split(",") if x.strip()] if not args.offline else []
    plan = compile_query_plan(args.question, sources or ["arxiv"])
    terms = plan["queries"][0].get("terms", []) if plan["queries"] else []
    config_path = control / "run-config.json"; context_path = control / "context.json"; plan_path = control / "query-plan.json"
    config_path.write_text(json.dumps(build_config(
        args.question, args.library, args.review_type, sources, args.offline, args.scope_status,
        allow_metadata_enrichment=args.allow_metadata_enrichment,
        allow_external_discovery=args.allow_external_discovery,
        allow_citation_tracking=args.allow_citation_tracking), ensure_ascii=False, indent=2), encoding="utf-8")
    context_path.write_text(json.dumps(build_context(args.question, terms), ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.scope_status not in {"in_scope", "cross_domain"}:
        write_onboarding(out, args.question, plan, sources)
        (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": "needs_scope_confirmation", "sources_requested": sources, "question": args.question, "scope_status": args.scope_status, "human_gates": ["scope"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    library = pathlib.Path(args.library).resolve() if args.library else control / "starter-library.json"
    if not args.library:
        library.write_text("[]\n", encoding="utf-8")
    command = [sys.executable, str(pathlib.Path(__file__).with_name("run_full_audit.py")), "run",
               "--run-config", str(config_path), "--library", str(library),
               "--context", str(context_path), "--out", str(out)]
    if args.allow_external_discovery and not args.offline:
        command += ["--collect", "--query-plan", str(plan_path), "--active-screen-budget", str(args.screen_budget)]
    subprocess.run(command, check=True)
    candidates = out / "normalization" / "candidates.json"
    if candidates.is_file():
        triage = out / "screening" / "auto-triage.json"
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("auto_triage.py")),
                        "--candidates", str(candidates), "--question", args.question, "--out", str(triage)], check=True)
    mode = "external_discovery" if args.allow_external_discovery and not args.offline else "local"
    (out / "autopilot-manifest.json").write_text(json.dumps({"schema_version": "1.0", "mode": mode, "sources_requested": sources if not args.offline else [], "question": args.question, "scope_status": args.scope_status, "human_gates": ["scope", "standards", "screening", "final_inclusion"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True); parser.add_argument("--library"); parser.add_argument("--out", required=True)
    parser.add_argument("--review-type", default="narrative", choices=("narrative", "systematic", "scoping", "rapid", "umbrella"))
    parser.add_argument("--scope-status", default="scope_uncertain", choices=("in_scope", "cross_domain", "out_of_scope", "scope_uncertain"),
                        help="Explicit scope decision. Full A-F execution requires in_scope or cross_domain; default is a safe draft state.")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES)); parser.add_argument("--offline", action="store_true",
                        help="Disable all online capabilities (the default is already local-only).")
    parser.add_argument("--allow-metadata-enrichment", action="store_true", help="Explicitly allow online metadata enrichment.")
    parser.add_argument("--allow-external-discovery", action="store_true", help="Explicitly allow online discovery of candidate papers.")
    parser.add_argument("--allow-citation-tracking", action="store_true", help="Explicitly allow online citation candidate discovery.")
    parser.add_argument("--screen-budget", type=int, default=100)
    args = parser.parse_args()
    if args.screen_budget < 1: parser.error("--screen-budget must be positive")
    if args.offline and any((args.allow_metadata_enrichment, args.allow_external_discovery, args.allow_citation_tracking)):
        parser.error("--offline cannot be combined with an --allow-* online capability")
    try: run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc: parser.error(str(exc))


if __name__ == "__main__": main()
