"""Native-text PDF parser using PyMuPDF."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable

from vibration_agent.ingestion.layout import (
    classify_text_block,
    logical_asset_path,
    make_asset_id,
    normalize_bbox,
    promote_font_titles,
)
from vibration_agent.ingestion.page_visual_analysis import (
    PageVisualAnalysis,
    VisualRecoverySettings,
    analyze_page,
    edge_signature,
    normalized_bbox,
    repeated_edge_signatures,
)
from vibration_agent.ingestion.ocr.router import ocr_image, ocr_page
from vibration_agent.schemas import DocumentAsset, OcrPage, PageBlock

MIN_IMAGE_BLOCK_DIMENSION = 4.0
PageOcrRunner = Callable[..., OcrPage]
ImageOcrRunner = Callable[..., OcrPage]


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


def _image_bbox_skip_reason(bbox: object) -> str | None:
    if not isinstance(bbox, list) or len(bbox) != 4:
        return "invalid_bbox"
    if not all(isinstance(value, float) and math.isfinite(value) for value in bbox):
        return "invalid_bbox"
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0:
        return "invalid_bbox"
    if width < MIN_IMAGE_BLOCK_DIMENSION or height < MIN_IMAGE_BLOCK_DIMENSION:
        return "tiny_bbox"
    return None


def _analysis_inputs(
    page_dict: dict[str, Any],
) -> tuple[list[tuple[tuple[float, float, float, float], str]], list[tuple[float, float, float, float]]]:
    text_blocks = []
    image_boxes = []
    for block in page_dict.get("blocks", []):
        bbox = normalized_bbox(block.get("bbox"))
        if bbox is None:
            continue
        if int(block.get("type", 0) or 0) == 1:
            image_boxes.append(bbox)
            continue
        text = _block_text(block)
        if text:
            text_blocks.append((bbox, normalize_text(text)))
    return text_blocks, image_boxes


def _visual_signatures(
    analysis: PageVisualAnalysis,
    *,
    page_width: float,
    page_height: float,
    image_boxes: list[tuple[float, float, float, float]],
    settings: VisualRecoverySettings,
) -> list[str]:
    signatures = []
    for box in image_boxes:
        width = box[2] - box[0]
        height = box[3] - box[1]
        if width < settings.direct_image_min_dimension or height < settings.direct_image_min_dimension:
            continue
        signature = edge_signature(
            box,
            page_width=page_width,
            page_height=page_height,
            origin="direct",
        )
        if signature:
            signatures.append(signature)
    for cluster in analysis.clusters:
        signature = edge_signature(
            cluster.bbox,
            page_width=page_width,
            page_height=page_height,
            origin="cluster",
        )
        if signature:
            signatures.append(signature)
    return signatures


def _cluster_asset(
    *,
    page: Any,
    doc_id: str,
    page_no: int,
    index: int,
    cluster: Any,
    asset_dir: Path | None,
    image_dpi: int,
) -> tuple[DocumentAsset, PageBlock]:
    block_id = f"p{page_no:04d}_cluster_{index:04d}"
    asset_id = make_asset_id(doc_id, page_no, index, "figure")
    output_path = _image_asset_path(asset_dir, asset_id)
    asset_path = logical_asset_path(doc_id, page_no, block_id)
    metadata = {"source": "pymupdf_fragment_cluster", **cluster.to_dict()}
    if output_path is not None:
        asset_path = str(_save_block_clip(page, list(cluster.bbox), output_path, dpi=image_dpi))
    asset = DocumentAsset(
        asset_id=asset_id,
        doc_id=doc_id,
        page_no=page_no,
        object_type="figure",
        asset_path=asset_path,
        bbox=list(cluster.bbox),
        confidence=1.0,
        metadata=metadata,
    )
    block = PageBlock(
        block_id=block_id,
        text="",
        bbox=list(cluster.bbox),
        block_type="figure",
        confidence=1.0,
        asset_id=asset_id,
        asset_path=asset_path,
        metadata=metadata,
    )
    return asset, block


def parse_native_pdf(
    pdf_path: str | Path,
    *,
    doc_id: str,
    asset_dir: str | Path | None = None,
    extract_image_assets: bool = True,
    image_dpi: int = 220,
    visual_settings: VisualRecoverySettings | None = None,
    page_ocr_enabled: bool = False,
    region_ocr_enabled: bool = False,
    workspace: str | Path | None = None,
    ocr_lang: str = "ch",
    tesseract_langs: str = "chi_sim+eng+osd",
    low_confidence_threshold: float = 0.6,
    page_ocr_runner: PageOcrRunner = ocr_page,
    image_ocr_runner: ImageOcrRunner = ocr_image,
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
    visual_cfg = visual_settings or VisualRecoverySettings()
    pages: list[OcrPage] = []
    with fitz.open(source) as doc:
        analyses: list[PageVisualAnalysis] = []
        image_boxes_by_page: list[list[tuple[float, float, float, float]]] = []
        signatures_by_page: list[list[str]] = []
        for page in doc:
            page_dict = page.get_text("dict", sort=True)
            text_blocks, image_boxes = _analysis_inputs(page_dict)
            analysis = analyze_page(
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
                text_blocks=text_blocks,
                image_boxes=image_boxes,
                settings=visual_cfg,
            )
            analyses.append(analysis)
            image_boxes_by_page.append(image_boxes)
            signatures_by_page.append(
                _visual_signatures(
                    analysis,
                    page_width=float(page.rect.width),
                    page_height=float(page.rect.height),
                    image_boxes=image_boxes,
                    settings=visual_cfg,
                )
            )
        repeated_signatures = repeated_edge_signatures(signatures_by_page)

        for page_index, page in enumerate(doc, start=1):
            page_dict = page.get_text("dict", sort=True)
            source_blocks = list(page_dict.get("blocks", []))
            analysis = analyses[page_index - 1]
            if analysis.suspected_scanned_page and page_ocr_enabled:
                image_dir = resolved_asset_dir / "scanned_pages" if resolved_asset_dir else None
                recovered = page_ocr_runner(
                    source,
                    page_index,
                    doc_id=doc_id,
                    lang=ocr_lang,
                    tesseract_langs=tesseract_langs,
                    dpi=image_dpi,
                    low_confidence_threshold=low_confidence_threshold,
                    workspace=workspace,
                    image_dir=image_dir,
                    keep_images=bool(image_dir),
                )
                metadata = dict(recovered.metadata)
                metadata.update(
                    {
                        "visual_analysis": analysis.to_dict(),
                        "visual_route": "scanned_page_ocr",
                        "cluster_recovery_skipped": True,
                    }
                )
                if image_dir:
                    image_path = image_dir / f"page_{page_index:04d}.png"
                    if image_path.exists():
                        asset_id = make_asset_id(doc_id, page_index, 1, "page_image")
                        page_asset = DocumentAsset(
                            asset_id=asset_id,
                            doc_id=doc_id,
                            page_no=page_index,
                            object_type="page_image",
                            asset_path=str(image_path),
                            bbox=[0.0, 0.0, float(page.rect.width), float(page.rect.height)],
                            text=recovered.normalized_text,
                            confidence=recovered.ocr_confidence,
                            metadata={"source": "scanned_page_recovery"},
                        )
                        recovered = recovered.model_copy(update={"assets": [page_asset]})
                pages.append(recovered.model_copy(update={"metadata": metadata}))
                continue

            blocks: list[PageBlock] = []
            assets: list[DocumentAsset] = []
            raw_parts: list[str] = []
            body_parts: list[str] = []
            asset_export_warnings: list[dict[str, str]] = []
            skipped_image_blocks = {"invalid_bbox": 0, "tiny_bbox": 0, "page_limit": 0}
            image_asset_count = 0
            level2_repeated_cover = 0

            for block_index, block in enumerate(source_blocks, start=1):
                block_id = f"p{page_index:04d}_b{block_index:04d}"
                bbox = normalize_bbox(block.get("bbox"))
                block_kind = int(block.get("type", 0) or 0)

                if block_kind == 1:
                    bbox_skip_reason = _image_bbox_skip_reason(bbox)
                    if bbox_skip_reason is not None:
                        skipped_image_blocks[bbox_skip_reason] += 1
                        continue
                    direct_signature = edge_signature(
                        tuple(bbox),  # type: ignore[arg-type]
                        page_width=float(page.rect.width),
                        page_height=float(page.rect.height),
                        origin="direct",
                    )
                    if direct_signature in repeated_signatures:
                        if page_index == 1:
                            level2_repeated_cover += 1
                        else:
                            skipped_image_blocks["repeated_decoration"] = (
                                skipped_image_blocks.get("repeated_decoration", 0) + 1
                            )
                        continue
                    if image_asset_count >= visual_cfg.direct_asset_limit:
                        skipped_image_blocks["page_limit"] += 1
                        continue
                    image_asset_count += 1
                    asset_id = make_asset_id(doc_id, page_index, len(assets) + 1, "figure")
                    output_path = _image_asset_path(resolved_asset_dir, asset_id)
                    asset_path = logical_asset_path(doc_id, page_index, block_id)
                    asset_metadata = {"block_id": block_id, "source": "pymupdf_image_block"}
                    if extract_image_assets and output_path is not None:
                        try:
                            asset_path = str(_save_block_clip(page, bbox, output_path, dpi=image_dpi))  # type: ignore[arg-type]
                        except Exception as exc:
                            reason = f"{type(exc).__name__}: {exc}"
                            asset_metadata["image_export_skipped"] = reason
                            asset_export_warnings.append({"block_id": block_id, "reason": reason})
                    asset = DocumentAsset(
                        asset_id=asset_id,
                        doc_id=doc_id,
                        page_no=page_index,
                        object_type="figure",
                        asset_path=asset_path,
                        bbox=bbox,
                        text="",
                        confidence=1.0,
                        metadata=asset_metadata,
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
                            metadata=asset_metadata,
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

            clustered_source_blocks = 0
            cluster_assets: list[DocumentAsset] = []
            for cluster_index, cluster in enumerate(analysis.clusters, start=1):
                cluster_signature = edge_signature(
                    cluster.bbox,
                    page_width=float(page.rect.width),
                    page_height=float(page.rect.height),
                    origin="cluster",
                )
                if cluster_signature in repeated_signatures:
                    continue
                try:
                    asset, block = _cluster_asset(
                        page=page,
                        doc_id=doc_id,
                        page_no=page_index,
                        index=len(assets) + 1,
                        cluster=cluster,
                        asset_dir=resolved_asset_dir,
                        image_dpi=image_dpi,
                    )
                except Exception as exc:
                    asset_export_warnings.append(
                        {"block_id": f"cluster_{cluster_index}", "reason": f"{type(exc).__name__}: {exc}"}
                    )
                    continue
                cluster_assets.append(asset)
                assets.append(asset)
                blocks.append(block)
                clustered_source_blocks += cluster.source_block_count

            if region_ocr_enabled and visual_cfg.region_ocr_limit > 0:
                ocr_candidates = sorted(
                    [
                        asset
                        for asset in assets
                        if asset.asset_path and Path(asset.asset_path).exists()
                        and asset.metadata.get("source") in {"pymupdf_image_block", "pymupdf_fragment_cluster"}
                    ],
                    key=lambda item: -(
                        (item.bbox[2] - item.bbox[0]) * (item.bbox[3] - item.bbox[1])  # type: ignore[index]
                    ),
                )
                selected_ids = {asset.asset_id for asset in ocr_candidates[: visual_cfg.region_ocr_limit]}
                updated_assets = []
                for asset in assets:
                    if asset.asset_id not in selected_ids:
                        if asset.metadata.get("source") in {"pymupdf_image_block", "pymupdf_fragment_cluster"}:
                            updated_assets.append(
                                asset.model_copy(update={"metadata": {**asset.metadata, "ocr_status": "not_selected"}})
                            )
                        else:
                            updated_assets.append(asset)
                        continue
                    result = image_ocr_runner(
                        asset.asset_path,
                        doc_id=doc_id,
                        page_no=page_index,
                        lang=ocr_lang,
                        tesseract_langs=tesseract_langs,
                        low_confidence_threshold=low_confidence_threshold,
                        workspace=workspace,
                    )
                    status = "ok" if result.normalized_text else ("failed" if result.raw_text else "empty")
                    updated_assets.append(
                        asset.model_copy(
                            update={
                                "text": result.normalized_text,
                                "confidence": result.ocr_confidence,
                                "metadata": {
                                    **asset.metadata,
                                    "ocr_status": status,
                                    "ocr_engine": result.primary_engine,
                                    "fallback_used": result.fallback_used,
                                },
                            }
                        )
                    )
                assets = updated_assets
                assets_by_id = {asset.asset_id: asset for asset in assets}
                blocks = [
                    block.model_copy(
                        update={
                            "text": assets_by_id[block.asset_id].text,
                            "metadata": assets_by_id[block.asset_id].metadata,
                        }
                    )
                    if block.asset_id in assets_by_id
                    else block
                    for block in blocks
                ]

            blocks = promote_font_titles(blocks)
            raw_text = "\n".join(raw_parts)
            normalized_text = normalize_text("\n".join(body_parts))
            page_metadata: dict[str, Any] = {}
            nonzero_skipped = {reason: count for reason, count in skipped_image_blocks.items() if count}
            if nonzero_skipped:
                page_metadata["skipped_image_blocks"] = nonzero_skipped
            if asset_export_warnings:
                page_metadata["asset_export_warnings"] = asset_export_warnings
            page_metadata["visual_analysis"] = analysis.to_dict()
            page_metadata["visual_route"] = "native_mixed"
            page_metadata["clustered_tiny_block_count"] = clustered_source_blocks
            deferred_tiny = max(0, analysis.tiny_image_block_count - clustered_source_blocks)
            if deferred_tiny:
                page_metadata["level2_deferred_tiny_blocks"] = deferred_tiny
            if level2_repeated_cover:
                page_metadata["level2_repeated_cover_candidates"] = level2_repeated_cover
            if analysis.overflow_cluster_count:
                page_metadata["cluster_overflow_count"] = analysis.overflow_cluster_count
            pages.append(
                OcrPage(
                    doc_id=doc_id,
                    page_no=page_index,
                    primary_engine="pymupdf",
                    fallback_used=False,
                    ocr_confidence=1.0 if normalized_text or assets else None,
                    layout_quality="ok" if normalized_text else ("low" if assets else "empty"),
                    raw_text=raw_text,
                    normalized_text=normalized_text,
                    blocks=blocks,
                    assets=assets,
                    needs_review=not bool(normalized_text),
                    metadata=page_metadata,
                )
            )
    return pages


def parse(pdf_path: Path, doc_id: str | None = None) -> list[dict]:
    """Backward-compatible parser returning dictionaries."""
    resolved_doc_id = doc_id or Path(pdf_path).stem
    return [page.model_dump(mode="json") for page in parse_native_pdf(pdf_path, doc_id=resolved_doc_id)]



