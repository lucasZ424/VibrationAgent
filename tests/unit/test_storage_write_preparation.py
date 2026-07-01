import re
from pathlib import Path

import pytest

from vibration_agent.storage.postgres import (
    POSTGRES_COLUMNS,
    POSTGRES_TABLES,
    PostgresWritePlan,
    citation_rows,
    figure_table_rows,
    prepare_ingestion_plan,
    qa_log_row,
    section_rows,
    term_rows,
    symbol_rows,
    unit_rows,
)
from vibration_agent.storage.qdrant import prepare_chunk_points
from vibration_agent.storage.redis_cache import prepare_manifest_cache


def _manifest():
    return {
        "schema_version": "0.1",
        "type": "document_ingestion_manifest",
        "status": "ok",
        "doc_id": "doc1",
        "title": "Rotor Book",
        "source_type": "book",
        "input": {
            "source_path": "C:/books/rotor.pdf",
            "filename": "rotor.pdf",
            "kind": "pdf",
            "sha256": "abc123",
            "language": "en",
            "doc_id_mode": "content",
            "processing_strategy": "native_pdf",
            "document_page_count": 5,
        },
        "counts": {"page_count": 5, "processed_pages": 5, "chunk_count": 1, "needs_review_page_count": 0, "total_token_estimate": 42},
        "needs_review_pages": [],
        "outputs": {},
        "warnings": [],
    }


def _chunk():
    return {
        "chunk_id": "doc1_p0001_00001",
        "doc_id": "doc1",
        "title": "Rotor Book",
        "source_type": "book",
        "source_path": "C:/books/rotor.pdf",
        "chunk_index": 1,
        "page_start": 1,
        "page_end": 2,
        "pages": [1, 2],
        "chunk_type": "body",
        "topic": "Chapter 1 Rotor Dynamics",
        "token_estimate": 42,
        "citation_anchor": "Rotor Book, pp. 1-2",
        "text": "Rotor dynamics text.",
        "metadata": {"section_key": "s0001", "section_title": "Chapter 1 Rotor Dynamics", "section_level": 1},
        "needs_review_pages": [],
        "assets": [
            {"asset_id": "doc1_p0001_body", "doc_id": "doc1", "page_no": 1, "object_type": "body", "asset_path": "chunk://doc1/body"},
            {"asset_id": "fig1", "doc_id": "doc1", "page_no": 2, "object_type": "figure", "asset_path": "C:/fig1.png", "text": "Figure 1 rotor orbit", "bbox": [1, 2, 3, 4]},
        ],
    }


def _parse_insertable_columns_from_sql() -> dict[str, tuple[str, ...]]:
    """Insertable columns across all migrations: CREATE TABLE, then ALTER ADD COLUMN.

    Spanning every ``*.sql`` (not just 001) keeps this guard honest as later
    migrations extend a table — e.g. the Obj7 qa_logs runtime columns in 002.
    """
    parsed: dict[str, list[str]] = {}
    for sql_path in sorted(Path("db/postgres/migrations").glob("*.sql")):
        text = sql_path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"CREATE TABLE\s+(\w+)\s*\((.*?)\n\);", text, re.S):
            table = match.group(1)
            columns: list[str] = []
            for raw_line in match.group(2).splitlines():
                line = raw_line.strip().rstrip(",")
                if not line or line.startswith("--"):
                    continue
                name = line.split()[0]
                if name.upper() in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK"}:
                    continue
                if name not in {"id", "created_at"}:
                    columns.append(name)
            parsed[table] = columns
        for table, column in re.findall(
            r"ALTER TABLE\s+(\w+)\s+ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)", text
        ):
            if column not in {"id", "created_at"}:
                parsed.setdefault(table, []).append(column)
    return {table: tuple(columns) for table, columns in parsed.items()}


def test_postgres_column_registry_matches_migration_insertable_columns():
    parsed = _parse_insertable_columns_from_sql()

    assert set(parsed) == set(POSTGRES_TABLES)
    assert parsed == POSTGRES_COLUMNS


def test_postgres_ingestion_plan_maps_manifest_chunks_and_assets():
    plan = prepare_ingestion_plan(_manifest(), [_chunk()])
    rows = plan.rows

    assert rows["documents"][0]["hash"] == "abc123"
    assert rows["documents"][0]["external_id"] == "doc1"
    assert rows["documents"][0]["file_path"] == "C:/books/rotor.pdf"
    assert rows["document_sections"][0]["heading"] == "Chapter 1 Rotor Dynamics"
    assert rows["chunks"][0]["chunk_type"] == "text"
    assert rows["chunks"][0]["token_count"] == 42
    assert rows["chunks"][0]["external_id"] == "doc1_p0001_00001"
    assert rows["chunks"][0]["pages"] == [1, 2]
    assert rows["chunks"][0]["source_type"] == "book"
    assert rows["chunks"][0]["_meta"]["chunk_id"] == "doc1_p0001_00001"
    assert rows["figures_tables"][0]["kind"] == "figure"
    assert rows["figures_tables"][0]["caption"] == "Figure 1 rotor orbit"
    assert rows["figures_tables"][0]["related_chunk_ids"] == []
    assert rows["figures_tables"][0]["_meta"]["related_chunk_refs"] == ["doc1_p0001_00001"]

    sql_rows = plan.sql_rows()
    assert "_meta" not in sql_rows["chunks"][0]
    assert "_meta" not in sql_rows["figures_tables"][0]

    dry_run = plan.dry_run()
    assert dry_run["status"] == "dry_run"
    assert dry_run["counts"]["documents"] == 1
    assert dry_run["counts"]["chunks"] == 1
    assert "sql_preview" in dry_run


