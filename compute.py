#!/usr/bin/env python3
"""Compatibility helper for stable-identifier A1 checks.

For full engineering audits use scripts/run_audit.py. This helper intentionally
does not compute legacy quality, saturation, venue or PDF scores.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "scripts"))
from run_audit import benchmark, health, load_items  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Compatibility helper: A1 and library health only")
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
