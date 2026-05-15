import json
from pathlib import Path

import fitz

from vibration_agent.config import load
from vibration_agent.ingestion.classify import classify_document
from vibration_agent.ingestion.ocr import router
from vibration_agent.ingestion.pipeline import parse_document_pages
from vibration_agent.ingestion.pymupdf_parser import parse_native_pdf


def _make_text_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Rotor imbalance produces synchronous vibration at running speed. " * 4)
    doc.save(path)
    doc.close()


def _make_blank_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def test_parse_native_pdf_pages(tmp_path):
    pdf = tmp_path / "native.pdf"
    _make_text_pdf(pdf)

    pages = parse_native_pdf(pdf, doc_id="doc1")

    assert len(pages) == 1
    assert pages[0].primary_engine == "pymupdf"
    assert pages[0].layout_quality == "ok"
    assert "Rotor imbalance" in pages[0].normalized_text
    assert pages[0].blocks


def test_parse_document_pages_writes_jsonl(tmp_path):
    pdf = tmp_path / "native.pdf"
    _make_text_pdf(pdf)
    doc = classify_document(pdf)
    settings = load()
    settings.paths.ocr_dir = tmp_path / "ocr"

    result = parse_document_pages(doc, settings=settings, max_pages=1, write_output=True)
    output_path = Path(result["output_path"])
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["status"] == "ok"
    assert output_path.exists()
    assert rows[0]["doc_id"] == doc.doc_id
    assert rows[0]["primary_engine"] == "pymupdf"


def test_ocr_router_returns_review_page_when_paddle_fails(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    _make_blank_pdf(pdf)

    def fail_paddle(*args, **kwargs):
        raise RuntimeError("forced paddle failure")

    monkeypatch.setattr(router.paddle_engine, "run", fail_paddle)
    page = router.ocr_page(pdf, 1, doc_id="scan1", image_dir=tmp_path / "images")

    assert page.page_no == 1
    assert page.needs_review is True
    assert page.fallback_used is True
    assert page.layout_quality in {"empty", "low"}