import json
from pathlib import Path

import fitz

from vibration_agent.ingestion import book_workflow
from vibration_agent.ingestion.book_workflow import BookWorkflowOptions, process_pdf
from vibration_agent.schemas import OcrPage, PageBlock


def _make_pdf(path: Path, pages: int = 2) -> None:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def test_book_workflow_uses_package_ocr_and_writes_outputs(tmp_path, monkeypatch):
    raw_pdf = tmp_path / "raw" / "book" / "book.pdf"
    raw_pdf.parent.mkdir(parents=True)
    _make_pdf(raw_pdf, pages=2)
    calls = []
    warmup_calls = []

    def fake_run(pdf_path, page_no, **kwargs):
        calls.append((pdf_path, page_no, kwargs))
        return OcrPage(
            doc_id=kwargs["doc_id"],
            page_no=page_no,
            primary_engine="fake-paddle",
            fallback_used=False,
            ocr_confidence=0.99,
            layout_quality="ok",
            raw_text=f"Page {page_no} rotor vibration text.",
            normalized_text=f"Page {page_no} rotor vibration text.",
            blocks=[
                PageBlock(
                    block_id=f"p{page_no:04d}_b0001",
                    text=f"Page {page_no} rotor vibration text.",
                    confidence=0.99,
                )
            ],
            needs_review=False,
        )

    monkeypatch.setattr(book_workflow.paddle_engine, "make_ocr", lambda **kwargs: warmup_calls.append(kwargs) or object())
    monkeypatch.setattr(book_workflow.paddle_engine, "run", fake_run)
    manifest = process_pdf(
        pdf_path=raw_pdf,
        workspace=tmp_path,
        options=BookWorkflowOptions(max_pages=2, resume=False),
    )

    assert len(warmup_calls) == 1
    assert len(calls) == 2
    assert manifest["processed_pages"] == 2
    assert manifest["chunk_count"] >= 1
    assert Path(manifest["outputs"]["ocr_pages_jsonl"]).exists()
    assert Path(manifest["outputs"]["chunks_jsonl"]).exists()
    assert Path(manifest["outputs"]["api_context_json"]).exists()

    rows = [
        json.loads(line)
        for line in Path(manifest["outputs"]["ocr_pages_jsonl"]).read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["primary_engine"] == "fake-paddle"
    assert rows[0]["schema_version"] == "0.1"


def test_book_workflow_resume_reuses_existing_pages(tmp_path, monkeypatch):
    raw_pdf = tmp_path / "raw" / "book" / "book.pdf"
    raw_pdf.parent.mkdir(parents=True)
    _make_pdf(raw_pdf, pages=1)
    calls = []
    warmup_calls = []

    def fake_run(pdf_path, page_no, **kwargs):
        calls.append(page_no)
        return OcrPage(
            doc_id=kwargs["doc_id"],
            page_no=page_no,
            primary_engine="fake-paddle",
            normalized_text="existing rotor text",
            raw_text="existing rotor text",
            blocks=[],
        )

    monkeypatch.setattr(book_workflow.paddle_engine, "make_ocr", lambda **kwargs: warmup_calls.append(kwargs) or object())
    monkeypatch.setattr(book_workflow.paddle_engine, "run", fake_run)
    options = BookWorkflowOptions(max_pages=1, resume=False)
    first = process_pdf(pdf_path=raw_pdf, workspace=tmp_path, options=options)
    second = process_pdf(
        pdf_path=raw_pdf,
        workspace=tmp_path,
        options=BookWorkflowOptions(max_pages=1, resume=True),
    )

    assert len(warmup_calls) == 1
    assert calls == [1]
    assert first["doc_id"] == second["doc_id"]
    assert second["processed_pages"] == 1
