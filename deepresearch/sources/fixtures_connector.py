"""A fixtures-backed source connector.

Serves verse text, original-language terms, and commentary context from the
bundled fixtures (and the on-disk cache). This is the connector used by the
dry-run skeleton so the full pipeline shape runs with zero network. FEAT-002
adds the real connectors (bible-api, Strong's, CCEL/New Advent, ...) alongside
this one via the same registry.
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


class FixturesConnector(SourceConnector):
    """Reads bundled sample data keyed by normalized reference."""

    name = "fixtures"

    def fetch(self, request: SourceRequest) -> SourceResult:
        if request.kind == "verse":
            return self._fetch_verse(request)
        if request.kind == "strongs":
            return self._fetch_strongs(request)
        if request.kind == "commentary":
            return self._fetch_commentary(request)
        return SourceResult.missing(self.name, f"unsupported request kind: {request.kind!r}")

    def _fetch_verse(self, request: SourceRequest) -> SourceResult:
        verses: dict[str, Any] = load_fixture("verses")
        ref = request.reference
        translation = (request.translation or "kjv").lower()
        entry = verses.get(ref, {}).get(translation)
        if not entry:
            return SourceResult.missing(
                self.name, f"no fixture verse for {ref!r} ({translation})"
            )
        return SourceResult(
            connector=self.name,
            data=dict(entry),
            citations=[
                Citation(
                    source=f"bible-api ({translation})",
                    locator=entry.get("reference", ref),
                    url=entry.get("url"),
                )
            ],
        )

    def _fetch_strongs(self, request: SourceRequest) -> SourceResult:
        strongs: dict[str, Any] = load_fixture("strongs")
        entries = strongs.get(request.reference)
        if not entries:
            return SourceResult.missing(
                self.name, f"no fixture lexicon data for {request.reference!r}"
            )
        return SourceResult(
            connector=self.name,
            data={"terms": entries},
            citations=[
                Citation(source=e.get("source", "Strong's"), locator=e.get("locator", e.get("strongs", "")))
                for e in entries
            ],
        )

    def _fetch_commentary(self, request: SourceRequest) -> SourceResult:
        commentary: dict[str, Any] = load_fixture("commentary")
        entries = commentary.get(request.reference)
        if not entries:
            return SourceResult.missing(
                self.name, f"no fixture commentary for {request.reference!r}"
            )
        return SourceResult(
            connector=self.name,
            data={"notes": entries},
            citations=[
                Citation(
                    source=e.get("source", "commentary"),
                    locator=e.get("locator", ""),
                    url=e.get("url"),
                )
                for e in entries
            ],
        )
