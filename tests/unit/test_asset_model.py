from vibration_agent.ingestion.chunking import chunk_pages, write_api_context_json
from vibration_agent.ingestion.layout import enrich_page_layout
from vibration_agent.knowledge.evidence import attach_citations, chunk_evidence_rows
from vibration_agent.schemas import OcrPage, PageBlock


def test_chunk_pages_attaches_body_and_page_assets(tmp_path):
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=3,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0003_b0001", text="转子系统振动响应说明。", bbox=[10, 10, 200, 30]),
                PageBlock(block_id="p0003_b0002", text="m x + c v + k x = F", bbox=[10, 50, 200, 70]),
                PageBlock(block_id="p0003_b0003", text="图 3. 转子轨迹", bbox=[10, 90, 200, 110]),
                PageBlock(block_id="p0003_b0004", text="表 3. 轴承参数", bbox=[10, 130, 200, 150]),
            ],
        )
    )

    chunks = chunk_pages(
        [page],
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=0,
    )

    assert len(chunks) == 1
    asset_types = [asset["object_type"] for asset in chunks[0]["assets"]]
    assert asset_types == ["body", "formula", "figure", "table"]
    assert chunks[0]["pages"] == [3]
    assert chunks[0]["assets"][0]["asset_path"] == "chunk://doc1/doc1_p0003_00001/body"
    assert chunks[0]["assets"][0]["text"] == ""
    assert all(asset["asset_id"] for asset in chunks[0]["assets"])
    assert all(asset["asset_path"] for asset in chunks[0]["assets"])


def test_api_context_exports_structured_asset_refs_without_markdown(tmp_path):
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0001_b0001", text="Rotor vibration body text.", bbox=[10, 10, 200, 30]),
                PageBlock(block_id="p0001_b0002", text="Fig. 1 Rotor orbit", bbox=[10, 50, 200, 70]),
            ],
        )
    )
    chunks = chunk_pages(
        [page],
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=0,
    )
    output = tmp_path / "api_context.json"

    write_api_context_json(output, doc_id="doc1", title="Rotor Book", chunks=chunks)
    payload = output.read_text(encoding="utf-8")
    data = __import__("json").loads(payload)

    assert "assets" in data
    assert data["chunks"][0]["asset_ids"]
    assert "![" not in payload
    assert all(asset["object_type"] != "body" for asset in data["assets"])
    assert any(asset["text"] == "Fig. 1 Rotor orbit" for asset in data["assets"])


def test_same_page_multiple_formulas_get_distinct_asset_ids():
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=2,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0002_b0001", text="m x + c v + k x = F", bbox=[10, 50, 200, 70]),
                PageBlock(block_id="p0002_b0002", text="ω = 2 π f", bbox=[10, 90, 200, 110]),
            ],
        )
    )

    formula_ids = [asset.asset_id for asset in page.assets if asset.object_type == "formula"]

    assert formula_ids == ["doc1_p0002_formula_0001", "doc1_p0002_formula_0002"]


def test_evidence_rows_separate_text_and_visual_assets(tmp_path):
    page = enrich_page_layout(
        OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0001_b0001", text="Rotor vibration body text.", bbox=[10, 10, 200, 30]),
                PageBlock(block_id="p0001_b0002", text="图 1. 转子轨迹", bbox=[10, 50, 200, 70]),
            ],
        )
    )
    chunk = chunk_pages(
        [page],
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=0,
    )[0]

    rows = chunk_evidence_rows(chunk)

    assert rows[0]["evidence_kind"] == "text"
    assert rows[0]["pages"] == [1]
    assert rows[1]["evidence_kind"] == "asset"
    assert rows[1]["object_type"] == "figure"
    assert rows[1]["asset_id"]


def test_citation_pages_are_enumerated_for_ranges():
    citations = attach_citations(
        "answer",
        [{"chunk_id": "c1", "doc_id": "d1", "page_start": 4, "page_end": 7, "ocr_confidence_min": 0.55}],
    )

    assert citations[0]["pages"] == [4, 5, 6, 7]
    assert citations[0]["confidence"] == 0.55


