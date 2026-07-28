#!/usr/bin/env python3
"""Create reproducible backward/forward citation candidate snapshots from OpenAlex."""
import argparse
import json
import pathlib
import urllib.parse
import urllib.request
import datetime as dt
from artifact_manifest import write_manifest
from credentials import require_openalex_api_key
from collect_open_sources import load_search_authorization


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/3.0"})
    with urllib.request.urlopen(request, timeout=45) as response: return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--seed", required=True); parser.add_argument("--run-config", required=True); parser.add_argument("--out", required=True); parser.add_argument("--limit", type=int, default=100); parser.add_argument("--allow-unavailable", action="store_true", help="write a structured zero-candidate result when permission or credentials are unavailable")
    args = parser.parse_args(); allowed = load_search_authorization(args.run_config, "allow_citation_tracking")
    if allowed is not None and "openalex" not in allowed: raise SystemExit("ERROR: OpenAlex is not authorized by automation.allowed_sources.")
    seeds = json.loads(pathlib.Path(args.seed).read_text(encoding="utf-8")); seeds = seeds if isinstance(seeds, list) else seeds.get("items", [])
    output = pathlib.Path(args.out); output.mkdir(parents=True, exist_ok=True)
    try:
        key = require_openalex_api_key()
    except Exception as exc:
        if not args.allow_unavailable:
            raise
        (output / "citation-candidates.json").write_text(json.dumps({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": [], "status": "not_expanded", "search_log": [], "seed_count": len(seeds), "reason": "openalex_credentials_unavailable", "note": "No request was sent. Candidates require an authorized OpenAlex connection and human screening."}, ensure_ascii=False, indent=2), encoding="utf-8")
        write_manifest(output, "citation-candidates", "1.0", {"seed": args.seed, "run-config": args.run_config}, {"citation_discovery": "not_expanded"})
        print("Citation expansion not run: OpenAlex credentials unavailable."); return
    candidates, search_log, seen = [], [], set()
    for seed in seeds[:20]:
        work_id = seed.get("openalex_id") or seed.get("id")
        if not work_id: continue
        try:
            work = get_json(f"https://api.openalex.org/works/{urllib.parse.quote(work_id.rsplit('/', 1)[-1])}?api_key={urllib.parse.quote(key)}")
            for ref in work.get("referenced_works", []):
                if ref not in seen: seen.add(ref); candidates.append({"openalex_id": ref, "source": "openalex", "pathway": "backward_citation", "seed": work_id})
            cited = get_json(f"https://api.openalex.org/works?filter=cites:{urllib.parse.quote(work_id)}&per-page={min(args.limit,200)}&api_key={urllib.parse.quote(key)}")
            for row in cited.get("results", []):
                if row.get("id") and row["id"] not in seen: seen.add(row["id"]); candidates.append({"openalex_id": row["id"], "title": row.get("title"), "year": row.get("publication_year"), "source": "openalex", "pathway": "forward_citation", "seed": work_id})
            search_log.append({"seed": work_id, "status": "complete", "limit": min(args.limit, 200)})
        except Exception as exc:
            search_log.append({"seed": work_id, "status": "failed", "error_type": type(exc).__name__})
    (output / "citation-candidates.json").write_text(json.dumps({"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": candidates, "status": "candidate_discovery", "search_log": search_log, "note": "Candidates require human screening before formal inclusion."}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_manifest(output, "citation-candidates", "1.0", {"seed": args.seed, "run-config": args.run_config}, {"citation_discovery": "partial" if any(x["status"] == "failed" for x in search_log) else "complete"})
    print(f"Wrote {len(candidates)} citation candidates.")


if __name__ == "__main__": main()
