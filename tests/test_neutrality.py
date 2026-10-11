"""Deterministic denominational-neutrality scanner tests.

These exercise :mod:`deepresearch.neutrality` the way the integrity tests
exercise the citation check: with an adversarial FAKE provider that emits
deliberately side-taking prose, plus the deterministic stub dry-run to guard
against false positives. Everything runs fully offline with no keys (the autouse
conftest guard still applies).

What is proven here:
  * loaded, side-taking prose is flagged with the correct category/snippet after
    synthesize + the neutrality check;
  * neutral prose ("traditions differ ...") yields ZERO flags;
  * the deterministic stub dry-run (end-to-end) produces NO neutrality flags on
    the fixture-backed topics;
  * the dossier validates both WITH flags present and WITHOUT any flags (empty);
  * the check NEVER mutates the underlying statements / talking points.
"""

from __future__ import annotations

import copy
import json

import jsonschema

from deepresearch import SCHEMA_VERSION
from deepresearch.config import Config
from deepresearch.llm.base import LLMProvider
from deepresearch.models import (
    Citation,
    Claim,
    CommentaryNote,
    Dossier,
    OriginalTerm,
    ReviewFlag,
    TalkingPoint,
    Translation,
)
from deepresearch.neutrality import check_neutrality
from deepresearch.pipeline import Pipeline
from deepresearch.synthesis import synthesize


# --------------------------------------------------------------------------- #
# Fake providers
# --------------------------------------------------------------------------- #


class LoadedProvider(LLMProvider):
    """A fake provider that emits deliberately side-taking denominational prose.

    Every claim it fabricates cites a REAL gathered source so the integrity
    check keeps the prose (we want the neutrality scanner, not the integrity
    check, to be what reacts to it).
    """

    name = "loaded"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "loaded-1"

    def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        cite = {"source": "King James Version (public domain)", "locator": "Matthew 5:17"}
        payload = {
            "title": "The one true church and the infallible authority of the Pope",
            "summary": "This proves baptism is required for salvation.",
            "misconception": {
                "statement": "Some think the Eucharist is merely symbolic.",
                "citations": [cite],
            },
            "deeper_truth": {
                "statement": "Salvation is by faith alone, and once saved always saved.",
                "citations": [cite],
            },
            "talking_points": [
                {
                    "point": "The one true church",
                    "detail": "Outside the church there is no salvation, and the Pope is infallible.",
                    "citations": [cite],
                },
            ],
        }
        return json.dumps(payload)


