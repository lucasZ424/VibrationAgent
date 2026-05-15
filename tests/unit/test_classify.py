from pathlib import Path

from vibration_agent.ingestion.classify import classify_document, iter_supported_files, scan_inputs


def test_docx_is_explicitly_deferred_when_classified_directly(tmp_path):
    docx = tmp_path / "manual.docx"
    docx.write_bytes(b"not a real docx, classification only")

    result = classify_document(docx)

    assert result.kind == "unsupported"
    assert result.processing_strategy == "unknown"
    assert any("DOCX support is deferred" in warning for warning in result.warnings)


def test_iter_supported_files_skips_docx_and_office_lockfiles(tmp_path):
    supported = tmp_path / "note.txt"
    docx = tmp_path / "manual.docx"
    lockfile = tmp_path / "~$manual.docx"
    supported.write_text("rotor note", encoding="utf-8")
    docx.write_bytes(b"deferred")
    lockfile.write_bytes(b"lock")

    files = list(iter_supported_files(tmp_path))
    scanned = scan_inputs(tmp_path)

    assert files == [supported.resolve()]
    assert [item.filename for item in scanned] == ["note.txt"]


def test_language_detection_for_mixed_engineering_text(tmp_path):
    text = tmp_path / "mixed.md"
    text.write_text("转子轴承振动诊断 rotor", encoding="utf-8")

    result = classify_document(text)

    assert result.kind == "text"
    assert result.processing_strategy == "text"
    assert result.language == "mixed"

