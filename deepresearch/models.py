"""Dossier data model.

These dataclasses define the shape of the research dossier that the pipeline
produces. FEAT-002 finalizes the synthesis content; the shapes and the JSON
Schema version live here so downstream bots have a stable contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from deepresearch import SCHEMA_VERSION

# Re-exported here so callers can import the source dataclasses from a single
# place without reaching into deepresearch.sources.base.
from deepresearch.sources.base import Citation


@dataclass
class VerseText:
    """A single translation of the target passage."""

    translation: str
    reference: str
    text: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class OriginalTerm:
    """An original-language term (Greek/Hebrew) tied to the passage."""

    surface: str
    transliteration: str
    strongs: str
    gloss: str
    language: str = "greek"
    citations: list[Citation] = field(default_factory=list)


@dataclass
class ContextNote:
    """A piece of historical / literary / commentary context."""

    kind: str  # e.g. "historical", "literary", "commentary", "church-fathers"
    summary: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class MisconceptionTruth:
    """The core 'spine' of the dossier: a common misconception paired with the
    deeper truth, each grounded in citations."""

    misconception: str
    deeper_truth: str
    explanation: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class Gap:
    """A graceful-degradation record: a source that was unavailable or that
    returned nothing, noted instead of crashing the run."""

    source: str
    reason: str


@dataclass
class Dossier:
    """Top-level research dossier."""

    schema_version: str = SCHEMA_VERSION
    query: str = ""
    query_kind: str = "reference"  # "reference" | "topic"
    normalized_reference: Optional[str] = None
    title: str = ""
    summary: str = ""
    translations: list[VerseText] = field(default_factory=list)
    original_terms: list[OriginalTerm] = field(default_factory=list)
    context_notes: list[ContextNote] = field(default_factory=list)
    misconceptions: list[MisconceptionTruth] = field(default_factory=list)
    long_form: str = ""
    gaps: list[Gap] = field(default_factory=list)
    provider: str = "stub"
    model: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
