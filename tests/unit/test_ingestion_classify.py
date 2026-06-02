from pathlib import Path

import fitz
from docx import Document

from vibration_agent.ingestion.classify import classify_document, scan_inputs
from vibration_agent.ingestion.pipeline import ingest


def _make_text_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Rotor imbalance produces synchronous vibration at running speed." * 3)
    doc.save(path)
    doc.close()


def _make_blank_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()


def test_classify_native_pdf(tmp_path):
    pdf = tmp_path / "native.pdf"
    _make_text_pdf(pdf)

    result = classify_document(pdf)

    assert result.kind == "pdf"
    assert result.page_count == 1
    assert result.processing_strategy == "native_pdf"
    assert result.doc_id == classify_document(pdf).doc_id


def test_classify_scanned_like_pdf(tmp_path):
    pdf = tmp_path / "scan.pdf"
    _make_blank_pdf(pdf)

    result = classify_document(pdf)

    assert result.kind == "pdf"
    assert result.page_count == 1
    assert result.processing_strategy == "ocr_pdf"
    assert result.warnings


def test_scan_inputs_and_pipeline(tmp_path):
    text = tmp_path / "note.txt"
    text.write_text("critical speed note", encoding="utf-8")
    unsupported = tmp_path / "ignore.bin"
    unsupported.write_bytes(b"x")

    scanned = scan_inputs(tmp_path)
    plan = ingest(tmp_path)

    assert [item.filename for item in scanned] == ["note.txt"]
    assert plan["status"] == "ok"
    assert plan["document_count"] == 1
    assert plan["documents"][0]["processing_strategy"] == "text"


def test_classify_docx_and_skip_office_lock_file(tmp_path):
    docx = tmp_path / "rotor_note.docx"
    document = Document()
    document.add_paragraph("Rotor damping reduces resonant vibration near critical speed.")
    document.save(docx)
    lock_file = tmp_path / "~$rotor_note.docx"
    lock_file.write_bytes(b"locked")

    result = classify_document(docx)
    scanned = scan_inputs(tmp_path)

    assert result.kind == "docx"
    assert result.processing_strategy == "docx"
    assert result.page_count == 1
    assert result.text_chars and result.text_chars > 20
    assert [item.filename for item in scanned] == ["rotor_note.docx"]
