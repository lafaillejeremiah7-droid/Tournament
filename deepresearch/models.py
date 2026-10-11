"""Dossier data model.

These dataclasses define the shape of the research dossier that the pipeline
produces. The structure mirrors ``deepresearch/schema/dossier.schema.json`` so
downstream bots in the pipeline have a stable, versioned contract.

Every substantive claim object carries at least one :class:`Citation`. The
dossier is built around a 'common misconception vs. deeper truth' spine
(``misconception`` + ``deeper_truth``) plus the supporting material gathered by
the source connectors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from deepresearch import SCHEMA_VERSION

# Re-exported here so callers can import the citation shape from a single place
# without reaching into deepresearch.sources.base.
from deepresearch.sources.base import Citation

# Re-exported so callers can import the neutrality finding shape from the model
# module alongside the dossier it attaches to.
from deepresearch.neutrality import ReviewFlag

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "dossier.schema.json"


def _citation_to_dict(c: Citation) -> dict[str, Any]:
    out: dict[str, Any] = {"source": c.source}
    if c.locator:
        out["locator"] = c.locator
    if c.url:
        out["url"] = c.url
    if c.note:
        out["note"] = c.note
    return out


def _citations_to_list(cs: list[Citation]) -> list[dict[str, Any]]:
    return [_citation_to_dict(c) for c in cs]


@dataclass
class Claim:
    """A substantive statement that must carry at least one citation.

    Used for the two spine sections (``misconception`` / ``deeper_truth``).
    """

    statement: str
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "citations": _citations_to_list(self.citations),
        }


@dataclass
class Translation:
    """A single public-domain translation of the target passage."""

    translation: str
    reference: str
    text: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "translation": self.translation,
            "reference": self.reference,
            "text": self.text,
            "citation": _citation_to_dict(self.citation),
        }


@dataclass
class OriginalTerm:
    """An original-language term (Greek/Hebrew) tied to the passage."""

    term: str
    transliteration: str
    strongs: str
    language: str  # "Greek" | "Hebrew"
    definition: str
    insight: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "transliteration": self.transliteration,
            "strongs": self.strongs,
            "language": self.language,
            "definition": self.definition,
            "insight": self.insight,
            "citation": _citation_to_dict(self.citation),
        }


@dataclass
class HistoricalNote:
    """A piece of historical / cultural background."""

    text: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "citation": _citation_to_dict(self.citation)}


@dataclass
class CommentaryNote:
    """A classic / public-domain commentary or Church-Father excerpt."""

    source: str
    excerpt: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "excerpt": self.excerpt,
            "citation": _citation_to_dict(self.citation),
        }


@dataclass
class CrossReference:
    """A related passage with a short note."""

    reference: str
    note: str
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "note": self.note,
            "citation": _citation_to_dict(self.citation),
        }


@dataclass
class TalkingPoint:
    """A single beat of the long-form script, each with its citations."""

    point: str
    detail: str
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point,
            "detail": self.detail,
            "citations": _citations_to_list(self.citations),
        }


@dataclass
class Gap:
    """A graceful-degradation record: a source that was unavailable or that
    returned nothing, noted instead of crashing the run."""

    source: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "reason": self.reason}


@dataclass
class Dossier:
    """Top-level research dossier."""

    schema_version: str = SCHEMA_VERSION
    query: str = ""
    query_kind: str = "reference"  # "reference" | "topic"
    resolved_reference: Optional[str] = None
    resolved_references: list[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    misconception: Optional[Claim] = None
    deeper_truth: Optional[Claim] = None
    translations: list[Translation] = field(default_factory=list)
    original_language_terms: list[OriginalTerm] = field(default_factory=list)
    historical_context: list[HistoricalNote] = field(default_factory=list)
    commentary: list[CommentaryNote] = field(default_factory=list)
    cross_references: list[CrossReference] = field(default_factory=list)
    talking_points: list[TalkingPoint] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    provider: str = "stub"
    model: Optional[str] = None
    # Optional, additive neutrality findings (see deepresearch/neutrality.py).
    # Always emitted in to_dict() as a list ([] when empty), which stays
    # schema-valid because review_flags is NOT in the schema's required list.
    review_flags: list[ReviewFlag] = field(default_factory=list)

    # ----------------------------------------------------------- citation index

    def build_citation_index(self) -> None:
        """Populate ``citations`` with every distinct citation in the dossier.

        Dedupe is by (source, locator, url). Call this after synthesis so the
        flat index downstream bots consume is always in sync with the body.
        """

        seen: set[tuple[str, str, Optional[str]]] = set()
        index: list[Citation] = []

        def add(cs: list[Citation]) -> None:
            for c in cs:
                key = (c.source, c.locator, c.url)
                if key not in seen:
                    seen.add(key)
                    index.append(c)

        if self.misconception:
            add(self.misconception.citations)
        if self.deeper_truth:
            add(self.deeper_truth.citations)
        for t in self.translations:
            add([t.citation])
        for term in self.original_language_terms:
            add([term.citation])
        for h in self.historical_context:
            add([h.citation])
        for cm in self.commentary:
            add([cm.citation])
        for xr in self.cross_references:
            add([xr.citation])
        for tp in self.talking_points:
            add(tp.citations)

        self.citations = index

    # ----------------------------------------------------------- serialization

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "query": self.query,
            "query_kind": self.query_kind,
            "resolved_reference": self.resolved_reference,
            "resolved_references": list(self.resolved_references),
            "title": self.title,
            "summary": self.summary,
            "misconception": (self.misconception or Claim("", [])).to_dict(),
            "deeper_truth": (self.deeper_truth or Claim("", [])).to_dict(),
            "translations": [t.to_dict() for t in self.translations],
            "original_language_terms": [t.to_dict() for t in self.original_language_terms],
            "historical_context": [h.to_dict() for h in self.historical_context],
            "commentary": [c.to_dict() for c in self.commentary],
            "cross_references": [x.to_dict() for x in self.cross_references],
            "talking_points": [t.to_dict() for t in self.talking_points],
            "gaps": [g.to_dict() for g in self.gaps],
            "citations": _citations_to_list(self.citations),
            "provider": self.provider,
            "model": self.model,
            "review_flags": [f.to_dict() for f in self.review_flags],
        }
        return payload

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def validate(self) -> None:
        """Validate ``self`` against the bundled JSON Schema.

        Raises ``jsonschema.ValidationError`` on failure.
        """

        import jsonschema

        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=self.to_dict(), schema=schema)
