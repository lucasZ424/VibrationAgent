from pathlib import Path

import fitz

from vibration_agent.ingestion.layout import classify_text_block, enrich_page_layout, promote_font_titles
from vibration_agent.ingestion.page_visual_analysis import VisualRecoverySettings
from vibration_agent.ingestion.pymupdf_parser import _image_bbox_skip_reason, parse_native_pdf
from vibration_agent.schemas import OcrPage, PageBlock



def test_enrich_page_layout_classifies_text_objects_and_assets():
    page = OcrPage(
        doc_id="doc1",
        page_no=1,
        primary_engine="paddleocr",
        normalized_text="",
        blocks=[
            PageBlock(block_id="p0001_b0001", text="第 1 章 转子动力学", bbox=[72, 40, 250, 60]),
            PageBlock(block_id="p0001_b0002", text="m x + c v + k x = F", bbox=[72, 100, 260, 120]),
            PageBlock(block_id="p0001_b0003", text="图 1. 转子结构示意图", bbox=[72, 160, 260, 180]),
            PageBlock(block_id="p0001_b0004", text="转子不平衡会产生同步振动。", bbox=[72, 220, 300, 240]),
        ],
    )

    enriched = enrich_page_layout(page)

    assert [block.block_type for block in enriched.blocks] == ["title", "formula", "figure", "body"]
    assert enriched.normalized_text == "第 1 章 转子动力学\n转子不平衡会产生同步振动。"
    assert [asset.object_type for asset in enriched.assets] == ["formula", "figure"]
    assert all(asset.asset_id and asset.asset_path and asset.bbox for asset in enriched.assets)


def test_parse_native_pdf_exports_image_block_as_figure_asset(tmp_path):
    pdf = tmp_path / "native_with_image.pdf"
    asset_dir = tmp_path / "assets"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Chapter 1 Rotor Dynamics")
    page.insert_text((72, 100), "Rotor imbalance produces synchronous vibration at running speed.")
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
    pixmap.clear_with(0xFF0000)
    page.insert_image(fitz.Rect(72, 140, 172, 240), pixmap=pixmap)
    doc.save(pdf)
    doc.close()

    pages = parse_native_pdf(pdf, doc_id="doc1", asset_dir=asset_dir)

    assert len(pages) == 1
    assert any(block.block_type == "title" for block in pages[0].blocks)
    assert any(block.block_type == "body" for block in pages[0].blocks)
    figure_assets = [asset for asset in pages[0].assets if asset.object_type == "figure"]
    assert len(figure_assets) == 1
    assert figure_assets[0].asset_id
    assert figure_assets[0].bbox
    assert figure_assets[0].asset_path
    assert Path(figure_assets[0].asset_path).exists()


def test_parse_native_pdf_keeps_text_when_image_export_fails(tmp_path, monkeypatch):
    # WHY: one malformed PDF image must not discard readable text or abort full-corpus ingestion.
    pdf = tmp_path / "native_with_bad_image.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Rotor order analysis remains readable.")
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
    page.insert_image(fitz.Rect(72, 140, 172, 240), pixmap=pixmap)
    doc.save(pdf)
    doc.close()

    monkeypatch.setattr(
        "vibration_agent.ingestion.pymupdf_parser._save_block_clip",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("invalid image dimensions")),
    )

    parsed = parse_native_pdf(pdf, doc_id="doc1", asset_dir=tmp_path / "assets")

    assert "Rotor order analysis remains readable." in parsed[0].normalized_text
    assert len(parsed[0].assets) == 1
    assert parsed[0].assets[0].asset_path.startswith("page://")
    assert "RuntimeError" in parsed[0].assets[0].metadata["image_export_skipped"]
    assert parsed[0].metadata["asset_export_warnings"][0]["block_id"]


