"""LLM provider base interface."""

from __future__ import annotations

import abc


class LLMProvider(abc.ABC):
    """Abstract base for text-completion LLM providers."""

    #: Stable provider name (e.g. "stub", "openai", "anthropic").
    name: str = ""

    @abc.abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return a completion for the given system + user prompts."""
        raise NotImplementedError


def build_provider(name: str, *, model: str | None = None, api_key: str | None = None) -> LLMProvider:
    """Factory: build a provider by name.

    The OpenAI/Anthropic providers import their SDKs lazily inside their own
    modules, so importing this module (and the package) never requires an SDK.
    """

    name = (name or "stub").lower()
    if name == "stub":
        from deepresearch.llm.stub_provider import StubProvider

        return StubProvider(model=model)
    if name == "openai":
        from deepresearch.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(model=model, api_key=api_key)
    if name == "anthropic":
        from deepresearch.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model, api_key=api_key)
    raise ValueError(f"unknown LLM provider: {name!r}")
