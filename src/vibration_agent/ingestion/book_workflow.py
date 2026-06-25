"""File-based scanned-book workflow used by the migration CLI.

This module keeps the emergency book workflow available while moving the actual
implementation into the package. It intentionally remains file-based: no
PostgreSQL, Qdrant, Redis, or Tutor-Orchestrator are required.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

import fitz  # type: ignore

from vibration_agent.ingestion.chunking import chunk_pages, estimate_tokens, write_api_context_json, write_jsonl
from vibration_agent.ingestion.classify import classify_document, slugify_filename
from vibration_agent.ingestion.ocr import paddle_engine
from vibration_agent.ingestion.pipeline import build_document_manifest
from vibration_agent.ingestion.ocr.router import ocr_page as routed_ocr_page
from vibration_agent.schemas import OcrPage

SCHEMA_VERSION = "0.1"
DocIdMode = Literal["legacy-path", "content"]


@dataclass(frozen=True)
class BookWorkflowOptions:
    source_type: str = "book"
    lang: str = "ch"
    ocr_version: str = "PP-OCRv4"
    det_model_name: str | None = "PP-OCRv4_mobile_det"
    rec_model_name: str | None = "PP-OCRv4_mobile_rec"
    dpi: int = 220
    target_tokens: int = 800
    overlap_tokens: int = 80
    rec_score_threshold: float = 0.0
    use_textline_orientation: bool = False
    max_pages: int | None = None
    resume: bool = True
    keep_images: bool = False
    doc_id_mode: DocIdMode = "legacy-path"
    use_fallback: bool = True
    low_confidence_threshold: float = 0.6


def legacy_path_doc_id(pdf_path: str | Path) -> str:
    path = Path(pdf_path).resolve()
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    stem = slugify_filename(path)
    return f"{stem}_{digest}" if stem else digest


def resolve_doc_id(pdf_path: str | Path, mode: DocIdMode) -> str:
    if mode == "content":
        return classify_document(pdf_path).doc_id
    return legacy_path_doc_id(pdf_path)


def pdf_page_count(pdf_path: str | Path) -> int:
    with fitz.open(Path(pdf_path)) as doc:
        return doc.page_count


def load_existing_pages(path: str | Path, doc_id: str) -> list[OcrPage]:
    pages: list[OcrPage] = []
    source = Path(path)
    if not source.exists():
        return pages
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        item["doc_id"] = doc_id
        pages.append(OcrPage.model_validate(item))
    return pages


def page_to_json_row(page: OcrPage) -> dict[str, Any]:
    row = page.model_dump(mode="json")
    row = {"schema_version": SCHEMA_VERSION, **row}
    return row


def write_pages_jsonl(path: str | Path, pages: Iterable[OcrPage]) -> None:
    write_jsonl(path, [page_to_json_row(page) for page in pages])


def find_pdfs(raw_dir: str | Path) -> list[Path]:
    root = Path(raw_dir)
    candidates = list(root.glob("*.pdf")) + list(root.glob("*.PDF"))
    return sorted({str(path.resolve()).lower(): path for path in candidates}.values(), key=lambda path: str(path).lower())


def ocr_one_page(
    *,
    pdf_path: Path,
    doc_id: str,
    page_no: int,
    image_dir: Path,
    workspace: Path,
    options: BookWorkflowOptions,
) -> OcrPage:
    if options.use_fallback:
        return routed_ocr_page(
            pdf_path,
            page_no,
            doc_id=doc_id,
            lang=options.lang,
            dpi=options.dpi,
            low_confidence_threshold=options.low_confidence_threshold,
            workspace=workspace,
            image_dir=image_dir,
            keep_images=options.keep_images,
            ocr_version=options.ocr_version,
            det_model_name=options.det_model_name,
            rec_model_name=options.rec_model_name,
            rec_score_threshold=options.rec_score_threshold,
            use_textline_orientation=options.use_textline_orientation,
        )

    return paddle_engine.run(
        pdf_path,
        page_no,
        doc_id=doc_id,
        lang=options.lang,
        dpi=options.dpi,
        workspace=workspace,
        image_dir=image_dir,
        keep_image=options.keep_images,
        review_threshold=options.low_confidence_threshold,
        ocr_version=options.ocr_version,
        det_model_name=options.det_model_name,
        rec_model_name=options.rec_model_name,
        rec_score_threshold=options.rec_score_threshold,
        use_textline_orientation=options.use_textline_orientation,
    )


def prepare_primary_ocr_engine(*, workspace: Path, options: BookWorkflowOptions) -> None:
    """Initialize PaddleOCR before page-level progress logs begin."""
    paddle_engine.configure_paddle_cache(workspace)
    paddle_engine.make_ocr(
        lang=options.lang,
        ocr_version=options.ocr_version,
        det_model_name=options.det_model_name,
        rec_model_name=options.rec_model_name,
        rec_score_threshold=options.rec_score_threshold,
        use_textline_orientation=options.use_textline_orientation,
    )


def process_pdf(*, pdf_path: str | Path, workspace: str | Path, options: BookWorkflowOptions) -> dict[str, Any]:
    root = Path(workspace).resolve()
    source = Path(pdf_path).resolve()
    doc_id = resolve_doc_id(source, options.doc_id_mode)
    title = source.stem

    ocr_dir = root / "data" / "ocr" / options.source_type / doc_id
    chunk_dir = root / "data" / "chunks" / options.source_type / doc_id
    export_dir = root / "data" / "exports" / options.source_type / doc_id
    image_dir = ocr_dir / "page_images"
    for output_dir in (ocr_dir, chunk_dir, export_dir):
        output_dir.mkdir(parents=True, exist_ok=True)

    page_count = pdf_page_count(source)
    page_limit = min(page_count, options.max_pages) if options.max_pages is not None else page_count
    pages_path = ocr_dir / "pages.jsonl"
    existing_pages = load_existing_pages(pages_path, doc_id) if options.resume else []
    existing_by_no = {page.page_no: page for page in existing_pages}
    pending_page_nos = [page_no for page_no in range(1, page_limit + 1) if page_no not in existing_by_no]

    if pending_page_nos:
        print(
            f"Initializing PaddleOCR for {source.name} ({len(pending_page_nos)} pending pages)",
            flush=True,
            file=sys.stderr,
        )
        prepare_primary_ocr_engine(workspace=root, options=options)
        print(f"PaddleOCR ready for {source.name}", flush=True, file=sys.stderr)

    pages: list[OcrPage] = []
    for page_no in range(1, page_limit + 1):
        if page_no in existing_by_no:
            pages.append(existing_by_no[page_no])
            continue
        print(f"OCR start {source.name} page {page_no}/{page_limit}", flush=True, file=sys.stderr)
        started_at = time.perf_counter()
        page = ocr_one_page(
            pdf_path=source,
            doc_id=doc_id,
            page_no=page_no,
            image_dir=image_dir,
            workspace=root,
            options=options,
        )
        elapsed = time.perf_counter() - started_at
        pages.append(page)
        confidence = "n/a" if page.ocr_confidence is None else f"{page.ocr_confidence:.3f}"
        print(
            f"OCR done {source.name} page {page_no}/{page_limit} "
            f"confidence={confidence} chars={len(page.normalized_text)} blocks={len(page.blocks)} "
            f"elapsed={elapsed:.1f}s",
            flush=True,
            file=sys.stderr,
        )
        write_pages_jsonl(pages_path, sorted(pages, key=lambda item: item.page_no))

    pages = sorted(pages, key=lambda item: item.page_no)
    write_pages_jsonl(pages_path, pages)

    chunks = chunk_pages(
        pages,
        doc_id=doc_id,
        title=title,
        source_path=source,
        source_type=options.source_type,
        target_tokens=options.target_tokens,
        overlap_tokens=options.overlap_tokens,
    )
    write_jsonl(chunk_dir / "chunks.jsonl", chunks)
    write_api_context_json(export_dir / "api_context.json", doc_id=doc_id, title=title, chunks=chunks)

    classification = classify_document(source).model_copy(update={"doc_id": doc_id, "processing_strategy": "ocr_pdf"})
    page_result = {
        "status": "ok" if pages else "insufficient",
        "page_count": page_count,
        "processed_pages": len(pages),
        "pages": [page_to_json_row(page) for page in pages],
        "warnings": [f"Page {page.page_no} needs review" for page in pages if page.needs_review],
    }
    manifest = build_document_manifest(
        document=classification,
        title=title,
        source_type=options.source_type,
        page_result=page_result,
        chunks=chunks,
        pages_path=pages_path,
        chunks_path=chunk_dir / "chunks.jsonl",
        api_context_path=export_dir / "api_context.json",
        manifest_path=export_dir / "manifest.json",
        write_output=True,
        doc_id_mode=options.doc_id_mode,
    )
    manifest.update(
        {
            "input_pdf": str(source),
            "doc_id_mode": options.doc_id_mode,
            "page_count": manifest["counts"]["page_count"],
            "processed_pages": manifest["counts"]["processed_pages"],
            "chunk_count": manifest["counts"]["chunk_count"],
            "total_token_estimate": manifest["counts"]["total_token_estimate"],
        }
    )
    manifest["outputs"] = {
        **manifest["outputs"],
        "ocr_pages_jsonl": str(pages_path),
    }
    (export_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def process_raw_dir(*, raw_dir: str | Path, workspace: str | Path, options: BookWorkflowOptions) -> list[dict[str, Any]]:
    pdfs = find_pdfs(raw_dir)
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found under {raw_dir}")
    return [process_pdf(pdf_path=pdf, workspace=workspace, options=options) for pdf in pdfs]



