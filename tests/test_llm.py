"""Stage 5 (LLM abstraction): the deterministic stub provider.

The stub provider is used in dry-run and tests. It must be deterministic,
reuse only the citations present in the brief (invents no sources), and return
schema-shaped JSON. The provider factory must build it with no SDK and no key.
"""

from __future__ import annotations

import json

from deepresearch.llm.base import LLMProvider, build_provider
from deepresearch.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from deepresearch.llm.stub_provider import StubProvider


def _brief() -> dict:
    return {
        "query": "Matthew 5:17",
        "query_kind": "reference",
        "resolved_reference": "Matthew 5:17",
        "resolved_references": ["Matthew 5:17"],
        "translations": [
            {
                "translation": "kjv",
                "reference": "Matthew 5:17",
                "text": "Think not that I am come to destroy the law...",
                "citation": {"source": "King James Version (public domain)", "locator": "Matthew 5:17"},
            }
        ],
        "original_language_terms": [
            {
                "term": "plerosai",
                "transliteration": "plerosai",
                "strongs": "G4137",
                "language": "Greek",
                "definition": "to fulfill",
                "insight": "to bring to the intended goal",
                "citation": {"source": "Public-domain Strong's Greek lexicon", "locator": "G4137"},
            }
        ],
        "historical_context": [],
        "commentary": [
            {
                "source": "Public-domain patristic commentary (CCEL)",
                "excerpt": "fulfil means completion",
                "citation": {"source": "Public-domain patristic commentary (CCEL)", "locator": "Commentary on Matthew"},
            }
        ],
        "cross_references": [],
    }


def test_factory_builds_stub_without_sdk_or_key():
    provider = build_provider("stub")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "stub"


def test_stub_provider_is_deterministic():
    provider = StubProvider()
    user = build_user_prompt(_brief())
    out1 = provider.complete(SYSTEM_PROMPT, user)
    out2 = provider.complete(SYSTEM_PROMPT, user)
    assert out1 == out2


def test_stub_provider_returns_schema_shaped_json():
    provider = StubProvider()
    out = provider.complete(SYSTEM_PROMPT, build_user_prompt(_brief()))
    parsed = json.loads(out)
    assert parsed["misconception"]["statement"]
    assert parsed["deeper_truth"]["statement"]
    assert parsed["talking_points"]
    # Every citation reuses a source present in the brief (invents nothing).
    allowed_sources = {
        "King James Version (public domain)",
        "Public-domain Strong's Greek lexicon",
        "Public-domain patristic commentary (CCEL)",
    }
    for tp in parsed["talking_points"]:
        for c in tp["citations"]:
            assert c["source"] in allowed_sources


def test_stub_provider_handles_empty_brief_without_inventing_sources():
    provider = StubProvider()
    empty = {"query": "mystery topic", "translations": [], "original_language_terms": [],
             "historical_context": [], "commentary": [], "cross_references": []}
    parsed = json.loads(provider.complete(SYSTEM_PROMPT, build_user_prompt(empty)))
    assert parsed["misconception"]["citations"] == []
    assert parsed["talking_points"] == []
