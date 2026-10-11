# deepresearch — the Deep Research agent (Bot #1)

**deepresearch** is **Bot #1** of a planned multi-bot, faith-content video
company. Its single job is to be the *research brain* at the front of the
pipeline: given a Bible verse/reference **or** a free-text topic about Jesus
Christ, it produces a structured, deeply-sourced **research dossier** built
around one spine:

> **What most people misunderstand** about this verse/teaching (the common
> misconception) **versus the deeper, source-anchored truth** of Jesus Christ's
> teaching.

The dossier is intentionally **long-form** (the talking points are sized for an
~8–20 minute script) and designed to be handed to the downstream bots that turn
it into an AI text-to-speech video. See the [Roadmap](#roadmap).

### Content-integrity principles

These rules are enforced in the prompts **and** re-checked in code
(`deepresearch/synthesis.py`):

- **Citations required.** Every substantive claim must point back to a gathered
  source. The post-synthesis integrity check drops any talking point whose
  citation cannot be resolved to real gathered material, and flags required
  spine claims that lack one.
- **Uncertainty is flagged, never invented.** When the sources are silent, the
  dossier says so (a `gaps[]` entry and/or an `[uncertain]` statement) instead
  of fabricating.
- **Denominational neutrality.** The shared **66-book canon** is the baseline.
  Where traditions differ (canon, interpretation), the difference is noted
  neutrally; no denomination is favored. The person and teaching of Jesus Christ
  stay at the center. Neutrality is now enforced **both** by the system prompt
  **and** by a programmatic check. `deepresearch/neutrality.py` is a
  **deterministic**, data-driven scanner (a curated lexicon of phrasings that
  assert one tradition's distinctive *as settled fact* — the one true church,
  papal/magisterial infallibility, Marian doctrine, purgatory, baptismal
  regeneration/mode as required, eucharistic real-presence vs. "merely symbolic"
  as settled, predestination / once-saved-always-saved, faith-alone vs. works,
  tongues-required, King-James-only). It scans the model's generated prose
  (title, summary, the misconception/deeper-truth statements, and every talking
  point) case-insensitively on word/phrase boundaries, and is wired into the
  pipeline **after `synthesize`, inside `write_output` before `validate()`**, so
  it runs on **every** path including dry-run/offline. Findings surface in the
  optional, additive **`review_flags`** field (JSON) and a **"Review Flags
  (neutrality)"** Markdown section. **Scope and limits (honest):** this is a
  **heuristic aid for the human reviewer, not a guarantee** — it uses a curated
  keyword lexicon, will not catch every side-taking phrasing or understand
  nuance, and is conservative to avoid false positives (neutral mentions like
  "traditions differ" are not flagged). Crucially it **flags, never censors**:
  it only records structured findings and never edits the dossier's statements
  or talking points. The human-review gate remains the real backstop. In dry-run
  the stub echoes neutral boilerplate, so it produces zero flags by construction.
- **No scraping of copyrighted modern translations.** Only public-domain
  scripture is ever fetched. Copyrighted modern translations (NIV, ESV, NASB,
  NLT, …) are refused *before* any URL is built, and commentary fetches are
  restricted to a public-domain host allowlist.

---

## Setup

Requires **Python ≥ 3.10**. In this environment use `/usr/bin/python3.12`
(the default `python3` on PATH is 3.9 and must not be used).

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'       # dev extra adds pytest
```

Optional LLM SDKs are lazy-imported extras (not needed for dry-run or tests):

```bash
pip install -e '.[openai]'       # OpenAI live mode
pip install -e '.[anthropic]'    # Anthropic live mode
```

Pinned runtime dependencies are also listed in `requirements.txt`
(`pip install -r requirements.txt`).

### Environment variables

Copy the template and fill in a key only if you want **live** mode:

```bash
cp .env.example .env
```

`.env.example` documents every variable (API keys plus optional config such as
`DEEPRESEARCH_PROVIDER`, `DEEPRESEARCH_MODEL`, `DEEPRESEARCH_TRANSLATIONS`,
`DEEPRESEARCH_DRY_RUN`). Keys are read from the environment only and are **never
committed** (`.env` is git-ignored). Dry-run needs no keys at all.

---

## Running it

### Dry-run (no keys, no network)

Dry-run uses the deterministic **stub provider** and bundled fixtures, so it is
fully reproducible with **zero API keys and zero network**:

```bash
# Verse reference
python -m deepresearch research "Matthew 5:17" --dry-run

# Free-text topic
python -m deepresearch research "turn the other cheek" --dry-run
```

Both commands write a `.json` and a `.md` dossier into the output directory
(default `output/`).

> **Dry-run spine prose is deterministic scaffolding.** The stub provider
> templates the `misconception` / `deeper_truth` statements from the gathered
> fixture material so the text *tracks the query* (a topic like "turn the other
> cheek" no longer gets Matthew-5:17 "cancel vs. fulfil" wording). It is still
> placeholder structure, not model-quality analysis — the live
> `openai`/`anthropic` providers produce the real spine. Dry-run exists to prove
> the pipeline, schema, and citation-integrity contract end to end with zero
> network and zero keys.

### Live mode

Install an SDK extra, set a key, and select a provider:

```bash
export OPENAI_API_KEY=...        # or ANTHROPIC_API_KEY=...
python -m deepresearch research "Matthew 5:17" --provider openai --model gpt-4o-mini
```

Live mode still fetches scripture only from public-domain sources and still runs
the full citation-integrity check.

### Flags

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Deterministic stub provider, no network, no keys. |
| `--provider {stub,openai,anthropic}` | LLM provider (default `stub` in dry-run). |
| `--model NAME` | Model name for the chosen provider. |
| `--translations kjv,web,asv` | Comma-separated public-domain translations. |
| `--output-dir DIR` | Where to write the dossiers (default `output`). |
| `--input-file PATH` | Read the query from a file instead of the positional arg. |

`DEEPRESEARCH_DRY_RUN=1` is an alternative to `--dry-run`.

---

## Testing

The test suite is **pytest** and runs with **no network and no API keys**, using
the dry-run path plus recorded/bundled fixtures. It is the documented runner:

```bash
unset OPENAI_API_KEY ANTHROPIC_API_KEY
.venv/bin/python -m pytest -q
```

The suite is a safety net: an autouse fixture (`tests/conftest.py`) unsets any
API keys and monkeypatches the package's default live HTTP getter so that **any**
real network call attempted during the suite raises and fails the test loudly.
Connectors are additionally always built with an **offline** cache. Together
these prove the suite never touches the network.

> The tests are written as pytest functions (fixtures, parametrization), so
> **pytest is the required runner**; `python -m unittest discover` will not
> collect them.

---

## Architecture

The pipeline runs **six discrete stages**, each a method on
`deepresearch/pipeline.py::Pipeline`, chained by `run()`:

1. **`normalize_reference`** — detect a verse *reference* vs. a free-text *topic*
   and normalize the reference. A topic resolves to no primary reference but is
   still routed to the connectors by its query text (the topic → candidate
   passages path).
2. **`fetch_translations`** — pull the public-domain translations for the verse
   (via the `bible_api` connector). For a *topic*, the query is first mapped to
   one or more **anchor passage references** (data-driven via
   `deepresearch/fixtures/topic_anchors.json`, e.g. "turn the other cheek" →
   Matthew 5:39), so a topic dossier also carries scripture text. An unmapped
   topic simply resolves no anchors and the dossier records the absence as a
   gap rather than crashing.

   **Topic-map coverage.** `topic_anchors.json` currently maps **35 lowercase
   topic/alias keys** (several aliases normalize to the same anchor list, e.g.
   "camel through the eye of a needle" and "eye of the needle" both resolve to
   Matthew 19:24 / Mark 10:25 / Luke 18:25) across the most commonly
   *misunderstood* teachings about Jesus. A subset of anchors ships bundled
   public-domain KJV/WEB/ASV verse text in `deepresearch/fixtures/verses.json`,
   so those topics carry real scripture **fully offline** (no network, no keys):

   - **Fixture-backed (work offline):** "turn the other cheek" → Matthew 5:39,
     "judge not" → Matthew 7:1, "ask and it will be given" → Matthew 7:7,
     "narrow gate" / "narrow road" → Matthew 7:13-14, "born again" → John 3:3,
     and "i am the way the truth and the life" → John 14:6.
   - **Gap-degrading offline:** every other mapped anchor (e.g. "render unto
     caesar", "faith without works", "eye of the needle") resolves correctly but
     has no bundled verse text yet, so offline it records a structured gap
     instead of scripture. Those anchors fetch live text when a network/cache is
     available. The fixture-backed subset above now also carries bundled
     public-domain Strong's terms and Church-Fathers / historical / cross-
     reference commentary, so those topics produce rich dossiers offline.
3. **`extract_original_terms`** — pull Strong's / lexicon key terms.
4. **`gather_context`** — pull historical background and classic commentary /
   Church-Fathers excerpts (plus cross-references).
5. **`synthesize`** — build the *misconception → deeper-truth* spine and the
   long-form talking points via the LLM provider, then run the citation
   integrity check.
6. **`write_output`** — validate against the JSON Schema and emit the JSON +
   Markdown dossiers (a human-review-gated handoff; nothing is auto-published).

Three abstractions keep it extensible:

### Source-connector abstraction (`deepresearch/sources/`)

- `base.py` — the `SourceConnector` ABC plus the shared `Citation`,
  `SourceRequest`, and `SourceResult` shapes. A result carries structured
  `data`, a list of `Citation`s, and a `gap` flag; connectors **return a gap
  instead of raising** when a source is unavailable (graceful degradation).
- `registry.py` — a `SourceRegistry` mapping a connector `name` to an instance,
  so new sources drop in without touching the pipeline core.
- Concrete connectors: `bible_api.py`, `strongs.py`, `commentary.py`.

**Adding a connector:**

1. Subclass `SourceConnector`, give it a unique `name`, and implement
   `fetch(request) -> SourceResult`. Never raise for an unavailable source —
   return `SourceResult.missing(name, reason)`.
2. Route any HTTP through the shared `Cache` so dry-run/tests replay fixtures.
3. Register it in `Pipeline._default_registry()` (or inject a custom registry).
4. Attach at least one `Citation` to every datum you return.

### LLM-provider abstraction (`deepresearch/llm/`)

- `base.py` — the `LLMProvider` ABC and a `build_provider(name, ...)` factory.
- `stub_provider.py` — a **deterministic**, fixture-grounded provider used in
  dry-run and tests. It reuses only the citations present in the brief and
  invents no sources, so the integrity check always passes offline.
- `openai_provider.py` / `anthropic_provider.py` — live providers whose SDKs are
  imported **lazily**, so the package imports and runs dry-run with zero SDKs.
- `prompts.py` — the shared system/user prompts that encode the content-integrity
  rules.

### Caching (`deepresearch/cache.py`)

A small on-disk, read-through / replay cache wraps HTTP with an **injectable**
getter. In `offline=True` mode it reads only from disk/fixtures and never calls
the getter, so dry-run and tests are fully offline. In live mode it reads
through to the getter and writes the response for later replay.

### Graceful degradation

A failing or unavailable source records a structured `Gap` (source + reason) in
the dossier and the run continues. If no sourced material is available at all,
the dossier still validates: required spine claims are honestly marked unsourced
and flagged, and a placeholder review beat keeps `talking_points` non-empty — the
run never crashes and never fabricates a citation.

---

## Dossier schema

The dossier is a **versioned JSON Schema contract** for downstream bots. The
schema lives at:

```
deepresearch/schema/dossier.schema.json   (JSON Schema draft-07)
```

Its `schema_version` must equal `deepresearch.SCHEMA_VERSION` (currently
**`0.1.0`**). The dataclasses in `deepresearch/models.py` mirror the schema and
`Dossier.validate()` validates an instance against it.

Top-level fields:

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | string | Must equal `deepresearch.SCHEMA_VERSION`. |
| `query` | string | Raw user input (reference or topic). |
| `query_kind` | enum | `"reference"` or `"topic"`. |
| `resolved_reference` | string \| null | Normalized primary reference, or `null` for a topic. |
| `resolved_references` | string[] | All references resolved this run. |
| `title`, `summary` | string | Short title + overview. |
| `misconception` | claim | **Required.** The common surface reading. |
| `deeper_truth` | claim | **Required.** The better-supported meaning. |
| `translations` | object[] | Public-domain translation + citation. |
| `original_language_terms` | object[] | Greek/Hebrew term, Strong's, definition, insight. |
| `historical_context` | object[] | Historical/cultural background. |
| `commentary` | object[] | Classic / Church-Father excerpts. |
| `cross_references` | object[] | Related passages with notes. |
| `talking_points` | object[] | **Required, non-empty.** Ordered, cited beats for the script. |
| `gaps` | object[] | Sources that were unavailable or returned nothing. |
| `citations` | citation[] | **Required.** Flat index of every distinct citation. |
| `provider`, `model` | string / null | Which LLM produced the synthesis. |
| `review_flags` | object[] | *Optional, additive.* Advisory neutrality findings `{category, snippet, reason, severity}` from `deepresearch/neutrality.py`. Not in `required`; `[]`/absent is valid. |

> **`schema_version` stays `0.1.0`.** Adding `review_flags` is an **additive,
> backward-compatible** change: the field is optional (not in the schema's
> `required` list), so every pre-existing dossier — and any run that produces no
> findings — validates unchanged. No version bump is warranted.

A **claim** is `{ "statement": string, "citations": [citation, …] }` with at
least one citation. A **citation** is
`{ "source": string, "locator"?: string, "url"?: string|null, "note"?: string }`.

---

## Sources (v1 wired)

Only **public-domain** sources are used:

- **Scripture** — [bible-api.com](https://bible-api.com), public-domain
  translations only: **KJV, WEB, ASV** (and other public-domain codes such as
  BBE, YLT, DRA, OEB). Copyrighted modern translations (NIV/ESV/…) are refused.
- **Original languages** — a public-domain **Strong's** Greek/Hebrew lexicon
  subset (data-driven; a fuller public-domain dataset drops in without code
  changes). The bundled subset now covers the pivotal Greek terms of the
  fixture-backed topics (e.g. *krino* for "judge not"; *aiteo/zeteo/krouo* for
  "ask, seek, knock"; *stenos/pyle* for the narrow gate; *gennao/anothen* for
  "born again"; *hodos/aletheia/zoe* for "the way, the truth, and the life").
- **Historical context & commentary** — public-domain corpora on a host
  allowlist: **CCEL** (ccel.org), **New Advent** Fathers of the Church
  (newadvent.org), **sacred-texts.com**, and **Project Gutenberg**
  (gutenberg.org). A descriptive User-Agent is sent and disallowed paths are
  skipped. The bundled commentary subset carries Church-Fathers excerpts,
  historical background, and cross-references for each fixture-backed topic.

Bundled fixtures under `deepresearch/fixtures/` let dry-run and tests produce
complete, schema-valid dossiers with zero network. Runtime `output/` dossiers
and the `.cache/` fetch cache are generated and git-ignored.

---

## Roadmap

deepresearch is the first of a planned multi-bot faith-content video company.
Its dossier is a **human-review-gated handoff**: it is written to `output/` for a
person to review and is **never auto-published**. Planned downstream bots:

1. **Deep Research agent** — *this bot.* Produces the sourced dossier. ✅
2. **Scriptwriter** — turns a reviewed dossier into a long-form video script.
3. **TTS voiceover** — renders the script as AI text-to-speech narration.
4. **Visuals** — generates/sources on-screen imagery and b-roll.
5. **Video assembly** — stitches voiceover + visuals into the finished video.
6. **YouTube publisher** — uploads, with titles/descriptions/metadata.
7. **Review dashboard** — the human-in-the-loop gate across every stage.

Each stage consumes the stable, versioned schema of the stage before it, with a
human review gate in between.
