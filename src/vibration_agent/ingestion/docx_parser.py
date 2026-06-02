"""DOCX parser producing the common page-level schema."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from vibration_agent.ingestion.layout import classify_text_block, make_asset_id
from vibration_agent.ingestion.pymupdf_parser import normalize_text
from vibration_agent.schemas import DocumentAsset, OcrPage, PageBlock


class DocxParseError(RuntimeError):
    """Raised when a DOCX cannot be parsed into usable page content."""


def _load_document(path: str | Path):
    try:
        from docx import Document  # type: ignore
    except ModuleNotFoundError as exc:
        raise DocxParseError("python-docx is required for DOCX parsing.") from exc

    try:
        return Document(str(Path(path).resolve()))
    except Exception as exc:
        raise DocxParseError(f"DOCX could not be opened: {exc}") from exc


def _style_name(paragraph) -> str:
    style = getattr(paragraph, "style", None)
    return str(getattr(style, "name", "") or "").lower()


def _paragraph_kind(text: str, paragraph, *, block_index: int) -> str:
    style = _style_name(paragraph)
    if style.startswith("heading") or style in {"title", "subtitle"}:
        return "title"
    return classify_text_block(text, block_index=block_index)


def _iter_table_texts(document) -> Iterable[str]:
    for table in document.tables:
        rows: list[str] = []
        for row in table.rows:
            cells = [normalize_text(cell.text) for cell in row.cells if normalize_text(cell.text)]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            yield "\n".join(rows)


def _text_parts_from_document(document) -> list[str]:
    parts: list[str] = []
    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if text:
            parts.append(text)
    parts.extend(_iter_table_texts(document))
    return parts


def _image_extension(content_type: str) -> str:
    subtype = content_type.rsplit("/", 1)[-1].lower()
    return {
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "png": ".png",
        "gif": ".gif",
        "bmp": ".bmp",
        "tiff": ".tiff",
        "webp": ".webp",
    }.get(subtype, ".bin")


def _extract_images(document, *, doc_id: str, asset_dir: Path | None) -> list[DocumentAsset]:
    assets: list[DocumentAsset] = []
    for rel in document.part.rels.values():
        target_part = getattr(rel, "target_part", None)
        content_type = str(getattr(target_part, "content_type", ""))
        if not content_type.startswith("image/"):
            continue
        asset_id = make_asset_id(doc_id, 1, len(assets) + 1, "figure")
        asset_path = f"docx://{doc_id}/image/{asset_id}"
        if asset_dir is not None:
            output_path = asset_dir / f"{asset_id}{_image_extension(content_type)}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(target_part.blob)
            asset_path = str(output_path)
        assets.append(
            DocumentAsset(
                asset_id=asset_id,
                doc_id=doc_id,
                page_no=1,
                object_type="figure",
                asset_path=asset_path,
                text="",
                confidence=1.0,
                metadata={"source": "docx_image_relationship", "content_type": content_type},
            )
        )
    return assets


def extract_docx_text(path: str | Path) -> str:
    """Return DOCX paragraph/table text for classification."""
    document = _load_document(path)
    return normalize_text("\n".join(_text_parts_from_document(document)))


def inspect_docx(path: str | Path) -> tuple[str, int]:
    """Return text and logical page count for DOCX classification."""
    document = _load_document(path)
    text = normalize_text("\n".join(_text_parts_from_document(document)))
    if text:
        return text, 1
    return "", 1 if document.part.rels else 0


def parse_docx(
    docx_path: str | Path,
    *,
    doc_id: str,
    asset_dir: str | Path | None = None,
    extract_image_assets: bool = True,
) -> list[OcrPage]:
    """Parse a DOCX into a single logical page compatible with PDF OCR output."""
    document = _load_document(docx_path)
    resolved_asset_dir = Path(asset_dir).resolve() if asset_dir is not None else None
    blocks: list[PageBlock] = []
    body_parts: list[str] = []

    for paragraph in document.paragraphs:
        text = normalize_text(paragraph.text)
        if not text:
            continue
        block_index = len(blocks) + 1
        block_type = _paragraph_kind(text, paragraph, block_index=block_index)
        blocks.append(
            PageBlock(
                block_id=f"p0001_b{block_index:04d}",
                text=text,
                block_type=block_type,
                confidence=1.0,
                metadata={"source": "docx_paragraph", "style": getattr(paragraph.style, "name", None)},
            )
        )
        if block_type in {"body", "title"}:
            body_parts.append(text)

    table_index = 0
    for table_text in _iter_table_texts(document):
        table_index += 1
        block_index = len(blocks) + 1
        asset_id = make_asset_id(doc_id, 1, table_index, "table")
        asset_path = f"docx://{doc_id}/table/{asset_id}"
        blocks.append(
            PageBlock(
                block_id=f"p0001_b{block_index:04d}",
                text=table_text,
                block_type="table",
                confidence=1.0,
                asset_id=asset_id,
                asset_path=asset_path,
                metadata={"source": "docx_table"},
            )
        )
        body_parts.append(table_text)

    assets: list[DocumentAsset] = []
    for block in blocks:
        if block.block_type == "table" and block.asset_id:
            assets.append(
                DocumentAsset(
                    asset_id=block.asset_id,
                    doc_id=doc_id,
                    page_no=1,
                    object_type="table",
                    asset_path=block.asset_path,
                    text=block.text,
                    confidence=1.0,
                    metadata={"block_id": block.block_id, "source": "docx_table"},
                )
            )

    if extract_image_assets:
        assets.extend(_extract_images(document, doc_id=doc_id, asset_dir=resolved_asset_dir))

    normalized_text = normalize_text("\n".join(body_parts))
    if not normalized_text and not assets:
        raise DocxParseError("DOCX contains no extractable text, tables, or images.")

    return [
        OcrPage(
            doc_id=doc_id,
            page_no=1,
            primary_engine="python-docx",
            fallback_used=False,
            ocr_confidence=1.0 if normalized_text or assets else None,
            layout_quality="ok" if normalized_text else "low",
            raw_text=normalize_text("\n".join(block.text for block in blocks)),
            normalized_text=normalized_text,
            blocks=blocks,
            assets=assets,
            needs_review=not bool(normalized_text),
        )
    ]


def docx_page_count(path: str | Path) -> int:
    return inspect_docx(path)[1]
