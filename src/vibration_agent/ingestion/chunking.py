"""Chunking helpers for page-level OCR/native text outputs."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from vibration_agent.schemas import DocumentAsset, OcrPage

SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class Paragraph:
    page_no: int
    text: str


def estimate_tokens(text: str) -> int:
    """Cheap mixed zh/en estimate when tokenizer packages are unavailable."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+(?:[-./][A-Za-z0-9_]+)*", text))
    other_chars = max(len(text) - cjk, 0)
    return max(1, int(cjk + ascii_words * 1.25 + other_chars / 6))


def enumerate_pages(page_start: int, page_end: int) -> list[int]:
    return list(range(page_start, page_end + 1))


def pages_to_paragraphs(pages: Sequence[OcrPage]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for page in pages:
        text = page.normalized_text.strip()
        if not text:
            continue
        parts = re.split(r"\n\s*\n|(?<=[.!?。！？；;])\n", text)
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


def overlap_tail(paragraphs: list[Paragraph], overlap_tokens: int) -> list[Paragraph]:
    if overlap_tokens <= 0:
        return []
    tail: list[Paragraph] = []
    total = 0
    for paragraph in reversed(paragraphs):
        tail.insert(0, paragraph)
        total += estimate_tokens(paragraph.text)
        if total >= overlap_tokens:
            break
    return tail


def _page_assets_by_range(pages: Sequence[OcrPage], page_start: int, page_end: int) -> list[DocumentAsset]:
    assets: list[DocumentAsset] = []
    seen: set[str] = set()
    for page in pages:
        if not (page_start <= page.page_no <= page_end):
            continue
        for asset in page.assets:
            if asset.asset_id in seen:
                continue
            seen.add(asset.asset_id)
            assets.append(asset)
    return assets


def _page_quality_by_range(pages: Sequence[OcrPage] | None, page_start: int, page_end: int) -> dict:
    if pages is None:
        return {"ocr_confidence_min": None, "ocr_confidence_avg": None, "needs_review_pages": []}
    selected = [page for page in pages if page_start <= page.page_no <= page_end]
    confidences = [page.ocr_confidence for page in selected if page.ocr_confidence is not None]
    return {
        "ocr_confidence_min": min(confidences) if confidences else None,
        "ocr_confidence_avg": (sum(confidences) / len(confidences)) if confidences else None,
        "needs_review_pages": [page.page_no for page in selected if page.needs_review],
    }


def _chunk_body_asset(*, chunk_id: str, doc_id: str, page_start: int, page_end: int, confidence: float | None) -> DocumentAsset:
    return DocumentAsset(
        asset_id=f"{chunk_id}_body",
        doc_id=doc_id,
        page_no=page_start,
        object_type="body",
        asset_path=f"chunk://{doc_id}/{chunk_id}/body",
        bbox=None,
        text="",
        confidence=confidence,
        metadata={"chunk_id": chunk_id, "pages": enumerate_pages(page_start, page_end)},
    )


def _asset_ref(asset: DocumentAsset) -> dict:
    return asset.model_dump(mode="json")


def _chunk_assets(
    *,
    pages: Sequence[OcrPage] | None,
    chunk_id: str,
    doc_id: str,
    page_start: int,
    page_end: int,
    confidence: float | None,
) -> list[dict]:
    body = _chunk_body_asset(
        chunk_id=chunk_id,
        doc_id=doc_id,
        page_start=page_start,
        page_end=page_end,
        confidence=confidence,
    )
    assets = [body]
    if pages is not None:
        assets.extend(_page_assets_by_range(pages, page_start, page_end))
    return [_asset_ref(asset) for asset in assets]


def chunk_paragraphs(
    paragraphs: Sequence[Paragraph],
    *,
    doc_id: str,
    title: str,
    source_path: str | Path,
    source_type: str,
    target_tokens: int,
    overlap_tokens: int,
    pages: Sequence[OcrPage] | None = None,
) -> list[dict]:
    chunks: list[dict] = []
    current: list[Paragraph] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        text = "\n\n".join(paragraph.text for paragraph in current).strip()
        page_start = min(paragraph.page_no for paragraph in current)
        page_end = max(paragraph.page_no for paragraph in current)
        page_numbers = enumerate_pages(page_start, page_end)
        quality = _page_quality_by_range(pages, page_start, page_end)
        confidence = quality["ocr_confidence_min"] if quality["ocr_confidence_min"] is not None else 1.0
        chunk_index = len(chunks) + 1
        chunk_id = f"{doc_id}_p{page_start:04d}_{chunk_index:05d}"
        assets = _chunk_assets(
            pages=pages,
            chunk_id=chunk_id,
            doc_id=doc_id,
            page_start=page_start,
            page_end=page_end,
            confidence=confidence,
        )
        chunks.append(
            {
                "schema_version": SCHEMA_VERSION,
                "type": "memory_chunk",
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "source_type": source_type,
                "source_path": str(source_path),
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "pages": page_numbers,
                "chunk_type": "body",
                "topic": None,
                "token_estimate": estimate_tokens(text),
                "char_count": len(text),
                "citation_anchor": f"{title}, pp. {page_start}-{page_end}",
                "text": text,
                "assets": assets,
                "ocr_confidence_min": quality["ocr_confidence_min"],
                "ocr_confidence_avg": quality["ocr_confidence_avg"],
                "needs_review_pages": quality["needs_review_pages"],
                "metadata": {"asset_policy": "body asset is a reference; chunk.text owns full body text"},
                "api_context": f"[chunk_id={chunk_id}; doc_id={doc_id}; pages={page_start}-{page_end}]\n{text}",
            }
        )
        current = overlap_tail(current, overlap_tokens)
        current_tokens = sum(estimate_tokens(paragraph.text) for paragraph in current)

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph.text)
        if current and current_tokens + paragraph_tokens > target_tokens:
            flush()
        current.append(paragraph)
        current_tokens += paragraph_tokens
        if paragraph_tokens >= target_tokens:
            flush()

    flush()
    return chunks