def test_postgres_sql_rows_rejects_unknown_non_helper_keys():
    rows = {table: [] for table in POSTGRES_TABLES}
    rows["documents"] = [
        {
            "title": "Rotor Book",
            "type": "book",
            "file_path": "C:/books/rotor.pdf",
            "hashh": "typo",
            "_meta": {"allowed_helper": True},
        }
    ]
    plan = PostgresWritePlan(rows=rows)

    with pytest.raises(ValueError, match="Unknown Postgres column"):
        plan.sql_rows()


def test_postgres_helpers_keep_cross_document_local_ids_separate():
    other_chunk = _chunk().copy()
    other_chunk.update(
        {
            "chunk_id": "doc2_p0001_00001",
            "doc_id": "doc2",
            "metadata": {"section_key": "s0001", "section_title": "Other Chapter", "section_level": 1},
            "assets": [
                {
                    "asset_id": "fig1",
                    "doc_id": "doc2",
                    "page_no": 1,
                    "object_type": "figure",
                    "asset_path": "C:/doc2_fig1.png",
                    "text": "Figure 1 from another document",
                }
            ],
        }
    )

    sections = section_rows([_chunk(), other_chunk])
    figures = figure_table_rows([_chunk(), other_chunk])

    assert len(sections) == 2
    assert {row["_meta"]["section_key"] for row in sections} == {"s0001"}
    assert len(figures) == 2
    assert {row["_meta"]["logical_doc_id"] for row in figures} == {"doc1", "doc2"}


def test_postgres_ingestion_plan_rejects_mixed_document_chunks():
    other_chunk = _chunk().copy()
    other_chunk.update({"chunk_id": "doc2_p0001_00001", "doc_id": "doc2"})

    with pytest.raises(ValueError, match="one manifest document"):
        prepare_ingestion_plan(_manifest(), [_chunk(), other_chunk])


def test_postgres_auxiliary_rows_cover_taxonomy_citations_and_qa_logs():
    citation = citation_rows("answer-1", [{"chunk_id": "c1", "doc_id": "d1", "pages": [1], "confidence": 0.8}])[0]
    qa_log = qa_log_row(
        "What is rotor orbit?",
        intent="qa",
        chosen_skills=["s2_retrieval", "s3_qa_summary"],
        retrieved_chunks=["c1"],
        final_verdict="answered",
    )

    assert citation["_meta"]["logical_chunk_id"] == "c1"
    assert qa_log["retrieved_chunks"] == []
    assert qa_log["_meta"]["logical_retrieved_chunk_ids"] == ["c1"]
    assert term_rows([{"canonical_term": "damping", "aliases": ["damp"]}])[0]["canonical_term"] == "damping"
    assert symbol_rows([{"symbol": "zeta", "unit": "1"}])[0]["canonical_symbol"] == "zeta"
    assert unit_rows([{"quantity": "frequency", "unit": "Hz"}])[0]["canonical_units"] == "Hz"


def test_qdrant_plan_payload_and_missing_vector_dry_run():
    plan = prepare_chunk_points([_chunk()])
    point = plan.points[0]

    assert point.vector is None
    assert point.payload["chunk_id"] == "doc1_p0001_00001"
    assert point.payload["doc_id"] == "doc1"
    assert point.payload["page_start"] == 1
    assert point.payload["chunk_type"] == "text"
    assert point.payload["topic"] == "Chapter 1 Rotor Dynamics"
    dry_run = plan.dry_run()
    assert dry_run["collection"] == "chunks"
    assert dry_run["missing_vector_count"] == 1


def test_qdrant_plan_accepts_precomputed_embeddings_and_records_model():
    vector = [0.1] * 1024
    plan = prepare_chunk_points(
        [_chunk()],
        embeddings={"doc1_p0001_00001": vector},
        embedding_model="bge-m3",
        embedding_version="2026-05-test",
    )
    point = plan.points[0]

    assert point.vector == vector
    assert point.payload["embedding_model"] == "bge-m3"
    assert point.payload["embedding_version"] == "2026-05-test"
    assert plan.dry_run()["missing_vector_count"] == 0


def test_redis_manifest_cache_is_cache_only():
    plan = prepare_manifest_cache(_manifest(), ttl_seconds=30)
    item = plan.items[0]

    assert item.key == "vibration_agent:manifest:doc1"
    assert item.ttl_seconds == 30
    dry_run = plan.dry_run()
    assert dry_run["role"] == "cache_only"
    assert dry_run["item_count"] == 1
