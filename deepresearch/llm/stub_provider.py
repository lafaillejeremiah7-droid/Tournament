"""Deterministic, fixture-backed stub LLM provider.

Produces reproducible, schema-shaped synthesis content with no network and no
API keys so dry-run and tests are deterministic. The pipeline passes a compact
JSON "brief" of the gathered sources as the user prompt; the stub echoes a
stable, grounded summary derived from it rather than inventing content.
"""

from __future__ import annotations

import json
from typing import Optional

from deepresearch.llm.base import LLMProvider


class StubProvider(LLMProvider):
    """Deterministic provider used in dry-run and tests."""

    name = "stub"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or "stub-deterministic-1"

    def complete(self, system: str, user: str) -> str:
        """Return a deterministic, grounded synthesis as JSON text.

        ``user`` is expected to be a JSON brief built by the pipeline. The stub
        reflects it back into a dossier-shaped structure. If parsing fails it
        still returns valid JSON so the pipeline never crashes in dry-run.
        """

        try:
            brief = json.loads(user)
        except (ValueError, TypeError):
            brief = {}

        query = brief.get("query", "")
        reference = brief.get("normalized_reference") or query
        terms = brief.get("original_terms", [])
        notes = brief.get("context_notes", [])

        gloss_bits = ", ".join(
            f"{t.get('transliteration', t.get('surface', ''))} ({t.get('gloss', '')})"
            for t in terms
            if t.get("gloss")
        )

        misconception = (
            f"Many assume {reference} means the old commands no longer matter."
            if reference
            else "Many assume this teaching cancels what came before it."
        )
        deeper_truth = (
            "The text points to continuity and completion rather than cancellation: "
            "the earlier Scriptures find their intended goal, not their deletion."
        )
        explanation = (
            "Grounded in the gathered sources"
            + (f", the key terms ({gloss_bits}) contrast 'abolish' with 'bring to full expression'. " if gloss_bits else ". ")
            + "The deeper truth is read in continuity with the shared 66-book canon, noting tradition "
            "differences neutrally and without inventing claims the sources do not support."
        )

        long_form = (
            f"[DRY-RUN PLACEHOLDER] Long-form study of {reference or query}.\n\n"
            "This deterministic stub stands in for the FEAT-002 synthesis step. "
            "It demonstrates the misconception -> deeper-truth spine while every "
            "substantive claim remains tied to a gathered source.\n\n"
            + "\n".join(f"- Context: {n.get('summary', '')}" for n in notes)
        ).strip()

        payload = {
            "title": f"What most people miss about {reference or query}".strip(),
            "summary": (
                f"A grounded look at {reference or query}: common misreadings versus the deeper, "
                "source-anchored meaning of Jesus Christ's teaching."
            ),
            "misconceptions": [
                {
                    "misconception": misconception,
                    "deeper_truth": deeper_truth,
                    "explanation": explanation,
                }
            ],
            "long_form": long_form,
        }
        return json.dumps(payload)
