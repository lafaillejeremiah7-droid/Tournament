# deepresearch

Bot #1 of a faith-content video pipeline: a **Deep Research agent** that turns a
Bible verse/reference **or** a free-text topic about Jesus Christ into a
structured, deeply-sourced research dossier built around a
**"common misconception vs. deeper truth"** spine.

The dossier is denominationally neutral (shared 66-book canon baseline, tradition
differences noted neutrally), every substantive claim carries a citation, and
uncertainty is flagged rather than invented. Output is emitted as both JSON (a
versioned schema contract for downstream bots) and long-form Markdown.

> Status: FEAT-001 scaffold. The dry-run skeleton runs the full pipeline shape
> with a deterministic stub provider and bundled fixtures. FEAT-002 adds the
> real source connectors + LLM synthesis; FEAT-003 adds tests + docs.

## Requirements

- Python **>= 3.10** (use `/usr/bin/python3.12` in this environment; the default
  `python3` on PATH is 3.9 and must not be used).

## Setup

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'      # dev extra adds pytest
```

Optional LLM SDKs are lazy-imported extras (not needed for dry-run):

```bash
pip install -e '.[openai]'       # OpenAI live mode
pip install -e '.[anthropic]'    # Anthropic live mode
```

## Usage

Dry-run needs **no API keys and no network** (bundled fixtures + stub provider):

```bash
# Verse reference
python -m deepresearch research "Matthew 5:17" --dry-run

# Free-text topic
python -m deepresearch research "turn the other cheek" --dry-run
```

Both commands write a `.json` and a `.md` dossier into the output directory
(default `output/`).

### Flags

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Use the deterministic stub provider, no network, no keys. |
| `--provider {stub,openai,anthropic}` | Select the LLM provider (default `stub` in dry-run). |
| `--model NAME` | Model name for the chosen provider. |
| `--translations kjv,web,asv` | Comma-separated public-domain translations. |
| `--output-dir DIR` | Where to write the dossiers (default `output`). |
| `--input-file PATH` | Read the query from a file instead of the positional arg. |

The environment variable `DEEPRESEARCH_DRY_RUN=1` is an alternative to `--dry-run`.

### Live mode

Copy `.env.example` to `.env` and set a key, then select a provider:

```bash
export OPENAI_API_KEY=...        # or ANTHROPIC_API_KEY=...
python -m deepresearch research "Matthew 5:17" --provider openai
```

Keys are read from the environment only and are never committed.

## Architecture

The pipeline runs six discrete stages (`deepresearch/pipeline.py`):

1. `normalize_reference` — reference vs. topic detection + normalization
2. `fetch_translations` — public-domain translations
3. `extract_original_terms` — Strong's / lexicon terms
4. `gather_context` — historical / commentary / Church-Fathers context
5. `synthesize` — misconception → deeper-truth spine via the LLM provider
6. `write_output` — schema-validated JSON + Markdown

Two core abstractions keep it extensible:

- **Source connectors** (`deepresearch/sources/`): a `SourceConnector` base +
  a `SourceRegistry` so new sources drop in without touching the pipeline core.
  Connectors return a `SourceResult` with `Citation`s and a `gap` flag for
  graceful degradation. A fixtures-backed connector powers dry-run.
- **LLM providers** (`deepresearch/llm/`): an `LLMProvider` base, a deterministic
  `StubProvider` (dry-run/tests), and OpenAI/Anthropic providers whose SDKs are
  imported lazily so the package imports with zero SDKs installed.

A shared on-disk cache (`deepresearch/cache.py`) wraps HTTP with an injectable
getter so dry-run and tests replay fixtures and never hit the network.

Generated `output/` and `.cache/` are git-ignored; bundled fixtures and the JSON
schema are committed.
