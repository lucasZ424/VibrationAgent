"""Document input classification for ingestion.

Target 4 scope: discover supported input files, assign stable doc_id, count pages,
and decide whether a PDF should use native parsing or OCR. This module does not
run OCR or chunking.

Office lock files such as ``~$name.docx`` are skipped so transient editor files
do not enter ingestion.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from vibration_agent.schemas import DocumentClassification, DocumentLanguage, ProcessingStrategy, SupportedKind

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}
SUPPORTED_PDF_SUFFIXES = {".pdf"}
SUPPORTED_DOCX_SUFFIXES = {".docx"}
SUPPORTED_SUFFIXES = SUPPORTED_PDF_SUFFIXES | SUPPORTED_DOCX_SUFFIXES | SUPPORTED_IMAGE_SUFFIXES | SUPPORTED_TEXT_SUFFIXES


@dataclass(frozen=True)
class PdfTextProfile:
    page_count: int
    sampled_pages: int
    sampled_page_numbers: tuple[int, ...]
    total_chars: int
    avg_chars_per_page: float
    text_density: float
    sampled_text: str
    needs_ocr: bool


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
    if suffix in SUPPORTED_DOCX_SUFFIXES:
        return "docx"
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        return "text"
    return "unsupported"


def detect_language(text: str) -> DocumentLanguage:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return "unknown"
    cjk = sum(1 for ch in compact if "\u4e00" <= ch <= "\u9fff")
    latin = len(re.findall(r"[A-Za-z]", compact))
    total = max(cjk + latin, 1)
    cjk_ratio = cjk / total
    latin_ratio = latin / total
    if cjk_ratio >= 0.25 and latin_ratio >= 0.25:
        return "mixed"
    if cjk_ratio >= 0.30:
        return "zh"
    if latin_ratio >= 0.60:
        return "en"
    return "unknown"


def sample_page_indices(page_count: int, max_sample_pages: int = 8) -> list[int]:
    """Return deterministic spread samples: front, middle, and tail pages.

    Indices are zero-based. Sampling only the first pages biases classification
    against books with scanned covers/front matter and native-text bodies.
    """
    if page_count <= 0 or max_sample_pages <= 0:
        return []
    if page_count <= max_sample_pages:
        return list(range(page_count))

    candidates = {0, 1, page_count - 2, page_count - 1}
    mid = page_count // 2
    candidates.update({max(0, mid - 1), mid})

    step = max(page_count // max_sample_pages, 1)
    cursor = 0
    while len(candidates) < max_sample_pages and cursor < page_count:
        candidates.add(cursor)
        cursor += step
    return sorted(index for index in candidates if 0 <= index < page_count)[:max_sample_pages]


def profile_pdf_text(
    pdf_path: Path,
    *,
    density_threshold: float = 0.2,
    min_chars_per_page: int = 40,
    max_sample_pages: int = 8,
) -> PdfTextProfile:
    """Profile a PDF text layer using spread page samples.

    ``text_density`` is normalized as chars per 1000 PDF points squared, matching
    `configs/ingestion.yaml`.
    """
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required for PDF classification.") from exc

    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        indices = sample_page_indices(page_count, max_sample_pages=max_sample_pages)
        total_chars = 0
        total_area = 0.0
        sampled_text_parts: list[str] = []
        for index in indices:
            page = doc.load_page(index)
            text = page.get_text("text") or ""
            normalized = re.sub(r"\s+", "", text)
            sampled_text_parts.append(text)
            total_chars += len(normalized)
            rect = page.rect
            total_area += max(float(rect.width * rect.height), 1.0)

    sampled_pages = len(indices)
    avg_chars = total_chars / sampled_pages if sampled_pages else 0.0
    density = (total_chars / total_area) * 1000.0 if total_area else 0.0
    sparse_text = avg_chars < min_chars_per_page
    sparse_density = density < density_threshold and avg_chars < (min_chars_per_page * 2)
    needs = sampled_pages == 0 or sparse_text or sparse_density
    return PdfTextProfile(
        page_count=page_count,
        sampled_pages=sampled_pages,
        sampled_page_numbers=tuple(index + 1 for index in indices),
        total_chars=total_chars,
        avg_chars_per_page=avg_chars,
        text_density=density,
        sampled_text="\n".join(sampled_text_parts),
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
    language: DocumentLanguage = "unknown"
    text_density: float | None = None
    text_chars: int | None = None
    image_size: tuple[int, int] | None = None

    if kind == "pdf":
        profile = profile_pdf_text(source, density_threshold=pdf_density_threshold)
        page_count = profile.page_count
        text_density = profile.text_density
        text_chars = profile.total_chars
        language = detect_language(profile.sampled_text)
        strategy = "ocr_pdf" if profile.needs_ocr else "native_pdf"
        if profile.needs_ocr:
            warnings.append("PDF text layer is missing or sparse; OCR is required.")
    elif kind == "image":
        page_count = 1
        strategy = "image"
        image_size = _image_size(source)
        if image_size is None:
            warnings.append("Image dimensions could not be read; Pillow may be unavailable or the file may be invalid.")
    elif kind == "docx":
        strategy = "docx"
        try:
            from vibration_agent.ingestion.docx_parser import DocxParseError, inspect_docx

            text, page_count = inspect_docx(source)
            text_chars = len(text)
            language = detect_language(text)
            if not text:
                warnings.append("DOCX contains no extractable text; page parsing may be insufficient.")
        except DocxParseError as exc:
            page_count = 0
            text_chars = 0
            warnings.append(f"DOCX could not be inspected: {exc}")
    elif kind == "text":
        page_count = 1
        strategy = "text"
        try:
            text = source.read_text(encoding="utf-8", errors="ignore")
            text_chars = len(text)
            language = detect_language(text)
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
        language=language,
        text_density=text_density,
        text_chars=text_chars,
        image_size=image_size,
        warnings=warnings,
    )


def iter_supported_files(path: str | Path, *, recursive: bool = True) -> Iterable[Path]:
    root = Path(path).resolve()
    if root.is_file():
        if not root.name.startswith("~$") and detect_kind(root) != "unsupported":
            yield root
        return
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise ValueError(f"Expected file or directory: {root}")

    iterator = root.rglob("*") if recursive else root.glob("*")
    files = [
        item
        for item in iterator
        if item.is_file() and not item.name.startswith("~$") and detect_kind(item) != "unsupported"
    ]
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
