"""End-to-end dry-run: a schema-valid dossier for BOTH a verse and a topic.

Runs the full six-stage pipeline through the CLI-equivalent config with no
network and no keys, then asserts the output is schema-valid and that the
misconception/deeper-truth spine and talking points are populated.
"""

from __future__ import annotations

import json

import jsonschema

from deepresearch import SCHEMA_VERSION
from deepresearch.config import Config
from deepresearch.pipeline import Pipeline


def _run(tmp_path, query: str) -> dict:
    config = Config.from_env_and_args(
        dry_run=True,
        output_dir=str(tmp_path / "out"),
        cache_dir=str(tmp_path / "cache"),
        load_env_file=False,
    )
    pipe = Pipeline(config)
    json_path, md_path = pipe.run(query)
    assert json_path.is_file()
    assert md_path.is_file()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data


def _assert_valid_and_populated(data: dict):
    import deepresearch
    from pathlib import Path

    schema_path = Path(deepresearch.__file__).resolve().parent / "schema" / "dossier.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)  # raises on failure

    assert data["schema_version"] == SCHEMA_VERSION
    assert data["misconception"]["statement"].strip()
    assert data["misconception"]["citations"]
    assert data["deeper_truth"]["statement"].strip()
    assert data["deeper_truth"]["citations"]
    assert data["talking_points"], "talking_points must be non-empty"
    for tp in data["talking_points"]:
        assert tp["point"].strip()


def test_end_to_end_verse_reference(tmp_path):
    data = _run(tmp_path, "Matthew 5:17")
    assert data["query_kind"] == "reference"
    assert data["resolved_reference"] == "Matthew 5:17"
    assert data["translations"], "a verse should resolve translations"
    assert data["provider"] == "stub"
    _assert_valid_and_populated(data)


def test_end_to_end_topic(tmp_path):
    data = _run(tmp_path, "turn the other cheek")
    assert data["query_kind"] == "topic"
    assert data["resolved_reference"] is None
    # A topic resolves to anchor passage(s) so the dossier still carries scripture.
    assert data["translations"], "a topic should resolve anchor translations"
    assert data["resolved_references"] == ["Matthew 5:39"]
    for t in data["translations"]:
        assert t["reference"] == "Matthew 5:39"
    assert data["original_language_terms"]
    assert data["commentary"]
    _assert_valid_and_populated(data)


def test_topic_spine_tracks_the_query(tmp_path):
    """The dry-run spine prose is derived from the gathered material, so a topic
    other than Matthew 5:17 does not get the old hardcoded cancel-vs-fulfil text."""
    data = _run(tmp_path, "turn the other cheek")
    spine = (data["misconception"]["statement"] + " " + data["deeper_truth"]["statement"]).lower()
    assert "turn the other cheek" in spine
    assert "cancel" not in spine and "overturns" not in spine


def test_end_to_end_topic_judge_not(tmp_path):
    """A new fixture-backed topic (enhancement A) carries real scripture offline."""
    data = _run(tmp_path, "judge not")
    assert data["query_kind"] == "topic"
    assert data["resolved_reference"] is None
    assert data["translations"], "a fixture-backed topic should resolve anchor translations"
    assert data["resolved_references"] == ["Matthew 7:1"]
    for t in data["translations"]:
        assert t["reference"] == "Matthew 7:1"
    _assert_valid_and_populated(data)


def test_end_to_end_topic_born_again(tmp_path):
    """A second new fixture-backed topic (enhancement A) carries real scripture offline."""
    data = _run(tmp_path, "born again")
    assert data["query_kind"] == "topic"
    assert data["resolved_reference"] is None
    assert data["translations"], "a fixture-backed topic should resolve anchor translations"
    assert data["resolved_references"] == ["John 3:3"]
    for t in data["translations"]:
        assert t["reference"] == "John 3:3"
    _assert_valid_and_populated(data)


def test_topic_alias_normalization(tmp_path):
    """resolve_topic_anchors maps aliases + varied casing/whitespace to the same anchors."""
    config = Config.from_env_and_args(
        dry_run=True,
        output_dir=str(tmp_path / "out"),
        cache_dir=str(tmp_path / "cache"),
        load_env_file=False,
    )
    pipe = Pipeline(config)

    # Case- and whitespace-insensitive matching of the same phrasing.
    assert pipe.resolve_topic_anchors("judge not") == ["Matthew 7:1"]
    assert pipe.resolve_topic_anchors("Judge Not") == ["Matthew 7:1"]
    assert pipe.resolve_topic_anchors("  judge   not ") == ["Matthew 7:1"]

    # Distinct alias phrasings resolve to the same anchor list.
    needle = ["Matthew 19:24", "Mark 10:25", "Luke 18:25"]
    assert pipe.resolve_topic_anchors("eye of the needle") == needle
    assert pipe.resolve_topic_anchors("camel through the eye of a needle") == needle

    # An unmapped topic yields no anchors.
    assert pipe.resolve_topic_anchors("the meaning of grace") == []


def test_end_to_end_unmapped_topic_degrades(tmp_path):
    """An unmapped topic still yields a schema-valid dossier with a recorded gap, no crash."""
    data = _run(tmp_path, "the meaning of grace")
    assert data["query_kind"] == "topic"
    assert data["resolved_reference"] is None
    assert data["resolved_references"] == []
    assert data["translations"] == []
    # No anchor means no scripture; the run degrades gracefully and records gaps
    # (e.g. strongs/commentary) rather than crashing.
    assert data["gaps"], "an unmapped topic should record at least one gap"
    _assert_valid_and_populated(data)


def test_end_to_end_is_deterministic(tmp_path):
    a = _run(tmp_path / "a", "Matthew 5:17")
    b = _run(tmp_path / "b", "Matthew 5:17")
    assert a == b


def test_cli_main_writes_dossiers(tmp_path, capsys):
    from deepresearch.cli import main

    rc = main(["research", "Matthew 5:17", "--dry-run", "--output-dir", str(tmp_path / "cliout")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Wrote JSON dossier" in out
    assert "Wrote Markdown dossier" in out
