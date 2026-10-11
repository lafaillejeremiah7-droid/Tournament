"""Deep Research agent package.

Bot #1 of a faith-content video pipeline. Turns a Bible verse/reference or a
free-text topic about Jesus Christ into a structured, deeply-sourced research
dossier built around a 'common misconception vs. deeper truth' spine.

The package imports cleanly with ZERO optional SDKs installed and runs its
dry-run path with ZERO network and ZERO API keys.
"""

__version__ = "0.1.0"

# Schema contract version for downstream bots in the pipeline. Bump when the
# dossier JSON Schema changes in a backward-incompatible way.
SCHEMA_VERSION = "0.1.0"

__all__ = ["__version__", "SCHEMA_VERSION"]
