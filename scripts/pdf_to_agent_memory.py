"""Convert an OCR-text PDF into chunk files suitable for AI API context input.

This is a minimal emergency workflow:
    OCR PDF -> page text -> cleaned paragraphs -> anchored chunks -> JSONL

It expects the PDF to already contain a text layer. It does not run OCR itself.
Prefer PyMuPDF when installed; fall back to pypdf for basic text extraction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class PageText:
    page_no: int
    text: str
    char_count: int


@dataclass(frozen=True)
class Paragraph:
    page_no: int
    text: str


def stable_doc_id(pdf_path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.stem).strip("_").lower()
    digest = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}" if stem else digest


def estimate_tokens(text: str) -> int:
    """Cheap mixed zh/en estimate when tokenizer packages are unavailable."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+(?:[-./][A-Za-z0-9_]+)*", text))
    other_chars = max(len(text) - cjk, 0)
    return max(1, int(cjk + ascii_words * 1.25 + other_chars / 6))


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages_pymupdf(pdf_path: Path) -> list[PageText]:
    import fitz  # type: ignore

    pages: list[PageText] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            text = normalize_text(page.get_text("text", sort=True))
            pages.append(PageText(page_no=index, text=text, char_count=len(text)))
    return pages


def extract_pages_pypdf(pdf_path: Path) -> list[PageText]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(pdf_path))
    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        pages.append(PageText(page_no=index, text=text, char_count=len(text)))
    return pages


def extract_pages(pdf_path: Path) -> tuple[list[PageText], str]:
    try:
        return extract_pages_pymupdf(pdf_path), "pymupdf"
    except ModuleNotFoundError:
        return extract_pages_pypdf(pdf_path), "pypdf"


def edge_lines(text: str, limit: int = 3) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:limit] + lines[-limit:]


def detect_repeated_edge_lines(pages: list[PageText]) -> set[str]:
    counter: Counter[str] = Counter()
    for page in pages:
        for line in edge_lines(page.text):
            compact = re.sub(r"\s+", " ", line).strip()
            if 3 <= len(compact) <= 120 and not compact.isdigit():
                counter[compact] += 1

    if not pages:
        return set()
    threshold = max(3, int(len(pages) * 0.20))
    return {line for line, count in counter.items() if count >= threshold}


def clean_page_text(text: str, repeated_lines: set[str]) -> str:
    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            cleaned.append("")
            continue
        if line in repeated_lines:
            continue
        if re.fullmatch(r"[-_]*\s*\d+\s*[-_]*", line):
            continue
        cleaned.append(line)
    return normalize_text("\n".join(cleaned))


def paragraphs_from_pages(pages: list[PageText], repeated_lines: set[str]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for page in pages:
        text = clean_page_text(page.text, repeated_lines)
        parts = re.split(r"\n\s*\n|(?<=[.!?銆傦紒锛焆)\n", text)
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
    for para in reversed(paragraphs):
        tail.insert(0, para)
        total += estimate_tokens(para.text)
        if total >= overlap_tokens:
            break
    return tail


def chunk_paragraphs(
    paragraphs: list[Paragraph],
    *,
    doc_id: str,
    title: str,
    source_path: Path,
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
        text = "\n\n".join(para.text for para in current).strip()
        page_start = min(para.page_no for para in current)
        page_end = max(para.page_no for para in current)
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
                "token_estimate": estimate_tokens(text),
                "char_count": len(text),
                "citation_anchor": f"{title}, pp. {page_start}-{page_end}",
                "text": text,
                "api_context": (
                    f"[chunk_id={chunk_id}; doc_id={doc_id}; pages={page_start}-{page_end}]\n{text}"
                ),
            }
        )
        current = overlap_tail(current, overlap_tokens)
        current_tokens = sum(estimate_tokens(para.text) for para in current)

    for para in paragraphs:
        para_tokens = estimate_tokens(para.text)
        if current and current_tokens + para_tokens > target_tokens:
            flush()
        current.append(para)
        current_tokens += para_tokens

        if para_tokens >= target_tokens:
            flush()

    flush()
    return chunks


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")



