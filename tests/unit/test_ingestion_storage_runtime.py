from vibration_agent.config import load
from vibration_agent.ingestion import pipeline
from vibration_agent.schemas import DocumentClassification, EmbeddingRecord
from vibration_agent.storage import ingestion as storage_ingestion


def _manifest(tmp_path):
    return {
        "schema_version": "0.1",
        "status": "ok",
        "doc_id": "doc1",
        "title": "Rotor Manual",
        "source_type": "manual",
        "input": {
            "source_path": str(tmp_path / "manual.pdf"),
            "filename": "manual.pdf",
            "kind": "pdf",
            "sha256": "abc123",
            "language": "en",
        },
        "counts": {"processed_pages": 1},
    }


def _chunk():
    return {
        "chunk_id": "doc1_p0001_00001",
        "doc_id": "doc1",
        "source_type": "manual",
        "page_start": 1,
        "page_end": 1,
        "pages": [1],
        "chunk_type": "body",
        "text": "Rotor damping evidence.",
        "metadata": {},
        "assets": [],
    }


def _result(tmp_path):
    return {
        "status": "ok",
        "stage": "document_structured_export_batch",
        "documents": [{"manifest": _manifest(tmp_path), "chunks": [_chunk()]}],
        "warnings": [],
    }


def test_ingestion_pipeline_attaches_storage_summary_when_exports_are_built(tmp_path, monkeypatch):
    # WHY: Docker-backed ingestion must be observable from the CLI/API result, not
    # hidden as an untested side effect after chunk export.
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    classification = DocumentClassification(
        doc_id="doc1",
        source_path=str(source),
        filename=source.name,
        suffix=".pdf",
        kind="pdf",
        file_size=source.stat().st_size,
        sha256="abc123",
        page_count=1,
        processing_strategy="native_pdf",
        language="en",
    )
    seen = {}

    monkeypatch.setattr(pipeline, "scan_inputs", lambda *args, **kwargs: [classification])
    monkeypatch.setattr(
        pipeline,
        "chunk_document_pages",
        lambda *args, **kwargs: {"status": "ok", "manifest": _manifest(tmp_path), "chunks": [_chunk()]},
    )

    def fake_persist(result, *, settings):
        seen["stage"] = result["stage"]
        return {
            "postgres": {"status": "disabled", "documents": 0, "chunks": 0},
            "qdrant": {"status": "disabled", "collection": None, "points": 0, "chunks": 0, "embeddable_chunks": 0},
            "warnings": [],
        }

    monkeypatch.setattr(pipeline, "persist_ingestion_result", fake_persist)

    result = pipeline.chunk_documents(source, settings=load(), source_type="manual")

    assert seen["stage"] == "document_structured_export_batch"
    assert result["storage"]["postgres"]["status"] == "disabled"


def test_qdrant_ingestion_upserts_only_when_embeddings_are_non_empty(tmp_path, monkeypatch):
    # WHY: a live Qdrant service is not enough; ingest must pass actual vectors to
    # make dense retrieval able to observe the newly ingested chunks.
    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = "test_chunks"
    settings.database.postgres_enabled = False
    calls = {}

    monkeypatch.setattr(storage_ingestion.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        storage_ingestion.qdrant,
        "delete_chunk_points_for_documents",
        lambda client, doc_ids, *, collection: calls.update({"deleted_doc_ids": doc_ids}) or len(doc_ids),
    )
    monkeypatch.setattr(
        storage_ingestion,
        "embed_texts",
        lambda texts, **kwargs: [
            EmbeddingRecord(text_hash="h1", vector=[1.0, 0.0], dimension=2, model_name="fake-model")
        ],
    )

    def fake_upsert(client, chunks, *, embeddings, collection, embedding_model, embedding_version):
        calls["collection"] = collection
        calls["embeddings"] = embeddings
        return len(embeddings)

    monkeypatch.setattr(storage_ingestion.qdrant, "upsert_chunk_points", fake_upsert)

    summary = storage_ingestion.persist_ingestion_result(_result(tmp_path), settings=settings)

    assert summary["qdrant"]["status"] == "ok"
    assert summary["qdrant"]["points"] == 1
    assert summary["qdrant"]["embeddable_chunks"] == 1
    assert calls["collection"] == "test_chunks"
    assert calls["embeddings"] == {"doc1_p0001_00001": [1.0, 0.0]}
    assert calls["deleted_doc_ids"] == ["doc1"]


def test_qdrant_ingestion_reports_skipped_when_embeddings_are_empty(tmp_path, monkeypatch):
    # WHY: with embeddings disabled, Qdrant cannot receive usable points even if
    # the Docker service is healthy; the ingest result must say that explicitly.
    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.postgres_enabled = False
    settings.embeddings.enabled = False
    calls = {}
    monkeypatch.setattr(storage_ingestion.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        storage_ingestion.qdrant,
        "delete_chunk_points_for_documents",
        lambda client, doc_ids, *, collection: calls.update({"deleted_doc_ids": doc_ids}) or len(doc_ids),
    )

    summary = storage_ingestion.persist_ingestion_result(_result(tmp_path), settings=settings)

    assert summary["qdrant"]["status"] == "skipped"
    assert summary["qdrant"]["points"] == 0
    assert summary["qdrant"]["embeddable_chunks"] == 1
    assert "no non-empty embeddings" in summary["warnings"][0]
    assert calls["deleted_doc_ids"] == ["doc1"]


def test_qdrant_ingestion_skips_blank_text_chunks_before_embedding(tmp_path, monkeypatch):
    # WHY: full-corpus validation should compare Qdrant points with chunks that
    # can actually produce meaningful vectors, not figure/table placeholders.
    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.postgres_enabled = False
    settings.embeddings.enabled = True
    result = _result(tmp_path)
    result["documents"][0]["chunks"] = [{**_chunk(), "text": "   "}]
    calls = {"embed": 0}

    def fake_embed(*args, **kwargs):
        calls["embed"] += 1
        return []

    monkeypatch.setattr(storage_ingestion, "embed_texts", fake_embed)
    monkeypatch.setattr(storage_ingestion.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        storage_ingestion.qdrant,
        "delete_chunk_points_for_documents",
        lambda client, doc_ids, *, collection: len(doc_ids),
    )

    summary = storage_ingestion.persist_ingestion_result(result, settings=settings)

    assert calls["embed"] == 0
    assert summary["qdrant"]["status"] == "skipped"
    assert summary["qdrant"]["chunks"] == 1
    assert summary["qdrant"]["embeddable_chunks"] == 0
    assert "no chunks with non-empty text" in summary["warnings"][0]