class NeutralProvider(LLMProvider):
    """A fake provider that emits careful, denominationally-neutral prose."""

    name = "neutral"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or "neutral-1"

    def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        cite = {"source": "King James Version (public domain)", "locator": "Matthew 5:17"}
        payload = {
            "title": "What most people miss about Matthew 5:17",
            "summary": (
                "Traditions differ on the details, and some denominations hold "
                "different views; the difference is noted neutrally."
            ),
            "misconception": {
                "statement": "Many assume the plain wording settles the matter.",
                "citations": [cite],
            },
            "deeper_truth": {
                "statement": (
                    "Read against the gathered sources, the passage carries a deeper, "
                    "better-supported meaning, with the work of the Spirit in baptism "
                    "and faith described as different traditions understand it."
                ),
                "citations": [cite],
            },
            "talking_points": [
                {
                    "point": "Note where traditions differ",
                    "detail": "Some denominations hold one view and others another; both are noted.",
                    "citations": [cite],
                },
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


def _schema() -> dict:
    from pathlib import Path

    import deepresearch

    schema_path = Path(deepresearch.__file__).resolve().parent / "schema" / "dossier.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# (a) loaded prose is flagged with correct category/snippet
# --------------------------------------------------------------------------- #


def test_loaded_prose_is_flagged_with_categories():
    d = _dossier_with_material()
    synthesize(d, LoadedProvider())
    flags = check_neutrality(d)

    categories = {f.category for f in flags}
    assert "one-true-church" in categories
    assert "papal-magisterial-authority" in categories
    assert "baptismal-regeneration-or-mode" in categories
    assert "eucharist-real-presence-vs-symbol" in categories
    assert "faith-alone-vs-works" in categories
    assert "predestination-or-eternal-security" in categories

    # Each flag carries a non-empty snippet that includes the loaded phrasing.
    for f in flags:
        assert f.snippet.strip()
        assert f.severity == "advisory"
        assert f.reason.strip()

    # The matched snippet for the papal flag should contain the loaded phrase.
    papal = [f for f in flags if f.category == "papal-magisterial-authority"]
    assert any("pope is infallible" in f.snippet.lower() for f in papal)


# --------------------------------------------------------------------------- #
# (b) neutral prose yields ZERO flags
# --------------------------------------------------------------------------- #


def test_neutral_prose_yields_zero_flags():
    d = _dossier_with_material()
    synthesize(d, NeutralProvider())
    flags = check_neutrality(d)
    assert flags == [], f"neutral prose must not be flagged, got: {[f.to_dict() for f in flags]}"


def test_bare_mentions_are_not_flagged():
    """A conservative scanner must not fire on neutral descriptive mentions."""
    d = Dossier(schema_version=SCHEMA_VERSION, query="x", query_kind="topic")
    d.misconception = Claim("Baptism and the Eucharist are discussed across traditions.", [])
    d.deeper_truth = Claim("The Pope and purgatory are mentioned descriptively here.", [])
    d.talking_points = [
        TalkingPoint("Faith and works", "Mary and tongues come up in church history.", [])
    ]
    assert check_neutrality(d) == []


# --------------------------------------------------------------------------- #
# (c) dry-run end-to-end on fixture-backed topics yields NO neutrality flags
# --------------------------------------------------------------------------- #


def _run_dry(tmp_path, query: str) -> dict:
    config = Config.from_env_and_args(
        dry_run=True,
        output_dir=str(tmp_path / "out"),
        cache_dir=str(tmp_path / "cache"),
        load_env_file=False,
    )
    pipe = Pipeline(config)
    json_path, _ = pipe.run(query)
    return json.loads(json_path.read_text(encoding="utf-8"))


def test_dry_run_stub_produces_no_neutrality_flags(tmp_path):
    for i, query in enumerate(
        ["Matthew 5:17", "judge not", "born again", "turn the other cheek"]
    ):
        data = _run_dry(tmp_path / f"q{i}", query)
        assert "review_flags" in data
        assert data["review_flags"] == [], (
            f"stub boilerplate must not be flagged for {query!r}: {data['review_flags']}"
        )


# --------------------------------------------------------------------------- #
# (d) schema validates WITH and WITHOUT flags
# --------------------------------------------------------------------------- #


def test_dossier_validates_with_and_without_flags():
    schema = _schema()

    d = _dossier_with_material()
    synthesize(d, LoadedProvider())

    # Without any flags (empty list is the default).
    assert d.review_flags == []
    d.validate()
    jsonschema.validate(instance=d.to_dict(), schema=schema)
    assert d.to_dict()["review_flags"] == []

    # With flags attached.
    d.review_flags = check_neutrality(d)
    assert d.review_flags, "loaded prose should have produced flags"
    d.validate()
    jsonschema.validate(instance=d.to_dict(), schema=schema)
    emitted = d.to_dict()["review_flags"]
    assert emitted and all(
        set(f) == {"category", "snippet", "reason", "severity"} for f in emitted
    )


def test_review_flag_roundtrips_to_dict():
    f = ReviewFlag(category="purgatory", snippet="...souls in purgatory...", reason="r")
    assert f.to_dict() == {
        "category": "purgatory",
        "snippet": "...souls in purgatory...",
        "reason": "r",
        "severity": "advisory",
    }


# --------------------------------------------------------------------------- #
# (e) the check NEVER mutates statements / talking points
# --------------------------------------------------------------------------- #


def test_check_does_not_mutate_dossier():
    d = _dossier_with_material()
    synthesize(d, LoadedProvider())

    before_misconception = d.misconception.statement
    before_deeper = d.deeper_truth.statement
    before_title = d.title
    before_summary = d.summary
    before_points = copy.deepcopy([(tp.point, tp.detail) for tp in d.talking_points])

    flags = check_neutrality(d)
    assert flags  # it did find something, so this is a meaningful test

    assert d.misconception.statement == before_misconception
    assert d.deeper_truth.statement == before_deeper
    assert d.title == before_title
    assert d.summary == before_summary
    assert [(tp.point, tp.detail) for tp in d.talking_points] == before_points
