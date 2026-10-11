"""Synthesis: turn gathered materials into the dossier via an LLM provider.

This module is provider-agnostic. It:

1. assembles the gathered source material (translations, original-language
   terms, historical/commentary excerpts, cross-references) into a brief that
   already carries every citation the model is allowed to use;
2. calls the selected :class:`~deepresearch.llm.base.LLMProvider` with the
   shared synthesis prompt;
3. parses the JSON result into the :class:`~deepresearch.models.Dossier`
   spine (misconception / deeper_truth / talking_points / cross_references);
4. runs a post-synthesis INTEGRITY CHECK that drops or flags any claim whose
   citation cannot be resolved back to a gathered source, and records
   uncertainty as a gap.

The deterministic stub provider returns fixture-grounded content, so dry-run
yields a complete, schema-valid dossier with zero network and zero keys.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from deepresearch.llm.base import LLMProvider
from deepresearch.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from deepresearch.models import (
    Citation,
    Claim,
    CrossReference,
    Dossier,
    Gap,
    TalkingPoint,
)


def _citation_key(source: str, locator: str) -> tuple[str, str]:
    return (source.strip().lower(), (locator or "").strip().lower())


def build_materials(dossier: Dossier) -> dict[str, Any]:
    """Assemble the citation-carrying brief handed to the LLM."""

    def cite(c: Citation) -> dict[str, Any]:
        d: dict[str, Any] = {"source": c.source, "locator": c.locator}
        if c.url:
            d["url"] = c.url
        return d

    return {
        "query": dossier.query,
        "query_kind": dossier.query_kind,
        "resolved_reference": dossier.resolved_reference,
        "resolved_references": dossier.resolved_references,
        "translations": [
            {
                "translation": t.translation,
                "reference": t.reference,
                "text": t.text,
                "citation": cite(t.citation),
            }
            for t in dossier.translations
        ],
        "original_language_terms": [
            {
                "term": t.term,
                "transliteration": t.transliteration,
                "strongs": t.strongs,
                "language": t.language,
                "definition": t.definition,
                "insight": t.insight,
                "citation": cite(t.citation),
            }
            for t in dossier.original_language_terms
        ],
        "historical_context": [
            {"text": h.text, "citation": cite(h.citation)} for h in dossier.historical_context
        ],
        "commentary": [
            {"source": c.source, "excerpt": c.excerpt, "citation": cite(c.citation)}
            for c in dossier.commentary
        ],
        "cross_references": [
            {"reference": x.reference, "note": x.note, "citation": cite(x.citation)}
            for x in dossier.cross_references
        ],
    }


def _known_citations(dossier: Dossier) -> dict[tuple[str, str], Citation]:
    """Index every citation already attached to gathered material."""
    index: dict[tuple[str, str], Citation] = {}

    def add(c: Citation) -> None:
        index.setdefault(_citation_key(c.source, c.locator), c)
        # Also index by source-only so a claim can cite a source without a
        # perfectly-matching locator.
        index.setdefault(_citation_key(c.source, ""), c)

    for t in dossier.translations:
        add(t.citation)
    for t in dossier.original_language_terms:
        add(t.citation)
    for h in dossier.historical_context:
        add(h.citation)
    for c in dossier.commentary:
        add(c.citation)
    for x in dossier.cross_references:
        add(x.citation)
    return index


def _resolve_citations(
    raw: list[dict[str, Any]], known: dict[tuple[str, str], Citation]
) -> list[Citation]:
    """Keep only citations that resolve to a gathered source."""
    resolved: list[Citation] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        locator = str(item.get("locator", "")).strip()
        if not source:
            continue
        hit = known.get(_citation_key(source, locator)) or known.get(_citation_key(source, ""))
        if hit is not None:
            resolved.append(Citation(source=hit.source, locator=hit.locator, url=hit.url))
    return resolved


def synthesize(dossier: Dossier, provider: LLMProvider) -> Dossier:
    """Run the LLM synthesis and the integrity check, mutating ``dossier``."""

    materials = build_materials(dossier)
    raw = provider.complete(SYSTEM_PROMPT, build_user_prompt(materials))

    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        parsed = {}
        dossier.gaps.append(
            Gap(source=f"llm:{provider.name}", reason="synthesis returned non-JSON output")
        )

    known = _known_citations(dossier)

    dossier.title = parsed.get("title") or f"What most people miss about {dossier.query}"
    dossier.summary = parsed.get("summary", "")

    # --- spine: misconception + deeper_truth ------------------------------
    dossier.misconception = _build_claim(parsed.get("misconception"), known, dossier, "misconception")
    dossier.deeper_truth = _build_claim(parsed.get("deeper_truth"), known, dossier, "deeper_truth")

    # --- cross references (only those the model grounded in material) -----
    xrefs: list[CrossReference] = []
    for x in parsed.get("cross_references", []) or []:
        if not isinstance(x, dict):
            continue
        cits = _resolve_citations([x.get("citation", {})], known)
        if not cits:
            continue
        xrefs.append(
            CrossReference(
                reference=str(x.get("reference", "")),
                note=str(x.get("note", "")),
                citation=cits[0],
            )
        )
    if xrefs:
        dossier.cross_references = xrefs

    # --- talking points ---------------------------------------------------
    points: list[TalkingPoint] = []
    dropped = 0
    for tp in parsed.get("talking_points", []) or []:
        if not isinstance(tp, dict):
            continue
        cits = _resolve_citations(tp.get("citations", []), known)
        point = str(tp.get("point", "")).strip()
        if not point:
            continue
        if not cits:
            # Integrity: a substantive beat with no resolvable citation is dropped.
            dropped += 1
            continue
        points.append(
            TalkingPoint(point=point, detail=str(tp.get("detail", "")), citations=cits)
        )
    dossier.talking_points = points

    if dropped:
        dossier.gaps.append(
            Gap(
                source=f"llm:{provider.name}",
                reason=f"integrity check dropped {dropped} talking point(s) lacking a resolvable citation",
            )
        )

    if not dossier.talking_points:
        # Guarantee a non-empty, honestly-flagged script even when no sources
        # were gathered (full graceful degradation): never fabricate citations.
        dossier.talking_points = [
            TalkingPoint(
                point="Insufficient sourced material",
                detail=(
                    "No public-domain source material was available for this query, so no "
                    "sourced talking points could be produced. This dossier needs more sources "
                    "before human review and must not be published as-is."
                ),
                citations=[],
            )
        ]
        dossier.gaps.append(
            Gap(
                source="integrity:talking_points",
                reason="no sourced talking points available; emitted a flagged review placeholder",
            )
        )

    dossier.build_citation_index()
    return dossier


def _build_claim(
    raw: Optional[dict[str, Any]],
    known: dict[tuple[str, str], Citation],
    dossier: Dossier,
    label: str,
) -> Claim:
    """Build a required spine claim; flag uncertainty if uncited/empty."""
    if not isinstance(raw, dict):
        raw = {}
    statement = str(raw.get("statement", "")).strip()
    cits = _resolve_citations(raw.get("citations", []), known)

    if not cits:
        # Required claim must carry a citation. Prefer the strongest gathered
        # source so the dossier stays schema-valid, and flag it for review.
        fallback = _first_citation(dossier)
        if fallback is not None:
            cits = [fallback]
            dossier.gaps.append(
                Gap(
                    source=f"integrity:{label}",
                    reason=f"'{label}' lacked a resolvable citation; attached nearest gathered source and flagged for review",
                )
            )
        else:
            # No external source exists at all (full degradation). Attach an
            # HONEST provenance pointer to the integrity check itself rather
            # than fabricating an external citation, and flag the uncertainty.
            cits = [
                Citation(
                    source="deepresearch integrity check",
                    locator=f"unsourced:{label}",
                    note="no public-domain source was available; flagged for human review",
                )
            ]
            dossier.gaps.append(
                Gap(
                    source=f"integrity:{label}",
                    reason=f"'{label}' had no gathered source; marked unsourced and flagged for review",
                )
            )
    if not statement:
        statement = f"[uncertain] The sources did not yield a clear {label.replace('_', ' ')}."
        dossier.gaps.append(
            Gap(source=f"integrity:{label}", reason=f"synthesis produced no {label} statement")
        )
    return Claim(statement=statement, citations=cits)


def _first_citation(dossier: Dossier) -> Optional[Citation]:
    for t in dossier.translations:
        return t.citation
    for t in dossier.original_language_terms:
        return t.citation
    for h in dossier.historical_context:
        return h.citation
    for c in dossier.commentary:
        return c.citation
    return None
