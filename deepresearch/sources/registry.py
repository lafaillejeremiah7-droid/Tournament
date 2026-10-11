"""Connector registry.

Maps a connector name to an instance so new connectors drop in without editing
the pipeline core. A registry is a plain object (not a global singleton) so the
pipeline and tests can build isolated sets of connectors.
"""

from __future__ import annotations

from typing import Iterable

from deepresearch.sources.base import SourceConnector


class SourceRegistry:
    """A small name -> connector-instance registry."""

    def __init__(self) -> None:
        self._connectors: dict[str, SourceConnector] = {}

    def register(self, connector: SourceConnector) -> SourceConnector:
        """Register a connector by its ``name``. Returns the connector."""
        if not connector.name:
            raise ValueError("connector.name must be a non-empty string")
        self._connectors[connector.name] = connector
        return connector

    def get(self, name: str) -> SourceConnector:
        """Return the connector registered under ``name``."""
        try:
            return self._connectors[name]
        except KeyError as exc:
            raise KeyError(f"no source connector registered under {name!r}") from exc

    def has(self, name: str) -> bool:
        return name in self._connectors

    def all(self) -> Iterable[SourceConnector]:
        """Return all registered connectors."""
        return list(self._connectors.values())

    def names(self) -> list[str]:
        return list(self._connectors.keys())
