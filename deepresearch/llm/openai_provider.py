"""OpenAI provider (SDK imported lazily).

The ``openai`` SDK is an optional extra. It is imported INSIDE methods so that
``import deepresearch`` works with zero SDKs installed. Selecting this provider
without the SDK or without a key raises a clear, actionable error.
"""

from __future__ import annotations

from typing import Optional

from deepresearch.llm.base import LLMProvider

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or DEFAULT_MODEL
        self._api_key = api_key

    def complete(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI  # lazy import of optional SDK
        except ImportError as exc:  # pragma: no cover - exercised only in live mode
            raise RuntimeError(
                "The 'openai' provider requires the openai SDK. Install it with "
                "`pip install 'deepresearch[openai]'`, or use --dry-run / --provider stub."
            ) from exc

        if not self._api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Export it for live mode, or use "
                "--dry-run / --provider stub."
            )

        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""
