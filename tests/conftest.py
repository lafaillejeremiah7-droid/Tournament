"""Shared pytest fixtures and the no-network safety net.

The entire suite MUST run with zero network and zero API keys. Two guards
enforce that:

1. ``_block_network`` (autouse) unsets any API keys and monkeypatches the
   package's default live HTTP getter so that *any* real request attempted
   during a test raises :class:`NetworkAccessError` and fails the test loudly.
2. Connectors are always constructed with an OFFLINE :class:`Cache`, so the
   read-through path can never reach the live getter in the first place. The
   guard above is the belt-and-braces backstop proving we never touch the net.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import deepresearch.cache as cache_module

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class NetworkAccessError(RuntimeError):
    """Raised if any test attempts a real network call."""


def _exploding_getter(url: str, *args: Any, **kwargs: Any) -> str:
    raise NetworkAccessError(
        f"a real network call was attempted during the test suite: {url!r}. "
        "Tests must be fully offline and fixture-backed."
    )


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee no API keys and no live network for every test."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("DEEPRESEARCH_PROVIDER", raising=False)
    # If any code path falls through to the default live getter, blow up.
    monkeypatch.setattr(cache_module, "default_http_getter", _exploding_getter)


@pytest.fixture
def exploding_getter():
    """Expose the exploding getter so a test can inject it into a Cache."""
    return _exploding_getter


def load_test_fixture(name: str) -> Any:
    """Load a recorded JSON fixture from tests/fixtures by base name."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))
