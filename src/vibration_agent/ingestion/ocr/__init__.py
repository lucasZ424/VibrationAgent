"""OCR router. Phase-0: PaddleOCR primary, Tesseract as explicit fallback."""
from .router import ocr_page

__all__ = ["ocr_page"]
