"""Deterministic page-level visual analysis for native PDFs."""
from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class VisualRecoverySettings:
    direct_image_min_dimension: float = 4.0
    grid_cell_size: float = 4.0
    grid_dilation_cells: int = 1
    min_cluster_blocks: int = 20
    min_cluster_dimension: float = 40.0
    min_cluster_area_ratio: float = 0.01
    scanned_text_ceiling: int = 15
    scanned_meaningful_block_ceiling: int = 8
    scanned_largest_region_ratio: float = 0.50
    scanned_occupancy_ratio: float = 0.65
    retained_cluster_limit: int = 16
    hard_cluster_limit: int = 24
    region_ocr_limit: int = 4
    direct_asset_limit: int = 100


@dataclass(frozen=True)
class VisualCluster:
    bbox: BBox
    source_block_count: int
    occupied_cells: int
    density: float
    area_ratio: float
    body_overlap_ratio: float
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": list(self.bbox),
            "source_block_count": self.source_block_count,
            "occupied_cells": self.occupied_cells,
            "density": self.density,
            "area_ratio": self.area_ratio,
            "body_overlap_ratio": self.body_overlap_ratio,
            "score": self.score,
        }


@dataclass(frozen=True)
class PageVisualAnalysis:
    native_text_chars: int
    image_block_count: int
    tiny_image_block_count: int
    valid_image_block_count: int
    tiny_image_block_ratio: float
    image_union_coverage_ratio: float
    body_region: BBox
    clusters: tuple[VisualCluster, ...]
    overflow_cluster_count: int
    suspected_scanned_page: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_text_chars": self.native_text_chars,
            "image_block_count": self.image_block_count,
            "tiny_image_block_count": self.tiny_image_block_count,
            "valid_image_block_count": self.valid_image_block_count,
            "tiny_image_block_ratio": self.tiny_image_block_ratio,
            "image_union_coverage_ratio": self.image_union_coverage_ratio,
            "body_region": list(self.body_region),
            "cluster_count": len(self.clusters),
            "overflow_cluster_count": self.overflow_cluster_count,
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "suspected_scanned_page": self.suspected_scanned_page,
            "suspected_fragmented_figure": bool(self.clusters),
        }


def normalized_bbox(value: object) -> BBox | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        box = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in box):
        return None
    x0, y0, x1, y1 = box
    return box if x1 > x0 and y1 > y0 else None


def _area(box: BBox) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersection_area(left: BBox, right: BBox) -> float:
    return max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1])
    )


def meaningful_text_length(text: str) -> int:
    return sum(1 for char in text if char.isprintable() and not char.isspace())


def is_page_backing_image(
    box: BBox,
    *,
    page_width: float,
    page_height: float,
    min_area_ratio: float = 0.80,
    edge_tolerance_ratio: float = 0.05,
) -> bool:
    """Identify a scan/background raster that carries most of the PDF page."""
    page_area = max(page_width * page_height, 1.0)
    if _area(box) / page_area < min_area_ratio:
        return False
    x_tolerance = page_width * edge_tolerance_ratio
    y_tolerance = page_height * edge_tolerance_ratio
    edge_hits = sum(
        (
            box[0] <= x_tolerance,
            box[1] <= y_tolerance,
            box[2] >= page_width - x_tolerance,
            box[3] >= page_height - y_tolerance,
        )
    )
    return edge_hits >= 2


def derive_body_region(
    *,
    page_width: float,
    page_height: float,
    text_blocks: Sequence[tuple[BBox, str]],
) -> BBox:
    safe = (page_width * 0.05, page_height * 0.08, page_width * 0.95, page_height * 0.92)
    usable = [
        (bbox, text)
        for bbox, text in text_blocks
        if text.strip() and not (bbox[3] <= page_height * 0.08 or bbox[1] >= page_height * 0.92)
    ]
    if len(usable) < 3 or sum(len(text.strip()) for _, text in usable) < 100:
        return safe
    x0 = max(safe[0], min(bbox[0] for bbox, _ in usable) - 24.0)
    y0 = max(safe[1], min(bbox[1] for bbox, _ in usable) - 24.0)
    x1 = min(safe[2], max(bbox[2] for bbox, _ in usable) + 24.0)
    y1 = min(safe[3], max(bbox[3] for bbox, _ in usable) + 24.0)
    return (x0, y0, x1, y1)


