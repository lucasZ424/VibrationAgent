import json
from pathlib import Path

from vibration_agent.config import load
from vibration_agent.ingestion.bibliography import extract_bibliography
from vibration_agent.ingestion.chunking import chunk_pages
from vibration_agent.ingestion.classify import classify_document
from vibration_agent.ingestion.pipeline import chunk_document_pages
from vibration_agent.knowledge.evidence import citation_from_chunk, chunk_text_evidence_row
from vibration_agent.retrieval.hybrid import load_chunks, search
from vibration_agent.retrieval.query_normalize import normalize
from vibration_agent.schemas import MemoryChunk, OcrPage, RetrievalOutput

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fixture_page() -> OcrPage:
    return OcrPage.model_validate(_jsonl(FIXTURES / "ocr" / "sample_pages.jsonl")[0])


def _fixture_chunk() -> dict:
    return _jsonl(FIXTURES / "chunks" / "sample_chunks.jsonl")[0]


def _fixture_zh_pages() -> list[OcrPage]:
    return [OcrPage.model_validate(row) for row in _jsonl(FIXTURES / "ocr" / "sample_zh_pages.jsonl")]


def _fixture_zh_chunk() -> dict:
    return _jsonl(FIXTURES / "chunks" / "sample_zh_chunks.jsonl")[0]


def _fixture_zh_docx_page() -> OcrPage:
    return OcrPage.model_validate(_jsonl(FIXTURES / "ocr" / "sample_zh_docx_pages.jsonl")[0])


def _fixture_zh_docx_chunk() -> dict:
    return _jsonl(FIXTURES / "chunks" / "sample_zh_docx_chunks.jsonl")[0]


def _project_workspace(path: Path) -> Path:
    (path / "configs").mkdir(parents=True, exist_ok=True)
    (path / "src" / "vibration_agent").mkdir(parents=True, exist_ok=True)
    return path


def test_small_pdf_fixture_classifies_as_native_pdf():
    pdf = FIXTURES / "raw" / "small_vibration_native.pdf"

    classification = classify_document(pdf)

    assert classification.kind == "pdf"
    assert classification.processing_strategy == "native_pdf"
    assert classification.page_count == 1
    assert classification.text_chars and classification.text_chars > 100


def test_page_and_chunk_fixtures_validate_against_schemas():
    page = _fixture_page()
    chunk = MemoryChunk.model_validate(_fixture_chunk())

    assert page.primary_engine == "pymupdf"
    assert page.layout_quality == "ok"
    assert page.blocks[0].block_type == "title"
    assert chunk.chunk_id == "fixture_rotor_doc_p0001_00001"
    assert chunk.assets[0].object_type == "body"
    assert chunk.pages == [1]
    assert chunk.source_path == "tests/fixtures/raw/small_vibration_native.pdf"


def test_zh_page_and_cross_page_chunk_fixtures_validate_against_schemas():
    pages = _fixture_zh_pages()
    chunk = MemoryChunk.model_validate(_fixture_zh_chunk())

    assert len(pages) == 2
    assert pages[0].primary_engine == "pymupdf"
    assert pages[0].blocks[0].block_type == "body"
    assert chunk.doc_id == "fixture_rotor_zh_doc"
    assert chunk.pages == [1, 2]
    assert chunk.page_start == 1
    assert chunk.page_end == 2
    assert chunk.metadata["page_boundary_crossed"] is True
    assert chunk.citation_anchor == "转子阻尼中文样例, pp. 1-2"
    assert chunk.source_path == "tests/fixtures/raw/small_vibration_zh.pdf"


def test_zh_docx_page_and_chunk_fixtures_validate_against_schemas():
    page = _fixture_zh_docx_page()
    chunk = MemoryChunk.model_validate(_fixture_zh_docx_chunk())

    assert page.primary_engine == "python-docx"
    assert page.layout_quality == "ok"
    assert any(block.block_type == "table" for block in page.blocks)
    assert chunk.doc_id == "fixture_rotor_zh_docx"
    assert chunk.pages == [1]
    assert chunk.page_start == 1
    assert chunk.page_end == 1
    assert chunk.source_path == "tests/fixtures/raw/small_vibration_zh.docx"
    assert "\u76d1\u6d4b\u91cf | \u7528\u9014" in chunk.text


