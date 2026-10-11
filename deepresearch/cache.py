"""On-disk fetch cache with an injectable HTTP getter.

The cache is keyed by a hash of (connector, request-signature). In dry-run /
offline mode it reads ONLY from the on-disk cache (and connectors fall back to
bundled fixtures) and never touches the network. In live mode it reads through
to the injected HTTP getter and writes responses to ``cache_dir``.

The HTTP getter is injected so tests and dry-run can supply fixture bytes
instead of performing real requests. The default live getter lazily imports
``requests`` so the package imports without any network stack exercised.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

# An HTTP getter takes a URL and returns the response body text.
HttpGetter = Callable[[str], str]


def default_http_getter(url: str, *, timeout: float = 20.0) -> str:
    """Live HTTP GET using ``requests`` (imported lazily)."""
    import requests  # local import: keep requests out of import-time path

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


class Cache:
    """A tiny read-through / replay cache over text payloads."""

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        offline: bool = False,
        http_getter: Optional[HttpGetter] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        # In offline mode we never fall back to a live getter.
        self._http_getter = http_getter

    def _key_path(self, namespace: str, signature: str) -> Path:
        digest = hashlib.sha256(f"{namespace}:{signature}".encode("utf-8")).hexdigest()
        return self.cache_dir / namespace / f"{digest}.json"

    def read(self, namespace: str, signature: str) -> Optional[str]:
        """Return a cached payload, or ``None`` if not present."""
        path = self._key_path(namespace, signature)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))["body"]
        return None

    def write(self, namespace: str, signature: str, body: str) -> None:
        """Persist a payload for later replay."""
        path = self._key_path(namespace, signature)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"signature": signature, "body": body}), encoding="utf-8")

    def fetch(self, namespace: str, signature: str, url: str) -> Optional[str]:
        """Read-through fetch.

        Returns a cached payload if present. In offline mode, returns ``None``
        on a miss (the caller then falls back to bundled fixtures or records a
        gap). In live mode, performs the HTTP GET, caches it, and returns it.
        """
        cached = self.read(namespace, signature)
        if cached is not None:
            return cached
        if self.offline:
            return None
        getter = self._http_getter or default_http_getter
        body = getter(url)
        self.write(namespace, signature, body)
        return body
