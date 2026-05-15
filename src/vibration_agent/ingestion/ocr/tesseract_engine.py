"""Tesseract fallback lane for scanned PDF pages."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from vibration_agent.schemas import OcrPage, PageBlock

from vibration_agent.ingestion.render import render_pdf_page


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _empty_page(doc_id: str, page_no: int, warning: str) -> OcrPage:
    return OcrPage(
        doc_id=doc_id,
        page_no=page_no,
        primary_engine="tesseract",
        fallback_used=True,
        ocr_confidence=None,
        layout_quality="empty",
        raw_text=warning,
        normalized_text="",
        blocks=[],
        needs_review=True,
    )


def run(
    pdf_path: str | Path,
    page_no: int,
    *,
    doc_id: str,
    langs: str = "chi_sim+eng+osd",
    dpi: int = 220,
    image_dir: str | Path | None = None,
    keep_image: bool = False,
) -> OcrPage:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ModuleNotFoundError as exc:
        return _empty_page(doc_id, page_no, f"tesseract dependency missing: {exc}")

    with tempfile.TemporaryDirectory() as tmpdir:
        if image_dir:
            image_path = Path(image_dir) / f"page_{page_no:04d}.tesseract.png"
        else:
            image_path = Path(tmpdir) / f"page_{page_no:04d}.png"
        render_pdf_page(pdf_path, page_no, image_path, dpi=dpi)
        try:
            with Image.open(image_path) as image:
                raw_text = pytesseract.image_to_string(image, lang=langs)
        except Exception as exc:
            return _empty_page(doc_id, page_no, f"tesseract failed: {exc}")
        finally:
            if image_dir is None or not keep_image:
                Path(image_path).unlink(missing_ok=True)

    normalized = normalize_text(raw_text)
    block = PageBlock(
        block_id=f"p{page_no:04d}_b0001",
        text=normalized,
        bbox=None,
        block_type="text",
        confidence=None,
    ) if normalized else None
    return OcrPage(
        doc_id=doc_id,
        page_no=page_no,
        primary_engine="tesseract",
        fallback_used=True,
        ocr_confidence=None,
        layout_quality="ok" if normalized else "empty",
        raw_text=raw_text,
        normalized_text=normalized,
        blocks=[block] if block else [],
        needs_review=not bool(normalized),
    )