def test_native_pdf_parser_rejects_microscopic_image_fragments():
    # WHY: malformed PDFs can expose hundreds of thousands of sub-point image masks as blocks.
    assert _image_bbox_skip_reason([10.0, 20.0, 10.5, 20.5]) == "tiny_bbox"
    assert _image_bbox_skip_reason([10.0, 20.0, 30.0, 19.0]) == "invalid_bbox"
    assert _image_bbox_skip_reason([10.0, 20.0, 30.0, 40.0]) is None


def test_native_pdf_parser_recovers_dense_tiny_blocks_as_one_cluster_asset(tmp_path):
    # WHY: fragmented vector plots must become one bounded asset, not hundreds of files.
    pdf = tmp_path / "fragmented_plot.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 80), "Native rotor spectrum discussion remains primary text.")
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 1, 1), False)
    for row in range(20):
        for column in range(20):
            x = 100 + column * 3
            y = 180 + row * 3
            page.insert_image(fitz.Rect(x, y, x + 0.5, y + 0.5), pixmap=pixmap)
    doc.save(pdf)
    doc.close()
    ocr_calls = []

    pages = parse_native_pdf(
        pdf,
        doc_id="doc1",
        asset_dir=tmp_path / "assets",
        visual_settings=VisualRecoverySettings(min_cluster_area_ratio=0.001),
        region_ocr_enabled=True,
        image_ocr_runner=lambda *args, **kwargs: ocr_calls.append(args[0]) or OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            normalized_text="频谱图",
            raw_text="频谱图",
        ),
    )

    clusters = [asset for asset in pages[0].assets if asset.metadata.get("source") == "pymupdf_fragment_cluster"]
    assert len(clusters) == 1
    assert len(ocr_calls) == 1
    assert clusters[0].text == "频谱图"
    assert len(list((tmp_path / "assets").glob("*.png"))) == 1


def test_native_pdf_parser_scanned_page_route_skips_cluster_recovery(tmp_path):
    # WHY: one page must not produce both full-page OCR body text and duplicate cluster assets.
    pdf = tmp_path / "scanned_page.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    page.insert_image(fitz.Rect(10, 10, 590, 790), pixmap=pixmap)
    doc.save(pdf)
    doc.close()
    calls = []

    pages = parse_native_pdf(
        pdf,
        doc_id="doc1",
        asset_dir=tmp_path / "assets",
        page_ocr_enabled=True,
        page_ocr_runner=lambda *args, **kwargs: calls.append(kwargs) or OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            normalized_text="Recovered scanned page text.",
            raw_text="Recovered scanned page text.",
        ),
    )

    assert len(calls) == 1
    assert pages[0].normalized_text == "Recovered scanned page text."
    assert pages[0].metadata["visual_route"] == "scanned_page_ocr"
    assert not any(asset.metadata.get("source") == "pymupdf_fragment_cluster" for asset in pages[0].assets)


def test_native_pdf_parser_suppresses_repeated_header_images(tmp_path):
    # WHY: repeated page furniture must not become one retained asset per page.
    pdf = tmp_path / "repeated_header.pdf"
    doc = fitz.open()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
    for _ in range(4):
        page = doc.new_page(width=600, height=800)
        page.insert_text((50, 120), "Rotor dynamics body text " * 8)
        page.insert_image(fitz.Rect(20, 10, 80, 30), pixmap=pixmap)
    doc.save(pdf)
    doc.close()

    pages = parse_native_pdf(pdf, doc_id="doc1", asset_dir=tmp_path / "assets")

    assert all(not page.assets for page in pages)
    assert pages[0].metadata["level2_repeated_cover_candidates"] == 1
    assert all(page.metadata["skipped_image_blocks"]["repeated_decoration"] == 1 for page in pages[1:])


