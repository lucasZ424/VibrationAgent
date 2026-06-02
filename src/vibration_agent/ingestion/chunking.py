"""Chunking helpers for page-level OCR/native text outputs."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from vibration_agent.ingestion.section_hierarchy import build_hierarchy_warnings, build_parent_map
from vibration_agent.schemas import DocumentAsset, DocumentBibliography, OcrPage

SCHEMA_VERSION = "0.1"
FRONT_MATTER_SECTION_KEY = "front_matter"


@dataclass(frozen=True)
class Paragraph:
    page_no: int
    text: str
    block_type: str = "body"
    section_key: str = FRONT_MATTER_SECTION_KEY
    section_title: str | None = None
    section_level: int = 0


@dataclass(frozen=True)
class SectionSpan:
    section_key: str
    title: str | None
    level: int
    page_start: int
    page_end: int
    paragraphs: list[Paragraph]


def estimate_tokens(text: str) -> int:
    """Cheap mixed zh/en estimate when tokenizer packages are unavailable."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+(?:[-./][A-Za-z0-9_]+)*", text))
    other_chars = max(len(text) - cjk, 0)
    return max(1, int(cjk + ascii_words * 1.25 + other_chars / 6))


def enumerate_pages(page_start: int, page_end: int) -> list[int]:
    return list(range(page_start, page_end + 1))


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _split_text_units(text: str) -> list[str]:
    raw_parts = re.split(r"\n\s*\n|(?<=[.!?\u3002\uff01\uff1f\uff1b;])\n", text.strip())
    units: list[str] = []
    for part in raw_parts:
        cleaned = _clean_text(part)
        if cleaned:
            units.append(cleaned)
    return units


def _infer_title_level(title: str) -> int:
    stripped = title.strip()
    if re.match(r"^chapter\s+\d+\b", stripped, re.IGNORECASE):
        return 1
    if numeric := re.match(r"^(\d+(?:\.\d+)+)\b", stripped):
        return numeric.group(1).count(".") + 1
    if re.match(r"^\d+[\.)]\s+\S+", stripped):
        return 2
    if stripped.startswith("\u7b2c") and "\u7ae0" in stripped:
        return 1
    if stripped.startswith("\u7b2c") and ("\u8282" in stripped or "\u5c0f\u8282" in stripped):
        return 2
    return 1


def _section_key(section_index: int) -> str:
    return f"s{section_index:04d}"


def pages_to_paragraphs(pages: Sequence[OcrPage]) -> list[Paragraph]:
    """Convert pages to ordered paragraphs while preserving title-derived sections."""
    paragraphs: list[Paragraph] = []
    section_index = 0
    current_section_key = FRONT_MATTER_SECTION_KEY
    current_section_title: str | None = None
    current_section_level = 0

    for page in pages:
        emitted_from_blocks = False
        for block in page.blocks:
            text = _clean_text(block.text)
            if not text:
                continue
            if block.block_type == "title":
                section_index += 1
                current_section_key = _section_key(section_index)
                current_section_title = text
                current_section_level = _infer_title_level(text)
                paragraphs.append(
                    Paragraph(
                        page_no=page.page_no,
                        text=text,
                        block_type="title",
                        section_key=current_section_key,
                        section_title=current_section_title,
                        section_level=current_section_level,
                    )
                )
                emitted_from_blocks = True
                continue
            if block.block_type == "table":
                for unit in _split_text_units(block.text):
                    paragraphs.append(
                        Paragraph(
                            page_no=page.page_no,
                            text=unit,
                            block_type="body",
                            section_key=current_section_key,
                            section_title=current_section_title,
                            section_level=current_section_level,
                        )
                    )
                    emitted_from_blocks = True
                continue
            if block.block_type != "body":
                continue
            for unit in _split_text_units(block.text):
                paragraphs.append(
                    Paragraph(
                        page_no=page.page_no,
                        text=unit,
                        block_type="body",
                        section_key=current_section_key,
                        section_title=current_section_title,
                        section_level=current_section_level,
                    )
                )
                emitted_from_blocks = True

        if emitted_from_blocks:
            continue

        for unit in _split_text_units(page.normalized_text):
            paragraphs.append(
                Paragraph(
                    page_no=page.page_no,
                    text=unit,
                    block_type="body",
                    section_key=current_section_key,
                    section_title=current_section_title,
                    section_level=current_section_level,
                )
            )
    return paragraphs