def _cells_for_box(box: BBox, cell_size: float) -> set[tuple[int, int]]:
    epsilon = 1e-9
    x0 = math.floor(box[0] / cell_size)
    y0 = math.floor(box[1] / cell_size)
    x1 = math.floor((box[2] - epsilon) / cell_size)
    y1 = math.floor((box[3] - epsilon) / cell_size)
    return {(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def _dilate(cells: set[tuple[int, int]], radius: int) -> set[tuple[int, int]]:
    if radius <= 0:
        return set(cells)
    return {
        (x + dx, y + dy)
        for x, y in cells
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    }


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(cells)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining, key=lambda item: (item[1], item[0]))
        remaining.remove(start)
        queue = deque([start])
        component = {start}
        while queue:
            x, y = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (x + dx, y + dy)
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)
        components.append(component)
    return components


def cluster_tiny_blocks(
    boxes: Sequence[BBox],
    *,
    page_width: float,
    page_height: float,
    body_region: BBox,
    settings: VisualRecoverySettings,
) -> list[VisualCluster]:
    if not boxes:
        return []
    original_cells = [_cells_for_box(box, settings.grid_cell_size) for box in boxes]
    occupied = set().union(*original_cells)
    cell_sources: dict[tuple[int, int], list[int]] = {}
    for index, cells in enumerate(original_cells):
        for cell in cells:
            cell_sources.setdefault(cell, []).append(index)
    components = _components(_dilate(occupied, settings.grid_dilation_cells))
    page_area = max(page_width * page_height, 1.0)
    clusters: list[VisualCluster] = []
    for component in components:
        source_indexes = sorted(
            {
                index
                for cell in component
                for index in cell_sources.get(cell, [])
            }
        )
        if len(source_indexes) < settings.min_cluster_blocks:
            continue
        source_boxes = [boxes[index] for index in source_indexes]
        bbox = (
            min(box[0] for box in source_boxes),
            min(box[1] for box in source_boxes),
            max(box[2] for box in source_boxes),
            max(box[3] for box in source_boxes),
        )
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        area = _area(bbox)
        if width < settings.min_cluster_dimension or height < settings.min_cluster_dimension:
            continue
        area_ratio = area / page_area
        if area_ratio < settings.min_cluster_area_ratio:
            continue
        body_overlap = _intersection_area(bbox, body_region) / max(area, 1.0)
        if body_overlap <= 0:
            continue
        component_original_cells = occupied.intersection(component)
        bbox_cells = max(1, math.ceil(width / settings.grid_cell_size) * math.ceil(height / settings.grid_cell_size))
        density = len(component_original_cells) / bbox_cells
        score = (
            area_ratio
            * min(1.0, max(0.1, density))
            * math.log2(len(source_indexes) + 1)
            * min(1.0, max(0.1, body_overlap))
        )
        clusters.append(
            VisualCluster(
                bbox=bbox,
                source_block_count=len(source_indexes),
                occupied_cells=len(component_original_cells),
                density=density,
                area_ratio=area_ratio,
                body_overlap_ratio=body_overlap,
                score=score,
            )
        )
    return sorted(clusters, key=lambda item: (-item.score, item.bbox))