def test_native_pdf_parser_bounds_region_ocr_calls(tmp_path):
    # WHY: visual recovery must not multiply OCR cost by every retained panel.
    pdf = tmp_path / "multi_panel.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((50, 80), "Six retained panels share one page. " * 5)
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), False)
    for index in range(6):
        column = index % 2
        row = index // 2
        x = 80 + column * 260
        y = 160 + row * 180
        page.insert_image(fitz.Rect(x, y, x + 180, y + 120), pixmap=pixmap)
    doc.save(pdf)
    doc.close()
    calls = []

    pages = parse_native_pdf(
        pdf,
        doc_id="doc1",
        asset_dir=tmp_path / "assets",
        region_ocr_enabled=True,
        image_ocr_runner=lambda *args, **kwargs: calls.append(args[0]) or OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            normalized_text="panel",
            raw_text="panel",
        ),
    )

    assert len(calls) == 4
    statuses = [asset.metadata.get("ocr_status") for asset in pages[0].assets]
    assert statuses.count("ok") == 4
    assert statuses.count("not_selected") == 2


def test_layout_avoids_common_formula_and_title_false_positives():
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            normalized_text="",
            blocks=[
                PageBlock(block_id="p0001_b0001", text="123", bbox=[72, 20, 90, 35]),
                PageBlock(block_id="p0001_b0002", text="rotor-bearing-system", bbox=[72, 70, 250, 90]),
                PageBlock(block_id="p0001_b0003", text="pp. 12-15, 18-20", bbox=[72, 100, 250, 120]),
                PageBlock(block_id="p0001_b0004", text="10. Smith, J. et al., 1998.", bbox=[72, 130, 300, 150]),
                PageBlock(block_id="p0001_b0005", text="Figure (a): rotor orbit", bbox=[72, 160, 300, 180]),
            ],
        )
    )

    assert [block.block_type for block in page.blocks] == ["body", "body", "body", "body", "figure"]
    assert page.normalized_text == "123\nrotor-bearing-system\npp. 12-15, 18-20\n10. Smith, J. et al., 1998."


def test_font_title_promotion_uses_page_baseline_and_preserves_large_prose():
    # WHY: brochure headings lack numbering, but larger complete prose must remain body evidence.
    blocks = [
        PageBlock(
            block_id="cover-title",
            text="ORBIT 60系列系统概述",
            block_type="body",
            metadata={"max_font_size": 24.0},
        ),
        PageBlock(
            block_id="tagline",
            text="涵盖全厂• 一体化系统",
            block_type="body",
            metadata={"max_font_size": 13.0},
        ),
        PageBlock(
            block_id="body",
            text="Orbit 60为关键设备提供连续在线监测和保护。",
            block_type="body",
            metadata={"max_font_size": 10.0},
        ),
        PageBlock(
            block_id="large-prose",
            text="该系统提供独立保护功能。",
            block_type="body",
            metadata={"max_font_size": 14.0},
        ),
        PageBlock(
            block_id="reference",
            text="[7] Zhang et al. Order analysis methods.",
            block_type="body",
            metadata={"max_font_size": 10.0},
        ),
    ]

    promoted = promote_font_titles(blocks)

    assert [block.block_type for block in promoted] == ["title", "body", "body", "body", "body"]
    assert promoted[1].metadata["layout_role"] == "label"
    assert promoted[4].metadata["layout_role"] == "bibliography"


def test_chapter_running_header_is_not_classified_as_title_when_too_close_to_top():
    running_header = classify_text_block(
        "第三章 转子动力学",
        block_index=1,
        bbox=[72, 20, 300, 40],
        page_height=1000,
    )
    chapter_title = classify_text_block(
        "第三章 转子动力学",
        block_index=1,
        bbox=[72, 120, 300, 150],
        page_height=1000,
    )

    assert running_header == "body"
    assert chapter_title == "title"


def test_asset_only_page_does_not_restore_caption_text_to_body():
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=2,
            primary_engine="paddleocr",
            normalized_text="图 2. 转子轨迹\n表 2. 参数",
            blocks=[
                PageBlock(block_id="p0002_b0001", text="图 2. 转子轨迹", bbox=[10, 10, 200, 30]),
                PageBlock(block_id="p0002_b0002", text="表 2. 参数", bbox=[10, 50, 200, 70]),
            ],
        )
    )

    assert page.normalized_text == ""
    assert [asset.object_type for asset in page.assets] == ["figure", "table"]


