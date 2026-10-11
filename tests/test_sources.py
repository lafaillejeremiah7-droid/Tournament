"""Stage 2-4: each source connector against recorded/bundled fixtures.

All connectors run fully offline. The bible-api connector is also exercised
against a RECORDED bible-api.com response body (served through an offline
cache that has the recording pre-written), proving the parser handles a real
API payload shape without any network.
"""

from __future__ import annotations

import json

import pytest

from deepresearch.cache import Cache
from deepresearch.sources.base import SourceRequest
from deepresearch.sources.bible_api import (
    BibleApiConnector,
    CopyrightedTranslationError,
    is_public_domain,
)
from deepresearch.sources.commentary import (
    CommentaryConnector,
    host_allowed,
    path_allowed,
)
from deepresearch.sources.registry import SourceRegistry
from deepresearch.sources.strongs import StrongsConnector

from tests.conftest import load_test_fixture


def _offline_cache() -> Cache:
    return Cache(".cache-test", offline=True)


# --------------------------------------------------------------- bible_api


def test_bible_api_falls_back_to_bundled_fixture_offline():
    conn = BibleApiConnector(_offline_cache(), context_window=5)
    result = conn.fetch(
        SourceRequest(kind="verse", reference="Matthew 5:17", translation="kjv")
    )
    assert not result.gap
    assert "fulfil" in result.data["text"].lower()
    assert result.data["translation"] == "kjv"
    assert result.citations
    assert "King James Version" in result.citations[0].source


def test_bible_api_parses_recorded_passage_body(tmp_path):
    """Seed an offline cache with a recorded bible-api.com body and parse it.

    The connector expands "Matthew 5:17" (window 5) to the passage
    "Matthew 5:12-22"; we pre-write the recording under that exact cache
    signature so the offline read-through hits it with zero network.
    """
    cache = Cache(tmp_path / "cache", offline=True)
    recorded = json.dumps(load_test_fixture("bible_api_matthew_5_17_kjv"))
    # Signature mirrors BibleApiConnector.fetch: "<passage_ref>|<translation>".
    cache.write("bible_api", "Matthew 5:12-22|kjv", recorded)

    conn = BibleApiConnector(cache, context_window=5)
    result = conn.fetch(
        SourceRequest(kind="verse", reference="Matthew 5:17", translation="kjv")
    )
    assert not result.gap
    # The recorded passage joins all five verses into one readable string.
    assert "Think not that I am come to destroy" in result.data["text"]
    assert result.data["reference"] == "Matthew 5:15-19"


@pytest.mark.parametrize("translation", ["niv", "esv", "NIV", "nasb", "nlt"])
def test_bible_api_refuses_copyrighted_translations(translation):
    """The public-domain allowlist must REFUSE copyrighted modern translations."""
    conn = BibleApiConnector(_offline_cache())
    result = conn.fetch(
        SourceRequest(kind="verse", reference="John 3:16", translation=translation)
    )
    assert result.gap is True
    assert "public-domain allowlist" in result.reason
    assert "refused" in result.reason


def test_is_public_domain_helper():
    assert is_public_domain("kjv")
    assert is_public_domain("WEB")
    assert is_public_domain("asv")
    assert not is_public_domain("niv")
    assert not is_public_domain("esv")


def test_bible_api_rejects_unknown_request_kind():
    conn = BibleApiConnector(_offline_cache())
    result = conn.fetch(SourceRequest(kind="strongs", reference="Matthew 5:17"))
    assert result.gap is True


# ----------------------------------------------------------------- strongs


def test_strongs_connector_returns_terms_for_reference():
    conn = StrongsConnector()
    result = conn.fetch(SourceRequest(kind="strongs", reference="Matthew 5:17"))
    assert not result.gap
    terms = result.data["terms"]
    assert any(t["strongs"] == "G4137" for t in terms)
    assert all(t["language"] in {"Greek", "Hebrew"} for t in terms)
    assert result.citations


def test_strongs_connector_returns_terms_for_topic():
    conn = StrongsConnector()
    result = conn.fetch(
        SourceRequest(kind="strongs", query="turn the other cheek")
    )
    assert not result.gap
    assert result.data["terms"]


def test_strongs_connector_records_gap_for_unknown_key():
    conn = StrongsConnector()
    result = conn.fetch(SourceRequest(kind="strongs", reference="Nonexistent 9:99"))
    assert result.gap is True
    assert "no public-domain lexicon" in result.reason


def test_strongs_connector_accepts_injected_dataset():
    dataset = {
        "Topic X": [
            {
                "term": "agape",
                "transliteration": "agape",
                "strongs": "G26",
                "language": "greek",
                "definition": "love",
                "insight": "self-giving love",
                "locator": "G26",
            }
        ]
    }
    conn = StrongsConnector(dataset=dataset)
    result = conn.fetch(SourceRequest(kind="strongs", reference="Topic X"))
    assert not result.gap
    assert result.data["terms"][0]["strongs"] == "G26"


# -------------------------------------------------------------- commentary


def test_commentary_connector_returns_notes_for_reference():
    conn = CommentaryConnector(_offline_cache())
    result = conn.fetch(SourceRequest(kind="commentary", reference="Matthew 5:17"))
    assert not result.gap
    notes = result.data["notes"]
    kinds = {n["kind"] for n in notes}
    assert "cross-reference" in kinds
    assert result.citations


def test_commentary_connector_returns_notes_for_topic():
    conn = CommentaryConnector(_offline_cache())
    result = conn.fetch(
        SourceRequest(kind="commentary", query="turn the other cheek")
    )
    assert not result.gap
    assert result.data["notes"]


def test_commentary_connector_records_gap_for_unknown_key():
    conn = CommentaryConnector(_offline_cache())
    result = conn.fetch(SourceRequest(kind="commentary", reference="Nowhere 1:1"))
    assert result.gap is True


def test_commentary_allowlist_helpers():
    assert host_allowed("https://www.ccel.org/ccel/schaff/npnf110.html")
    assert host_allowed("https://www.newadvent.org/fathers/200118.htm")
    assert not host_allowed("https://evil.example.com/scrape")
    assert path_allowed("https://www.ccel.org/ccel/schaff/npnf110.html")
    assert not path_allowed("https://www.ccel.org/search?q=x")


def test_commentary_skips_offallowlist_urls():
    """A URL that is off the allowlist is skipped rather than scraped."""
    conn = CommentaryConnector(_offline_cache())
    conn._data = lambda: {  # type: ignore[method-assign]
        "Spoof 1:1": [
            {
                "kind": "commentary",
                "excerpt": "should be skipped",
                "source": "Not allowed",
                "locator": "x",
                "url": "https://evil.example.com/page",
            }
        ]
    }
    result = conn.fetch(SourceRequest(kind="commentary", reference="Spoof 1:1"))
    assert result.gap is True
    assert "off-allowlist" in result.reason


# ------------------------------------------------------------------ registry


def test_registry_registers_and_looks_up_connectors():
    reg = SourceRegistry()
    reg.register(StrongsConnector())
    assert reg.has("strongs")
    assert "strongs" in reg.names()
    assert reg.get("strongs").name == "strongs"
    with pytest.raises(KeyError):
        reg.get("missing")
