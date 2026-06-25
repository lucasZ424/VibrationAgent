"""Unified ingestion pipeline."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from vibration_agent.config import Settings, load
from vibration_agent.schemas import DocumentBibliography, DocumentClassification, OcrPage
from vibration_agent.storage.ingestion import persist_ingestion_result

from .bibliography import extract_bibliography
from .chunking import SCHEMA_VERSION, chunk_pages, write_api_context_json, write_jsonl
from .classify import scan_inputs
from .docx_parser import DocxParseError, parse_docx
from .layout import enrich_page_layout
from .ocr.router import ocr_page
from .page_visual_analysis import VisualRecoverySettings as PageVisualRecoverySettings
from .pymupdf_parser import parse_native_pdf


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _page_row(page: OcrPage) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **page.model_dump(mode="json")}


def document_output_paths(cfg: Settings, *, source_type: str, doc_id: str) -> dict[str, Path]:
    """Return the canonical structured export paths for one document."""
    return {
        "pages_jsonl": cfg.paths.ocr_dir / source_type / doc_id / "pages.jsonl",
        "chunks_jsonl": cfg.paths.chunks_dir / source_type / doc_id / "chunks.jsonl",
        "api_context_json": cfg.paths.exports_dir / source_type / doc_id / "api_context.json",
        "manifest_json": cfg.paths.exports_dir / source_type / doc_id / "manifest.json",
        "extracted_dir": cfg.paths.extracted_dir / source_type / doc_id,
        "page_images_dir": cfg.paths.ocr_dir / source_type / doc_id / "page_images",
    }


def _confidence_summary(page_rows: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, float | None]:
    page_confidences = [row.get("ocr_confidence") for row in page_rows if row.get("ocr_confidence") is not None]
    chunk_minima = [chunk.get("ocr_confidence_min") for chunk in chunks if chunk.get("ocr_confidence_min") is not None]
    chunk_averages = [chunk.get("ocr_confidence_avg") for chunk in chunks if chunk.get("ocr_confidence_avg") is not None]
    return {
        "page_ocr_confidence_min": min(page_confidences) if page_confidences else None,
        "page_ocr_confidence_avg": (sum(page_confidences) / len(page_confidences)) if page_confidences else None,
        "chunk_ocr_confidence_min": min(chunk_minima) if chunk_minima else None,
        "chunk_ocr_confidence_avg": (sum(chunk_averages) / len(chunk_averages)) if chunk_averages else None,
    }


def build_document_manifest(
    *,
    document: DocumentClassification,
    title: str,
    source_type: str,
    page_result: dict[str, Any],
    chunks: list[dict[str, Any]],
    pages_path: Path,
    chunks_path: Path,
    api_context_path: Path,
    manifest_path: Path,
    write_output: bool,
    doc_id_mode: str = "content",
) -> dict[str, Any]:
    """Build the canonical document export manifest."""
    page_rows = page_result.get("pages", [])
    needs_review_pages = [row["page_no"] for row in page_rows if row.get("needs_review")]
    warnings = list(page_result.get("warnings", []))
    output_paths = {
        "pages_jsonl": str(pages_path),
        "chunks_jsonl": str(chunks_path),
        "api_context_json": str(api_context_path),
        "manifest_json": str(manifest_path),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "document_ingestion_manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if chunks else page_result.get("status", "insufficient"),
        "doc_id": document.doc_id,
        "title": title,
        "source_type": source_type,
        "input": {
            "source_path": document.source_path,
            "filename": document.filename,
            "kind": document.kind,
            "sha256": document.sha256,
            "language": document.language,
            "doc_id_mode": doc_id_mode,
            "processing_strategy": document.processing_strategy,
            "document_page_count": document.page_count,
        },
        "counts": {
            "page_count": page_result.get("page_count", document.page_count or 0),
            "processed_pages": len(page_rows),
            "chunk_count": len(chunks),
            "needs_review_page_count": len(needs_review_pages),
            "total_token_estimate": sum(int(chunk.get("token_estimate", 0)) for chunk in chunks),
        },
        "quality": _confidence_summary(page_rows, chunks),
        "needs_review_pages": needs_review_pages,
        "outputs": output_paths if write_output else {key: None for key in output_paths},
        "output_formats": {
            "pages": "jsonl",
            "chunks": "jsonl",
            "api_context": "json",
            "manifest": "json",
        },
        "downstream_use": ["s1_ingestion", "s2_retrieval"],
        "markdown_outputs": [],
        "warnings": warnings,
    }


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
    source_type: str = "book",
) -> dict[str, Any]:
    """Parse or OCR one classified document into page-level JSON objects."""
    cfg = settings or load()
    source = Path(document.source_path)
    if document.kind not in {"pdf", "docx"}:
        return {
            "status": "insufficient",
            "stage": "page_parse",
            "doc_id": document.doc_id,
            "source_path": document.source_path,
            "pages": [],
            "warnings": ["Page parsing currently supports PDF and DOCX inputs only."],
        }

    paths = document_output_paths(cfg, source_type=source_type, doc_id=document.doc_id)
    page_count = document.page_count or (1 if document.kind == "docx" else 0)
    page_limit = min(page_count, max_pages) if max_pages is not None else page_count
    pages: list[OcrPage] = []

    if document.processing_strategy == "native_pdf":
        visual = cfg.visual_recovery
        native_pages = parse_native_pdf(
            source,
            doc_id=document.doc_id,
            asset_dir=paths["extracted_dir"],
            image_dpi=cfg.ocr.render_dpi,
            visual_settings=PageVisualRecoverySettings(
                direct_image_min_dimension=visual.direct_image_min_dimension,
                grid_cell_size=visual.grid_cell_size,
                min_cluster_blocks=visual.min_cluster_blocks,
                min_cluster_dimension=visual.min_cluster_dimension,
                min_cluster_area_ratio=visual.min_cluster_area_ratio,
                scanned_text_ceiling=visual.scanned_text_ceiling,
                scanned_meaningful_block_ceiling=visual.scanned_meaningful_block_ceiling,
                scanned_largest_region_ratio=visual.scanned_largest_region_ratio,
                scanned_occupancy_ratio=visual.scanned_occupancy_ratio,
                retained_cluster_limit=visual.retained_cluster_limit,
                hard_cluster_limit=visual.hard_cluster_limit,
                region_ocr_limit=visual.region_ocr_limit,
                direct_asset_limit=visual.direct_asset_limit,
            ),
            page_ocr_enabled=visual.enabled,
            region_ocr_enabled=visual.enabled and visual.region_ocr_enabled,
            workspace=cfg.paths.workspace,
            ocr_lang=cfg.ocr.paddleocr_lang,
            tesseract_langs=cfg.ocr.tesseract_langs,
            low_confidence_threshold=cfg.ocr.low_confidence_threshold,
        )
        pages = native_pages[:page_limit]
    elif document.processing_strategy == "ocr_pdf":
        for page_no in range(1, page_limit + 1):
            page = ocr_page(
                source,
                page_no,
                doc_id=document.doc_id,
                lang=cfg.ocr.paddleocr_lang,
                tesseract_langs=cfg.ocr.tesseract_langs,
                low_confidence_threshold=cfg.ocr.low_confidence_threshold,
                workspace=cfg.paths.workspace,
                image_dir=paths["page_images_dir"],
                keep_images=keep_images,
            )
            pages.append(enrich_page_layout(page))
    elif document.processing_strategy == "docx":
        try:
            pages = parse_docx(source, doc_id=document.doc_id, asset_dir=paths["extracted_dir"])[:page_limit]
        except DocxParseError as exc:
            return {
                "status": "insufficient",
                "stage": "page_parse",
                "doc_id": document.doc_id,
                "source_path": document.source_path,
                "processing_strategy": document.processing_strategy,
                "page_count": document.page_count or 0,
                "processed_pages": 0,
                "output_path": None,
                "pages": [],
                "warnings": [str(exc)],
            }
    else:
        return {
            "status": "insufficient",
            "stage": "page_parse",
            "doc_id": document.doc_id,
            "source_path": document.source_path,
            "pages": [],
            "warnings": [f"Unsupported processing strategy: {document.processing_strategy}"],
        }

    page_rows = [_page_row(page) for page in pages]
    output_path = paths["pages_jsonl"]
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


def _document_bibliography(
    document: DocumentClassification,
    pages: list[OcrPage],
) -> DocumentBibliography:
    """Extract bibliography for a parsed PDF; empty defaults when unavailable.

    Reuses the already-parsed first page text so OCR'd documents (whose embedded
    text layer is empty) still get author/year inference. Non-PDF or unparsed
    documents yield the empty bibliography, preserving Phase-1 citation output.
    """
    if document.kind != "pdf" or not pages:
        return DocumentBibliography()
    return extract_bibliography(
        document.source_path,
        first_page_text=pages[0].normalized_text or None,
    )


def chunk_document_pages(
    document: DocumentClassification,
    *,
    settings: Settings | None = None,
    max_pages: int | None = None,
    write_output: bool = True,
    keep_images: bool = False,
    title: str | None = None,
    source_type: str = "book",
) -> dict[str, Any]:
    """Parse/OCR a document and write Objective-9 structured exports."""
    cfg = settings or load()
    page_result = parse_document_pages(
        document,
        settings=cfg,
        max_pages=max_pages,
        write_output=write_output,
        keep_images=keep_images,
        source_type=source_type,
    )
    pages = [OcrPage.model_validate(row) for row in page_result.get("pages", [])]
    resolved_title = title or Path(document.source_path).stem
    bibliography = _document_bibliography(document, pages)
    chunks = chunk_pages(
        pages,
        doc_id=document.doc_id,
        title=resolved_title,
        source_path=document.source_path,
        source_type=source_type,
        target_tokens=cfg.chunking.target_tokens,
        overlap_tokens=cfg.chunking.overlap_tokens,
        bibliography=bibliography,
    )

    paths = document_output_paths(cfg, source_type=source_type, doc_id=document.doc_id)
    manifest = build_document_manifest(
        document=document,
        title=resolved_title,
        source_type=source_type,
        page_result=page_result,
        chunks=chunks,
        pages_path=paths["pages_jsonl"],
        chunks_path=paths["chunks_jsonl"],
        api_context_path=paths["api_context_json"],
        manifest_path=paths["manifest_json"],
        write_output=write_output,
    )

    if write_output:
        write_jsonl(paths["chunks_jsonl"], chunks)
        write_api_context_json(paths["api_context_json"], doc_id=document.doc_id, title=resolved_title, chunks=chunks)
        _write_json(paths["manifest_json"], manifest)

    return {
        "status": manifest["status"],
        "stage": "document_structured_export",
        "doc_id": document.doc_id,
        "source_path": document.source_path,
        "page_result": page_result,
        "processed_pages": len(pages),
        "chunk_count": len(chunks),
        "pages_output_path": str(paths["pages_jsonl"]) if write_output else None,
        "chunks_output_path": str(paths["chunks_jsonl"]) if write_output else None,
        "api_context_output_path": str(paths["api_context_json"]) if write_output else None,
        "manifest_output_path": str(paths["manifest_json"]) if write_output else None,
        "outputs": manifest["outputs"],
        "manifest": manifest,
        "chunks": chunks,
        "warnings": manifest["warnings"],
    }


def parse_pages(
    path: str | Path,
    *,
    recursive: bool = True,
    max_pages: int | None = None,
    write_output: bool = True,
    keep_images: bool = False,
    source_type: str = "book",
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
            source_type=source_type,
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


def chunk_documents(
    path: str | Path,
    *,
    recursive: bool = True,
    max_pages: int | None = None,
    write_output: bool = True,
    keep_images: bool = False,
    source_type: str = "book",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Classify inputs, then parse and write structured document exports."""
    cfg = settings or load()
    classifications = scan_inputs(
        path,
        recursive=recursive,
        pdf_density_threshold=cfg.classify.ocr_text_density_threshold,
    )
    results = [
        chunk_document_pages(
            document,
            settings=cfg,
            max_pages=max_pages,
            write_output=write_output,
            keep_images=keep_images,
            source_type=source_type,
        )
        for document in classifications
    ]
    result = {
        "status": "ok" if results else "insufficient",
        "stage": "document_structured_export_batch",
        "input_path": str(Path(path).resolve()),
        "document_count": len(results),
        "documents": results,
        "warnings": [] if results else ["No supported input files found."],
    }
    result["storage"] = persist_ingestion_result(result, settings=cfg)
    result["warnings"].extend(result["storage"].get("warnings", []))
    return result


__all__ = [
    "DocumentClassification",
    "build_document_manifest",
    "document_output_paths",
    "chunk_document_pages",
    "chunk_documents",
    "ingest",
    "parse_document_pages",
    "parse_pages",
    "scan_inputs",
]
