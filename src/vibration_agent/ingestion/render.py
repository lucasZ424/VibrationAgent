"""PDF page rendering helpers shared by ingestion parsers and OCR engines."""
from __future__ import annotations

from pathlib import Path


def render_pdf_page(pdf_path: str | Path, page_no: int, image_path: str | Path, *, dpi: int = 220) -> Path:
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required to render PDF pages for OCR.") from exc

    source = Path(pdf_path).resolve()
    target = Path(image_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as doc:
        page = doc.load_page(page_no - 1)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        pix.save(target)
    return target