"""PaddleOCR primary lane for scanned PDF pages."""
from __future__ import annotations

import os
import re
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from vibration_agent.ingestion.render import render_pdf_page
from vibration_agent.schemas import OcrPage, PageBlock

MOJIBAKE_MARKERS = (
    "\u9365",
    "\u95c4",
    "\u93c3",
    "\u93c8",
    "\u7efe",
    "\u9428",
    "\u6d93",
    "\u6d63",
    "\u59af",
    "\u675e",
    "\u59ca",
    "\u7487",
    "\u951f",
)

_cached_ocr: Any | None = None
_cached_key: tuple[Any, ...] | None = None


def configure_paddle_cache(workspace: str | Path | None = None) -> None:
    """Keep Paddle/PaddleX caches under data/cache; caller-supplied env wins."""
    if workspace is None:
        return
    root = Path(workspace).resolve()
    data_dir = root / "data"
    cache_dir = data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("USERPROFILE", str(data_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("PADDLE_HOME", str(cache_dir / "paddle"))
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir / "paddlex"))
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")


def normalize_ocr_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def repair_mojibake(text: str) -> str:
    if not text or not any(marker in text for marker in MOJIBAKE_MARKERS):
        return text
    try:
        repaired = text.encode("gb18030", errors="ignore").decode("utf-8", errors="replace")
    except UnicodeError:
        return text
    bad_before = sum(text.count(marker) for marker in MOJIBAKE_MARKERS) + text.count("\ufffd")
    bad_after = sum(repaired.count(marker) for marker in MOJIBAKE_MARKERS) + repaired.count("\ufffd")
    return repaired if bad_after < bad_before else text


def _to_plain_json(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): _to_plain_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_json(v) for v in value]
    return value


def make_ocr(
    *,
    lang: str = "ch",
    ocr_version: str = "PP-OCRv4",
    det_model_name: str | None = "PP-OCRv4_mobile_det",
    rec_model_name: str | None = "PP-OCRv4_mobile_rec",
    rec_score_threshold: float = 0.0,
    use_textline_orientation: bool = False,
) -> Any:
    global _cached_key, _cached_ocr

    key = (lang, ocr_version, det_model_name, rec_model_name, rec_score_threshold, use_textline_orientation)
    if _cached_ocr is not None and _cached_key == key:
        return _cached_ocr

    from paddleocr import PaddleOCR  # type: ignore

    kwargs: dict[str, Any] = {
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": use_textline_orientation,
        "text_rec_score_thresh": rec_score_threshold,
    }
    if det_model_name or rec_model_name:
        kwargs["text_detection_model_name"] = det_model_name
        kwargs["text_recognition_model_name"] = rec_model_name
    else:
        kwargs["lang"] = lang
        kwargs["ocr_version"] = ocr_version

    _cached_ocr = PaddleOCR(**kwargs)
    _cached_key = key
    return _cached_ocr


def result_to_page(doc_id: str, page_no: int, result: Any, *, review_threshold: float = 0.6) -> OcrPage:
    data = dict(result)
    raw_texts = [str(item) for item in data.get("rec_texts", []) if str(item).strip()]
    rec_texts = [repair_mojibake(text) for text in raw_texts]
    scores = [float(score) for score in data.get("rec_scores", [])]
    boxes = _to_plain_json(data.get("rec_boxes", data.get("rec_polys", [])))

    blocks: list[PageBlock] = []
    for index, text in enumerate(rec_texts):
        score = scores[index] if index < len(scores) else None
        bbox = boxes[index] if index < len(boxes) else None
        blocks.append(
            PageBlock(
                block_id=f"p{page_no:04d}_b{index + 1:04d}",
                text=text,
                bbox=bbox,
                block_type="text",
                confidence=score,
            )
        )

    raw_text = "\n".join(raw_texts)
    normalized_text = normalize_ocr_text("\n".join(rec_texts))
    avg_conf = sum(scores) / len(scores) if scores else None
    needs_review = avg_conf is None or avg_conf < review_threshold or len(normalized_text) < 20
    layout_quality = "empty" if not normalized_text else ("low" if needs_review else "ok")
    return OcrPage(
        doc_id=doc_id,
        page_no=page_no,
        primary_engine="paddleocr",
        fallback_used=False,
        ocr_confidence=avg_conf,
        layout_quality=layout_quality,
        raw_text=raw_text,
        normalized_text=normalized_text,
        blocks=blocks,
        needs_review=needs_review,
    )


def run(
    pdf_path: str | Path,
    page_no: int,
    *,
    doc_id: str,
    lang: str = "ch",
    dpi: int = 220,
    workspace: str | Path | None = None,
    image_dir: str | Path | None = None,
    keep_image: bool = False,
    review_threshold: float = 0.6,
    ocr_version: str = "PP-OCRv4",
    det_model_name: str | None = "PP-OCRv4_mobile_det",
    rec_model_name: str | None = "PP-OCRv4_mobile_rec",
    rec_score_threshold: float = 0.0,
    use_textline_orientation: bool = False,
) -> OcrPage:
    configure_paddle_cache(workspace)
    temp_dir = nullcontext(None) if image_dir else tempfile.TemporaryDirectory()
    with temp_dir as tmpdir:
        if image_dir:
            Path(image_dir).mkdir(parents=True, exist_ok=True)
            image_path = Path(image_dir) / f"page_{page_no:04d}.png"
        else:
            image_path = Path(tmpdir) / f"page_{page_no:04d}.png"
        render_pdf_page(pdf_path, page_no, image_path, dpi=dpi)
        ocr = make_ocr(
            lang=lang,
            ocr_version=ocr_version,
            det_model_name=det_model_name,
            rec_model_name=rec_model_name,
            rec_score_threshold=rec_score_threshold,
            use_textline_orientation=use_textline_orientation,
        )
        results = ocr.predict(str(image_path))
        if image_dir is None or not keep_image:
            Path(image_path).unlink(missing_ok=True)
        if not results:
            return OcrPage(
                doc_id=doc_id,
                page_no=page_no,
                primary_engine="paddleocr",
                fallback_used=False,
                ocr_confidence=None,
                layout_quality="empty",
                raw_text="",
                normalized_text="",
                blocks=[],
                needs_review=True,
            )
        return result_to_page(doc_id, page_no, results[0], review_threshold=review_threshold)


def run_image(
    image_path: str | Path,
    *,
    doc_id: str,
    page_no: int,
    lang: str = "ch",
    workspace: str | Path | None = None,
    review_threshold: float = 0.6,
    ocr_version: str = "PP-OCRv4",
    det_model_name: str | None = "PP-OCRv4_mobile_det",
    rec_model_name: str | None = "PP-OCRv4_mobile_rec",
    rec_score_threshold: float = 0.0,
    use_textline_orientation: bool = False,
) -> OcrPage:
    configure_paddle_cache(workspace)
    ocr = make_ocr(
        lang=lang,
        ocr_version=ocr_version,
        det_model_name=det_model_name,
        rec_model_name=rec_model_name,
        rec_score_threshold=rec_score_threshold,
        use_textline_orientation=use_textline_orientation,
    )
    results = ocr.predict(str(Path(image_path).resolve()))
    if not results:
        return OcrPage(
            doc_id=doc_id,
            page_no=page_no,
            primary_engine="paddleocr",
            ocr_confidence=None,
            layout_quality="empty",
            needs_review=True,
        )
    return result_to_page(doc_id, page_no, results[0], review_threshold=review_threshold)
