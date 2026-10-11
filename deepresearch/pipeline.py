"""The research pipeline.

Six discrete stages, each a method, chained by :meth:`Pipeline.run`:

1. normalize_reference    - detect reference vs. topic, normalize the reference
2. fetch_translations     - pull the public-domain translations (bible-api)
3. extract_original_terms - pull Strong's / lexicon terms
4. gather_context         - pull historical / commentary / Church-Fathers context
5. synthesize             - build the misconception -> deeper-truth spine via the LLM
6. write_output           - emit JSON + Markdown dossiers

Every connector routes HTTP through the shared cache, so dry-run / offline runs
replay bundled fixtures with zero network. A connector that fails or is offline
without a fixture records a structured :class:`Gap` and the run continues
(graceful degradation) rather than crashing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from deepresearch import SCHEMA_VERSION
from deepresearch.cache import Cache
from deepresearch.fixtures import load_fixture
from deepresearch.config import Config
from deepresearch.llm.base import LLMProvider, build_provider
from deepresearch.models import (
    CommentaryNote,
    CrossReference,
    Dossier,
    Gap,
    HistoricalNote,
    OriginalTerm,
    Translation,
)
from deepresearch.sources.base import Citation, SourceRequest
from deepresearch.sources.bible_api import BibleApiConnector
from deepresearch.sources.commentary import CommentaryConnector
from deepresearch.sources.registry import SourceRegistry
from deepresearch.sources.strongs import StrongsConnector
from deepresearch.synthesis import synthesize

# A loose Bible reference matcher: "Book C:V" / "Book C:V-V" / "1 John 2:3".
_REFERENCE_RE = re.compile(
    r"^\s*(?:[1-3]\s+)?[A-Za-z]+(?:\s+[A-Za-z]+)?\s+\d+(?::\d+(?:-\d+)?)?\s*$"
)


class Pipeline:
    """Orchestrates the six research stages."""

    def __init__(
        self,
        config: Config,
        *,
        registry: Optional[SourceRegistry] = None,
        provider: Optional[LLMProvider] = None,
        cache: Optional[Cache] = None,
    ) -> None:
        self.config = config
        self.cache = cache or Cache(config.cache_dir, offline=config.offline)
        self.registry = registry or self._default_registry()
        self.provider = provider or build_provider(
            config.llm_provider,
            model=config.llm_model,
            api_key=(
                config.openai_api_key
                if config.llm_provider == "openai"
                else config.anthropic_api_key
            ),
        )

    def _default_registry(self) -> SourceRegistry:
        reg = SourceRegistry()
        reg.register(BibleApiConnector(self.cache, context_window=self.config.context_window))
        reg.register(StrongsConnector())
        reg.register(CommentaryConnector(self.cache))
        return reg

    # ------------------------------------------------------------------ stages

    def normalize_reference(self, query: str) -> tuple[str, Optional[str]]:
        """Return (query_kind, normalized_reference)."""
        q = query.strip()
        if _REFERENCE_RE.match(q):
            normalized = re.sub(r"\s+", " ", q)
            return "reference", normalized
        return "topic", None

    def resolve_topic_anchors(self, query: str) -> list[str]:
        """Map a free-text topic to one or more anchor passage references.

        A topic has no primary ``resolved_reference``, but many topics map to
        well-known passages (e.g. "turn the other cheek" -> Matthew 5:39). The
        mapping is data-driven (``fixtures/topic_anchors.json``) so new topics
        drop in without code changes; an unknown topic simply yields ``[]`` and
        the topic dossier carries no scripture text (recorded as a gap).
        """
        try:
            anchors: dict[str, list[str]] = load_fixture("topic_anchors")
        except FileNotFoundError:
            return []
        key = re.sub(r"\s+", " ", query.strip()).lower()
        for topic, refs in anchors.items():
            if topic.strip().lower() == key:
                return list(refs)
        return []

    def fetch_translations(self, references: list[str], gaps: list[Gap]) -> list[Translation]:
        if not references:
            return []
        connector = self.registry.get("bible_api")
        out: list[Translation] = []
        for reference in references:
            for translation in self.config.translations:
                result = connector.fetch(
                    SourceRequest(kind="verse", reference=reference, translation=translation)
                )
                if result.gap:
                    gaps.append(
                        Gap(source=f"bible_api:verse:{translation}", reason=result.reason)
                    )
                    continue
                citation = result.citations[0] if result.citations else Citation(source="bible-api")
                out.append(
                    Translation(
                        translation=translation,
                        reference=result.data.get("reference", reference),
                        text=result.data.get("text", ""),
                        citation=citation,
                    )
                )
        return out

    def extract_original_terms(
        self, reference: Optional[str], query: str, gaps: list[Gap]
    ) -> list[OriginalTerm]:
        connector = self.registry.get("strongs")
        lookup = reference or query
        result = connector.fetch(SourceRequest(kind="strongs", reference=lookup, query=query))
        if result.gap:
            gaps.append(Gap(source="strongs", reason=result.reason))
            return []
        terms: list[OriginalTerm] = []
        for entry in result.data.get("terms", []):
            terms.append(
                OriginalTerm(
                    term=entry.get("term", ""),
                    transliteration=entry.get("transliteration", ""),
                    strongs=entry.get("strongs", ""),
                    language=entry.get("language", "Greek"),
                    definition=entry.get("definition", ""),
                    insight=entry.get("insight", ""),
                    citation=Citation(
                        source=entry.get("source", "Public-domain Strong's lexicon"),
                        locator=entry.get("locator", entry.get("strongs", "")),
                        url=entry.get("url"),
                    ),
                )
            )
        return terms

    def gather_context(
        self, reference: Optional[str], query: str, gaps: list[Gap]
    ) -> tuple[list[HistoricalNote], list[CommentaryNote]]:
        connector = self.registry.get("commentary")
        lookup = reference or query
        result = connector.fetch(SourceRequest(kind="commentary", reference=lookup, query=query))
        if result.gap:
            gaps.append(Gap(source="commentary", reason=result.reason))
            return [], []
        historical: list[HistoricalNote] = []
        commentary: list[CommentaryNote] = []
        for entry in result.data.get("notes", []):
            citation = Citation(
                source=entry.get("source", "Public-domain commentary"),
                locator=entry.get("locator", ""),
                url=entry.get("url"),
            )
            kind = entry.get("kind")
            if kind == "cross-reference":
                # Cross-references are surfaced in their own section.
                continue
            if kind == "historical":
                historical.append(
                    HistoricalNote(text=entry.get("text", entry.get("excerpt", "")), citation=citation)
                )
            else:
                commentary.append(
                    CommentaryNote(
                        source=entry.get("source", "Public-domain commentary"),
                        excerpt=entry.get("excerpt", entry.get("text", "")),
                        citation=citation,
                    )
                )
        return historical, commentary

    def gather_cross_references(
        self, reference: Optional[str], query: str, gaps: list[Gap]
    ) -> list[CrossReference]:
        """Cross-references are served through the commentary connector's data
        (kind == 'cross-reference') so new ones drop in via fixtures."""
        connector = self.registry.get("commentary")
        lookup = reference or query
        result = connector.fetch(
            SourceRequest(kind="commentary", reference=lookup, query=query, params={"xref": True})
        )
        if result.gap:
            return []
        xrefs: list[CrossReference] = []
        for entry in result.data.get("notes", []):
            if entry.get("kind") != "cross-reference":
                continue
            xrefs.append(
                CrossReference(
                    reference=entry.get("reference", entry.get("locator", "")),
                    note=entry.get("text", entry.get("excerpt", "")),
                    citation=Citation(
                        source=entry.get("source", "Public-domain cross-reference"),
                        locator=entry.get("locator", ""),
                        url=entry.get("url"),
                    ),
                )
            )
        return xrefs

    def synthesize(self, dossier: Dossier) -> Dossier:
        return synthesize(dossier, self.provider)

    def write_output(self, dossier: Dossier) -> tuple[Path, Path]:
        """Validate against the schema and write JSON + Markdown dossiers.

        Human-review-gated: files are written to the output dir for review and
        nothing is auto-published.
        """
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        dossier.validate()

        slug = _slugify(dossier.resolved_reference or dossier.query or "dossier")
        json_path = out_dir / f"{slug}.json"
        md_path = out_dir / f"{slug}.md"

        json_path.write_text(dossier.to_json(), encoding="utf-8")
        md_path.write_text(_render_markdown(dossier), encoding="utf-8")
        return json_path, md_path

    # -------------------------------------------------------------------- run

    def run(self, query: str) -> tuple[Path, Path]:
        gaps: list[Gap] = []
        query_kind, normalized = self.normalize_reference(query)

        dossier = Dossier(
            schema_version=SCHEMA_VERSION,
            query=query,
            query_kind=query_kind,
            resolved_reference=normalized,
            provider=self.provider.name,
            model=self.config.llm_model,
        )
        # A verse query fetches its own reference; a topic query resolves to one
        # or more anchor passages so the topic dossier still carries scripture.
        if normalized:
            translation_refs = [normalized]
        else:
            translation_refs = self.resolve_topic_anchors(query)
        dossier.translations = self.fetch_translations(translation_refs, gaps)
        seen_refs: set[str] = set()
        dossier.resolved_references = [
            t.reference
            for t in dossier.translations
            if not (t.reference in seen_refs or seen_refs.add(t.reference))
        ]
        dossier.original_language_terms = self.extract_original_terms(normalized, query, gaps)
        historical, commentary = self.gather_context(normalized, query, gaps)
        dossier.historical_context = historical
        dossier.commentary = commentary
        dossier.cross_references = self.gather_cross_references(normalized, query, gaps)
        dossier.gaps = gaps
        dossier = self.synthesize(dossier)
        return self.write_output(dossier)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug or "dossier"


def _cite_str(c: Citation) -> str:
    bits = [c.source]
    if c.locator:
        bits.append(c.locator)
    label = " - ".join(bits)
    if c.url:
        return f"{label} ({c.url})"
    return label


def _render_markdown(dossier: Dossier) -> str:
    lines: list[str] = []
    lines.append(f"# {dossier.title}")
    lines.append("")
    lines.append(f"> Query: `{dossier.query}` ({dossier.query_kind})")
    if dossier.resolved_reference:
        lines.append(">")
        lines.append(f"> Reference: **{dossier.resolved_reference}**")
    lines.append("")
    lines.append("> Review status: DRAFT - human review required before any publishing.")
    lines.append("")
    if dossier.summary:
        lines.append(dossier.summary)
        lines.append("")

    lines.append("## Misconception")
    if dossier.misconception:
        lines.append(dossier.misconception.statement)
        for c in dossier.misconception.citations:
            lines.append(f"  - _source: {_cite_str(c)}_")
    lines.append("")

    lines.append("## Deeper Truth")
    if dossier.deeper_truth:
        lines.append(dossier.deeper_truth.statement)
        for c in dossier.deeper_truth.citations:
            lines.append(f"  - _source: {_cite_str(c)}_")
    lines.append("")

    if dossier.translations:
        lines.append("## Translations")
        for v in dossier.translations:
            lines.append(f"- **{v.translation.upper()}** ({v.reference}): {v.text}  _({_cite_str(v.citation)})_")
        lines.append("")

    if dossier.original_language_terms:
        lines.append("## Original-Language Insight")
        for t in dossier.original_language_terms:
            lines.append(
                f"- **{t.term}** ({t.transliteration}, {t.strongs}, {t.language}): "
                f"{t.definition} {t.insight}  _({_cite_str(t.citation)})_"
            )
        lines.append("")

    if dossier.historical_context:
        lines.append("## Historical Context")
        for h in dossier.historical_context:
            lines.append(f"- {h.text}  _({_cite_str(h.citation)})_")
        lines.append("")

    if dossier.commentary:
        lines.append("## Commentary")
        for c in dossier.commentary:
            lines.append(f"- **{c.source}**: {c.excerpt}  _({_cite_str(c.citation)})_")
        lines.append("")

    if dossier.cross_references:
        lines.append("## Cross-References")
        for x in dossier.cross_references:
            lines.append(f"- **{x.reference}**: {x.note}  _({_cite_str(x.citation)})_")
        lines.append("")

    if dossier.talking_points:
        lines.append("## Talking Points")
        for i, tp in enumerate(dossier.talking_points, 1):
            cites = "; ".join(_cite_str(c) for c in tp.citations)
            lines.append(f"{i}. **{tp.point}** - {tp.detail}  _({cites})_")
        lines.append("")

    lines.append("## Sources")
    if dossier.citations:
        for c in dossier.citations:
            lines.append(f"- {_cite_str(c)}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Gaps")
    if dossier.gaps:
        for g in dossier.gaps:
            lines.append(f"- `{g.source}`: {g.reason}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("---")
    lines.append(
        f"_Generated by deepresearch (provider: {dossier.provider}, schema {dossier.schema_version}). "
        "Draft for human review; not auto-published._"
    )
    return "\n".join(lines) + "\n"
