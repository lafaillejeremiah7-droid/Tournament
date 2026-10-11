"""Bible text connector backed by bible-api.com.

Fetches the target verse and the surrounding passage (per
``config.context_window``) across the configured public-domain translations.
All HTTP goes through :class:`deepresearch.cache.Cache` so dry-run / tests
replay recorded fixtures and never touch the network.

COPYRIGHT SAFETY: only public-domain translations are ever requested. The
allowlist below is enforced BEFORE any URL is built, so a copyrighted modern
translation (NIV/ESV/...) is rejected and never fetched.
"""

from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import quote

from deepresearch.cache import Cache
from deepresearch.fixtures import load_fixture
from deepresearch.sources.base import (
    Citation,
    SourceConnector,
    SourceRequest,
    SourceResult,
)

#: Public-domain translations bible-api.com serves. NEVER add copyrighted
#: modern translations (NIV, ESV, NASB, NLT, ...). Keys are the API's codes.
PUBLIC_DOMAIN_TRANSLATIONS = {
    "kjv": "King James Version (public domain)",
    "web": "World English Bible (public domain)",
    "asv": "American Standard Version (public domain)",
    "bbe": "Bible in Basic English (public domain)",
    "ylt": "Young's Literal Translation (public domain)",
    "dra": "Douay-Rheims 1899 American Edition (public domain)",
    "oeb-us": "Open English Bible, US spelling (public domain)",
}

API_BASE = "https://bible-api.com"
USER_AGENT = "deepresearch-bot/0.1 (public-domain scripture research; contact: maintainer)"


class CopyrightedTranslationError(ValueError):
    """Raised when a non-public-domain translation is requested."""


def is_public_domain(translation: str) -> bool:
    return translation.strip().lower() in PUBLIC_DOMAIN_TRANSLATIONS


def _build_url(reference: str, translation: str) -> str:
    return f"{API_BASE}/{quote(reference)}?translation={translation}"


class BibleApiConnector(SourceConnector):
    """Fetch public-domain scripture text from bible-api.com (cached)."""

    name = "bible_api"

    def __init__(self, cache: Cache, *, context_window: int = 5) -> None:
        self.cache = cache
        self.context_window = max(0, int(context_window))

    def fetch(self, request: SourceRequest) -> SourceResult:
        if request.kind != "verse":
            return SourceResult.missing(self.name, f"unsupported request kind: {request.kind!r}")

        translation = (request.translation or "kjv").strip().lower()
        if not is_public_domain(translation):
            # Hard refusal: never build a URL or fetch a copyrighted text.
            return SourceResult.missing(
                self.name,
                f"translation {translation!r} is not on the public-domain allowlist; refused",
            )

        reference = request.reference
        passage_ref = self._passage_reference(reference, request)
        url = _build_url(passage_ref, translation)
        signature = f"{passage_ref}|{translation}"

        body = self._read(signature, url)
        if body is None:
            body = self._fixture_body(reference, translation)
        if body is None:
            return SourceResult.missing(
                self.name,
                f"no cached/fixture text for {passage_ref!r} ({translation}) and network unavailable",
            )

        try:
            data = json.loads(body)
        except (ValueError, TypeError):
            return SourceResult.missing(
                self.name, f"malformed bible-api payload for {passage_ref!r} ({translation})"
            )

        text = _normalize_text(data)
        resolved_ref = data.get("reference", passage_ref)
        return SourceResult(
            connector=self.name,
            data={"reference": resolved_ref, "text": text, "translation": translation},
            citations=[
                Citation(
                    source=PUBLIC_DOMAIN_TRANSLATIONS[translation],
                    locator=resolved_ref,
                    url=url,
                )
            ],
        )

    # ------------------------------------------------------------- internals

    def _read(self, signature: str, url: str) -> Optional[str]:
        """Read through the cache; swallow network errors into a gap."""
        try:
            return self.cache.fetch("bible_api", signature, url)
        except Exception:  # noqa: BLE001 - degrade gracefully, never crash
            return None

    def _fixture_body(self, reference: str, translation: str) -> Optional[str]:
        """Fall back to a bundled fixture entry rendered as a bible-api body."""
        try:
            verses = load_fixture("verses")
        except FileNotFoundError:
            return None
        entry = verses.get(reference, {}).get(translation)
        if not entry:
            return None
        return json.dumps(
            {
                "reference": entry.get("reference", reference),
                "text": entry.get("text", ""),
                "translation_id": translation,
            }
        )

    def _passage_reference(self, reference: str, request: SourceRequest) -> str:
        """Expand a single verse to a passage spanning the context window.

        ``Matthew 5:17`` with window 2 becomes ``Matthew 5:15-19``. A reference
        that is already a range, or lacks a verse number, is left as-is.
        """

        window = int(request.params.get("context_window", self.context_window))
        if window <= 0:
            return reference
        m = re.match(r"^(.*?\s\d+):(\d+)\s*$", reference)
        if not m:
            return reference
        book_chapter, verse_s = m.group(1), m.group(2)
        verse = int(verse_s)
        start = max(1, verse - window)
        end = verse + window
        if start == end:
            return f"{book_chapter}:{start}"
        return f"{book_chapter}:{start}-{end}"


def _normalize_text(data: dict) -> str:
    """Join bible-api 'verses' into a single readable passage string."""
    if isinstance(data.get("verses"), list) and data["verses"]:
        parts = [str(v.get("text", "")).strip() for v in data["verses"]]
        return " ".join(p for p in parts if p).strip()
    return str(data.get("text", "")).strip()
