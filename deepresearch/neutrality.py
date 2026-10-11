"""Deterministic denominational-neutrality scanner.

This module is a lightweight, data-driven, fully-deterministic check that scans
the GENERATED prose of a finished :class:`~deepresearch.models.Dossier` for
phrasings that assert ONE Christian tradition's distinctive teaching *as settled
fact*, in a project whose stated baseline is the shared 66-book canon with
denominational differences noted neutrally.

Design goals / contract
------------------------
* **It never mutates or censors content.** It only READS the dossier and returns
  a list of structured :class:`ReviewFlag` findings for the human reviewer. The
  pipeline attaches those findings to ``dossier.review_flags`` (an optional,
  additive schema field) so they surface in the JSON and Markdown output.
* **It is deterministic.** No network, no model, no randomness. The same dossier
  always yields the same findings, so it runs on every path including
  dry-run/offline and is fully testable without a model.
* **It is conservative.** Each pattern requires the loaded claim to be framed as
  a fact ("is required for salvation", "the one true church", "the Pope is
  infallible"). Neutral, descriptive mentions ("traditions differ", "some
  denominations hold", "the work of the Spirit in baptism and faith") are NOT
  flagged. The curated lexicon below was tuned so it produces ZERO findings on
  the deterministic stub boilerplate and on the seeded public-domain commentary
  text bundled with the project.

Surfacing mechanism (documented choice)
--------------------------------------
We surface findings via an OPTIONAL, additive ``review_flags`` field on the
dossier schema (array of ``{category, snippet, reason, severity}``). The field
is NOT in the schema's ``required`` list, so pre-existing dossiers (and any that
produce no findings) validate unchanged, and ``schema_version`` stays ``0.1.0``
because the change is backward-compatible. The alternative (folding findings
into ``gaps[]``) was rejected because neutrality findings are advisory review
hints, semantically distinct from the "a source was unavailable" meaning of a
gap.

Scope and limits (honest)
-------------------------
This is a HEURISTIC AID for the human reviewer, not a guarantee of neutrality.
It uses a curated keyword/phrase lexicon and will neither catch every
side-taking phrasing nor understand nuance. It flags; it never edits. The
human-review gate remains the real backstop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from deepresearch.models import Dossier


@dataclass
class ReviewFlag:
    """One structured neutrality finding for the human reviewer.

    Attributes
    ----------
    category:
        Which family of denominational distinctive matched (e.g.
        ``"papal-magisterial-authority"``).
    snippet:
        The matched phrase plus minimal surrounding context from the scanned
        field, so a reviewer can locate it quickly.
    reason:
        Why the phrasing may be non-neutral (states one tradition's distinctive
        as settled fact).
    severity:
        Advisory level. Always ``"advisory"`` today; kept as a field so the
        severity vocabulary can grow without a schema change.
    """

    category: str
    snippet: str
    reason: str
    severity: str = "advisory"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "snippet": self.snippet,
            "reason": self.reason,
            "severity": self.severity,
        }


# ---------------------------------------------------------------------------
# Curated lexicon.
#
# Each entry is (category, reason, [patterns]). A pattern is matched
# case-insensitively on word/phrase boundaries (``\b`` around the phrase) so we
# avoid substring false positives (e.g. "popery" would NOT match "pope"-less
# text, and "baptism" alone never fires). Patterns are deliberately written to
# require an ASSERTED-AS-FACT framing, not a neutral/descriptive mention.
# ---------------------------------------------------------------------------

_LEXICON: list[tuple[str, str, list[str]]] = [
    (
        "one-true-church",
        "asserts a single tradition is 'the one true church', which takes a "
        "denominational side as settled fact.",
        [
            r"the one true church",
            r"the only true church",
            r"outside the church there is no salvation",
        ],
    ),
    (
        "papal-magisterial-authority",
        "asserts papal / magisterial supremacy or infallibility as settled "
        "fact rather than noting it as one tradition's teaching.",
        [
            r"the pope is infallible",
            r"papal infallibility is",
            r"infallible authority of the pope",
            r"the magisterium is infallible",
            r"supremacy of the pope",
        ],
    ),
    (
        "marian-doctrine",
        "states a distinctive Marian doctrine as settled fact.",
        [
            r"the immaculate conception",
            r"the bodily assumption of mary",
            r"the assumption of mary",
            r"mary was sinless",
            r"mary is the mediatrix",
            r"co-redemptrix",
            r"the perpetual virginity of mary",
        ],
    ),
    (
        "purgatory",
        "asserts purgatory as a settled fact rather than a tradition-specific "
        "teaching.",
        [
            r"souls in purgatory",
            r"the fire of purgatory",
            r"purgatory purifies",
            r"must be purified in purgatory",
        ],
    ),
    (
        "baptismal-regeneration-or-mode",
        "frames a baptismal doctrine or mode as universally required for "
        "salvation, which is a contested denominational distinctive.",
        [
            r"baptism is required for salvation",
            r"baptism is necessary for salvation",
            r"you must be baptized to be saved",
            r"only immersion is valid baptism",
            r"infant baptism is required",
            r"baptismal regeneration is",
        ],
    ),
    (
        "eucharist-real-presence-vs-symbol",
        "settles the contested eucharistic question (real presence vs. "
        "symbol / transubstantiation) as fact.",
        [
            r"the eucharist is merely symbolic",
            r"communion is merely symbolic",
            r"the bread and wine are merely symbolic",
            r"transubstantiation is",
            r"the real presence is a fact",
            r"the bread literally becomes",
        ],
    ),
    (
        "predestination-or-eternal-security",
        "states a contested soteriological distinctive (predestination / "
        "once-saved-always-saved) as settled fact.",
        [
            r"once saved,? always saved",
            r"predestination is settled",
            r"the elect are unconditionally chosen",
            r"you cannot lose your salvation",
            r"salvation can never be lost",
        ],
    ),
    (
        "faith-alone-vs-works",
        "settles the contested faith-alone vs. works debate as fact.",
        [
            r"faith alone saves",
            r"salvation is by faith alone",
            r"works are required for salvation",
            r"you are justified by works",
        ],
    ),
    (
        "tongues-required",
        "asserts speaking in tongues as a required mark of salvation / the "
        "Spirit, a contested charismatic distinctive.",
        [
            r"speaking in tongues is required",
            r"tongues is the (?:only )?evidence of the spirit",
            r"you must speak in tongues",
        ],
    ),
    (
        "king-james-only",
        "asserts a King-James-only position as fact.",
        [
            r"king james only",
            r"the king james is the only (?:true|valid|inspired)",
            r"only the king james version is",
        ],
    ),
]

# Pre-compile every pattern once (module import time) for determinism + speed.
_COMPILED: list[tuple[str, str, re.Pattern[str]]] = [
    (category, reason, re.compile(r"\b" + pattern + r"\b", re.IGNORECASE))
    for category, reason, patterns in _LEXICON
    for pattern in patterns
]

# How much surrounding context to include around a match in the snippet.
_CONTEXT_CHARS = 40


def _snippet(text: str, start: int, end: int) -> str:
    """Return the matched phrase plus a little surrounding context."""
    lo = max(0, start - _CONTEXT_CHARS)
    hi = min(len(text), end + _CONTEXT_CHARS)
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(text) else ""
    fragment = " ".join(text[lo:hi].split())
    return f"{prefix}{fragment}{suffix}"


def _scan_text(text: str) -> list[ReviewFlag]:
    if not text:
        return []
    findings: list[ReviewFlag] = []
    for category, reason, pattern in _COMPILED:
        for m in pattern.finditer(text):
            findings.append(
                ReviewFlag(
                    category=category,
                    snippet=_snippet(text, m.start(), m.end()),
                    reason=reason,
                    severity="advisory",
                )
            )
    return findings


def _iter_scanned_fields(dossier: "Dossier") -> list[str]:
    """Collect every GENERATED prose string the scanner looks at.

    Scans title, summary, the misconception/deeper_truth statements, and every
    talking point's point + detail. Deliberately does NOT scan citations,
    translations, raw commentary excerpts, or historical notes: those are
    gathered source material, not the model's own synthesized prose.
    """
    texts: list[str] = [dossier.title or "", dossier.summary or ""]
    if dossier.misconception:
        texts.append(dossier.misconception.statement or "")
    if dossier.deeper_truth:
        texts.append(dossier.deeper_truth.statement or "")
    for tp in dossier.talking_points:
        texts.append(tp.point or "")
        texts.append(tp.detail or "")
    return texts


def check_neutrality(dossier: "Dossier") -> list[ReviewFlag]:
    """Scan a dossier's generated prose and return neutrality findings.

    Pure and deterministic: it reads the dossier and returns a list of
    :class:`ReviewFlag`. It NEVER mutates the dossier. Attaching the findings
    (to ``dossier.review_flags``) is the caller's responsibility.
    """
    findings: list[ReviewFlag] = []
    for text in _iter_scanned_fields(dossier):
        findings.extend(_scan_text(text))
    return findings
