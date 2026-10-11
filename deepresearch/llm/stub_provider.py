"""Deterministic, fixture-grounded stub LLM provider.

Produces reproducible, schema-shaped synthesis content with no network and no
API keys so dry-run and tests are deterministic. It consumes the JSON brief of
gathered materials built by :mod:`deepresearch.synthesis` and reflects it back
into a dossier-shaped structure, REUSING the citations present in the brief so
the integrity check always passes. It invents no sources.

The misconception / deeper-truth spine prose is DETERMINISTIC SCAFFOLDING
templated from the gathered material (it reuses a provided commentary or
historical excerpt), so it tracks the query rather than hardcoding a single
theme. It is placeholder structure for dry-run and tests, not model-quality
analysis; live providers (openai/anthropic) produce the real spine.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from deepresearch.llm.base import LLMProvider


class StubProvider(LLMProvider):
    """Deterministic provider used in dry-run and tests."""

    name = "stub"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or "stub-deterministic-1"

    def complete(self, system: str, user: str) -> str:  # noqa: ARG002 - system unused
        brief = self._parse_brief(user)

        query = brief.get("query", "")
        reference = brief.get("resolved_reference") or query or "this teaching"
        translations = brief.get("translations", [])
        terms = brief.get("original_language_terms", [])
        historical = brief.get("historical_context", [])
        commentary = brief.get("commentary", [])
        xrefs = brief.get("cross_references", [])

        # Collect the citations the brief actually provided, in priority order.
        term_cites = [t["citation"] for t in terms if t.get("citation")]
        trans_cites = [t["citation"] for t in translations if t.get("citation")]
        hist_cites = [h["citation"] for h in historical if h.get("citation")]
        comm_cites = [c["citation"] for c in commentary if c.get("citation")]
        all_cites = trans_cites + term_cites + hist_cites + comm_cites

        if not all_cites:
            # Nothing gathered: return a minimal, honestly-uncertain payload.
            return json.dumps(
                {
                    "title": f"What most people miss about {reference}",
                    "summary": "No public-domain sources were available for this query in offline mode.",
                    "misconception": {"statement": "", "citations": []},
                    "deeper_truth": {"statement": "", "citations": []},
                    "talking_points": [],
                }
            )

        gloss_bits = ", ".join(
            f"{t.get('transliteration') or t.get('term', '')} ({t.get('definition', '')})"
            for t in terms
            if t.get("definition")
        )

        misconception_cite = comm_cites[0] if comm_cites else all_cites[0]
        truth_cites = (term_cites[:1] or trans_cites[:1] or all_cites[:1]) + comm_cites[:1]

        # Derive the spine prose from the gathered material so the dry-run text
        # tracks THIS query instead of a hardcoded theme. The deeper-truth
        # statement reuses a classic commentary excerpt (or historical note)
        # that the brief actually provided; the misconception frames the surface
        # reading the sources push back on. This is deterministic scaffolding,
        # not model-quality prose (see the stub's module docstring and README).
        source_insight = ""
        if commentary and commentary[0].get("excerpt"):
            source_insight = commentary[0]["excerpt"].strip()
        elif historical and historical[0].get("text"):
            source_insight = historical[0]["text"].strip()

        misconception = {
            "statement": (
                f"Many people take {reference} at surface level and assume its plain wording "
                "settles the matter, without weighing how the original language, historical "
                "setting, and the wider teaching of Jesus Christ shape its meaning."
            ),
            "citations": [misconception_cite],
        }
        truth_statement = (
            f"Read against the gathered public-domain sources, {reference} carries a deeper, "
            "better-supported meaning than the surface reading suggests"
        )
        if source_insight:
            truth_statement += f": {source_insight}"
        elif gloss_bits:
            truth_statement += f", as the key terms ({gloss_bits}) make clear"
        truth_statement += "." if not truth_statement.endswith(".") else ""
        deeper_truth = {
            "statement": truth_statement,
            "citations": truth_cites or [all_cites[0]],
        }

        talking_points = self._build_talking_points(
            reference, translations, terms, historical, commentary, all_cites
        )

        cross_references = [
            {
                "reference": x.get("reference", ""),
                "note": x.get("note", ""),
                "citation": x.get("citation", {}),
            }
            for x in xrefs
            if x.get("citation")
        ]

        payload: dict[str, Any] = {
            "title": f"What most people miss about {reference}",
            "summary": (
                f"A grounded, denominationally-neutral look at {reference}: the common surface "
                "reading versus the deeper, source-anchored meaning of Jesus Christ's teaching, "
                "drawn only from public-domain sources."
            ),
            "misconception": misconception,
            "deeper_truth": deeper_truth,
            "cross_references": cross_references,
            "talking_points": talking_points,
        }
        return json.dumps(payload)

    # ------------------------------------------------------------- internals

    @staticmethod
    def _parse_brief(user: str) -> dict[str, Any]:
        # The user prompt is a header line followed by a JSON block.
        start = user.find("{")
        if start == -1:
            return {}
        try:
            return json.loads(user[start:])
        except (ValueError, TypeError):
            return {}

    def _build_talking_points(
        self,
        reference: str,
        translations: list,
        terms: list,
        historical: list,
        commentary: list,
        all_cites: list,
    ) -> list[dict[str, Any]]:
        """Build 8+ ordered, cited beats sized for a long-form script."""
        points: list[dict[str, Any]] = []

        def add(point: str, detail: str, cites: list) -> None:
            points.append({"point": point, "detail": detail, "citations": cites or [all_cites[0]]})

        add(
            "Open with the common assumption",
            f"State plainly how most listeners first hear {reference} and why that reading feels natural.",
            [all_cites[0]],
        )
        if translations:
            t0 = translations[0]
            add(
                "Read the passage in public-domain translations",
                f"Compare the wording across translations, e.g. {t0.get('translation', '').upper()}: "
                f"\"{t0.get('text', '')}\".",
                [t.get("citation") for t in translations if t.get("citation")][:3],
            )
        for term in terms:
            add(
                f"Unpack the key word '{term.get('transliteration') or term.get('term', '')}'",
                f"{term.get('definition', '')} {term.get('insight', '')}".strip()
                + f" (Strong's {term.get('strongs', '')}, {term.get('language', '')}).",
                [term.get("citation")],
            )
        for h in historical:
            add(
                "Set the historical and cultural scene",
                h.get("text", ""),
                [h.get("citation")],
            )
        for c in commentary:
            add(
                f"Hear a classic voice: {c.get('source', 'commentary')}",
                c.get("excerpt", ""),
                [c.get("citation")],
            )
        add(
            "Name the misconception directly",
            "Contrast the surface reading with what the gathered sources actually support, "
            "flagging any point the sources leave uncertain rather than filling the gap.",
            all_cites[:2],
        )
        add(
            "Land the deeper truth",
            "Summarize the better-supported meaning in continuity with the shared 66-book canon, "
            "noting tradition differences neutrally and centering the teaching of Jesus Christ.",
            all_cites[:2],
        )
        add(
            "Close with application",
            "Invite the listener to carry the deeper truth into daily life, without overstating "
            "beyond the sources.",
            [all_cites[0]],
        )
        return points
