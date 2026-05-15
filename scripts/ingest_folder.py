"""Classify or page-parse supported files for the ingestion pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_local_src_importable() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_local_src_importable()

from vibration_agent.ingestion.pipeline import ingest, parse_pages  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ingestion plans or page-level OCR outputs.")
    parser.add_argument("--src", required=True, help="Input file or directory")
    parser.add_argument("--no-recursive", action="store_true", help="Only scan the top-level directory")
    parser.add_argument("--parse-pages", action="store_true", help="Run native parsing/OCR after classification")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit parsed pages per document")
    parser.add_argument("--no-write", action="store_true", help="Do not write pages.jsonl")
    parser.add_argument("--keep-images", action="store_true", help="Keep rendered page images for OCR PDFs")
    args = parser.parse_args(argv)

    if args.parse_pages:
        result = parse_pages(
            args.src,
            recursive=not args.no_recursive,
            max_pages=args.max_pages,
            write_output=not args.no_write,
            keep_images=args.keep_images,
        )
    else:
        result = ingest(args.src, recursive=not args.no_recursive)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())