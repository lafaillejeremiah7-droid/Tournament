"""Anthropic provider (SDK imported lazily).

The ``anthropic`` SDK is an optional extra. It is imported INSIDE methods so
``import deepresearch`` works with zero SDKs installed. Selecting this provider
without the SDK or without a key raises a clear, actionable error.
"""

from __future__ import annotations

from typing import Optional

from deepresearch.llm.base import LLMProvider

DEFAULT_MODEL = "claude-3-5-sonnet-latest"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or DEFAULT_MODEL
        self._api_key = api_key

    def complete(self, system: str, user: str) -> str:
        try:
            import anthropic  # lazy import of optional SDK
        except ImportError as exc:  # pragma: no cover - exercised only in live mode
            raise RuntimeError(
                "The 'anthropic' provider requires the anthropic SDK. Install it with "
                "`pip install 'deepresearch[anthropic]'`, or use --dry-run / --provider stub."
            ) from exc

        if not self._api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it for live mode, or use "
                "--dry-run / --provider stub."
            )

        client = anthropic.Anthropic(api_key=self._api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", None) == "text"]
        return "".join(parts)