def write_api_context_json(path: Path, *, doc_id: str, title: str, chunks: list[dict]) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "type": "api_context_pack",
        "doc_id": doc_id,
        "title": title,
        "usage_note": (
            "Use chunk_id and pages when citing. Do not answer beyond the supplied chunks."
        ),
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def build_manifest(
    *,
    pdf_path: Path,
    output_dir: Path,
    doc_id: str,
    title: str,
    source_type: str,
    extractor: str,
    pages: list[PageText],
    chunks: list[dict],
    warnings: list[str],
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_pdf": str(pdf_path),
        "output_dir": str(output_dir),
        "doc_id": doc_id,
        "title": title,
        "source_type": source_type,
        "extractor": extractor,
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "total_chars": sum(page.char_count for page in pages),
        "total_token_estimate": sum(chunk["token_estimate"] for chunk in chunks),
        "empty_or_low_text_pages": [
            page.page_no for page in pages if page.char_count < 40
        ],
        "files": {
            "chunks_jsonl": str(output_dir / "chunks.jsonl"),
            "api_context_json": str(output_dir / "api_context.json"),
            "manifest_json": str(output_dir / "manifest.json"),
        },
        "warnings": warnings,
    }


def convert_pdf(
    *,
    pdf_path: Path,
    output_dir: Path,
    doc_id: str | None,
    title: str | None,
    source_type: str,
    target_tokens: int,
    overlap_tokens: int,
    min_total_chars: int,
) -> dict:
    pdf_path = pdf_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved_doc_id = doc_id or stable_doc_id(pdf_path)
    resolved_title = title or pdf_path.stem

    pages, extractor = extract_pages(pdf_path)
    warnings: list[str] = []
    total_chars = sum(page.char_count for page in pages)
    if total_chars < min_total_chars:
        warnings.append(
            "Very little text was extracted. The PDF may be scanned without an OCR text layer."
        )

    repeated_lines = detect_repeated_edge_lines(pages)
    paragraphs = paragraphs_from_pages(pages, repeated_lines)
    chunks = chunk_paragraphs(
        paragraphs,
        doc_id=resolved_doc_id,
        title=resolved_title,
        source_path=pdf_path,
        source_type=source_type,
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
    )

    write_jsonl(output_dir / "chunks.jsonl", chunks)
    write_api_context_json(
        output_dir / "api_context.json",
        doc_id=resolved_doc_id,
        title=resolved_title,
        chunks=chunks,
    )
    manifest = build_manifest(
        pdf_path=pdf_path,
        output_dir=output_dir,
        doc_id=resolved_doc_id,
        title=resolved_title,
        source_type=source_type,
        extractor=extractor,
        pages=pages,
        chunks=chunks,
        warnings=warnings,
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert an OCR-text PDF into AI-agent memory chunks."
    )
    parser.add_argument("pdf", type=Path, help="Input PDF with OCR text layer")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/exports/memory"),
        help="Output directory",
    )
    parser.add_argument("--doc-id", default=None, help="Stable document id")
    parser.add_argument("--title", default=None, help="Document title")
    parser.add_argument("--source-type", default="book", help="book|standard|paper|manual|note")
    parser.add_argument("--target-tokens", type=int, default=800)
    parser.add_argument("--overlap-tokens", type=int, default=80)
    parser.add_argument("--min-total-chars", type=int, default=500)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = convert_pdf(
            pdf_path=args.pdf,
            output_dir=args.out_dir,
            doc_id=args.doc_id,
            title=args.title,
            source_type=args.source_type,
            target_tokens=args.target_tokens,
            overlap_tokens=args.overlap_tokens,
            min_total_chars=args.min_total_chars,
        )
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


