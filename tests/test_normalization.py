"""Stage 1: reference-vs-topic normalization.

Covers the verse-reference parsing path AND the topic -> candidate-passage
path (a free-text topic resolves to no primary reference but is still routed
through the connectors by its query text).
"""

from __future__ import annotations

import pytest

from deepresearch.config import Config
from deepresearch.pipeline import Pipeline


def _pipeline() -> Pipeline:
    # Dry-run config is inherently offline + stub provider: no net, no keys.
    return Pipeline(Config.from_env_and_args(dry_run=True, load_env_file=False))


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Matthew 5:17", "Matthew 5:17"),
        ("  Matthew   5:17 ", "Matthew 5:17"),
        ("1 John 2:3", "1 John 2:3"),
        ("John 3:16-17", "John 3:16-17"),
        ("Genesis 1", "Genesis 1"),
        ("2 Corinthians 5:17", "2 Corinthians 5:17"),
    ],
)
def test_verse_reference_is_detected_and_normalized(query, expected):
    kind, normalized = _pipeline().normalize_reference(query)
    assert kind == "reference"
    assert normalized == expected


@pytest.mark.parametrize(
    "query",
    [
        "turn the other cheek",
        "what did Jesus mean by the kingdom of heaven",
        "the meaning of grace",
    ],
)
def test_free_text_topic_is_detected_as_topic(query):
    kind, normalized = _pipeline().normalize_reference(query)
    assert kind == "topic"
    assert normalized is None


def test_topic_path_routes_candidate_passages_through_connectors():
    """A topic yields no primary reference but still gathers sourced material.

    This exercises the topic -> candidate-passage path: the Strong's and
    commentary connectors are keyed by the query text, so a topic produces
    original-language terms, commentary, and cross-references.
    """
    pipe = _pipeline()
    gaps: list = []
    terms = pipe.extract_original_terms(None, "turn the other cheek", gaps)
    historical, commentary = pipe.gather_context(None, "turn the other cheek", gaps)
    xrefs = pipe.gather_cross_references(None, "turn the other cheek", gaps)

    assert terms, "topic should resolve original-language terms"
    assert commentary, "topic should resolve commentary"
    assert xrefs, "topic should resolve cross references"
    # No verse reference means translations are not fetched for a topic.
    assert pipe.fetch_translations(None, gaps) == []
