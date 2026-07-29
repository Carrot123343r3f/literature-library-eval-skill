import json
import urllib.error
import urllib.parse
import urllib.request

from .contracts import clean, norm, stable_ids
from credentials import CredentialError, require_openalex_api_key


class ExternalSearchError(RuntimeError):
    pass


def require_openalex_authorization(config, required_permission):
    """Check the module-specific consent immediately before OpenAlex access."""
    automation = config.get("automation") or {}
    sources = {str(item).lower() for item in automation.get("allowed_sources", [])}
    if automation.get("allow_search") is not True or "openalex" not in sources:
        raise ExternalSearchError("External candidates require allow_search=true and openalex in allowed_sources.")
    if required_permission not in {"allow_metadata_enrichment", "allow_external_discovery"}:
        raise ExternalSearchError("OpenAlex access requires a supported module permission.")
    if automation.get(required_permission) is not True:
        raise ExternalSearchError(f"OpenAlex access requires explicit automation.{required_permission}=true.")
    authorized = automation.get("authorized_sources")
    if isinstance(authorized, list) and authorized and "openalex" not in {str(item).lower() for item in authorized}:
        raise ExternalSearchError("OpenAlex is not included in the user's authorized_sources.")
    try:
        return require_openalex_api_key()
    except CredentialError as exc:
        raise ExternalSearchError(str(exc)) from exc


def search_openalex(query, api_key, limit=100, *, config=None, required_permission=None):
    # Enforce authorization at the HTTP boundary, not only in CLI callers.
    if not isinstance(config, dict) or not required_permission:
        raise ExternalSearchError("OpenAlex search requires run-config and module-specific permission.")
    require_openalex_authorization(config, required_permission)
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


def enrich_openalex_record(record, api_key, config):
    """Fill missing metadata from one authorized OpenAlex lookup.

    The returned record keeps user-supplied values and only fills blanks.
    Matching is conservative: DOI match wins; otherwise normalized title and
    publication year must agree. The lookup log is returned for provenance.
    """
    doi = clean(record.get("DOI") or record.get("doi"))
    title = clean(record.get("title"))
    query = doi or title
    if not query:
        return dict(record), {"source": "openalex", "status": "skipped", "reason": "missing_doi_and_title"}
    works, log = search_openalex(query, api_key, limit=10, config=config,
                                 required_permission="allow_metadata_enrichment")
    wanted_title, wanted_year = norm(title), record.get("year") or record.get("publication_year")
    wanted_year = int(wanted_year) if str(wanted_year).isdigit() else None
    match = None
    for work in works:
        candidate = normalize_openalex(work)
        if doi and stable_ids(candidate) & stable_ids(record):
            match = candidate; break
        candidate_year = candidate.get("publication_year")
        if title and norm(candidate.get("title")) == wanted_title and (not wanted_year or candidate_year == wanted_year):
            match = candidate; break
    if not match:
        return dict(record), {**log, "status": "no_confident_match", "match_confidence": "none"}
    enriched = dict(record)
    filled = []
    for key, value in match.items():
        if value not in (None, "", [], {}) and not enriched.get(key):
            enriched[key] = value; filled.append(key)
    return enriched, {**log, "status": "complete", "match_confidence": "doi_or_exact_title_year", "filled_fields": filled}


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