def test_retrieval_fixture_validates_against_schema():
    payload = json.loads((FIXTURES / "retrieval" / "sample_retrieval.json").read_text(encoding="utf-8"))

    retrieval = RetrievalOutput.model_validate(payload)

    assert retrieval.status == "ok"
    assert retrieval.hits[0].chunk_id == "fixture_rotor_doc_p0001_00001"
    assert retrieval.hits[0].reason


def test_zh_retrieval_fixture_validates_against_schema():
    payload = json.loads((FIXTURES / "retrieval" / "sample_zh_retrieval.json").read_text(encoding="utf-8"))

    retrieval = RetrievalOutput.model_validate(payload)

    assert retrieval.status == "ok"
    assert retrieval.intent == "engineering"
    assert retrieval.hits[0].chunk_id == "fixture_rotor_zh_doc_p0001_00001"
    assert retrieval.hits[0].pages == [1, 2]


def test_chunker_regression_matches_page_and_chunk_fixtures():
    page = _fixture_page()
    expected = _fixture_chunk()

    chunks = chunk_pages(
        [page],
        doc_id="fixture_rotor_doc",
        title="Rotor Vibration Fixture",
        source_path="tests/fixtures/raw/small_vibration_native.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=60,
    )

    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == expected["chunk_id"]
    assert chunks[0]["pages"] == expected["pages"]
    assert chunks[0]["text"] == expected["text"]
    assert chunks[0]["metadata"]["section_key"] == expected["metadata"]["section_key"]
    assert chunks[0]["citation_anchor"] == "Rotor Vibration Fixture, p. 1"
    # Obj3 keys: chunker emits them, committed fixture carries them, they agree.
    assert chunks[0]["metadata"]["section_parent_keys"] == expected["metadata"]["section_parent_keys"] == []
    assert (
        chunks[0]["metadata"]["bibliography"]
        == expected["metadata"]["bibliography"]
        == {"year": None, "authors": [], "publisher": None}
    )


def test_chunker_regression_matches_zh_cross_page_fixture():
    pages = _fixture_zh_pages()
    expected = _fixture_zh_chunk()

    chunks = chunk_pages(
        pages,
        doc_id="fixture_rotor_zh_doc",
        title="转子阻尼中文样例",
        source_path="tests/fixtures/raw/small_vibration_zh.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=60,
    )

    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == expected["chunk_id"]
    assert chunks[0]["pages"] == [1, 2]
    assert chunks[0]["metadata"]["page_boundary_crossed"] is True
    assert chunks[0]["text"] == expected["text"]
    # Heading-less zh front matter -> no parents; no bibliography passed -> defaults.
    assert chunks[0]["metadata"]["section_parent_keys"] == expected["metadata"]["section_parent_keys"] == []
    assert (
        chunks[0]["metadata"]["bibliography"]
        == expected["metadata"]["bibliography"]
        == {"year": None, "authors": [], "publisher": None}
    )


def test_pdf_pipeline_output_stays_aligned_with_chunk_fixture(tmp_path):
    pdf = FIXTURES / "raw" / "small_vibration_native.pdf"
    document = classify_document(pdf)
    settings = load(_project_workspace(tmp_path / "workspace"))

    result = chunk_document_pages(document, settings=settings, max_pages=1, write_output=True)
    produced = _jsonl(Path(result["chunks_output_path"]))[0]
    fixture = _fixture_chunk()

    assert result["status"] == "ok"
    assert produced["pages"] == fixture["pages"]
    assert produced["text"] == fixture["text"]
    assert produced["metadata"]["section_key"] == fixture["metadata"]["section_key"]
    assert produced["metadata"]["section_title"] == fixture["metadata"]["section_title"]


def test_zh_pdf_pipeline_output_stays_aligned_with_chunk_fixture(tmp_path):
    pdf = FIXTURES / "raw" / "small_vibration_zh.pdf"
    document = classify_document(pdf)
    settings = load(_project_workspace(tmp_path / "workspace"))

    result = chunk_document_pages(document, settings=settings, max_pages=2, write_output=True)
    produced = _jsonl(Path(result["chunks_output_path"]))[0]
    fixture = _fixture_zh_chunk()

    assert result["status"] == "ok"
    assert produced["page_start"] == 1
    assert produced["page_end"] == 2
    assert produced["pages"] == fixture["pages"]
    assert produced["text"] == fixture["text"]
    assert produced["metadata"]["section_key"] == fixture["metadata"]["section_key"]
    assert produced["metadata"]["page_boundary_crossed"] is True