def paragraphs_to_sections(paragraphs: Sequence[Paragraph]) -> list[SectionSpan]:
    sections: list[SectionSpan] = []
    current_key: str | None = None
    current: list[Paragraph] = []

    def flush() -> None:
        nonlocal current, current_key
        if not current:
            return
        sections.append(
            SectionSpan(
                section_key=current_key or FRONT_MATTER_SECTION_KEY,
                title=current[0].section_title,
                level=current[0].section_level,
                page_start=min(paragraph.page_no for paragraph in current),
                page_end=max(paragraph.page_no for paragraph in current),
                paragraphs=list(current),
            )
        )
        current = []
        current_key = None

    for paragraph in paragraphs:
        if current and paragraph.section_key != current_key:
            flush()
        current_key = paragraph.section_key
        current.append(paragraph)
    flush()
    return sections


def overlap_tail(paragraphs: list[Paragraph], overlap_tokens: int) -> list[Paragraph]:
    if overlap_tokens <= 0:
        return []
    tail: list[Paragraph] = []
    total = 0
    section_key = paragraphs[-1].section_key if paragraphs else None
    for paragraph in reversed(paragraphs):
        if paragraph.section_key != section_key:
            break
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


def _section_metadata(
    paragraphs: Sequence[Paragraph],
    parent_map: dict[str, list[str]] | None = None,
    hierarchy_warnings: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    section_keys = list(dict.fromkeys(paragraph.section_key for paragraph in paragraphs))
    section_titles = list(dict.fromkeys(paragraph.section_title for paragraph in paragraphs if paragraph.section_title))
    section_levels = [paragraph.section_level for paragraph in paragraphs if paragraph.section_level]
    primary_key = section_keys[0] if section_keys else FRONT_MATTER_SECTION_KEY
    return {
        "section_key": primary_key,
        "section_keys": section_keys,
        "section_parent_keys": (parent_map or {}).get(primary_key, []),
        "section_hierarchy_source": "heading_level" if section_levels else "unsectioned",
        "section_hierarchy_warnings": (hierarchy_warnings or {}).get(primary_key, []),
        "section_title": section_titles[0] if section_titles else None,
        "section_level": section_levels[0] if section_levels else 0,
        "section_boundary_crossed": len(section_keys) > 1,
        "section_boundary_policy": "flush_before_new_section",
        "title_in_text": any(paragraph.block_type == "title" for paragraph in paragraphs),
        "paragraph_count": len(paragraphs),
    }


def _bibliography_metadata(bibliography: DocumentBibliography | None) -> dict[str, Any]:
    """Serialize bibliography for chunk metadata; empty/None when unavailable."""
    if bibliography is None:
        return {"year": None, "authors": [], "publisher": None}
    return {
        "year": bibliography.year,
        "authors": list(bibliography.authors),
        "publisher": bibliography.publisher,
    }

def _section_title_for_header(section_title: str | None, limit: int = 60) -> str | None:
    if not section_title:
        return None
    normalized = _clean_text(section_title)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def _citation_anchor(
    title: str,
    page_start: int,
    page_end: int,
    bibliography: DocumentBibliography | None = None,
) -> str:
    page_part = f"p. {page_start}" if page_start == page_end else f"pp. {page_start}-{page_end}"
    if bibliography is not None and bibliography.has_author_year():
        lead = bibliography.authors[0]
        if len(bibliography.authors) > 1:
            lead = f"{lead} et al."
        return f"{lead} ({bibliography.year}), {page_part}"
    return f"{title}, {page_part}"


def _api_context_text(*, chunk_id: str, doc_id: str, page_start: int, page_end: int, section_meta: dict[str, Any], text: str) -> str:
    section_title = _section_title_for_header(section_meta.get("section_title"))
    header_parts = [
        f"chunk_id={chunk_id}",
        f"doc_id={doc_id}",
        f"pages={page_start}-{page_end}",
        f"section={section_meta['section_key']}",
    ]
    if section_title:
        header_parts.append(f"section_title={section_title}")
    return f"[{'; '.join(header_parts)}]\n{text}"

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
    bibliography: DocumentBibliography | None = None,
) -> list[dict]:
    chunks: list[dict] = []
    current: list[Paragraph] = []
    current_tokens = 0
    parent_map = build_parent_map(
        (paragraph.section_key, paragraph.section_level) for paragraph in paragraphs
    )
    hierarchy_warnings = build_hierarchy_warnings(
        (paragraph.section_key, paragraph.section_level) for paragraph in paragraphs
    )

    def flush(*, keep_overlap: bool) -> None:
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
        section_meta = _section_metadata(current, parent_map=parent_map, hierarchy_warnings=hierarchy_warnings)
        metadata = {
            "asset_policy": "body asset is a reference; chunk.text owns full body text",
            "page_boundary_crossed": page_start != page_end,
            "target_tokens": target_tokens,
            "overlap_tokens": overlap_tokens,
            "bibliography": _bibliography_metadata(bibliography),
            **section_meta,
        }
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
                "topic": section_meta["section_title"],
                "token_estimate": estimate_tokens(text),
                "char_count": len(text),
                "citation_anchor": _citation_anchor(title, page_start, page_end, bibliography),
                "text": text,
                "assets": assets,
                "ocr_confidence_min": quality["ocr_confidence_min"],
                "ocr_confidence_avg": quality["ocr_confidence_avg"],
                "needs_review_pages": quality["needs_review_pages"],
                "metadata": metadata,
                "api_context": _api_context_text(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    page_start=page_start,
                    page_end=page_end,
                    section_meta=section_meta,
                    text=text,
                ),
            }
        )
        current = overlap_tail(current, overlap_tokens) if keep_overlap else []
        current_tokens = sum(estimate_tokens(paragraph.text) for paragraph in current)

    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph.text)
        if current and paragraph.section_key != current[-1].section_key:
            flush(keep_overlap=False)
        if current and current_tokens + paragraph_tokens > target_tokens:
            flush(keep_overlap=True)
        current.append(paragraph)
        current_tokens += paragraph_tokens
        if paragraph_tokens >= target_tokens:
            flush(keep_overlap=False)

    flush(keep_overlap=False)
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
    bibliography: DocumentBibliography | None = None,
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
        bibliography=bibliography,
    )


