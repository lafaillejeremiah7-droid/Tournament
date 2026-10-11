"""Configuration loaded from environment and CLI overrides.

Keys are read from the environment at build time only; they are NEVER
hardcoded. A tiny optional .env loader reads a local .env if present so that
developers do not have to export vars by hand. Dry-run needs no keys at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_TRANSLATIONS = ["kjv", "web", "asv"]
DEFAULT_CONTEXT_WINDOW = 5
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_CACHE_DIR = ".cache"


def load_dotenv(path: str | os.PathLike[str] = ".env") -> None:
    """Minimal, dependency-free .env loader.

    Reads simple ``KEY=VALUE`` lines from a local .env if it exists and sets
    them in ``os.environ`` only when not already present. Lines that are blank
    or start with ``#`` are ignored. Never raises on a missing file.
    """

    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """Runtime configuration for a single research run."""

    dry_run: bool = False
    offline: bool = False
    llm_provider: str = "stub"
    llm_model: Optional[str] = None
    translations: list[str] = field(default_factory=lambda: list(DEFAULT_TRANSLATIONS))
    context_window: int = DEFAULT_CONTEXT_WINDOW
    output_dir: str = DEFAULT_OUTPUT_DIR
    cache_dir: str = DEFAULT_CACHE_DIR

    # Keys are populated from the environment, never persisted/committed.
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    @classmethod
    def from_env_and_args(
        cls,
        *,
        dry_run: Optional[bool] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        translations: Optional[list[str]] = None,
        context_window: Optional[int] = None,
        output_dir: Optional[str] = None,
        cache_dir: Optional[str] = None,
        offline: Optional[bool] = None,
        load_env_file: bool = True,
    ) -> "Config":
        """Build a Config from env defaults with explicit CLI overrides on top."""

        if load_env_file:
            load_dotenv()

        env_dry_run = _env_bool("DEEPRESEARCH_DRY_RUN", False)
        resolved_dry_run = env_dry_run if dry_run is None else dry_run

        # In dry-run the default provider is the deterministic stub; otherwise
        # fall back to the env-selected provider or 'stub'.
        env_provider = os.environ.get("DEEPRESEARCH_PROVIDER")
        if provider is not None:
            resolved_provider = provider
        elif resolved_dry_run:
            resolved_provider = "stub"
        else:
            resolved_provider = env_provider or "stub"

        # Dry-run is inherently offline. Otherwise honor explicit/env setting.
        env_offline = _env_bool("DEEPRESEARCH_OFFLINE", False)
        resolved_offline = resolved_dry_run or (env_offline if offline is None else offline)

        resolved_translations = (
            list(translations)
            if translations
            else _env_list("DEEPRESEARCH_TRANSLATIONS", DEFAULT_TRANSLATIONS)
        )

        return cls(
            dry_run=resolved_dry_run,
            offline=resolved_offline,
            llm_provider=resolved_provider,
            llm_model=model or os.environ.get("DEEPRESEARCH_MODEL"),
            translations=resolved_translations,
            context_window=context_window
            if context_window is not None
            else int(os.environ.get("DEEPRESEARCH_CONTEXT_WINDOW", DEFAULT_CONTEXT_WINDOW)),
            output_dir=output_dir or os.environ.get("DEEPRESEARCH_OUTPUT_DIR", DEFAULT_OUTPUT_DIR),
            cache_dir=cache_dir or os.environ.get("DEEPRESEARCH_CACHE_DIR", DEFAULT_CACHE_DIR),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )


def _env_list(name: str, default: list[str]) -> list[str]:
    val = os.environ.get(name)
    if not val:
        return list(default)
    return [item.strip() for item in val.split(",") if item.strip()]
