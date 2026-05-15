"""Document input classification for ingestion.

Target 4 scope: discover supported input files, assign stable doc_id, count pages,
and decide whether a PDF should use native parsing or OCR. This module does not
run OCR or chunking.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

SupportedKind = Literal["pdf", "image", "text", "unsupported"]
ProcessingStrategy = Literal["native_pdf", "ocr_pdf", "image", "text", "unknown"]

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}
SUPPORTED_PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = SUPPORTED_PDF_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES | SUPPORTED_TEXT_SUFFIXES


@dataclass(frozen=True)
class PdfTextProfile:
    page_count: int
    sampled_pages: int
    total_chars: int
    avg_chars_per_page: float
    text_density: float
    needs_ocr: bool


@dataclass(frozen=True)
class DocumentClassification:
    doc_id: str
    source_path: str
    filename: str
    suffix: str
    kind: SupportedKind
    mime_type: str | None
    file_size: int
    sha256: str
    page_count: int | None
    processing_strategy: ProcessingStrategy
    text_density: float | None = None
    text_chars: int | None = None
    image_size: tuple[int, int] | None = None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "source_path": self.source_path,
            "filename": self.filename,
            "suffix": self.suffix,
            "kind": self.kind,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "processing_strategy": self.processing_strategy,
            "text_density": self.text_density,
            "text_chars": self.text_chars,
            "image_size": list(self.image_size) if self.image_size else None,
            "warnings": list(self.warnings),
        }


def slugify_filename(path: Path, max_length: int = 80) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_").lower()
    if not stem:
        stem = "document"
    return stem[:max_length].strip("_") or "document"


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_doc_id(path: Path) -> str:
    resolved = path.resolve()
    return f"{slugify_filename(resolved)}_{file_sha256(resolved)[:8]}"


def detect_kind(path: Path) -> SupportedKind:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_PDF_SUFFIXES:
        return "pdf"
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return "text"
    return "unsupported"


def profile_pdf_text(
    pdf_path: Path,
    *,
    density_threshold: float = 0.2,
    min_chars_per_page: int = 40,
    max_sample_pages: int = 8,
) -> PdfTextProfile:
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required for PDF classification.") from exc

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        sampled_pages = min(page_count, max_sample_pages)
        total_chars = 0
        total_area = 0.0
        for index in range(sampled_pages):
            page = doc.load_page(index)
            text = page.get_text("text") or ""
            normalized = re.sub(r"\s+", "", text)
            total_chars += len(normalized)
            rect = page.rect
            total_area += max(float(rect.width * rect.height), 1.0)

    avg_chars = total_chars / sampled_pages if sampled_pages else 0.0
    density = (total_chars / total_area) * 1000.0 if total_area else 0.0
    sparse_text = avg_chars < min_chars_per_page
    sparse_density = density < density_threshold and avg_chars < (min_chars_per_page * 2)
    needs = sampled_pages == 0 or sparse_text or sparse_density
    return PdfTextProfile(
        page_count=page_count,
        sampled_pages=sampled_pages,
        total_chars=total_chars,
        avg_chars_per_page=avg_chars,
        text_density=density,
        needs_ocr=needs,
    )


def needs_ocr(pdf_path: Path, *, density_threshold: float = 0.2) -> bool:
    """Return True when the PDF text layer is absent or too sparse."""
    return profile_pdf_text(pdf_path, density_threshold=density_threshold).needs_ocr


def _image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return None

    try:
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return None


def classify_document(path: str | Path, *, pdf_density_threshold: float = 0.2) -> DocumentClassification:
    source = Path(path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if not source.is_file():
        raise ValueError(f"Expected a file, got directory: {source}")

    kind = detect_kind(source)
    suffix = source.suffix.lower()
    mime_type = mimetypes.guess_type(source.name)[0]
    sha = file_sha256(source)
    warnings: list[str] = []
    page_count: int | None = None
    strategy: ProcessingStrategy = "unknown"
    text_density: float | None = None
    text_chars: int | None = None
    image_size: tuple[int, int] | None = None

    if kind == "pdf":
        profile = profile_pdf_text(source, density_threshold=pdf_density_threshold)
        page_count = profile.page_count
        text_density = profile.text_density
        text_chars = profile.total_chars
        strategy = "ocr_pdf" if profile.needs_ocr else "native_pdf"
        if profile.needs_ocr:
            warnings.append("PDF text layer is missing or sparse; OCR is required.")
    elif kind == "image":
        page_count = 1
        strategy = "image"
        image_size = _image_size(source)
        if image_size is None:
            warnings.append("Image dimensions could not be read; Pillow may be unavailable or the file may be invalid.")
    elif kind == "text":
        page_count = 1
        strategy = "text"
        try:
            text_chars = len(source.read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            warnings.append(f"Text file could not be read: {exc}")
    else:
        warnings.append("Unsupported file type; no ingestion strategy selected.")

    return DocumentClassification(
        doc_id=f"{slugify_filename(source)}_{sha[:8]}",
        source_path=str(source),
        filename=source.name,
        suffix=suffix,
        kind=kind,
        mime_type=mime_type,
        file_size=source.stat().st_size,
        sha256=sha,
        page_count=page_count,
        processing_strategy=strategy,
        text_density=text_density,
        text_chars=text_chars,
        image_size=image_size,
        warnings=tuple(warnings),
    )


def iter_supported_files(path: str | Path, *, recursive: bool = True) -> Iterable[Path]:
    root = Path(path).resolve()
    if root.is_file():
        if detect_kind(root) != "unsupported":
            yield root
        return
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise ValueError(f"Expected file or directory: {root}")

    iterator = root.rglob("*") if recursive else root.glob("*")
    files = [item for item in iterator if item.is_file() and detect_kind(item) != "unsupported"]
    for item in sorted(files, key=lambda p: str(p).lower()):
        yield item


def scan_inputs(
    path: str | Path,
    *,
    recursive: bool = True,
    pdf_density_threshold: float = 0.2,
) -> list[DocumentClassification]:
    return [
        classify_document(item, pdf_density_threshold=pdf_density_threshold)
        for item in iter_supported_files(path, recursive=recursive)
    ]