def _section_page_start(section: dict[str, Any]) -> int:
    if section.get("page_start") is not None:
        return int(section["page_start"])
    if section.get("page_no") is not None:
        return int(section["page_no"])
    source_paragraphs = section.get("paragraphs")
    if isinstance(source_paragraphs, list):
        for item in source_paragraphs:
            if isinstance(item, dict):
                page_value = item.get("page_no") or item.get("page_start")
                if page_value is not None:
                    return int(page_value)
    raise ValueError("section requires page_start/page_no or paragraph-level page_no for citation-safe chunking")


def _section_paragraphs_from_dict(section: dict[str, Any], index: int) -> list[Paragraph]:
    section_title = section.get("title") or section.get("topic")
    section_key = str(section.get("section_key") or section.get("section_id") or _section_key(index))
    section_level = int(section.get("level") or (_infer_title_level(str(section_title)) if section_title else 1))
    page_start = _section_page_start(section)
    paragraphs: list[Paragraph] = []
    if section_title:
        paragraphs.append(
            Paragraph(
                page_no=page_start,
                text=str(section_title),
                block_type="title",
                section_key=section_key,
                section_title=str(section_title),
                section_level=section_level,
            )
        )

    source_paragraphs = section.get("paragraphs")
    if isinstance(source_paragraphs, list):
        for item in source_paragraphs:
            if isinstance(item, dict):
                text = str(item.get("text", ""))
                page_no = int(item.get("page_no") or item.get("page_start") or page_start)
            else:
                text = str(item)
                page_no = page_start
            for unit in _split_text_units(text):
                paragraphs.append(
                    Paragraph(
                        page_no=page_no,
                        text=unit,
                        block_type="body",
                        section_key=section_key,
                        section_title=str(section_title) if section_title else None,
                        section_level=section_level,
                    )
                )
        return paragraphs

    for unit in _split_text_units(str(section.get("text", ""))):
        paragraphs.append(
            Paragraph(
                page_no=page_start,
                text=unit,
                block_type="body",
                section_key=section_key,
                section_title=str(section_title) if section_title else None,
                section_level=section_level,
            )
        )
    return paragraphs


def chunk_sections(
    sections: Sequence[dict[str, Any]],
    *,
    doc_id: str,
    title: str,
    source_path: str | Path,
    source_type: str = "book",
    target_tokens: int = 600,
    overlap_tokens: int = 60,
    pages: Sequence[OcrPage] | None = None,
    bibliography: DocumentBibliography | None = None,
) -> list[dict]:
    """Chunk structured sections without crossing section boundaries."""
    paragraphs: list[Paragraph] = []
    for index, section in enumerate(sections, start=1):
        paragraphs.extend(_section_paragraphs_from_dict(section, index))
    return chunk_paragraphs(
        paragraphs,
        doc_id=doc_id,
        title=title,
        source_path=source_path,
        source_type=source_type,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
        pages=pages,
        bibliography=bibliography,
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
