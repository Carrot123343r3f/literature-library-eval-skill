#!/usr/bin/env python3
"""Collect reproducible candidate-set snapshots from open scholarly sources.

Input query plan example:
{"queries":[{"id":"core","query":"battery cathode stability",
 "sources":["openalex","crossref","europepmc","arxiv"]}]}
"""
import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/2.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def openalex(query):
    data = get_json("https://api.openalex.org/works?per-page=50&search=" + urllib.parse.quote(query))
    items = [{"id": w.get("doi") or w.get("id"), "title": w.get("title"), "year": w.get("publication_year")}
             for w in data.get("results", [])]
    return {"count": data.get("meta", {}).get("count"), "items": items}


def crossref(query):
    data = get_json("https://api.crossref.org/works?rows=50&query=" + urllib.parse.quote(query))
    message = data.get("message", {})
    items = [{"id": "doi:" + x["DOI"].lower() if x.get("DOI") else None,
              "title": (x.get("title") or [None])[0], "year": (x.get("published", {}).get("date-parts") or [[None]])[0][0]}
             for x in message.get("items", [])]
    return {"count": message.get("total-results"), "items": items}


def europepmc(query):
    data = get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&pageSize=50&query=" + urllib.parse.quote(query))
    items = [{"id": "pmid:" + x["pmid"] if x.get("pmid") else x.get("doi"),
              "title": x.get("title"), "year": x.get("pubYear")} for x in data.get("resultList", {}).get("result", [])]
    return {"count": data.get("hitCount"), "items": items}


def arxiv(query):
    url = "https://export.arxiv.org/api/query?max_results=50&search_query=all:" + urllib.parse.quote(query)
    request = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/2.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        root = ET.fromstring(response.read())
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    items = [{"id": (x.findtext("a:id", default="", namespaces=ns).split("/")[-1]),
              "title": " ".join((x.findtext("a:title", default="", namespaces=ns)).split()),
              "year": (x.findtext("a:published", default="", namespaces=ns)[:4])} for x in entries]
    return {"count": len(items), "items": items, "note": "arXiv API returns a page snapshot; count is not corpus total"}


COLLECTORS = {"openalex": openalex, "crossref": crossref, "europepmc": europepmc, "arxiv": arxiv}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="query-plan JSON")
    parser.add_argument("--out", required=True, help="snapshot JSON")
    args = parser.parse_args()
    with open(args.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    result = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "queries": []}
    for row in plan.get("queries", []):
        entry = {"id": row.get("id"), "query": row["query"], "sources": {}}
        for source in row.get("sources", ["openalex"]):
            collector = COLLECTORS.get(source)
            if not collector:
                entry["sources"][source] = {"error": "unsupported open-source collector"}
                continue
            try:
                entry["sources"][source] = collector(row["query"])
            except Exception as exc:
                entry["sources"][source] = {"error": str(exc)[:240]}
            time.sleep(0.25)
        result["queries"].append(entry)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
