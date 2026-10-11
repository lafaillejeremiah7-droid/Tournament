"""LLM provider abstraction.

A base interface plus a deterministic stub provider (for dry-run/tests) and
thin OpenAI / Anthropic providers whose SDKs are imported lazily so the package
imports with zero SDKs installed.
"""