def chunk_pages(
    pages: Sequence[OcrPage],
    *,
    doc_id: str,
    title: str,
    source_path: str | Path,
    source_type: str,
    target_tokens: int,
    overlap_tokens: int,
) -> list[dict]:
    return chunk_paragraphs(
        pages_to_paragraphs(pages),
        doc_id=doc_id,
        title=title,
        source_path=source_path,
        source_type=source_type,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
        pages=pages,
    )


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _api_asset_record(asset: dict) -> dict:
    return {
        "asset_id": asset.get("asset_id"),
        "doc_id": asset.get("doc_id"),
        "object_type": asset.get("object_type"),
        "page_no": asset.get("page_no"),
        "asset_path": asset.get("asset_path"),
        "bbox": asset.get("bbox"),
        "text": asset.get("text", ""),
        "confidence": asset.get("confidence"),
        "metadata": asset.get("metadata", {}),
    }


def _api_asset_ref(asset: dict) -> dict:
    return {
        "asset_id": asset.get("asset_id"),
        "object_type": asset.get("object_type"),
        "page_no": asset.get("page_no"),
        "asset_path": asset.get("asset_path"),
        "bbox": asset.get("bbox"),
    }


def _collect_api_assets(chunks: Sequence[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for chunk in chunks:
        for asset in chunk.get("assets", []):
            if not isinstance(asset, dict):
                continue
            if asset.get("object_type") == "body":
                continue
            asset_id = asset.get("asset_id")
            if asset_id and asset_id not in by_id:
                by_id[asset_id] = _api_asset_record(asset)
    return list(by_id.values())


def write_api_context_json(path: str | Path, *, doc_id: str, title: str, chunks: Sequence[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": "api_context_pack",
        "doc_id": doc_id,
        "title": title,
        "usage_note": "Use chunk_id, pages, asset_ids, and top-level assets[] when citing. Do not answer beyond supplied chunks/assets.",
        "assets": _collect_api_assets(chunks),
        "chunks": [
            {
                "chunk_id": chunk["chunk_id"],
                "pages": chunk.get("pages") or enumerate_pages(chunk["page_start"], chunk["page_end"]),
                "token_estimate": chunk["token_estimate"],
                "text": chunk["api_context"],
                "asset_ids": [asset.get("asset_id") for asset in chunk.get("assets", []) if isinstance(asset, dict)],
                "assets": [_api_asset_ref(asset) for asset in chunk.get("assets", []) if isinstance(asset, dict)],
            }
            for chunk in chunks
        ],
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def chunk_sections(sections: list[dict], *, target_tokens: int = 600) -> list[dict]:
    """Input: structured sections. Output: chunk rows ready for the chunks table."""
    raise NotImplementedError("Section-aware chunking starts after layout/section extraction.")


