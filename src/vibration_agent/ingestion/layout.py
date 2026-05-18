"""Lightweight page layout object recognition.

Target 6 is a deterministic layout layer, not a full vision layout model. It
classifies text blocks into body/title/formula/figure/table signals and creates
page-level asset references for non-body objects so later chunking/storage can
cite them without forcing them into the main body text.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from vibration_agent.schemas import AssetType, DocumentAsset, OcrPage, PageBlock

NON_BODY_ASSET_TYPES: set[AssetType] = {"formula", "figure", "table", "page_image"}

_FIGURE_CAPTION_RE = re.compile(r"^\s*(图|圖|Fig\.?|Figure)\s*[\dIVXivx一二三四五六七八九十]+[\-\.．、:：]?")
_TABLE_CAPTION_RE = re.compile(r"^\s*(表|Table)\s*[\dIVXivx一二三四五六七八九十]+[\-\.．、:：]?")
_TITLE_RE = re.compile(r"^\s*(第\s*[\d一二三四五六七八九十]+\s*[章节篇]|Chapter\s+\d+|[\d一二三四五六七八九十]+[\.、]\s*\S+)", re.IGNORECASE)
_FORMULA_TOKENS_RE = re.compile(r"(=|≈|≠|≤|≥|\+|\-|\*|/|\^|ω|Ω|ζ|π|\b(?:sin|cos|tan|sqrt|log|exp)\b)")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def normalize_bbox(bbox: object) -> list[float] | list[list[float]] | None:
    if bbox is None:
        return None
    if isinstance(bbox, (list, tuple)):
        if all(isinstance(item, (int, float)) for item in bbox):
            return [float(item) for item in bbox]
        if all(isinstance(item, (list, tuple)) for item in bbox):
            return [[float(value) for value in item] for item in bbox]  # type: ignore[arg-type]
    return None


def logical_asset_path(doc_id: str, page_no: int, block_id: str) -> str:
    return f"page://{doc_id}/p{page_no:04d}/{block_id}"


def make_asset_id(doc_id: str, page_no: int, index: int, object_type: AssetType) -> str:
    safe_type = re.sub(r"[^A-Za-z0-9_]+", "_", object_type).strip("_") or "asset"
    return f"{doc_id}_p{page_no:04d}_{safe_type}_{index:04d}"


def _token_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _looks_like_formula(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 3:
        return False
    if _FIGURE_CAPTION_RE.match(text) or _TABLE_CAPTION_RE.match(text):
        return False
    formula_chars = len(_FORMULA_TOKENS_RE.findall(text))
    letters = len(re.findall(r"[A-Za-zα-ωΑ-Ω]", text))
    digits = len(re.findall(r"\d", text))
    words = _token_count(text)
    return formula_chars >= 2 and (letters + digits) >= 2 and words <= 18


def classify_text_block(
    text: str,
    *,
    block_index: int = 1,
    block_count: int | None = None,
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

    words = _token_count(stripped)
    top_ratio = None
    normalized_bbox = normalize_bbox(bbox)
    if page_height and isinstance(normalized_bbox, list) and normalized_bbox and isinstance(normalized_bbox[0], float):
        top_ratio = float(normalized_bbox[1]) / max(page_height, 1.0)  # type: ignore[index]

    early_block = block_index == 1 and (top_ratio is None or top_ratio <= 0.35)
    if _TITLE_RE.match(stripped) or (early_block and words <= 16 and len(stripped) <= 80):
        return "title"
    return "body"


def asset_from_block(
    *,
    page: OcrPage,
    block: PageBlock,
    object_type: AssetType,
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
        metadata={"block_id": block.block_id, **(metadata or {})},
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
                block_count=len(page.blocks),
                bbox=block.bbox,
            )

        asset_id = block.asset_id
        asset_path = block.asset_path
        if block_type in NON_BODY_ASSET_TYPES:
            asset_index = len(assets) + 1
            asset_id = asset_id or make_asset_id(page.doc_id, page.page_no, asset_index, block_type)
            asset_path = asset_path or logical_asset_path(page.doc_id, page.page_no, block.block_id)
            if asset_id not in known_asset_ids:
                assets.append(
                    asset_from_block(
                        page=page,
                        block=block.model_copy(update={"asset_id": asset_id, "asset_path": asset_path, "block_type": block_type}),
                        object_type=block_type,
                        asset_index=asset_index,
                        asset_path=asset_path,
                    )
                )
                known_asset_ids.add(asset_id)

        blocks.append(block.model_copy(update={"block_type": block_type, "asset_id": asset_id, "asset_path": asset_path}))

    body_text = "\n".join(block.text for block in blocks if block.block_type in {"body", "title"} and block.text.strip())
    return page.model_copy(update={"blocks": blocks, "assets": assets, "normalized_text": body_text.strip() or page.normalized_text})


def enrich_pages_layout(pages: Iterable[OcrPage]) -> list[OcrPage]:
    return [enrich_page_layout(page) for page in pages]

