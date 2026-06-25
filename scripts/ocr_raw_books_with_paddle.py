"""Thin CLI for the scanned-book OCR workflow.

The implementation lives in `vibration_agent.ingestion.book_workflow`. This script
is kept only as a compatibility entry point for the earlier emergency command.
"""
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

from vibration_agent.ingestion.book_workflow import BookWorkflowOptions, process_raw_dir  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR over scanned PDFs in data/raw/book and export API-ready chunks."
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/book"))
    parser.add_argument("--source-type", default="book")
    parser.add_argument("--lang", default="ch")
    parser.add_argument("--ocr-version", default="PP-OCRv4")
    parser.add_argument("--det-model-name", default="PP-OCRv4_mobile_det")
    parser.add_argument("--rec-model-name", default="PP-OCRv4_mobile_rec")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--target-tokens", type=int, default=800)
    parser.add_argument("--overlap-tokens", type=int, default=80)
    parser.add_argument("--rec-score-threshold", type=float, default=0.0)
    parser.add_argument("--use-textline-orientation", action="store_true")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--keep-images", action="store_true")
    parser.add_argument(
        "--doc-id-mode",
        choices=("legacy-path", "content"),
        default="legacy-path",
        help="legacy-path preserves the original emergency script output paths; content uses the formal classifier doc_id.",
    )
    fallback = parser.add_mutually_exclusive_group()
    fallback.add_argument(
        "--use-fallback",
        dest="use_fallback",
        action="store_true",
        help="Use Tesseract for empty or low-confidence PaddleOCR pages (default).",
    )
    fallback.add_argument(
        "--no-fallback",
        dest="use_fallback",
        action="store_false",
        help="Disable Tesseract fallback for OCR troubleshooting.",
    )
    parser.set_defaults(use_fallback=True)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.6)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    options = BookWorkflowOptions(
        source_type=args.source_type,
        lang=args.lang,
        ocr_version=args.ocr_version,
        det_model_name=args.det_model_name or None,
        rec_model_name=args.rec_model_name or None,
        dpi=args.dpi,
        target_tokens=args.target_tokens,
        overlap_tokens=args.overlap_tokens,
        rec_score_threshold=args.rec_score_threshold,
        use_textline_orientation=args.use_textline_orientation,
        max_pages=args.max_pages,
        resume=not args.no_resume,
        keep_images=args.keep_images,
        doc_id_mode=args.doc_id_mode,
        use_fallback=args.use_fallback,
        low_confidence_threshold=args.low_confidence_threshold,
    )

    try:
        manifests = process_raw_dir(raw_dir=args.raw_dir, workspace=Path.cwd(), options=options)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to process raw books: {exc}", file=sys.stderr)
        return 3

    print(json.dumps({"processed": manifests}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
