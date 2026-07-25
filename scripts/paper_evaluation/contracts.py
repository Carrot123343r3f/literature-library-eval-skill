import json
import pathlib
import re

VERDICTS = {"pass", "concern", "fail", "not_assessable"}
ELIGIBILITY = {"eligible", "possibly_eligible", "out_of_scope", "insufficient_metadata"}


def load_items(path):
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return value["items"]
    raise ValueError(f"{path} must be a JSON array or object with items[].")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def year(record):
    found = re.search(r"\b(19|20)\d{2}\b", str(record.get("year") or record.get("publication_year") or record.get("date") or ""))
    return int(found.group(0)) if found else None


def stable_ids(record):
    ids = set()
    doi = clean(record.get("DOI") or record.get("doi")).lower().replace("https://doi.org/", "")
    if doi:
        ids.add("doi:" + doi)
    openalex = clean(record.get("openalex_id") or record.get("id"))
    if openalex.startswith("https://openalex.org/"):
        ids.add("openalex:" + openalex.rsplit("/", 1)[-1].lower())
    arxiv = clean(record.get("arxiv") or record.get("arXiv"))
    if arxiv:
        ids.add("arxiv:" + arxiv.lower())
    return ids


def text(record):
    return " ".join(clean(record.get(key)) for key in ("title", "abstract", "abstractNote", "keywords", "topics", "tags"))


def list_value(value):
    if isinstance(value, str):
        return [clean(value)] if clean(value) else []
    return [clean(item) for item in value if clean(item)] if isinstance(value, list) else []
