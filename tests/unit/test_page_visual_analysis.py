import time

from vibration_agent.ingestion.page_visual_analysis import (
    VisualRecoverySettings,
    analyze_page,
    cluster_tiny_blocks,
    derive_body_region,
    edge_signature,
    repeated_edge_signatures,
)


def _fragment_grid(x0=100.0, y0=100.0, columns=20, rows=20, spacing=2.0):
    return [
        (
            x0 + column * spacing,
            y0 + row * spacing,
            x0 + column * spacing + 0.5,
            y0 + row * spacing + 0.5,
        )
        for row in range(rows)
        for column in range(columns)
    ]


def test_dense_tiny_fragments_form_one_retained_visual_region():
    # WHY: vectorized engineering plots must survive even when every source block is microscopic.
    settings = VisualRecoverySettings(min_cluster_dimension=30.0, min_cluster_area_ratio=0.001)
    clusters = cluster_tiny_blocks(
        _fragment_grid(),
        page_width=600,
        page_height=800,
        body_region=(30, 64, 570, 736),
        settings=settings,
    )

    assert len(clusters) == 1
    assert clusters[0].source_block_count == 400
    assert clusters[0].area_ratio > 0


def test_separated_fragmented_panels_remain_separate():
    # WHY: merging multi-panel figures page-wide destroys panel-level provenance.
    settings = VisualRecoverySettings(min_cluster_dimension=20.0, min_cluster_area_ratio=0.001)
    boxes = _fragment_grid(x0=80, columns=12, rows=12) + _fragment_grid(x0=350, columns=12, rows=12)

    clusters = cluster_tiny_blocks(
        boxes,
        page_width=600,
        page_height=800,
        body_region=(30, 64, 570, 736),
        settings=settings,
    )

    assert len(clusters) == 2
    assert clusters[0].bbox[2] < clusters[1].bbox[0]


def test_sparse_text_uses_page_safe_body_region():
    # WHY: sparse/scanned pages cannot derive a trustworthy narrow body region from one text block.
    region = derive_body_region(
        page_width=600,
        page_height=800,
        text_blocks=[((100, 100, 200, 120), "cover")],
    )

    assert region == (30.0, 64.0, 570.0, 736.0)


def test_scanned_route_requires_low_text_and_dominant_visual_region():
    # WHY: a sparse cover must not be OCR-routed unless visual content dominates the page.
    scanned = analyze_page(
        page_width=600,
        page_height=800,
        text_blocks=[((50, 50, 100, 70), "cover")],
        image_boxes=[(20, 20, 580, 780)],
    )
    cover = analyze_page(
        page_width=600,
        page_height=800,
        text_blocks=[((50, 50, 100, 70), "cover")],
        image_boxes=[(250, 250, 350, 350)],
    )

    assert scanned.suspected_scanned_page is True
    assert cover.suspected_scanned_page is False


def test_repeated_edge_signature_requires_three_and_half_of_pages():
    # WHY: one-off cover logos must not be suppressed as repeated decoration.
    signature = edge_signature(
        (20, 10, 80, 30),
        page_width=600,
        page_height=800,
        origin="direct",
    )

    assert signature
    assert repeated_edge_signatures([[signature], [signature], [signature], [], []]) == {signature}
    assert repeated_edge_signatures([[signature], [signature], [], [], []]) == set()


def test_page_analysis_scales_near_linearly_with_fragment_count():
    # WHY: pathological PDFs can contain tens of thousands of fragments on one page.
    def elapsed(count):
        boxes = [
            (
                100.0 + (index % 100) * 0.5,
                100.0 + ((index // 100) % 100) * 0.5,
                100.25 + (index % 100) * 0.5,
                100.25 + ((index // 100) % 100) * 0.5,
            )
            for index in range(count)
        ]
        started = time.perf_counter()
        analyze_page(
            page_width=600,
            page_height=800,
            text_blocks=[((40, 80, 560, 140), "native text " * 20)],
            image_boxes=boxes,
        )
        return time.perf_counter() - started

    small = min(elapsed(3_000) for _ in range(2))
    large = min(elapsed(30_000) for _ in range(2))

    assert large / max(small, 1e-6) < 25
