from pathlib import Path

import fitz

from vibration_agent.ingestion.layout import classify_text_block, enrich_page_layout
from vibration_agent.ingestion.pymupdf_parser import parse_native_pdf
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


