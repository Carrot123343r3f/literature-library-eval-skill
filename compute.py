#!/usr/bin/env python3
"""DEPRECATED — lightweight compatibility wrapper for A1 + library health only.

WARNING: This script does NOT compute A2–F6. For full engineering audits, use:
    python scripts/run_audit.py --run-config <path> --out <outdir>
This helper exists only for backwards compatibility with simple A1 recall
checks and will not be extended. Legacy fixed scores for quality, saturation,
venue, and PDF scores are permanently retired.

For full documentation, see README.md and AI_GUIDE.md.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "scripts"))
from run_audit import benchmark, health, load_items  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="DEPRECATED: compatibility helper for A1 + library health. Use scripts/run_audit.py for full A–F audits.",
        epilog="WARNING: A2, A3, B–F dimensions are NOT computed by this script. Use scripts/run_audit.py --run-config <path> --out <outdir> for a complete evaluation."
    )
    parser.add_argument("--jsonfile", required=True, help="normalized library JSON")
    parser.add_argument("--benchmark", help="stable-identifier benchmark JSON")
    args = parser.parse_args()
    library = load_items(args.jsonfile)
    result = {"library_health": health(library),
              "note": "Use scripts/run_audit.py for A2, A3 and B–F; legacy fixed scores are retired."}
    if args.benchmark:
        result["a1"] = benchmark(library, load_items(args.benchmark))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
