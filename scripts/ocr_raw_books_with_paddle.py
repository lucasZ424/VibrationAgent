"""OCR scanned book PDFs with PaddleOCR and export agent-memory chunks.

Minimal book workflow:
    data/raw/book/*.pdf
      -> data/ocr/book/<doc_id>/pages.jsonl
      -> data/chunks/book/<doc_id>/chunks.jsonl
      -> data/exports/book/<doc_id>/{api_context.json, manifest.json}

This script is intentionally file-based. It does not require PostgreSQL, Qdrant,
Redis, or the Tutor-Orchestrator.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from pdf_to_agent_memory import (
    Paragraph,
    chunk_paragraphs,
    estimate_tokens,
    stable_doc_id,
    write_api_context_json,
    write_jsonl,
)


SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class OcrPage:
    doc_id: str
    page_no: int
    primary_engine: str
    fallback_used: bool
    ocr_confidence: float | None
    layout_quality: str
    raw_text: str
    normalized_text: str
    blocks: list[dict[str, Any]]
    needs_review: bool


def configure_workspace_cache(workspace: Path) -> None:
    """Keep Paddle/PaddleX cache writes inside the project workspace."""
    data_dir = workspace / "data"
    cache_dir = data_dir / "cache"
    paddle_home = cache_dir / "paddle"
    cache_dir.mkdir(parents=True, exist_ok=True)
    paddle_home.mkdir(parents=True, exist_ok=True)

    os.environ["USERPROFILE"] = str(data_dir.resolve())
    os.environ["XDG_CACHE_HOME"] = str(cache_dir.resolve())
    os.environ["PADDLE_HOME"] = str(paddle_home.resolve())
    os.environ["PADDLE_PDX_CACHE_HOME"] = str((cache_dir / "paddlex").resolve())
    os.environ["PADDLE_PDX_MODEL_SOURCE"] = "bos"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "False"
    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["PADDLE_EXTENSION_DIR"] = str((cache_dir / "paddle_extension").resolve())
    os.environ["HF_HOME"] = str((cache_dir / "huggingface").resolve())
    os.environ["MODELSCOPE_CACHE"] = str((cache_dir / "modelscope").resolve())


def make_ocr(
    lang: str,
    ocr_version: str,
    det_model_name: str | None,
    rec_model_name: str | None,
    rec_score_threshold: float,
    use_textline_orientation: bool,
):
    from paddleocr import PaddleOCR

    kwargs = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": use_textline_orientation,
        "text_rec_score_thresh": rec_score_threshold,
    }
    if det_model_name or rec_model_name:
        kwargs["text_detection_model_name"] = det_model_name
        kwargs["text_recognition_model_name"] = rec_model_name
    else:
        kwargs["lang"] = lang
        kwargs["ocr_version"] = ocr_version
    return PaddleOCR(**kwargs)


def render_page(pdf_path: Path, page_index: int, image_path: Path, dpi: int) -> None:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(image_path)


def normalize_ocr_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


MOJIBAKE_MARKERS = (
    "\u9365",  # mojibake often seen in mis-decoded Chinese OCR text
    "\u95c4",
    "\u93c3",
    "\u93c8",
    "\u7efe",
    "\u9428",
    "\u6d93",
    "\u6d63",
    "\u59af",
    "\u675e",
    "\u59ca",
    "\u7487",
    "\u951f",
)


def repair_mojibake(text: str) -> str:
    if not text or not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text
    try:
        repaired = text.encode("gb18030", errors="ignore").decode("utf-8", errors="replace")
    except UnicodeError:
        return text
    bad_before = sum(text.count(marker) for marker in MOJIBAKE_MARKERS) + text.count("\ufffd")
    bad_after = sum(repaired.count(marker) for marker in MOJIBAKE_MARKERS) + repaired.count("\ufffd")
    return repaired if bad_after < bad_before else text


def to_plain_json(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): to_plain_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_json(v) for v in value]
    return value


def result_to_page(doc_id: str, page_no: int, result: Any) -> OcrPage:
    data = dict(result)
    raw_rec_texts = [str(item) for item in data.get("rec_texts", []) if str(item).strip()]
    rec_texts = [repair_mojibake(text) for text in raw_rec_texts]
    rec_scores = [float(score) for score in data.get("rec_scores", [])]
    rec_boxes = to_plain_json(data.get("rec_boxes", data.get("rec_polys", [])))

    blocks: list[dict[str, Any]] = []
    for idx, text in enumerate(rec_texts):
        score = rec_scores[idx] if idx < len(rec_scores) else None
        bbox = rec_boxes[idx] if idx < len(rec_boxes) else None
        blocks.append(
            {
                "block_id": f"p{page_no:04d}_b{idx + 1:04d}",
                "text": text,
                "bbox": bbox,
                "confidence": score,
            }
        )

    raw_text = "\n".join(raw_rec_texts)
    normalized_text = normalize_ocr_text(raw_text)
    avg_conf = sum(rec_scores) / len(rec_scores) if rec_scores else None
    needs_review = avg_conf is None or avg_conf < 0.60 or len(normalized_text) < 20
    layout_quality = "empty" if not normalized_text else ("low" if needs_review else "ok")

    return OcrPage(
        doc_id=doc_id,
        page_no=page_no,
        primary_engine="paddleocr",
        fallback_used=False,
        ocr_confidence=avg_conf,
        layout_quality=layout_quality,
        raw_text=raw_text,
        normalized_text=normalized_text,
        blocks=blocks,
        needs_review=needs_review,
    )


def ocr_page(
    *,
    ocr: Any,
    pdf_path: Path,
    doc_id: str,
    page_no: int,
    image_dir: Path,
    dpi: int,
    keep_images: bool,
) -> OcrPage:
    image_path = image_dir / f"page_{page_no:04d}.png"
    render_page(pdf_path, page_no - 1, image_path, dpi)
    try:
        results = ocr.predict(str(image_path))
        if not results:
            return OcrPage(
                doc_id=doc_id,
                page_no=page_no,
                primary_engine="paddleocr",
                fallback_used=False,
                ocr_confidence=None,
                layout_quality="empty",
                raw_text="",
                normalized_text="",
                blocks=[],
                needs_review=True,
            )
        return result_to_page(doc_id, page_no, results[0])
    finally:
        if not keep_images:
            image_path.unlink(missing_ok=True)


def write_pages_jsonl(path: Path, pages: list[OcrPage]) -> None:
    rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "doc_id": page.doc_id,
            "page_no": page.page_no,
            "primary_engine": page.primary_engine,
            "fallback_used": page.fallback_used,
            "ocr_confidence": page.ocr_confidence,
            "layout_quality": page.layout_quality,
            "raw_text": page.raw_text,
            "normalized_text": page.normalized_text,
            "blocks": page.blocks,
            "needs_review": page.needs_review,
        }
        for page in pages
    ]
    write_jsonl(path, rows)



def pages_to_paragraphs(pages: list[OcrPage]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for page in pages:
        text = page.normalized_text
        if not text:
            continue
        parts = re.split(r"\n\s*\n|(?<=[.!?銆傦紒锛燂紱;])\n", text)
        buffer: list[str] = []
        for part in parts:
            part = re.sub(r"\s+", " ", part).strip()
            if not part:
                continue
            buffer.append(part)
            if estimate_tokens(" ".join(buffer)) >= 80:
                paragraphs.append(Paragraph(page_no=page.page_no, text=" ".join(buffer)))
                buffer = []
        if buffer:
            paragraphs.append(Paragraph(page_no=page.page_no, text=" ".join(buffer)))
    return paragraphs


def load_existing_pages(path: Path, doc_id: str) -> list[OcrPage]:
    pages: list[OcrPage] = []
    if not path.exists():
        return pages
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        pages.append(
            OcrPage(
                doc_id=doc_id,
                page_no=int(item["page_no"]),
                primary_engine=item.get("primary_engine", "paddleocr"),
                fallback_used=bool(item.get("fallback_used", False)),
                ocr_confidence=item.get("ocr_confidence"),
                layout_quality=item.get("layout_quality", "unknown"),
                raw_text=item.get("raw_text", ""),
                normalized_text=item.get("normalized_text", ""),
                blocks=item.get("blocks", []),
                needs_review=bool(item.get("needs_review", False)),
            )
        )
    return pages


def pdf_page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def process_pdf(
    *,
    pdf_path: Path,
    workspace: Path,
    ocr: Any,
    source_type: str,
    dpi: int,
    target_tokens: int,
    overlap_tokens: int,
    max_pages: int | None,
    resume: bool,
    keep_images: bool,
) -> dict[str, Any]:
    doc_id = stable_doc_id(pdf_path)
    title = pdf_path.stem
    ocr_dir = workspace / "data" / "ocr" / "book" / doc_id
    chunk_dir = workspace / "data" / "chunks" / "book" / doc_id
    export_dir = workspace / "data" / "exports" / "book" / doc_id
    image_dir = ocr_dir / "page_images"
    for path in (ocr_dir, chunk_dir, export_dir):
        path.mkdir(parents=True, exist_ok=True)

    page_count = pdf_page_count(pdf_path)
    page_limit = min(page_count, max_pages) if max_pages else page_count
    pages_path = ocr_dir / "pages.jsonl"
    existing_pages = load_existing_pages(pages_path, doc_id) if resume else []
    existing_by_no = {page.page_no: page for page in existing_pages}

    pages: list[OcrPage] = []
    for page_no in range(1, page_limit + 1):
        if page_no in existing_by_no:
            pages.append(existing_by_no[page_no])
            continue
        print(f"OCR {pdf_path.name} page {page_no}/{page_limit}", flush=True)
        pages.append(
            ocr_page(
                ocr=ocr,
                pdf_path=pdf_path,
                doc_id=doc_id,
                page_no=page_no,
                image_dir=image_dir,
                dpi=dpi,
                keep_images=keep_images,
            )
        )
        write_pages_jsonl(pages_path, sorted(pages, key=lambda item: item.page_no))

    pages = sorted(pages, key=lambda item: item.page_no)
    write_pages_jsonl(pages_path, pages)

    chunks = chunk_paragraphs(
        pages_to_paragraphs(pages),
        doc_id=doc_id,
        title=title,
        source_path=pdf_path,
        source_type=source_type,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
    )
    write_jsonl(chunk_dir / "chunks.jsonl", chunks)
    write_api_context_json(
        export_dir / "api_context.json",
        doc_id=doc_id,
        title=title,
        chunks=chunks,
    )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_pdf": str(pdf_path),
        "doc_id": doc_id,
        "title": title,
        "source_type": source_type,
        "page_count": page_count,
        "processed_pages": len(pages),
        "chunk_count": len(chunks),
        "total_token_estimate": sum(chunk["token_estimate"] for chunk in chunks),
        "needs_review_pages": [page.page_no for page in pages if page.needs_review],
        "outputs": {
            "ocr_pages_jsonl": str(pages_path),
            "chunks_jsonl": str(chunk_dir / "chunks.jsonl"),
            "api_context_json": str(export_dir / "api_context.json"),
            "manifest_json": str(export_dir / "manifest.json"),
        },
    }
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path.cwd()
    configure_workspace_cache(workspace)

    raw_dir = args.raw_dir
    pdf_candidates = list(raw_dir.glob("*.pdf")) + list(raw_dir.glob("*.PDF"))
    pdfs = sorted({str(path.resolve()).lower(): path for path in pdf_candidates}.values(), key=lambda path: str(path).lower())
    if not pdfs:
        print(f"No PDF files found under {raw_dir}", file=sys.stderr)
        return 1

    try:
        ocr = make_ocr(
            args.lang,
            args.ocr_version,
            args.det_model_name or None,
            args.rec_model_name or None,
            args.rec_score_threshold,
            args.use_textline_orientation,
        )
    except Exception as exc:
        print(f"Failed to initialize PaddleOCR: {exc}", file=sys.stderr)
        return 2

    manifests = []
    for pdf_path in pdfs:
        try:
            manifests.append(
                process_pdf(
                    pdf_path=pdf_path,
                    workspace=workspace,
                    ocr=ocr,
                    source_type=args.source_type,
                    dpi=args.dpi,
                    target_tokens=args.target_tokens,
                    overlap_tokens=args.overlap_tokens,
                    max_pages=args.max_pages,
                    resume=not args.no_resume,
                    keep_images=args.keep_images,
                )
            )
        except Exception as exc:
            print(f"Failed to process {pdf_path}: {exc}", file=sys.stderr)
            return 3

    print(json.dumps({"processed": manifests}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



