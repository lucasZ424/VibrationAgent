"""Native-text PDF parser using PyMuPDF."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vibration_agent.schemas import OcrPage, PageBlock


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _block_text(block: dict[str, Any]) -> str:
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(str(span.get("text", "")) for span in spans).strip()
        if line_text:
            lines.append(line_text)
    return "\n".join(lines).strip()


def parse_native_pdf(pdf_path: str | Path, *, doc_id: str) -> list[OcrPage]:
    """Parse a PDF text layer into the common page-level schema."""
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required for native PDF parsing.") from exc

    source = Path(pdf_path).resolve()
    pages: list[OcrPage] = []
    with fitz.open(source) as doc:
        for page_index, page in enumerate(doc, start=1):
            page_dict = page.get_text("dict", sort=True)
            blocks: list[PageBlock] = []
            raw_parts: list[str] = []
            for block_index, block in enumerate(page_dict.get("blocks", []), start=1):
                text = _block_text(block)
                if not text:
                    continue
                raw_parts.append(text)
                blocks.append(
                    PageBlock(
                        block_id=f"p{page_index:04d}_b{block_index:04d}",
                        text=normalize_text(text),
                        bbox=list(block.get("bbox", [])) or None,
                        block_type="text",
                        confidence=1.0,
                    )
                )

            raw_text = "\n".join(raw_parts)
            normalized_text = normalize_text(raw_text)
            pages.append(
                OcrPage(
                    doc_id=doc_id,
                    page_no=page_index,
                    primary_engine="pymupdf",
                    fallback_used=False,
                    ocr_confidence=1.0 if normalized_text else None,
                    layout_quality="ok" if normalized_text else "empty",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    blocks=blocks,
                    needs_review=not bool(normalized_text),
                )
            )
    return pages


def parse(pdf_path: Path, doc_id: str | None = None) -> list[dict]:
    """Backward-compatible parser returning dictionaries."""
    resolved_doc_id = doc_id or Path(pdf_path).stem
    return [page.model_dump(mode="json") for page in parse_native_pdf(pdf_path, doc_id=resolved_doc_id)]