def test_zh_docx_pipeline_output_stays_aligned_with_chunk_fixture(tmp_path):
    docx = FIXTURES / "raw" / "small_vibration_zh.docx"
    document = classify_document(docx)
    settings = load(_project_workspace(tmp_path / "workspace"))

    result = chunk_document_pages(document, settings=settings, max_pages=1, write_output=True)
    produced = _jsonl(Path(result["chunks_output_path"]))[0]
    fixture = _fixture_zh_docx_chunk()

    assert result["status"] == "ok"
    assert produced["pages"] == fixture["pages"]
    assert produced["text"] == fixture["text"]
    assert produced["metadata"]["section_key"] == fixture["metadata"]["section_key"]
    assert produced["metadata"]["section_title"] == fixture["metadata"]["section_title"]


def test_fixture_pdfs_have_no_recoverable_bibliography():
    # The committed fixture PDFs carry no author/year, which is *why* their chunk
    # fixtures hold empty bibliography defaults and Phase-1 citation anchors. Pin
    # it so a future PDF that gains metadata flags the now-stale fixtures.
    for name in ("small_vibration_native.pdf", "small_vibration_zh.pdf"):
        bib = extract_bibliography(FIXTURES / "raw" / name)
        assert bib.has_author_year() is False
        assert bib.year is None
        assert bib.authors == []
        assert bib.publisher is None


def test_pdf_pipeline_threads_bibliography_into_chunk_metadata_and_anchor(tmp_path):
    import fitz  # type: ignore

    pdf = tmp_path / "bibliography_fixture.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Chapter 1 Rotor Dynamics\n"
        "Rotor vibration evidence near critical speed needs enough text for native parsing.\n"
        "Condition monitoring records amplitude, phase, orbit, damping, and speed trends.",
        fontsize=12,
    )
    doc.set_metadata({"author": "Bently; Hatch", "creationDate": "D:20200101000000"})
    doc.save(pdf)
    doc.close()

    document = classify_document(pdf)
    settings = load(_project_workspace(tmp_path / "workspace"))
    result = chunk_document_pages(document, settings=settings, max_pages=1, write_output=True)
    produced = _jsonl(Path(result["chunks_output_path"]))[0]

    assert result["status"] == "ok"
    assert produced["metadata"]["bibliography"] == {
        "year": 2020,
        "authors": ["Bently", "Hatch"],
        "publisher": None,
    }
    assert produced["citation_anchor"] == "Bently et al. (2020), p. 1"


def test_fixture_chunk_supports_query_normalize():
    normalized = normalize("rotor unbalance critical speed")

    assert "rotor unbalance critical speed" in normalized["normalized_query"]
    assert normalized["intent_hint"] == "engineering"


def test_fixture_chunk_supports_search():
    chunks = load_chunks(chunk_paths=[FIXTURES / "chunks" / "sample_chunks.jsonl"])

    result = search("rotor unbalance critical speed", chunks=chunks, top_k=1)

    assert result["status"] == "ok"
    assert result["hits"][0]["chunk_id"] == chunks[0]["chunk_id"]


def test_zh_fixture_chunk_supports_search():
    chunks = load_chunks(chunk_paths=[FIXTURES / "chunks" / "sample_zh_chunks.jsonl"])

    result = search("阻尼比 临界转速 转子振动", chunks=chunks, top_k=1)

    assert result["status"] == "ok"
    assert result["hits"][0]["chunk_id"] == chunks[0]["chunk_id"]
    assert result["hits"][0]["pages"] == [1, 2]


def test_fixture_chunk_supports_evidence_helpers():
    chunks = load_chunks(chunk_paths=[FIXTURES / "chunks" / "sample_chunks.jsonl"])

    evidence = chunk_text_evidence_row(chunks[0])
    citation = citation_from_chunk(chunks[0])

    assert evidence["evidence_kind"] == "text"
    assert evidence["pages"] == [1]
    assert citation.evidence_type == "documented"
    assert citation.pages == [1]
