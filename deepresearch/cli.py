"""Command-line interface: ``python -m deepresearch research <query>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from deepresearch import __version__
from deepresearch.config import Config
from deepresearch.pipeline import Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepresearch",
        description="Deep Research agent: build a sourced dossier for a Bible verse or a topic about Jesus Christ.",
    )
    parser.add_argument("--version", action="version", version=f"deepresearch {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    research = sub.add_parser("research", help="Research a verse reference or a free-text topic.")
    research.add_argument("query", nargs="?", default=None, help="A verse reference (e.g. 'Matthew 5:17') or a topic.")
    research.add_argument("--dry-run", action="store_true", help="Run with the deterministic stub provider, no network, no keys.")
    research.add_argument("--provider", choices=["stub", "openai", "anthropic"], default=None, help="LLM provider.")
    research.add_argument("--model", default=None, help="Model name for the chosen provider.")
    research.add_argument("--translations", default=None, help="Comma-separated public-domain translations (default kjv,web,asv).")
    research.add_argument("--output-dir", default=None, help="Directory for the JSON + Markdown dossiers.")
    research.add_argument("--input-file", default=None, help="Read the query from this file instead of the positional arg.")
    return parser


def _resolve_query(args: argparse.Namespace) -> str:
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit(f"error: input file {args.input_file!r} is empty")
        return text
    if args.query:
        return args.query
    raise SystemExit("error: provide a query argument or --input-file")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "research":
        query = _resolve_query(args)
        translations = (
            [t.strip() for t in args.translations.split(",") if t.strip()]
            if args.translations
            else None
        )
        config = Config.from_env_and_args(
            dry_run=True if args.dry_run else None,
            provider=args.provider,
            model=args.model,
            translations=translations,
            output_dir=args.output_dir,
        )
        pipeline = Pipeline(config)
        json_path, md_path = pipeline.run(query)
        print(f"Wrote JSON dossier:     {json_path}")
        print(f"Wrote Markdown dossier: {md_path}")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
