"""The research pipeline.

Six discrete stages, each a method, chained by :meth:`Pipeline.run`:

1. normalize_reference  - detect reference vs. topic, normalize the reference
2. fetch_translations   - pull the public-domain translations
3. extract_original_terms - pull Strong's / lexicon terms
4. gather_context       - pull historical / commentary / Church-Fathers context
5. synthesize           - build the misconception -> truth spine via the LLM
6. write_output         - emit JSON + Markdown dossiers

In FEAT-001 the data comes from the bundled fixtures connector and the
deterministic stub provider, but the stage boundaries, data shapes, and
graceful-degradation (gap recording) are real. FEAT-002 fills in real logic.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from deepresearch import SCHEMA_VERSION
from deepresearch.cache import Cache
from deepresearch.config import Config
from deepresearch.llm.base import LLMProvider, build_provider
from deepresearch.llm.prompts import SYSTEM_PROMPT
from deepresearch.models import (
    ContextNote,
    Dossier,
    Gap,
    MisconceptionTruth,
    OriginalTerm,
    VerseText,
)
from deepresearch.sources.base import Citation, SourceRequest
from deepresearch.sources.fixtures_connector import FixturesConnector
from deepresearch.sources.registry import SourceRegistry

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
        self.cache = cache or Cache(config.cache_dir, offline=config.offline)

    @staticmethod
    def _default_registry() -> SourceRegistry:
        reg = SourceRegistry()
        reg.register(FixturesConnector())
        return reg

    # ------------------------------------------------------------------ stages

    def normalize_reference(self, query: str) -> tuple[str, Optional[str]]:
        """Return (query_kind, normalized_reference)."""
        q = query.strip()
        if _REFERENCE_RE.match(q):
            # Normalize whitespace; keep the human-readable form.
            normalized = re.sub(r"\s+", " ", q)
            return "reference", normalized
        return "topic", None

    def fetch_translations(self, reference: Optional[str], gaps: list[Gap]) -> list[VerseText]:
        if not reference:
            return []
        connector = self.registry.get("fixtures")
        out: list[VerseText] = []
        for translation in self.config.translations:
            result = connector.fetch(
                SourceRequest(kind="verse", reference=reference, translation=translation)
            )
            if result.gap:
                gaps.append(Gap(source=f"{result.connector}:verse:{translation}", reason=result.reason))
                continue
            out.append(
                VerseText(
                    translation=translation,
                    reference=result.data.get("reference", reference),
                    text=result.data.get("text", ""),
                    citations=result.citations,
                )
            )
        return out

    def extract_original_terms(self, reference: Optional[str], gaps: list[Gap]) -> list[OriginalTerm]:
        if not reference:
            return []
        connector = self.registry.get("fixtures")
        result = connector.fetch(SourceRequest(kind="strongs", reference=reference))
        if result.gap:
            gaps.append(Gap(source=f"{result.connector}:strongs", reason=result.reason))
            return []
        terms: list[OriginalTerm] = []
        for entry in result.data.get("terms", []):
            terms.append(
                OriginalTerm(
                    surface=entry.get("surface", ""),
                    transliteration=entry.get("transliteration", ""),
                    strongs=entry.get("strongs", ""),
                    gloss=entry.get("gloss", ""),
                    language=entry.get("language", "greek"),
                    citations=[
                        Citation(
                            source=entry.get("source", "Strong's"),
                            locator=entry.get("locator", entry.get("strongs", "")),
                        )
                    ],
                )
            )
        return terms

    def gather_context(self, reference: Optional[str], query: str, gaps: list[Gap]) -> list[ContextNote]:
        connector = self.registry.get("fixtures")
        lookup = reference or query
        result = connector.fetch(SourceRequest(kind="commentary", reference=lookup, query=query))
        if result.gap:
            gaps.append(Gap(source=f"{result.connector}:commentary", reason=result.reason))
            return []
        notes: list[ContextNote] = []
        for entry in result.data.get("notes", []):
            notes.append(
                ContextNote(
                    kind=entry.get("kind", "commentary"),
                    summary=entry.get("summary", ""),
                    citations=[
                        Citation(
                            source=entry.get("source", "commentary"),
                            locator=entry.get("locator", ""),
                            url=entry.get("url"),
                        )
                    ],
                )
            )
        return notes

    def synthesize(self, dossier: Dossier) -> Dossier:
        """Build the misconception -> truth spine and long-form via the LLM."""
        brief = {
            "query": dossier.query,
            "query_kind": dossier.query_kind,
            "normalized_reference": dossier.normalized_reference,
            "translations": [{"translation": v.translation, "text": v.text} for v in dossier.translations],
            "original_terms": [
                {"surface": t.surface, "transliteration": t.transliteration, "gloss": t.gloss}
                for t in dossier.original_terms
            ],
            "context_notes": [{"kind": n.kind, "summary": n.summary} for n in dossier.context_notes],
        }
        raw = self.provider.complete(SYSTEM_PROMPT, json.dumps(brief))
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            parsed = {}
            dossier.gaps.append(Gap(source=f"llm:{self.provider.name}", reason="non-JSON synthesis output"))

        dossier.title = parsed.get("title", dossier.title or f"Study of {dossier.query}")
        dossier.summary = parsed.get("summary", "")
        dossier.long_form = parsed.get("long_form", "")
        dossier.misconceptions = [
            MisconceptionTruth(
                misconception=m.get("misconception", ""),
                deeper_truth=m.get("deeper_truth", ""),
                explanation=m.get("explanation", ""),
            )
            for m in parsed.get("misconceptions", [])
        ]
        return dossier

    def write_output(self, dossier: Dossier) -> tuple[Path, Path]:
        """Validate against the schema and write JSON + Markdown dossiers."""
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = dossier.to_dict()
        self._validate(payload)

        slug = _slugify(dossier.normalized_reference or dossier.query or "dossier")
        json_path = out_dir / f"{slug}.json"
        md_path = out_dir / f"{slug}.md"

        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
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
            normalized_reference=normalized,
            provider=self.provider.name,
            model=self.config.llm_model,
        )
        dossier.translations = self.fetch_translations(normalized, gaps)
        dossier.original_terms = self.extract_original_terms(normalized, gaps)
        dossier.context_notes = self.gather_context(normalized, query, gaps)
        dossier.gaps = gaps
        dossier = self.synthesize(dossier)
        return self.write_output(dossier)

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _validate(payload: dict) -> None:
        import jsonschema

        schema_path = Path(__file__).resolve().parent / "schema" / "dossier.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=payload, schema=schema)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug or "dossier"


def _render_markdown(dossier: Dossier) -> str:
    lines: list[str] = []
    lines.append(f"# {dossier.title}")
    lines.append("")
    lines.append(f"> Query: `{dossier.query}` ({dossier.query_kind})")
    if dossier.normalized_reference:
        lines.append(f">")
        lines.append(f"> Reference: **{dossier.normalized_reference}**")
    lines.append("")
    lines.append(dossier.summary)
    lines.append("")

    if dossier.translations:
        lines.append("## Translations")
        for v in dossier.translations:
            cite = v.citations[0].source if v.citations else v.translation
            lines.append(f"- **{v.translation.upper()}** — {v.text}  _({cite})_")
        lines.append("")

    if dossier.original_terms:
        lines.append("## Original-language terms")
        for t in dossier.original_terms:
            lines.append(f"- **{t.surface}** ({t.transliteration}, {t.strongs}): {t.gloss}")
        lines.append("")

    if dossier.context_notes:
        lines.append("## Context")
        for n in dossier.context_notes:
            cite = n.citations[0].source if n.citations else n.kind
            lines.append(f"- *{n.kind}*: {n.summary}  _({cite})_")
        lines.append("")

    if dossier.misconceptions:
        lines.append("## Common misconception vs. deeper truth")
        for m in dossier.misconceptions:
            lines.append(f"### Misconception")
            lines.append(m.misconception)
            lines.append("")
            lines.append(f"### Deeper truth")
            lines.append(m.deeper_truth)
            lines.append("")
            lines.append(m.explanation)
            lines.append("")

    if dossier.long_form:
        lines.append("## Long-form study")
        lines.append(dossier.long_form)
        lines.append("")

    if dossier.gaps:
        lines.append("## Gaps (sources unavailable)")
        for g in dossier.gaps:
            lines.append(f"- `{g.source}`: {g.reason}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated by deepresearch (provider: {dossier.provider}, schema {dossier.schema_version})_")
    return "\n".join(lines) + "\n"
