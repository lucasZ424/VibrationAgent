import json
from pathlib import Path

from vibration_agent.config import load
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


def test_retrieval_fixture_validates_against_schema():
    payload = json.loads((FIXTURES / "retrieval" / "sample_retrieval.json").read_text(encoding="utf-8"))

    retrieval = RetrievalOutput.model_validate(payload)

    assert retrieval.status == "ok"
    assert retrieval.hits[0].chunk_id == "fixture_rotor_doc_p0001_00001"
    assert retrieval.hits[0].reason


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


def test_fixture_chunk_supports_query_normalize():
    normalized = normalize("rotor unbalance critical speed")

    assert "rotor unbalance critical speed" in normalized["normalized_query"]
    assert normalized["intent_hint"] == "engineering"


def test_fixture_chunk_supports_search():
    chunks = load_chunks(chunk_paths=[FIXTURES / "chunks" / "sample_chunks.jsonl"])

    result = search("rotor unbalance critical speed", chunks=chunks, top_k=1)

    assert result["status"] == "ok"
    assert result["hits"][0]["chunk_id"] == chunks[0]["chunk_id"]


def test_fixture_chunk_supports_evidence_helpers():
    chunks = load_chunks(chunk_paths=[FIXTURES / "chunks" / "sample_chunks.jsonl"])

    evidence = chunk_text_evidence_row(chunks[0])
    citation = citation_from_chunk(chunks[0])

    assert evidence["evidence_kind"] == "text"
    assert evidence["pages"] == [1]
    assert citation.evidence_type == "documented"
    assert citation.pages == [1]