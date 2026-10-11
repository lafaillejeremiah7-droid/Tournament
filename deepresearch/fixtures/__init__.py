"""Bundled sample source data for the dry-run skeleton.

These committed JSON files let the dry-run path and tests produce
placeholder-but-valid output with zero network and zero API keys. FEAT-002
replaces the fixtures-only path with real connectors (read-through cached).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_fixture(name: str) -> Any:
    """Load a bundled fixture JSON file by base name (without extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"bundled fixture not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
