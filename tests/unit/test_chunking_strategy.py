import pytest

from vibration_agent.ingestion.chunking import chunk_pages, chunk_sections
from vibration_agent.schemas import MemoryChunk, OcrPage, PageBlock


def _body(prefix: str, count: int) -> str:
    return "\n".join(f"{prefix} sentence {index}." for index in range(count))


def test_chunk_pages_preserves_section_boundaries_and_stable_ids(tmp_path):
    pages = [
        OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            ocr_confidence=0.91,
            blocks=[
                PageBlock(block_id="p0001_b0001", text="Chapter 1 Rotor Dynamics", block_type="title"),
                PageBlock(block_id="p0001_b0002", text=_body("rotor response", 8), block_type="body"),
            ],
        ),
        OcrPage(
            doc_id="doc1",
            page_no=2,
            primary_engine="paddleocr",
            ocr_confidence=0.83,
            blocks=[
                PageBlock(block_id="p0002_b0001", text="Chapter 2 Fault Diagnosis", block_type="title"),
                PageBlock(block_id="p0002_b0002", text=_body("fault diagnosis", 8), block_type="body"),
            ],
        ),
    ]

    chunks = chunk_pages(
        pages,
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=24,
        overlap_tokens=6,
    )
    rerun = chunk_pages(
        pages,
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=24,
        overlap_tokens=6,
    )

    assert [chunk["chunk_id"] for chunk in chunks] == [chunk["chunk_id"] for chunk in rerun]
    assert all(chunk["metadata"]["section_boundary_crossed"] is False for chunk in chunks)
    assert not any("Chapter 1 Rotor Dynamics" in chunk["text"] and "Chapter 2 Fault Diagnosis" in chunk["text"] for chunk in chunks)
    assert {chunk["topic"] for chunk in chunks} == {"Chapter 1 Rotor Dynamics", "Chapter 2 Fault Diagnosis"}
    assert all(chunk["pages"] for chunk in chunks)


def test_chunk_pages_keeps_page_enumeration_when_section_spans_pages(tmp_path):
    pages = [
        OcrPage(
            doc_id="doc1",
            page_no=4,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0004_b0001", text="1.1 Rotor Response", block_type="title"),
                PageBlock(block_id="p0004_b0002", text="Page four response evidence.", block_type="body"),
            ],
        ),
        OcrPage(
            doc_id="doc1",
            page_no=5,
            primary_engine="paddleocr",
            blocks=[PageBlock(block_id="p0005_b0001", text="Page five response evidence.", block_type="body")],
        ),
    ]

    chunks = chunk_pages(
        pages,
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=60,
    )

    assert len(chunks) == 1
    assert chunks[0]["page_start"] == 4
    assert chunks[0]["page_end"] == 5
    assert chunks[0]["pages"] == [4, 5]
    assert chunks[0]["metadata"]["page_boundary_crossed"] is True
    assert MemoryChunk.model_validate(chunks[0]).pages == [4, 5]


def test_chunk_sections_uses_structured_section_boundaries(tmp_path):
    sections = [
        {
            "title": "1.1 Rotor Response",
            "page_start": 4,
            "paragraphs": [
                {"page_no": 4, "text": "Response paragraph one."},
                {"page_no": 5, "text": "Response paragraph two."},
            ],
        },
        {
            "title": "1.2 Bearing Faults",
            "page_start": 6,
            "text": "Bearing fault paragraph.",
        },
    ]

    chunks = chunk_sections(
        sections,
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        target_tokens=600,
        overlap_tokens=60,
    )

    assert [chunk["topic"] for chunk in chunks] == ["1.1 Rotor Response", "1.2 Bearing Faults"]
    assert chunks[0]["pages"] == [4, 5]
    assert chunks[0]["metadata"]["section_key"] == "s0001"
    assert all(chunk["metadata"]["section_boundary_crossed"] is False for chunk in chunks)

def test_api_context_includes_readable_section_title(tmp_path):
    page = OcrPage(
        doc_id="doc1",
        page_no=1,
        primary_engine="paddleocr",
        blocks=[
            PageBlock(block_id="p0001_b0001", text="1.2.3 Detailed Rotor Orbit Interpretation", block_type="title"),
            PageBlock(block_id="p0001_b0002", text="Orbit interpretation body.", block_type="body"),
        ],
    )

    chunk = chunk_pages(
        [page],
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=600,
        overlap_tokens=60,
    )[0]

    assert "section_title=1.2.3 Detailed Rotor Orbit Interpretation" in chunk["api_context"]
    assert chunk["metadata"]["section_level"] == 3
    assert chunk["metadata"]["title_in_text"] is True
    assert chunk["metadata"]["section_boundary_policy"] == "flush_before_new_section"


def test_overlap_does_not_leak_across_section_boundaries(tmp_path):
    pages = [
        OcrPage(
            doc_id="doc1",
            page_no=1,
            primary_engine="paddleocr",
            blocks=[
                PageBlock(block_id="p0001_b0001", text="Chapter 1 Rotor Dynamics", block_type="title"),
                PageBlock(block_id="p0001_b0002", text=_body("rotor response", 6), block_type="body"),
                PageBlock(block_id="p0001_b0003", text="Chapter 2 Bearing Faults", block_type="title"),
                PageBlock(block_id="p0001_b0004", text="bearing fault body.", block_type="body"),
            ],
        )
    ]

    chunks = chunk_pages(
        pages,
        doc_id="doc1",
        title="Rotor Book",
        source_path=tmp_path / "book.pdf",
        source_type="book",
        target_tokens=22,
        overlap_tokens=20,
    )

    chapter_2_chunks = [chunk for chunk in chunks if chunk["topic"] == "Chapter 2 Bearing Faults"]
    assert chapter_2_chunks
    assert all("Chapter 1 Rotor Dynamics" not in chunk["text"] for chunk in chapter_2_chunks)
    assert all("rotor response" not in chunk["text"] for chunk in chapter_2_chunks)


def test_chunk_sections_requires_page_information(tmp_path):
    with pytest.raises(ValueError, match="page_start/page_no"):
        chunk_sections(
            [{"title": "1.1 Missing Page", "text": "No page anchor."}],
            doc_id="doc1",
            title="Rotor Book",
            source_path=tmp_path / "book.pdf",
        )