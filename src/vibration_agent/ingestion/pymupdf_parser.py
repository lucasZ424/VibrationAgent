"""Native-text PDF parser using PyMuPDF."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vibration_agent.ingestion.layout import classify_text_block, logical_asset_path, make_asset_id, normalize_bbox
from vibration_agent.schemas import DocumentAsset, OcrPage, PageBlock


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _block_text(block: dict[str, Any]) -> str:
    """Extract text spans from a PyMuPDF block.

    Image-only blocks are handled separately as figure assets in Target 6. They
    are not coerced into empty text blocks.
    """
    lines: list[str] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(str(span.get("text", "")) for span in spans).strip()
        if line_text:
            lines.append(line_text)
    return "\n".join(lines).strip()


def _max_font_size(block: dict[str, Any]) -> float | None:
    sizes: list[float] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            try:
                sizes.append(float(span.get("size")))
            except (TypeError, ValueError):
                continue
    return max(sizes) if sizes else None


def _save_block_clip(page: Any, bbox: list[float], output_path: Path, *, dpi: int = 220) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    import fitz  # type: ignore

    rect = fitz.Rect(bbox)
    pixmap = page.get_pixmap(clip=rect, dpi=dpi, alpha=False)
    pixmap.save(output_path)
    return output_path


def _image_asset_path(asset_dir: Path | None, asset_id: str) -> Path | None:
    if asset_dir is None:
        return None
    return asset_dir / f"{asset_id}.png"


def parse_native_pdf(
    pdf_path: str | Path,
    *,
    doc_id: str,
    asset_dir: str | Path | None = None,
    extract_image_assets: bool = True,
) -> list[OcrPage]:
    """Parse a PDF text layer into the common page-level schema.

    Text blocks are classified as body/title/formula/figure/table. PyMuPDF image
    blocks become page-level figure assets with bbox and asset_path; when
    ``asset_dir`` is supplied, the image region is rendered to disk.
    """
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyMuPDF is required for native PDF parsing.") from exc

    source = Path(pdf_path).resolve()
    resolved_asset_dir = Path(asset_dir).resolve() if asset_dir is not None else None
    pages: list[OcrPage] = []
    with fitz.open(source) as doc:
        for page_index, page in enumerate(doc, start=1):
            page_dict = page.get_text("dict", sort=True)
            source_blocks = list(page_dict.get("blocks", []))
            blocks: list[PageBlock] = []
            assets: list[DocumentAsset] = []
            raw_parts: list[str] = []
            body_parts: list[str] = []

            for block_index, block in enumerate(source_blocks, start=1):
                block_id = f"p{page_index:04d}_b{block_index:04d}"
                bbox = normalize_bbox(block.get("bbox"))
                block_kind = int(block.get("type", 0) or 0)

                if block_kind == 1:
                    asset_id = make_asset_id(doc_id, page_index, len(assets) + 1, "figure")
                    output_path = _image_asset_path(resolved_asset_dir, asset_id)
                    asset_path = logical_asset_path(doc_id, page_index, block_id)
                    if extract_image_assets and output_path is not None and isinstance(bbox, list) and bbox and isinstance(bbox[0], float):
                        asset_path = str(_save_block_clip(page, bbox, output_path))  # type: ignore[arg-type]
                    asset = DocumentAsset(
                        asset_id=asset_id,
                        doc_id=doc_id,
                        page_no=page_index,
                        object_type="figure",
                        asset_path=asset_path,
                        bbox=bbox,
                        text="",
                        confidence=1.0,
                        metadata={"block_id": block_id, "source": "pymupdf_image_block"},
                    )
                    assets.append(asset)
                    blocks.append(
                        PageBlock(
                            block_id=block_id,
                            text="",
                            bbox=bbox,
                            block_type="figure",
                            confidence=1.0,
                            asset_id=asset_id,
                            asset_path=asset_path,
                            metadata={"source": "pymupdf_image_block"},
                        )
                    )
                    continue

                text = _block_text(block)
                if not text:
                    continue
                normalized = normalize_text(text)
                object_type = classify_text_block(
                    normalized,
                    block_index=block_index,
                    block_count=len(source_blocks),
                    bbox=bbox,
                    page_height=float(page.rect.height),
                )
                metadata: dict[str, Any] = {"source": "pymupdf_text_block"}
                if max_size := _max_font_size(block):
                    metadata["max_font_size"] = max_size

                asset_id = None
                asset_path = None
                if object_type in {"formula", "figure", "table"}:
                    asset_id = make_asset_id(doc_id, page_index, len(assets) + 1, object_type)
                    asset_path = logical_asset_path(doc_id, page_index, block_id)
                    assets.append(
                        DocumentAsset(
                            asset_id=asset_id,
                            doc_id=doc_id,
                            page_no=page_index,
                            object_type=object_type,
                            asset_path=asset_path,
                            bbox=bbox,
                            text=normalized,
                            confidence=1.0,
                            metadata={"block_id": block_id, "source": "pymupdf_text_block"},
                        )
                    )
                else:
                    body_parts.append(normalized)

                raw_parts.append(text)
                blocks.append(
                    PageBlock(
                        block_id=block_id,
                        text=normalized,
                        bbox=bbox,
                        block_type=object_type,
                        confidence=1.0,
                        asset_id=asset_id,
                        asset_path=asset_path,
                        metadata=metadata,
                    )
                )

            raw_text = "\n".join(raw_parts)
            normalized_text = normalize_text("\n".join(body_parts))
            pages.append(
                OcrPage(
                    doc_id=doc_id,
                    page_no=page_index,
                    primary_engine="pymupdf",
                    fallback_used=False,
                    ocr_confidence=1.0 if normalized_text or assets else None,
                    layout_quality="ok" if normalized_text or assets else "empty",
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    blocks=blocks,
                    assets=assets,
                    needs_review=not bool(normalized_text or assets),
                )
            )
    return pages


def parse(pdf_path: Path, doc_id: str | None = None) -> list[dict]:
    """Backward-compatible parser returning dictionaries."""
    resolved_doc_id = doc_id or Path(pdf_path).stem
    return [page.model_dump(mode="json") for page in parse_native_pdf(pdf_path, doc_id=resolved_doc_id)]
