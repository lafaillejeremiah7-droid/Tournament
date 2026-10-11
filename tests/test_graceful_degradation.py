"""Graceful degradation + the no-network safety net.

(1) A simulated unavailable source records a Gap and does NOT raise, and the
    pipeline still produces a schema-valid dossier.
(2) The suite proves it never touches the network: if a connector's cache is
    ever allowed to reach the live getter, that getter raises and the test
    fails. Here we assert the offline Cache never calls the getter at all, and
    that a getter wired to explode is never invoked on the offline path.
"""

from __future__ import annotations

import json

import jsonschema
import pytest

from deepresearch import SCHEMA_VERSION
from deepresearch.cache import Cache
from deepresearch.config import Config
from deepresearch.models import Dossier
from deepresearch.pipeline import Pipeline
from deepresearch.sources.base import SourceConnector, SourceRequest, SourceResult
from deepresearch.sources.bible_api import BibleApiConnector
from deepresearch.sources.commentary import CommentaryConnector
from deepresearch.sources.registry import SourceRegistry
from deepresearch.sources.strongs import StrongsConnector

from tests.conftest import NetworkAccessError


class _UnavailableConnector(SourceConnector):
    """A connector that always reports itself unavailable (no raise)."""

    name = "bible_api"

    def fetch(self, request: SourceRequest) -> SourceResult:
        return SourceResult.missing(self.name, "simulated outage: source unavailable")


def _registry_with_unavailable_bible(cache: Cache) -> SourceRegistry:
    reg = SourceRegistry()
    reg.register(_UnavailableConnector())
    reg.register(StrongsConnector())
    reg.register(CommentaryConnector(cache))
    return reg


def test_unavailable_source_records_gap_and_does_not_raise(tmp_path):
    config = Config.from_env_and_args(
        dry_run=True,
        output_dir=str(tmp_path / "out"),
        cache_dir=str(tmp_path / "cache"),
        load_env_file=False,
    )
    cache = Cache(config.cache_dir, offline=True)
    pipe = Pipeline(
        config,
        registry=_registry_with_unavailable_bible(cache),
        cache=cache,
    )
    # Must not raise despite the unavailable bible_api source.
    json_path, _ = pipe.run("Matthew 5:17")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    # The outage is recorded as one or more gaps (one per requested translation).
    assert data["gaps"], "an unavailable source must record a gap"
    assert any("simulated outage" in g["reason"] for g in data["gaps"])
    # And the pipeline still produced valid, populated output from the rest.
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["talking_points"]
    assert data["translations"] == []  # the unavailable source contributed none


def test_dossier_with_all_sources_missing_still_validates(tmp_path):
    """Full degradation: no sources at all yields a flagged, schema-valid dossier."""

    class _AllMissing(SourceConnector):
        def __init__(self, name: str) -> None:
            self.name = name

        def fetch(self, request: SourceRequest) -> SourceResult:
            return SourceResult.missing(self.name, "nothing available")

    reg = SourceRegistry()
    reg.register(_AllMissing("bible_api"))
    reg.register(_AllMissing("strongs"))
    reg.register(_AllMissing("commentary"))

    config = Config.from_env_and_args(
        dry_run=True,
        output_dir=str(tmp_path / "out"),
        cache_dir=str(tmp_path / "cache"),
        load_env_file=False,
    )
    pipe = Pipeline(config, registry=reg, cache=Cache(config.cache_dir, offline=True))
    json_path, _ = pipe.run("Matthew 5:17")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    from pathlib import Path
    import deepresearch

    schema = json.loads(
        (Path(deepresearch.__file__).resolve().parent / "schema" / "dossier.schema.json").read_text()
    )
    jsonschema.validate(instance=data, schema=schema)
    assert data["gaps"]
    assert data["talking_points"]  # placeholder beat, still non-empty


# ------------------------------------------------------- no-network proof


def test_offline_cache_never_calls_the_getter(tmp_path):
    """An offline Cache must return None on a miss and NEVER call the getter."""

    def explode(url, *a, **k):
        raise NetworkAccessError(url)

    cache = Cache(tmp_path / "cache", offline=True, http_getter=explode)
    # Miss on an offline cache returns None without touching the getter.
    assert cache.fetch("ns", "sig", "https://example.com") is None


def test_connectors_on_offline_path_do_not_touch_network(tmp_path):
    """Running every connector offline must not invoke the exploding getter."""

    def explode(url, *a, **k):
        raise NetworkAccessError(url)

    cache = Cache(tmp_path / "cache", offline=True, http_getter=explode)
    bible = BibleApiConnector(cache)
    commentary = CommentaryConnector(cache)
    strongs = StrongsConnector()

    # None of these should raise NetworkAccessError.
    bible.fetch(SourceRequest(kind="verse", reference="Matthew 5:17", translation="kjv"))
    commentary.fetch(SourceRequest(kind="commentary", reference="Matthew 5:17"))
    strongs.fetch(SourceRequest(kind="strongs", reference="Matthew 5:17"))


def test_live_cache_would_use_getter_but_fixtures_keep_us_offline(tmp_path):
    """Sanity check that the getter IS the thing a live fetch would call.

    Proves the exploding guard is wired to the real code path: a non-offline
    cache with the exploding getter raises on a miss, which is exactly what the
    autouse network guard relies on to fail the suite if anything goes live.
    """

    def explode(url, *a, **k):
        raise NetworkAccessError(url)

    cache = Cache(tmp_path / "cache", offline=False, http_getter=explode)
    with pytest.raises(NetworkAccessError):
        cache.fetch("ns", "sig", "https://example.com")
