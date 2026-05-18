"""Lightweight page layout object recognition.

Target 6 is a deterministic layout layer, not a full vision layout model. It
classifies text blocks into body/title/formula/figure/table signals and creates
page-level asset references for non-body objects so later chunking/storage can
cite them without forcing them into the main body text.
"""
from __future__ import annotations

import re
from typing import Iterable

from vibration_agent.schemas import AssetObjectType, AssetType, DocumentAsset, OcrPage, PageBlock

NON_BODY_ASSET_TYPES: set[AssetObjectType] = {"formula", "figure", "table", "page_image"}

_FIGURE_CAPTION_RE = re.compile(r"^\s*(图|圖|Fig\.?|Figure)\s*(?:[\dIVXivx一二三四五六七八九十]+|\([a-zA-Z]\))?\s*[\-\.．、:：]?", re.IGNORECASE)
_TABLE_CAPTION_RE = re.compile(r"^\s*(表|Table)\s*(?:[\dIVXivx一二三四五六七八九十]+|\([a-zA-Z]\))?\s*[\-\.．、:：]?", re.IGNORECASE)
_CHAPTER_TITLE_RE = re.compile(r"^\s*(第\s*[\d一二三四五六七八九十]+\s*[章节篇]|Chapter\s+\d+)\b", re.IGNORECASE)
_SECTION_TITLE_RE = re.compile(r"^\s*(?:\d+(?:\.\d+){0,3}|[一二三四五六七八九十]+)[\.、]\s*\S+")
_STRONG_FORMULA_RE = re.compile(r"(=|≈|≠|≤|≥)")
_SPACED_MATH_OPERATOR_RE = re.compile(r"[A-Za-z0-9α-ωΑ-Ω)]\s*(?:\+|\*|/|\^|−)\s*[A-Za-z0-9α-ωΑ-Ω(]")
_MATH_WORD_RE = re.compile(r"\b(?:sin|cos|tan|sqrt|log|exp)\b|[ωΩζπ]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_REFERENCE_LIKE_RE = re.compile(r"^\s*\d+\.\s+.+(?:\bet\s+al\b|\b19\d{2}\b|\b20\d{2}\b|,)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")


def normalize_bbox(bbox: object) -> list[float] | list[list[float]] | None:
    if bbox is None:
        return None
    if isinstance(bbox, (list, tuple)):
        if all(isinstance(item, (int, float)) for item in bbox):
            return [float(item) for item in bbox]
        if all(isinstance(item, (list, tuple)) for item in bbox):
            return [[float(value) for value in item] for item in bbox]  # type: ignore[arg-type]
    return None


def bbox_top_ratio(bbox: object, page_height: float | None) -> float | None:
    if not page_height:
        return None
    normalized = normalize_bbox(bbox)
    if not normalized:
        return None
    if isinstance(normalized[0], float):
        return float(normalized[1]) / max(page_height, 1.0)  # type: ignore[index]
    y_values = [float(point[1]) for point in normalized if len(point) >= 2]  # type: ignore[union-attr]
    return min(y_values) / max(page_height, 1.0) if y_values else None


def logical_asset_path(doc_id: str, page_no: int, block_id: str) -> str:
    return f"page://{doc_id}/p{page_no:04d}/{block_id}"


def make_asset_id(doc_id: str, page_no: int, index: int, object_type: AssetObjectType) -> str:
    safe_type = re.sub(r"[^A-Za-z0-9_]+", "_", object_type).strip("_") or "asset"
    return f"{doc_id}_p{page_no:04d}_{safe_type}_{index:04d}"


def _token_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _looks_like_formula(text: str) -> bool:
    stripped = re.sub(r"\s+", " ", text).strip()
    compact = re.sub(r"\s+", "", stripped)
    if len(compact) < 3:
        return False
    if _FIGURE_CAPTION_RE.match(stripped) or _TABLE_CAPTION_RE.match(stripped):
        return False
    words = _token_count(stripped)
    letters_or_digits = len(re.findall(r"[A-Za-z0-9α-ωΑ-Ω]", stripped))
    if words > 20 or letters_or_digits < 2:
        return False
    if _STRONG_FORMULA_RE.search(stripped):
        return True
    if _MATH_WORD_RE.search(stripped) and _SPACED_MATH_OPERATOR_RE.search(stripped):
        return True
    return False


def _title_position_ok(*, block_index: int, bbox: object, page_height: float | None, min_top_ratio: float = 0.0) -> bool:
    top_ratio = bbox_top_ratio(bbox, page_height)
    if block_index > 3:
        return False
    if top_ratio is None:
        return True
    return min_top_ratio <= top_ratio <= 0.45


def _looks_like_title(text: str, *, block_index: int, bbox: object, page_height: float | None) -> bool:
    stripped = re.sub(r"\s+", " ", text).strip()
    if _PAGE_NUMBER_RE.match(stripped) or _REFERENCE_LIKE_RE.match(stripped):
        return False
    if _CHAPTER_TITLE_RE.match(stripped):
        return _title_position_ok(block_index=block_index, bbox=bbox, page_height=page_height, min_top_ratio=0.06) and _token_count(stripped) <= 24
    if not _SECTION_TITLE_RE.match(stripped):
        return False
    return _title_position_ok(block_index=block_index, bbox=bbox, page_height=page_height) and _token_count(stripped) <= 24


def classify_text_block(
    text: str,
    *,
    block_index: int = 1,
    bbox: object = None,
    page_height: float | None = None,
) -> AssetType:
    """Classify a text-bearing block into the Target-6 object vocabulary."""
    stripped = re.sub(r"\s+", " ", text).strip()
    if not stripped:
        return "unknown"
    if _TABLE_CAPTION_RE.match(stripped):
        return "table"
    if _FIGURE_CAPTION_RE.match(stripped):
        return "figure"
    if _looks_like_formula(stripped):
        return "formula"
    if _looks_like_title(stripped, block_index=block_index, bbox=bbox, page_height=page_height):
        return "title"
    return "body"


def asset_from_block(
    *,
    page: OcrPage,
    block: PageBlock,
    object_type: AssetObjectType,
    asset_index: int,
    asset_path: str | None = None,
    metadata: dict | None = None,
) -> DocumentAsset:
    asset_id = block.asset_id or make_asset_id(page.doc_id, page.page_no, asset_index, object_type)
    resolved_asset_path = asset_path or block.asset_path or logical_asset_path(page.doc_id, page.page_no, block.block_id)
    return DocumentAsset(
        asset_id=asset_id,
        doc_id=page.doc_id,
        page_no=page.page_no,
        object_type=object_type,
        asset_path=resolved_asset_path,
        bbox=block.bbox,
        text=block.text,
        confidence=block.confidence,
        metadata={"block_id": block.block_id, "source": "layout_text_block", **(metadata or {})},
    )


def enrich_page_layout(page: OcrPage) -> OcrPage:
    """Return a page with block types and non-body asset references populated."""
    blocks: list[PageBlock] = []
    assets: list[DocumentAsset] = list(page.assets)
    known_asset_ids = {asset.asset_id for asset in assets}

    for index, block in enumerate(page.blocks, start=1):
        block_type = block.block_type
        if block_type in {"text", "unknown"}:
            block_type = classify_text_block(
                block.text,
                block_index=index,
                bbox=block.bbox,
            )

        asset_id = block.asset_id
        asset_path = block.asset_path
        if block_type in NON_BODY_ASSET_TYPES:
            asset_index = len(assets) + 1
            asset_type = block_type  # narrowed by membership check
            asset_id = asset_id or make_asset_id(page.doc_id, page.page_no, asset_index, asset_type)  # type: ignore[arg-type]
            asset_path = asset_path or logical_asset_path(page.doc_id, page.page_no, block.block_id)
            if asset_id not in known_asset_ids:
                enriched_block = block.validated_copy(asset_id=asset_id, asset_path=asset_path, block_type=block_type)
                assets.append(
                    asset_from_block(
                        page=page,
                        block=enriched_block,
                        object_type=asset_type,  # type: ignore[arg-type]
                        asset_index=asset_index,
                        asset_path=asset_path,
                    )
                )
                known_asset_ids.add(asset_id)

        blocks.append(block.validated_copy(block_type=block_type, asset_id=asset_id, asset_path=asset_path))

    body_text = "\n".join(block.text for block in blocks if block.block_type in {"body", "title"} and block.text.strip())
    normalized_text = body_text.strip() if blocks else page.normalized_text
    return page.model_copy(update={"blocks": blocks, "assets": assets, "normalized_text": normalized_text})


def enrich_pages_layout(pages: Iterable[OcrPage]) -> list[OcrPage]:
    return [enrich_page_layout(page) for page in pages]



