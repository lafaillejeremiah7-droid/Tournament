"""Source-connector base interface and shared data shapes.

Every connector implements :class:`SourceConnector`. A fetch takes a
:class:`SourceRequest` and returns a :class:`SourceResult` that carries
structured ``data`` plus a list of :class:`Citation` objects. When a source is
unavailable the connector returns a result with ``gap=True`` and a ``reason``
instead of raising, so the pipeline degrades gracefully.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Citation:
    """A pointer to where a claim/datum came from."""

    source: str
    locator: str = ""  # e.g. "Matthew 5:17" or a page/section id
    url: Optional[str] = None
    note: str = ""


@dataclass
class SourceRequest:
    """A request to a source connector."""

    kind: str  # e.g. "verse", "strongs", "commentary"
    reference: str = ""
    query: str = ""
    translation: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceResult:
    """The outcome of a connector fetch."""

    connector: str
    data: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    gap: bool = False
    reason: str = ""

    @classmethod
    def missing(cls, connector: str, reason: str) -> "SourceResult":
        """Build a graceful-degradation 'gap' result."""
        return cls(connector=connector, data={}, citations=[], gap=True, reason=reason)


class SourceConnector(abc.ABC):
    """Abstract base for all source connectors."""

    #: Stable connector name used for registry lookup and citations.
    name: str = ""

    @abc.abstractmethod
    def fetch(self, request: SourceRequest) -> SourceResult:
        """Fetch structured data for ``request``.

        Implementations must NOT raise for an unavailable source; return
        ``SourceResult.missing(...)`` instead so the pipeline can record a gap.
        """
        raise NotImplementedError
