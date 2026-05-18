"""Unified ingestion pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from vibration_agent.config import Settings, load
from vibration_agent.schemas import DocumentClassification, OcrPage

from .classify import scan_inputs
from .layout import enrich_page_layout
from .ocr.router import ocr_page
from .pymupdf_parser import parse_native_pdf


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def ingest(path: str | Path, *, recursive: bool = True, settings: Settings | None = None) -> dict[str, Any]:
    """Classify a file or directory and return ingestion-plan metadata."""
    cfg = settings or load()
    classifications = scan_inputs(
        path,
        recursive=recursive,
        pdf_density_threshold=cfg.classify.ocr_text_density_threshold,
    )
    documents = [item.to_dict() for item in classifications]
    return {
        "status": "ok" if documents else "insufficient",
        "stage": "input_classification",
        "input_path": str(Path(path).resolve()),
        "document_count": len(documents),
        "documents": documents,
        "warnings": [] if documents else ["No supported input files found."],
    }


def parse_document_pages(
    document: DocumentClassification,
    *,
    settings: Settings | None = None,
    max_pages: int | None = None,
    write_output: bool = True,
    keep_images: bool = False,
) -> dict[str, Any]:
    """Parse or OCR one classified document into page-level JSON objects."""
    cfg = settings or load()
    source = Path(document.source_path)
    if document.kind != "pdf":
        return {
            "status": "insufficient",
            "stage": "page_parse",
            "doc_id": document.doc_id,
            "source_path": document.source_path,
            "pages": [],
            "warnings": ["Target 5 page parsing currently supports PDF inputs only."],
        }

    page_count = document.page_count or 0
    page_limit = min(page_count, max_pages) if max_pages is not None else page_count
    pages: list[OcrPage] = []

    if document.processing_strategy == "native_pdf":
        asset_dir = cfg.paths.extracted_dir / document.doc_id
        native_pages = parse_native_pdf(source, doc_id=document.doc_id, asset_dir=asset_dir)
        pages = native_pages[:page_limit]
    elif document.processing_strategy == "ocr_pdf":
        image_dir = cfg.paths.ocr_dir / document.doc_id / "page_images"
        for page_no in range(1, page_limit + 1):
            page = ocr_page(
                source,
                page_no,
                doc_id=document.doc_id,
                lang=cfg.ocr.paddleocr_lang,
                tesseract_langs=cfg.ocr.tesseract_langs,
                low_confidence_threshold=cfg.ocr.low_confidence_threshold,
                workspace=cfg.paths.workspace,
                image_dir=image_dir,
                keep_images=keep_images,
            )
            pages.append(enrich_page_layout(page))
    else:
        return {
            "status": "insufficient",
            "stage": "page_parse",
            "doc_id": document.doc_id,
            "source_path": document.source_path,
            "pages": [],
            "warnings": [f"Unsupported processing strategy: {document.processing_strategy}"],
        }

    page_rows = [page.model_dump(mode="json") for page in pages]
    output_path = cfg.paths.ocr_dir / document.doc_id / "pages.jsonl"
    if write_output:
        _write_jsonl(output_path, page_rows)

    return {
        "status": "ok" if pages else "insufficient",
        "stage": "page_parse",
        "doc_id": document.doc_id,
        "source_path": document.source_path,
        "processing_strategy": document.processing_strategy,
        "page_count": page_count,
        "processed_pages": len(pages),
        "output_path": str(output_path) if write_output else None,
        "pages": page_rows,
        "warnings": [f"Page {page.page_no} needs review" for page in pages if page.needs_review],
    }


def parse_pages(
    path: str | Path,
    *,
    recursive: bool = True,
    max_pages: int | None = None,
    write_output: bool = True,
    keep_images: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Classify inputs, then run page-level parsing/OCR for supported PDFs."""
    cfg = settings or load()
    classifications = scan_inputs(
        path,
        recursive=recursive,
        pdf_density_threshold=cfg.classify.ocr_text_density_threshold,
    )
    results = [
        parse_document_pages(
            document,
            settings=cfg,
            max_pages=max_pages,
            write_output=write_output,
            keep_images=keep_images,
        )
        for document in classifications
    ]
    return {
        "status": "ok" if results else "insufficient",
        "stage": "page_parse_batch",
        "input_path": str(Path(path).resolve()),
        "document_count": len(results),
        "documents": results,
        "warnings": [] if results else ["No supported input files found."],
    }


__all__ = [
    "DocumentClassification",
    "ingest",
    "parse_document_pages",
    "parse_pages",
    "scan_inputs",
]

