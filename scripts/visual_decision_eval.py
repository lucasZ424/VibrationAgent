"""Evaluate deterministic page-visual decisions against labeled fixtures."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vibration_agent.ingestion.page_visual_analysis import (  # noqa: E402
    analyze_page,
    edge_signature,
    repeated_edge_signatures,
)


def _fragment_region(spec: list[float]) -> list[tuple[float, float, float, float]]:
    x0, y0, x1, y1, spacing = spec
    boxes = []
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            boxes.append((x, y, min(x + 0.5, x1), min(y + 0.5, y1)))
            x += spacing
        y += spacing
    return boxes


def _bbox_matches(actual: list[float], expected: list[float], tolerance: float) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(actual, expected))


def _evaluate_document_case(case: dict[str, Any]) -> dict[str, Any]:
    width, height = case["page_size"]
    signatures_by_page = []
    for page in case["pages"]:
        signatures = []
        for row in page.get("direct_images", []):
            signature = edge_signature(
                tuple(float(value) for value in row),
                page_width=float(width),
                page_height=float(height),
                origin="direct",
            )
            if signature:
                signatures.append(signature)
        signatures_by_page.append(signatures)
    repeated = repeated_edge_signatures(signatures_by_page)
    expected_repeated = int(case["expected_repeated_decorations"])
    actual_retained = sum(
        signature not in repeated
        for signatures in signatures_by_page
        for signature in signatures
    )
    expected_retained = int(case.get("expected_retained_decorations", 0))
    passed = len(repeated) == expected_repeated and actual_retained == expected_retained
    return {
        "id": case["id"],
        "passed": passed,
        "expected_repeated_decorations": expected_repeated,
        "actual_repeated_decorations": len(repeated),
        "expected_retained_decorations": expected_retained,
        "actual_retained_decorations": actual_retained,
    }


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("kind") == "document":
        return _evaluate_document_case(case)
    width, height = case["page_size"]
    text_blocks = [
        ((float(row[0]), float(row[1]), float(row[2]), float(row[3])), str(row[4]))
        for row in case.get("text_blocks", [])
    ]
    image_boxes = [
        tuple(float(value) for value in row)
        for row in [*case.get("direct_images", []), *case.get("tiny_boxes", [])]
    ]
    for region in case.get("fragment_regions", []):
        image_boxes.extend(_fragment_region(region))
    result = analyze_page(
        page_width=float(width),
        page_height=float(height),
        text_blocks=text_blocks,
        image_boxes=image_boxes,
    )
    route = "scanned" if result.suspected_scanned_page else "native"
    cluster_bboxes = [list(cluster.bbox) for cluster in result.clusters]
    expected_bboxes = case.get("expected_cluster_bboxes", [])
    tolerance = float(case.get("bbox_tolerance", 0.0))
    bboxes_match = len(cluster_bboxes) == len(expected_bboxes) and all(
        _bbox_matches(actual, expected, tolerance)
        for actual, expected in zip(cluster_bboxes, expected_bboxes)
    )
    clustered_sources = sum(cluster.source_block_count for cluster in result.clusters)
    deferred_tiny = result.tiny_image_block_count - clustered_sources
    baseline_required = bool(case.get("baseline_must_fail", False))
    baseline_failed_as_expected = (
        result.valid_image_block_count != case["expected_clusters"]
        if baseline_required
        else None
    )
    checks = [
        route == case["expected_route"],
        len(result.clusters) == case["expected_clusters"],
        bboxes_match,
    ]
    if baseline_required:
        checks.append(bool(baseline_failed_as_expected))
    if "expected_valid_images" in case:
        checks.append(result.valid_image_block_count == case["expected_valid_images"])
    if "expected_deferred_tiny" in case:
        checks.append(deferred_tiny == case["expected_deferred_tiny"])
    return {
        "id": case["id"],
        "passed": all(checks),
        "expected_route": case["expected_route"],
        "actual_route": route,
        "expected_clusters": case["expected_clusters"],
        "actual_clusters": len(result.clusters),
        "expected_cluster_bboxes": expected_bboxes,
        "actual_cluster_bboxes": cluster_bboxes,
        "bbox_tolerance": tolerance,
        "expected_valid_images": case.get("expected_valid_images"),
        "actual_valid_images": result.valid_image_block_count,
        "expected_deferred_tiny": case.get("expected_deferred_tiny"),
        "actual_deferred_tiny": deferred_tiny,
        "baseline_failed_as_expected": baseline_failed_as_expected,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "tests" / "fixtures" / "visual_decision" / "cases.json",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    results = [evaluate_case(case) for case in payload.get("cases", [])]
    report = {
        "schema_version": "2",
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": sum(not item["passed"] for item in results),
        "results": results,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
