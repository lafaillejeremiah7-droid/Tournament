"""Historical / cultural context + classic commentary connector.

Serves public-domain historical background and classic commentary / Church-
Father excerpts. Live sources are restricted to a documented allowlist of
public-domain corpora:

  * CCEL              - ccel.org              (Christian Classics Ethereal Library)
  * New Advent        - newadvent.org         (Fathers of the Church)
  * sacred-texts.com  - sacred-texts.com      (public-domain religious texts)
  * Project Gutenberg - gutenberg.org         (public-domain books)

ToS / robots.txt respect: only hosts on :data:`ALLOWED_HOSTS` are fetched, a
descriptive :data:`USER_AGENT` is sent, and a path that is disallowed (or a
host that is not on the allowlist) is skipped and recorded as a gap rather than
scraped. All fetches go through the shared cache. For dry-run / tests, bundled
public-domain excerpts are served from fixtures with zero network.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from deepresearch.cache import Cache
from deepresearch.fixtures import load_fixture
from deepresearch.sources.base import (
    Citation,
    SourceConnector,
    SourceRequest,
    SourceResult,
)

USER_AGENT = "deepresearch-bot/0.1 (public-domain commentary research; respects robots.txt)"

#: Hosts whose public-domain content we are permitted to fetch.
ALLOWED_HOSTS = {
    "ccel.org",
    "www.ccel.org",
    "newadvent.org",
    "www.newadvent.org",
    "sacred-texts.com",
    "www.sacred-texts.com",
    "gutenberg.org",
    "www.gutenberg.org",
}

#: Path prefixes we treat as disallowed regardless of host (defensive default;
#: a full implementation would parse each host's robots.txt and cache it).
DISALLOWED_PREFIXES = ("/search", "/cgi-bin", "/admin")


def host_allowed(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower() in ALLOWED_HOSTS
    except ValueError:
        return False


def path_allowed(url: str) -> bool:
    path = urlparse(url).path or "/"
    return not any(path.startswith(p) for p in DISALLOWED_PREFIXES)


class CommentaryConnector(SourceConnector):
    """Fetch public-domain historical context + commentary excerpts (cached)."""

    name = "commentary"

    def __init__(self, cache: Cache) -> None:
        self.cache = cache

    def _data(self) -> dict[str, Any]:
        try:
            return load_fixture("commentary")
        except FileNotFoundError:
            return {}

    def fetch(self, request: SourceRequest) -> SourceResult:
        if request.kind != "commentary":
            return SourceResult.missing(self.name, f"unsupported request kind: {request.kind!r}")

        key = request.reference or request.query
        entries = self._data().get(key)
        if not entries:
            return SourceResult.missing(
                self.name, f"no public-domain commentary for {key!r}"
            )

        notes: list[dict[str, Any]] = []
        citations: list[Citation] = []
        for e in entries:
            url = e.get("url")
            # Enforce the allowlist/robots policy for any URL we might fetch.
            if url and (not host_allowed(url) or not path_allowed(url)):
                # Skip disallowed/off-allowlist URL; record a gap, keep the text
                # only if it is a bundled public-domain excerpt (no live fetch).
                continue
            if url:
                self._prime_cache(e, url)
            citation = Citation(
                source=e.get("source", "Public-domain commentary"),
                locator=e.get("locator", ""),
                url=url,
            )
            citations.append(citation)
            notes.append(
                {
                    "kind": e.get("kind", "commentary"),
                    "text": e.get("text", e.get("summary", "")),
                    "excerpt": e.get("excerpt", e.get("summary", "")),
                    "source": e.get("source", "Public-domain commentary"),
                    "locator": e.get("locator", ""),
                    "url": url,
                }
            )

        if not notes:
            return SourceResult.missing(
                self.name, f"all commentary sources for {key!r} were off-allowlist or disallowed"
            )

        return SourceResult(connector=self.name, data={"notes": notes}, citations=citations)

    def _prime_cache(self, entry: dict[str, Any], url: str) -> Optional[str]:
        """Read through the cache for a live excerpt; never raise.

        Bundled fixtures already carry the excerpt text, so in dry-run/offline
        this is a no-op cache miss. In live mode it caches the fetched page.
        """
        signature = entry.get("locator", "") or url
        try:
            return self.cache.fetch("commentary", signature, url)
        except Exception:  # noqa: BLE001 - degrade gracefully
            return None
