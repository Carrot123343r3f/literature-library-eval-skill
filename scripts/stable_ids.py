"""Canonical stable-identifier extraction shared by audit and search tools."""
import re


def doi(value):
    match = re.search(r"(10\.\d{4,9}/\S+)", str(value or ""), re.I)
    return match.group(1).rstrip(".,;:)]}").casefold() if match else ""


def _openalex(value):
    raw = str(value or "").strip().casefold()
    if not raw:
        return ""
    match = re.search(r"(?:openalex\.org/)?([wa]\d+)$", raw)
    return match.group(1) if match else ""


def stable_ids(item):
    """Return canonical DOI/OpenAlex/arXiv/PMID/PMCID identifiers for one record.

    A raw OpenAlex URL or ID is normalized to ``openalex:w…``. Title similarity
    is intentionally excluded: it is a manual-review cue, never recall evidence.
    """
    if not isinstance(item, dict):
        return set()
    found = set()
    for key in ("DOI", "doi", "extra", "id"):
        value = doi(item.get(key))
        if value:
            found.add("doi:" + value)
    for key, prefix in (("PMID", "pmid"), ("pmid", "pmid"),
                        ("PMCID", "pmcid"), ("pmcid", "pmcid"),
                        ("arxiv", "arxiv"), ("arXiv", "arxiv")):
        value = str(item.get(key) or "").strip()
        if value:
            found.add(prefix + ":" + value.casefold())
    for key in ("openalex_id", "openalex", "id"):
        value = _openalex(item.get(key))
        if value:
            found.add("openalex:" + value)
    raw = str(item.get("id") or "").strip().casefold()
    if raw.startswith(("pmid:", "pmcid:", "arxiv:", "openalex:")):
        found.add(raw)
    if item.get("source") == "arxiv" and raw and not raw.startswith(("http://", "https://")):
        found.add("arxiv:" + raw)
    return found
