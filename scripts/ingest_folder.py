"""Compatibility shim for the canonical Phase-0 CLI.

Deprecated: prefer `python -m apps.cli.main ingest ...` or
`python -m apps.cli.main parse-pages ...`. This wrapper keeps older Objective-9
commands working while routing behavior through the single canonical CLI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_project_importable() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    for path in (root, src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


_ensure_project_importable()

from apps.cli.main import main as cli_main  # noqa: E402


def _forward_args(args: argparse.Namespace) -> list[str]:
    prefix: list[str] = []
    if args.workspace is not None:
        prefix.extend(["--workspace", str(args.workspace)])

    if args.chunk_documents:
        forwarded = ["ingest", args.src]
    elif args.parse_pages:
        forwarded = ["parse-pages", args.src]
    else:
        forwarded = ["ingest", args.src, "--plan-only"]

    if args.no_recursive:
        forwarded.append("--no-recursive")
    if args.source_type != "book":
        forwarded.extend(["--source-type", args.source_type])
    if args.max_pages is not None:
        forwarded.extend(["--max-pages", str(args.max_pages)])
    if args.no_write:
        forwarded.append("--no-write")
    if args.keep_images:
        forwarded.append("--keep-images")
    return [*prefix, *forwarded]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deprecated compatibility wrapper. Prefer `python -m apps.cli.main ingest ...`."
    )
    parser.add_argument("--src", required=True, help="Input file or directory")
    parser.add_argument("--workspace", type=Path, default=None, help="Project workspace root")
    parser.add_argument("--no-recursive", action="store_true", help="Only scan the top-level directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--parse-pages", action="store_true", help="Run native parsing/OCR after classification")
    mode.add_argument("--chunk-documents", action="store_true", help="Write pages/chunks/api_context/manifest exports")
    parser.add_argument("--source-type", default="book", help="Source type namespace for structured outputs")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit parsed pages per document")
    parser.add_argument("--no-write", action="store_true", help="Do not write structured output files")
    parser.add_argument("--keep-images", action="store_true", help="Keep rendered page images for OCR PDFs")
    args = parser.parse_args(argv)

    return cli_main(_forward_args(args))


if __name__ == "__main__":
    raise SystemExit(main())