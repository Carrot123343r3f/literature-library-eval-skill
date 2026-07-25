import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .contracts import clean, norm, stable_ids


class ExternalSearchError(RuntimeError):
    pass


def require_openalex_authorization(config):
    automation = config.get("automation") or {}
    sources = {str(item).lower() for item in automation.get("allowed_sources", [])}
    if automation.get("allow_search") is not True or "openalex" not in sources:
        raise ExternalSearchError("External candidates require allow_search=true and openalex in allowed_sources.")
    api_key = os.environ.get("OPENALEX_API_KEY")
    if not api_key:
        raise ExternalSearchError("OpenAlex is authorized but no configured OPENALEX_API_KEY is available; no external ranking was generated.")
    return api_key


def search_openalex(query, api_key, limit=100):
    params = {"search": query, "per-page": min(100, max(1, limit)), "sort": "relevance_score:desc", "api_key": api_key}
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "literature-library-eval/2.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise ExternalSearchError(f"OpenAlex search failed: {exc}") from exc
    if not isinstance(payload.get("results"), list):
        raise ExternalSearchError("OpenAlex returned no usable results.")
    return payload["results"], {"source": "openalex", "query": query, "result_count": len(payload["results"]), "status": "complete"}


def abstract(index):
    if not isinstance(index, dict): return ""
    length = max((max(pos) for pos in index.values() if pos), default=-1) + 1
    words = [""] * length
    for token, positions in index.items():
        for pos in positions or []:
            if isinstance(pos, int) and 0 <= pos < length: words[pos] = token
    return " ".join(words)


def normalize_openalex(work):
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    return {"title": work.get("title"), "DOI": clean(work.get("doi")).replace("https://doi.org/", ""), "openalex_id": work.get("id"),
            "publication_year": work.get("publication_year"), "cited_by_count": work.get("cited_by_count"), "citation_normalized_percentile": work.get("citation_normalized_percentile"),
            "fwci": work.get("fwci"), "publicationTitle": source.get("display_name"), "open_access_url": (work.get("open_access") or {}).get("oa_url"),
            "abstract": abstract(work.get("abstract_inverted_index")), "source": "openalex", "topics": [item.get("display_name") for item in work.get("topics", []) if item.get("display_name")]}


def without_library_duplicates(candidates, library):
    ids = set().union(*(stable_ids(item) for item in library)) if library else set()
    titles = {norm(item.get("title")) for item in library if norm(item.get("title"))}
    seen, result = set(), []
    for item in candidates:
        key = next(iter(stable_ids(item)), "") or norm(item.get("title"))
        if not key or key in seen or stable_ids(item) & ids or norm(item.get("title")) in titles: continue
        seen.add(key); result.append(item)
    return result
