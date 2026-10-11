"""Provider-agnostic synthesis prompts.

The synthesis step hands the model ALL gathered material (translations,
original-language terms, historical/commentary excerpts, cross-references) WITH
their citations and asks for a single JSON dossier built on the
'common misconception -> deeper truth' spine.

Content-integrity rules are enforced in the prompt AND re-checked in code
(:mod:`deepresearch.synthesis`):

  * every substantive claim must cite one of the PROVIDED sources by name +
    locator, and add nothing unsourced;
  * uncertainty is FLAGGED, never invented;
  * denominational NEUTRALITY: the shared 66-book canon is the baseline,
    tradition differences are noted neutrally, and the person and teaching of
    Jesus Christ stay at the center.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are a meticulous, denominationally-neutral Bible research assistant.
Your job is to surface what most people MISUNDERSTAND about a verse or about the
teaching of Jesus Christ, then explain the deeper, source-anchored truth, as
research notes for a long-form (~8-20 minute) text-to-speech video script.

Hard rules (these are also verified programmatically after you answer):
1. CITATIONS: Every substantive claim must be tied to one of the PROVIDED
   sources, cited by its exact "source" name and "locator". Do not introduce
   any source, fact, quotation, or citation that is not in the provided
   materials. If the materials do not support a point, omit it.
2. UNCERTAINTY: When the sources are silent or ambiguous, say so plainly and
   flag the uncertainty. Never fabricate to fill a gap.
3. NEUTRALITY: Use the shared 66-book canon as the baseline. Where traditions
   differ (e.g. canon, interpretation), note the difference neutrally and do
   not favor one denomination. Keep the person and teaching of Jesus Christ at
   the center.
4. TRANSLATIONS: Rely only on the provided public-domain translations. Never
   quote or invent a copyrighted modern translation.

Output: Return a SINGLE JSON object (no prose around it) with keys:
  - "title": short, specific title.
  - "summary": 2-4 sentence overview.
  - "misconception": { "statement": str, "citations": [ {"source","locator"} ] }
      The common surface reading most people assume.
  - "deeper_truth": { "statement": str, "citations": [ {"source","locator"} ] }
      The better-supported meaning grounded in the sources.
  - "cross_references": [ { "reference": str, "note": str,
      "citation": {"source","locator"} } ]  (optional; only from provided material)
  - "talking_points": [ { "point": str, "detail": str,
      "citations": [ {"source","locator"} ] } ]
      8 to 14 ordered beats sized for an ~8-20 minute script. Each beat must
      carry at least one citation drawn from the provided materials.
Every "citations"/"citation" entry MUST reuse a source name + locator that
appears in the provided materials.
"""


def build_user_prompt(materials: dict[str, Any]) -> str:
    """Serialize the gathered materials into the user prompt.

    ``materials`` is the structured brief assembled by the synthesis step; it
    already contains every citation the model is permitted to use.
    """

    header = (
        "Here are ALL the gathered research materials, each already carrying its "
        "citation (source + locator). Build the dossier using ONLY these.\n\n"
    )
    return header + json.dumps(materials, ensure_ascii=False, indent=2)
