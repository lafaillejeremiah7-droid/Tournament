"""Original-language key-term connector (public-domain Strong's lexicon).

Maps the pivotal words of a passage/topic to their Strong's number, Greek or
Hebrew lemma, a public-domain definition, and an interpretive insight, each
with a citation.

The data is loaded from a bundled, public-domain Strong's subset
(``deepresearch/fixtures/strongs.json``). The connector is intentionally
data-driven: dropping in a fuller public-domain Strong's dataset (same JSON
shape, keyed by reference/topic) extends coverage WITHOUT any code change.
"""

from __future__ import annotations

from typing import Any

from deepresearch.fixtures import load_fixture
from deepresearch.sources.base import (
    Citation,
    SourceConnector,
    SourceRequest,
    SourceResult,
)

DEFAULT_SOURCE = "Public-domain Strong's lexicon"

#: Normalize the language field to the schema's capitalized enum.
_LANGUAGE_MAP = {
    "greek": "Greek",
    "hebrew": "Hebrew",
    "grc": "Greek",
    "heb": "Hebrew",
}


class StrongsConnector(SourceConnector):
    """Resolve pivotal original-language terms for a reference or topic."""

    name = "strongs"

    def __init__(self, dataset: dict[str, Any] | None = None) -> None:
        # Allow injecting a larger dataset; default to the bundled subset.
        self._dataset = dataset

    def _data(self) -> dict[str, Any]:
        if self._dataset is not None:
            return self._dataset
        try:
            return load_fixture("strongs")
        except FileNotFoundError:
            return {}

    def fetch(self, request: SourceRequest) -> SourceResult:
        if request.kind != "strongs":
            return SourceResult.missing(self.name, f"unsupported request kind: {request.kind!r}")

        data = self._data()
        key = request.reference or request.query
        entries = data.get(key)
        if not entries:
            return SourceResult.missing(
                self.name, f"no public-domain lexicon data for {key!r}"
            )

        normalized: list[dict[str, Any]] = []
        citations: list[Citation] = []
        for e in entries:
            language = _LANGUAGE_MAP.get(str(e.get("language", "greek")).lower(), "Greek")
            source = e.get("source", DEFAULT_SOURCE)
            locator = e.get("locator", e.get("strongs", ""))
            citation = Citation(source=source, locator=locator, url=e.get("url"))
            citations.append(citation)
            normalized.append(
                {
                    "term": e.get("term", e.get("surface", "")),
                    "transliteration": e.get("transliteration", ""),
                    "strongs": e.get("strongs", ""),
                    "language": language,
                    "definition": e.get("definition", e.get("gloss", "")),
                    "insight": e.get("insight", ""),
                    "source": source,
                    "locator": locator,
                    "url": e.get("url"),
                }
            )

        return SourceResult(
            connector=self.name,
            data={"terms": normalized},
            citations=citations,
        )
