"""Chunking helpers for page-level OCR/native text outputs."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from vibration_agent.schemas import OcrPage

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


def chunk_paragraphs(
    paragraphs: Sequence[Paragraph],
    *,
    doc_id: str,
    title: str,
    source_path: str | Path,
    source_type: str,
    target_tokens: int,
    overlap_tokens: int,
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
        chunk_index = len(chunks) + 1
        chunk_id = f"{doc_id}_p{page_start:04d}_{chunk_index:05d}"
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
                "chunk_type": "body",
                "topic": None,
                "token_estimate": estimate_tokens(text),
                "char_count": len(text),
                "citation_anchor": f"{title}, pp. {page_start}-{page_end}",
                "text": text,
                "assets": [],
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
    )


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_api_context_json(path: str | Path, *, doc_id: str, title: str, chunks: Sequence[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": "api_context_pack",
        "doc_id": doc_id,
        "title": title,
        "usage_note": "Use chunk_id and pages when citing. Do not answer beyond the supplied chunks.",
        "chunks": [
            {
                "chunk_id": chunk["chunk_id"],
                "pages": f"{chunk['page_start']}-{chunk['page_end']}",
                "token_estimate": chunk["token_estimate"],
                "text": chunk["api_context"],
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