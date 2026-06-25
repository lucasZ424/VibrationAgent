"""OCR router for scanned PDF pages.

PaddleOCR is the primary lane. Tesseract is used only when Paddle output is empty,
low-confidence, or explicitly requested for key evidence pages.
"""
from __future__ import annotations

from pathlib import Path

from vibration_agent.schemas import OcrPage

from . import paddle_engine, tesseract_engine


def _should_fallback(page: OcrPage, *, threshold: float, key_evidence_page: bool = False) -> bool:
    if key_evidence_page:
        return True
    if not page.normalized_text.strip():
        return True
    if page.ocr_confidence is None:
        return True
    return page.ocr_confidence < threshold


def _merge_fallback(primary: OcrPage, fallback: OcrPage) -> OcrPage:
    """Prefer the more informative fallback text; revisit merging after evaluation data."""
    if fallback.normalized_text and len(fallback.normalized_text) > len(primary.normalized_text):
        return fallback.model_copy(update={"fallback_used": True})
    return primary.model_copy(update={"fallback_used": True, "needs_review": True})


def ocr_page(
    pdf_path: str | Path,
    page_no: int,
    *,
    doc_id: str,
    lang: str = "ch",
    tesseract_langs: str = "chi_sim+eng+osd",
    dpi: int = 220,
    low_confidence_threshold: float = 0.6,
    key_evidence_page: bool = False,
    workspace: str | Path | None = None,
    image_dir: str | Path | None = None,
    keep_images: bool = False,
    ocr_version: str = "PP-OCRv4",
    det_model_name: str | None = "PP-OCRv4_mobile_det",
    rec_model_name: str | None = "PP-OCRv4_mobile_rec",
    rec_score_threshold: float = 0.0,
    use_textline_orientation: bool = False,
) -> OcrPage:
    try:
        primary = paddle_engine.run(
            pdf_path,
            page_no,
            doc_id=doc_id,
            lang=lang,
            dpi=dpi,
            workspace=workspace,
            image_dir=image_dir,
            keep_image=keep_images,
            review_threshold=low_confidence_threshold,
            ocr_version=ocr_version,
            det_model_name=det_model_name,
            rec_model_name=rec_model_name,
            rec_score_threshold=rec_score_threshold,
            use_textline_orientation=use_textline_orientation,
        )
    except Exception as exc:
        primary = OcrPage(
            doc_id=doc_id,
            page_no=page_no,
            primary_engine="paddleocr",
            fallback_used=False,
            ocr_confidence=None,
            layout_quality="empty",
            raw_text=f"paddleocr failed: {exc}",
            normalized_text="",
            blocks=[],
            needs_review=True,
        )

    if not _should_fallback(primary, threshold=low_confidence_threshold, key_evidence_page=key_evidence_page):
        return primary

    try:
        fallback = tesseract_engine.run(
            pdf_path,
            page_no,
            doc_id=doc_id,
            langs=tesseract_langs,
            dpi=dpi,
            image_dir=image_dir,
            keep_image=keep_images,
        )
    except Exception:
        return primary.model_copy(update={"fallback_used": True, "needs_review": True})
    return _merge_fallback(primary, fallback)


def ocr_image(
    image_path: str | Path,
    *,
    doc_id: str,
    page_no: int,
    lang: str = "ch",
    tesseract_langs: str = "chi_sim+eng+osd",
    low_confidence_threshold: float = 0.6,
    workspace: str | Path | None = None,
) -> OcrPage:
    try:
        primary = paddle_engine.run_image(
            image_path,
            doc_id=doc_id,
            page_no=page_no,
            lang=lang,
            workspace=workspace,
            review_threshold=low_confidence_threshold,
        )
    except Exception as exc:
        primary = OcrPage(
            doc_id=doc_id,
            page_no=page_no,
            primary_engine="paddleocr",
            raw_text=f"paddleocr failed: {exc}",
            needs_review=True,
        )
    if not _should_fallback(primary, threshold=low_confidence_threshold):
        return primary
    try:
        fallback = tesseract_engine.run_image(
            image_path,
            doc_id=doc_id,
            page_no=page_no,
            langs=tesseract_langs,
        )
    except Exception:
        return primary.model_copy(update={"fallback_used": True, "needs_review": True})
    return _merge_fallback(primary, fallback)
