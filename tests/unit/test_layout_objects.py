from pathlib import Path

import fitz

from vibration_agent.ingestion.layout import enrich_page_layout
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




