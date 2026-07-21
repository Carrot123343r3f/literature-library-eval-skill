"""Tests for stable identifier normalisation in normalize_candidates.py."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from normalize_candidates import (
    doi, normalise_openalex, normalise_pmid, normalise_pmcid,
    normalise_arxiv, key, title_year, validate_snapshot
)


class TestDOI:
    def test_bare(self):
        assert doi("10.1234/foo.bar") == "10.1234/foo.bar"

    def test_https(self):
        assert doi("https://doi.org/10.1234/foo") == "10.1234/foo"

    def test_http_dx(self):
        assert doi("http://dx.doi.org/10.1234/foo") == "10.1234/foo"

    def test_prefixed(self):
        assert doi("doi:10.1234/foo") == "10.1234/foo"

    def test_trailing_dot(self):
        assert doi("10.1234/foo.") == "10.1234/foo"

    def test_trailing_comma(self):
        assert doi("10.1234/foo,") == "10.1234/foo"

    def test_trailing_paren(self):
        assert doi("10.1234/foo)") == "10.1234/foo"

    def test_uppercase(self):
        assert doi("10.1234/FOO.BAR") == "10.1234/foo.bar"

    def test_empty(self):
        assert doi("") == ""

    def test_none(self):
        assert doi(None) == ""


class TestOpenAlex:
    def test_bare(self):
        assert normalise_openalex("W123456789") == "openalex:w123456789"

    def test_url(self):
        assert normalise_openalex("https://openalex.org/W123456789") == "openalex:w123456789"

    def test_http_url(self):
        assert normalise_openalex("http://openalex.org/W123456789") == "openalex:w123456789"

    def test_prefixed(self):
        assert normalise_openalex("openalex:W123456789") == "openalex:w123456789"

    def test_prefixed_space(self):
        assert normalise_openalex("openalex: W123456789") == "openalex:w123456789"

    def test_non_w(self):
        assert normalise_openalex("A123") == ""

    def test_empty(self):
        assert normalise_openalex("") == ""


class TestPMID:
    def test_bare(self):
        assert normalise_pmid("12345678") == "pmid:12345678"

    def test_prefixed(self):
        assert normalise_pmid("pmid:12345678") == "pmid:12345678"

    def test_prefixed_upper(self):
        assert normalise_pmid("PMID:12345678") == "pmid:12345678"

    def test_empty(self):
        assert normalise_pmid("") == ""


class TestPMCID:
    def test_bare(self):
        assert normalise_pmcid("PMC1234567") == "pmcid:pmc1234567"

    def test_prefixed(self):
        assert normalise_pmcid("pmcid:PMC1234567") == "pmcid:pmc1234567"

    def test_empty(self):
        assert normalise_pmcid("") == ""


class TestArXiv:
    def test_bare_new(self):
        assert normalise_arxiv("2301.00001") == "arxiv:2301.00001"

    def test_prefixed(self):
        assert normalise_arxiv("arxiv:2301.00001") == "arxiv:2301.00001"

    def test_with_version(self):
        assert normalise_arxiv("2301.00001v2") == "arxiv:2301.00001"

    def test_url(self):
        assert normalise_arxiv("https://arxiv.org/abs/2301.00001") == "arxiv:2301.00001"

    def test_url_with_version(self):
        assert normalise_arxiv("https://arxiv.org/abs/2301.00001v3") == "arxiv:2301.00001"

    def test_old_format(self):
        assert normalise_arxiv("hep-th/9901001") == ""

    def test_empty(self):
        assert normalise_arxiv("") == ""


class TestKey:
    def test_doi(self):
        assert key({"id": "10.1000/foo"}) == "doi:10.1000/foo"

    def test_openalex_url(self):
        assert key({"id": "https://openalex.org/W123"}) == "openalex:w123"

    def test_arxiv_source(self):
        assert key({"id": "2301.00001", "source": "arxiv"}) == "arxiv:2301.00001"

    def test_pmid_prefixed(self):
        assert key({"id": "pmid:12345678"}) == "pmid:12345678"

    def test_empty(self):
        assert key({}) == ""


class TestTitleYear:
    def test_normal(self):
        assert title_year({"title": "Hello World", "year": "2024"}) == ("helloworld", "2024")

    def test_no_title(self):
        assert title_year({}) is None

    def test_no_year(self):
        assert title_year({"title": "Test"}) == ("test", "")


class TestValidateSnapshot:
    def test_empty(self):
        w = validate_snapshot({})
        assert len(w) >= 1

    def test_valid(self):
        w = validate_snapshot({
            "queries": [{
                "id": "q1",
                "sources": {
                    "openalex": {"status": "complete", "items": []}
                }
            }]
        })
        assert w == []

    def test_bad_status(self):
        w = validate_snapshot({
            "queries": [{
                "id": "q1",
                "sources": {
                    "openalex": {"status": "weird", "items": []}
                }
            }]
        })
        assert len(w) >= 1
