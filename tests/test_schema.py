"""Dossier schema validation: a known-good dossier passes, a malformed fails.

Also pins the schema contract version to ``deepresearch.SCHEMA_VERSION`` and
confirms the schema file is draft-07 and lives at the documented path.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

import deepresearch
from deepresearch.models import (
    Citation,
    Claim,
    Dossier,
    TalkingPoint,
    Translation,
)

SCHEMA_PATH = Path(deepresearch.__file__).resolve().parent / "schema" / "dossier.schema.json"


def _good_dossier() -> Dossier:
    cite = Citation(source="King James Version (public domain)", locator="Matthew 5:17")
    d = Dossier(
        schema_version=deepresearch.SCHEMA_VERSION,
        query="Matthew 5:17",
        query_kind="reference",
        resolved_reference="Matthew 5:17",
        title="t",
        summary="s",
        misconception=Claim(statement="surface reading", citations=[cite]),
        deeper_truth=Claim(statement="deeper reading", citations=[cite]),
        translations=[Translation("kjv", "Matthew 5:17", "text", cite)],
        talking_points=[TalkingPoint("point", "detail", [cite])],
    )
    d.build_citation_index()
    return d


def test_schema_file_exists_and_is_draft07():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["required"]  # has required fields


def test_schema_version_constant_matches():
    assert deepresearch.SCHEMA_VERSION == "0.1.0"


def test_known_good_dossier_validates():
    # Should not raise.
    _good_dossier().validate()


def test_malformed_dossier_missing_required_fails():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = _good_dossier().to_dict()
    del bad["talking_points"]  # required by schema
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_malformed_claim_without_citation_fails():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = _good_dossier().to_dict()
    bad["misconception"]["citations"] = []  # claim requires minItems: 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_malformed_bad_language_enum_fails():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = _good_dossier().to_dict()
    bad["original_language_terms"] = [
        {
            "term": "x",
            "transliteration": "x",
            "strongs": "G1",
            "language": "Klingon",  # not in enum ["Greek","Hebrew"]
            "definition": "d",
            "insight": "i",
            "citation": {"source": "s"},
        }
    ]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_malformed_additional_property_fails():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = _good_dossier().to_dict()
    bad["unexpected_field"] = "nope"  # additionalProperties: false
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
