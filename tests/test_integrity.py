"""Citation-integrity enforcement: the product's moat.

The stub provider only ever reuses citations present in the brief, so the
drop/flag/fallback paths in :mod:`deepresearch.synthesis` never fire in the
rest of the suite. This module drives those paths directly with a FAKE provider
that fabricates and omits citations, and asserts the runtime behavior:

  * a talking point whose citation does not resolve to gathered material is
    DROPPED and counted into a ``Gap``;
  * a talking point whose citation DOES resolve survives;
  * the required spine claims (misconception / deeper_truth) that cite nothing
    resolvable get a FLAGGED fallback citation (the nearest gathered source) and
    a matching ``integrity:<label>`` gap;
  * when no material was gathered at all, the spine gets an honest, non-fabricated
    integrity-check provenance pointer instead of an invented source;
  * no fabricated source name ever survives into the dossier.

Runs fully offline with no keys (the autouse conftest guard still applies).
"""

from __future__ import annotations

import json

from deepresearch import SCHEMA_VERSION
from deepresearch.llm.base import LLMProvider
from deepresearch.models import (
    Citation,
    CommentaryNote,
    Dossier,
    OriginalTerm,
    Translation,
)
from deepresearch.synthesis import synthesize


class FabricatingProvider(LLMProvider):
    """A fake provider that returns made-up and uncited claims.

    It ignores the brief and emits a payload with (a) one talking point citing a
    source that was never gathered, (b) one talking point whose citation DOES
    match a gathered source, (c) one talking point with no citations at all, and
    (d) spine claims citing a fabricated source. This is exactly the adversarial
    shape the integrity check exists to defend against.
    """

    name = "fake"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "fake-1"

    def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        payload = {
            "title": "Fabricated title",
            "summary": "A payload full of made-up and uncited claims.",
            "misconception": {
                "statement": "A plausible-sounding but uncited misconception.",
                "citations": [{"source": "Totally Made Up Source", "locator": "99:99"}],
            },
            "deeper_truth": {
                "statement": "A deeper truth citing a source that was never gathered.",
                "citations": [{"source": "Another Fabricated Source", "locator": "fake"}],
            },
            "talking_points": [
                {
                    "point": "fabricated",
                    "detail": "cites a source that does not exist in the brief",
                    "citations": [{"source": "Nonexistent Journal", "locator": "p.1"}],
                },
                {
                    "point": "cited",
                    "detail": "cites a real gathered source",
                    "citations": [
                        {"source": "King James Version (public domain)", "locator": "Matthew 5:17"}
                    ],
                },
                {
                    "point": "uncited",
                    "detail": "carries no citations at all",
                    "citations": [],
                },
            ],
        }
        return json.dumps(payload)


class EmptyProvider(LLMProvider):
    """A fake provider that fabricates spine claims when NOTHING was gathered."""

    name = "empty"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "empty-1"

    def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        payload = {
            "title": "No sources",
            "summary": "",
            "misconception": {
                "statement": "An uncited misconception with nothing gathered.",
                "citations": [{"source": "Invented", "locator": "x"}],
            },
            "deeper_truth": {
                "statement": "An uncited deeper truth with nothing gathered.",
                "citations": [{"source": "Invented", "locator": "y"}],
            },
            "talking_points": [
                {"point": "fabricated", "detail": "no sources exist", "citations": []}
            ],
        }
        return json.dumps(payload)


def _dossier_with_material() -> Dossier:
    kjv = Citation(source="King James Version (public domain)", locator="Matthew 5:17")
    strongs = Citation(source="Public-domain Strong's Greek lexicon", locator="G4137")
    comm = Citation(source="Public-domain patristic commentary (CCEL)", locator="Commentary on Matthew")
    d = Dossier(
        schema_version=SCHEMA_VERSION,
        query="Matthew 5:17",
        query_kind="reference",
        resolved_reference="Matthew 5:17",
        provider="fake",
    )
    d.translations = [
        Translation(translation="kjv", reference="Matthew 5:17", text="Think not...", citation=kjv)
    ]
    d.original_language_terms = [
        OriginalTerm(
            term="plerosai",
            transliteration="plerosai",
            strongs="G4137",
            language="Greek",
            definition="to fulfill",
            insight="bring to the goal",
            citation=strongs,
        )
    ]
    d.commentary = [
        CommentaryNote(source="Public-domain patristic commentary (CCEL)", excerpt="...", citation=comm)
    ]
    return d


def test_fabricated_talking_point_is_dropped_and_cited_one_survives():
    d = _dossier_with_material()
    synthesize(d, FabricatingProvider())

    points = {tp.point for tp in d.talking_points}
    # The fabricated and uncited beats are dropped; only the resolvable one lives.
    assert points == {"cited"}

    dropped_gaps = [g for g in d.gaps if "integrity check dropped" in g.reason]
    assert dropped_gaps, "a gap must record the dropped talking points"
    # Two beats (fabricated + uncited) were dropped.
    assert "dropped 2 talking point(s)" in dropped_gaps[0].reason
    assert dropped_gaps[0].source == "llm:fake"


def test_spine_claims_get_flagged_fallback_citation():
    d = _dossier_with_material()
    synthesize(d, FabricatingProvider())

    # Both spine claims cited fabricated sources; the integrity check must have
    # replaced them with the nearest gathered source (never the made-up one).
    for label in ("misconception", "deeper_truth"):
        claim = getattr(d, label)
        assert claim.citations, f"{label} must keep at least one citation"
        for c in claim.citations:
            assert c.source != "Totally Made Up Source"
            assert c.source != "Another Fabricated Source"
        # And a gap flags the substitution for human review.
        gaps = [g for g in d.gaps if g.source == f"integrity:{label}"]
        assert gaps, f"{label} substitution must be flagged as a gap"

    # No fabricated source name may survive anywhere in the citation index.
    d.build_citation_index()
    fabricated = {"Totally Made Up Source", "Another Fabricated Source", "Nonexistent Journal"}
    for c in d.citations:
        assert c.source not in fabricated


def test_dossier_validates_after_integrity_fixups():
    d = _dossier_with_material()
    synthesize(d, FabricatingProvider())
    d.validate()  # raises on schema failure


def test_no_material_yields_honest_unsourced_pointer_not_fabrication():
    d = Dossier(
        schema_version=SCHEMA_VERSION,
        query="an obscure topic with no sources",
        query_kind="topic",
        resolved_reference=None,
        provider="empty",
    )
    synthesize(d, EmptyProvider())

    # Spine claims must carry an honest integrity-check pointer, not the invented
    # source the fake model supplied.
    for label in ("misconception", "deeper_truth"):
        claim = getattr(d, label)
        assert claim.citations
        for c in claim.citations:
            assert c.source == "deepresearch integrity check"
            assert c.source != "Invented"

    # No sourced talking points survive, so the flagged review placeholder fires.
    assert len(d.talking_points) == 1
    assert d.talking_points[0].point == "Insufficient sourced material"
    assert d.talking_points[0].citations == []
    assert any(g.source == "integrity:talking_points" for g in d.gaps)

    d.validate()  # still schema-valid
