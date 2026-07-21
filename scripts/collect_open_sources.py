#!/usr/bin/env python3
"""Collect paginated, source-level candidate snapshots from open scholarly APIs."""
import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/3.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def openalex(query, limit):
    cursor, items, total = "*", [], None
    while len(items) < limit and cursor:
        url = "https://api.openalex.org/works?per-page=200&cursor=" + urllib.parse.quote(cursor) + "&search=" + urllib.parse.quote(query)
        data = get_json(url); total = data.get("meta", {}).get("count", total)
        page = data.get("results", [])
        items.extend({"id": w.get("doi") or w.get("id"), "title": w.get("title"), "year": w.get("publication_year"), "source": "openalex"} for w in page)
        cursor = data.get("meta", {}).get("next_cursor") if page else None
        time.sleep(0.15)
    return {"query": query, "reported_total": total, "items": items[:limit], "retrieved": min(len(items), limit),
            "complete": bool(total is not None and len(items) >= total), "completion_reason": "all_results" if total is not None and len(items) >= total else "limit_reached"}


def crossref(query, limit):
    rows, offset, total = [], 0, None
    while len(rows) < limit:
        size = min(1000, limit - len(rows))
        url = "https://api.crossref.org/works?rows=" + str(size) + "&offset=" + str(offset) + "&query=" + urllib.parse.quote(query)
        message = get_json(url).get("message", {}); total = message.get("total-results", total); page = message.get("items", [])
        rows.extend({"id": "doi:" + x["DOI"].lower() if x.get("DOI") else None, "title": (x.get("title") or [None])[0],
                     "year": (x.get("published", {}).get("date-parts") or [[None]])[0][0], "source": "crossref"} for x in page)
        if not page: break
        offset += len(page); time.sleep(0.15)
    return {"query": query, "reported_total": total, "items": rows[:limit], "retrieved": min(len(rows), limit),
            "complete": bool(total is not None and len(rows) >= total), "completion_reason": "all_results" if total is not None and len(rows) >= total else "limit_reached"}


def europepmc(query, limit):
    rows, page_no, total = [], 1, None
    while len(rows) < limit:
        size = min(1000, limit - len(rows))
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&pageSize=" + str(size) + "&page=" + str(page_no) + "&query=" + urllib.parse.quote(query)
        data = get_json(url); total = data.get("hitCount", total); page = data.get("resultList", {}).get("result", [])
        rows.extend({"id": "pmid:" + x["pmid"] if x.get("pmid") else x.get("doi"), "title": x.get("title"), "year": x.get("pubYear"), "source": "europepmc"} for x in page)
        if not page: break
        page_no += 1; time.sleep(0.15)
    return {"query": query, "reported_total": total, "items": rows[:limit], "retrieved": min(len(rows), limit),
            "complete": bool(total is not None and len(rows) >= total), "completion_reason": "all_results" if total is not None and len(rows) >= total else "limit_reached"}


def arxiv(query, limit):
    rows, start = [], 0
    while len(rows) < limit:
        size = min(200, limit - len(rows))
        url = "https://export.arxiv.org/api/query?start=" + str(start) + "&max_results=" + str(size) + "&search_query=all:" + urllib.parse.quote(query)
        request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/3.0"})
        with urllib.request.urlopen(request, timeout=45) as response: root = ET.fromstring(response.read())
        ns = {"a": "http://www.w3.org/2005/Atom"}; entries = root.findall("a:entry", ns)
        rows.extend({"id": x.findtext("a:id", default="", namespaces=ns).split("/")[-1], "title": " ".join(x.findtext("a:title", default="", namespaces=ns).split()),
                     "year": x.findtext("a:published", default="", namespaces=ns)[:4], "source": "arxiv"} for x in entries)
        if len(entries) < size: break
        start += len(entries); time.sleep(0.5)
    return {"query": query, "reported_total": None, "items": rows[:limit], "retrieved": min(len(rows), limit),
            "complete": len(rows) < limit, "completion_reason": "exhausted" if len(rows) < limit else "at_limit_boundary", "note": "arXiv API does not report total results. When retrieved == limit, unknown whether results are exhausted or truncated."}


COLLECTORS = {"openalex": openalex, "crossref": crossref, "europepmc": europepmc, "arxiv": arxiv}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="query-plan JSON with queries[{id,query,sources}]")
    parser.add_argument("--out", required=True, help="source snapshot JSON")
    parser.add_argument("--max-records", type=int, default=1000, help="maximum records per source/query; a limit means an incomplete snapshot")
    args = parser.parse_args()
    if args.max_records < 1: parser.error("--max-records must be positive")
    with open(args.plan, encoding="utf-8") as fh: plan = json.load(fh)
    result = {"schema_version": "1.0", "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "max_records_per_source_query": args.max_records, "queries": []}
    for row in plan.get("queries", []):
        entry = {"id": row.get("id"), "query": row["query"], "sources": {}}
        for source in row.get("sources", ["openalex"]):
            collector = COLLECTORS.get(source)
            if not collector: entry["sources"][source] = {"status": "failed", "error": "unsupported open-source collector"}; continue
            try:
                collected = collector(row["query"], args.max_records); collected["status"] = "complete" if collected["complete"] else "partial"
                entry["sources"][source] = collected
            except Exception as exc:
                entry["sources"][source] = {"status": "failed", "error": str(exc)[:240]}
        result["queries"].append(entry)
    with open(args.out, "w", encoding="utf-8") as fh: json.dump(result, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__": main()