def analyze_page(
    *,
    page_width: float,
    page_height: float,
    text_blocks: Sequence[tuple[BBox, str]],
    image_boxes: Sequence[BBox],
    settings: VisualRecoverySettings | None = None,
) -> PageVisualAnalysis:
    cfg = settings or VisualRecoverySettings()
    tiny: list[BBox] = []
    valid: list[BBox] = []
    for box in image_boxes:
        target = (
            tiny
            if box[2] - box[0] < cfg.direct_image_min_dimension
            or box[3] - box[1] < cfg.direct_image_min_dimension
            else valid
        )
        target.append(box)
    body_region = derive_body_region(
        page_width=page_width,
        page_height=page_height,
        text_blocks=text_blocks,
    )
    clusters = cluster_tiny_blocks(
        tiny,
        page_width=page_width,
        page_height=page_height,
        body_region=body_region,
        settings=cfg,
    )
    page_area = max(page_width * page_height, 1.0)
    visual_regions = [*valid, *(cluster.bbox for cluster in clusters)]
    largest_region_ratio = max((_area(box) / page_area for box in visual_regions), default=0.0)
    occupied_cells = set()
    for box in image_boxes:
        occupied_cells.update(_cells_for_box(box, cfg.grid_cell_size))
    safe_region_area = max(_area(body_region), 1.0)
    occupancy_area = len(occupied_cells) * cfg.grid_cell_size * cfg.grid_cell_size
    occupancy_ratio = min(1.0, occupancy_area / safe_region_area)
    native_text_chars = sum(len(text.strip()) for _, text in text_blocks)
    meaningful_lengths = [meaningful_text_length(text) for _, text in text_blocks]
    meaningful_chars = sum(meaningful_lengths)
    suspected_scanned = (
        meaningful_chars < cfg.scanned_text_ceiling
        and max(meaningful_lengths, default=0) <= cfg.scanned_meaningful_block_ceiling
        and (
        largest_region_ratio >= cfg.scanned_largest_region_ratio
        or occupancy_ratio >= cfg.scanned_occupancy_ratio
        )
    )
    retained = clusters[: cfg.retained_cluster_limit]
    return PageVisualAnalysis(
        native_text_chars=native_text_chars,
        image_block_count=len(image_boxes),
        tiny_image_block_count=len(tiny),
        valid_image_block_count=len(valid),
        tiny_image_block_ratio=(len(tiny) / len(image_boxes)) if image_boxes else 0.0,
        image_union_coverage_ratio=occupancy_ratio,
        body_region=body_region,
        clusters=tuple(retained),
        overflow_cluster_count=max(0, len(clusters) - len(retained)),
        suspected_scanned_page=suspected_scanned,
    )


def edge_signature(
    bbox: BBox,
    *,
    page_width: float,
    page_height: float,
    origin: str,
) -> str | None:
    band = None
    if bbox[3] <= page_height * 0.08:
        band = "top"
    elif bbox[1] >= page_height * 0.92:
        band = "bottom"
    if band is None:
        return None
    normalized = tuple(round(value * 100) for value in (
        bbox[0] / page_width,
        bbox[1] / page_height,
        bbox[2] / page_width,
        bbox[3] / page_height,
    ))
    aspect = round(((bbox[2] - bbox[0]) / max(bbox[3] - bbox[1], 1e-6)) * 10)
    return f"{band}:{origin}:{normalized}:{aspect}"


def repeated_edge_signatures(
    signatures_by_page: Sequence[Iterable[str]],
) -> set[str]:
    counts = Counter(signature for page in signatures_by_page for signature in set(page))
    eligible_pages = max(len(signatures_by_page), 1)
    return {
        signature
        for signature, count in counts.items()
        if count >= 3 and count / eligible_pages >= 0.50
    }


__all__ = [
    "BBox",
    "PageVisualAnalysis",
    "VisualCluster",
    "VisualRecoverySettings",
    "analyze_page",
    "cluster_tiny_blocks",
    "derive_body_region",
    "edge_signature",
    "is_page_backing_image",
    "meaningful_text_length",
    "normalized_bbox",
    "repeated_edge_signatures",
]
