#!/usr/bin/env python3
"""Run the mandatory AI-led first assessment when no anchors or query exist.

It creates provisional multi-source anchor/dev/validation artifacts, executes
q0 plus atomic variants across suitable open sources, and produces a report
containing A1-A3 and B1-B3.  The first-run outputs are explicitly labelled
``automated-screening`` or ``partial_snapshot``; this command never claims
that first-run evidence is independently measured or saturated.
"""
import argparse
import pathlib
import subprocess
import sys


def run(script_dir, script, *args):
    command = [sys.executable, str(script_dir / script), *map(str, args)]
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--library", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-anchor-candidates", type=int, default=80)
    parser.add_argument("--min-validation", type=int, default=15)
    parser.add_argument("--min-dev", type=int, default=15)
    parser.add_argument("--max-per-query", type=int, default=50)
    args = parser.parse_args()
    root = pathlib.Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    script_dir = pathlib.Path(__file__).parent
    anchors = root / "anchor-candidates.json"
    source_snapshot = root / "first-run-source-snapshot.json"
    evidence_dir = root / "first-run-evidence"
    search_dir = root / "first-run-search"
    report_dir = root / "audit"
    run(script_dir, "build_anchor_candidates.py", "--context", args.context, "--out", anchors,
        "--snapshot-out", source_snapshot, "--max", args.max_anchor_candidates)
    run(script_dir, "prepare_first_run_evidence.py", "--candidates", anchors,
        "--context", args.context, "--out", evidence_dir, "--min-validation", args.min_validation,
        "--min-dev", args.min_dev)
    run(script_dir, "search_for_eval.py", "--library", args.library, "--context", args.context,
        "--dev-set", evidence_dir / "ai-dev-set.json", "--validation-set", evidence_dir / "ai-validation-set.json",
        "--ai-provisional", "--allow-partial", "--out", search_dir, "--max-per-query", args.max_per_query)
    run(script_dir, "run_audit.py", "--library", args.library, "--context", args.context,
        "--benchmark", evidence_dir / "ai-benchmark.json", "--benchmark-evidence-status", "automated-screening",
        "--gold", evidence_dir / "ai-validation-set.json", "--query-hits", search_dir / "query-hits.json",
        "--candidate-snapshots", source_snapshot,
        "--search-meta", search_dir / "search_meta.json", "--evidence-manifest", evidence_dir / "evidence-manifest.json",
        "--out", report_dir)
    print(f"First-run audit complete: {report_dir}")


if __name__ == "__main__":
    main()
