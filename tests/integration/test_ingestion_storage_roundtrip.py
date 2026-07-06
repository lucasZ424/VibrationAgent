import uuid

import pytest

from vibration_agent.config import load
from vibration_agent.schemas import EmbeddingRecord
from vibration_agent.storage import ingestion as storage_ingestion
from vibration_agent.storage import postgres_client, qdrant
from vibration_agent.storage.qdrant_client import create_client

pytestmark = pytest.mark.integration


def _ingestion_result(tmp_path, marker: str):
    doc_id = f"doc_{marker}"
    chunk_id = f"{doc_id}_p0001_00001"
    source_path = tmp_path / f"{marker}.pdf"
    source_path.write_bytes(b"%PDF-1.4\n")
    chunk = {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "title": "Rotor Storage Smoke",
        "source_type": "manual",
        "source_path": str(source_path),
        "page_start": 1,
        "page_end": 1,
        "pages": [1],
        "chunk_type": "body",
        "text": f"live storage smoke rotor damping {marker}",
        "metadata": {},
        "assets": [],
    }
    manifest = {
        "schema_version": "0.1",
        "status": "ok",
        "doc_id": doc_id,
        "title": "Rotor Storage Smoke",
        "source_type": "manual",
        "input": {
            "source_path": str(source_path),
            "filename": source_path.name,
            "kind": "pdf",
            "sha256": marker,
            "language": "en",
        },
        "counts": {"processed_pages": 1, "chunk_count": 1},
    }
    return {
        "status": "ok",
        "stage": "document_structured_export_batch",
        "documents": [{"manifest": manifest, "chunks": [chunk]}],
        "warnings": [],
    }


def test_live_ingestion_persists_postgres_and_qdrant(tmp_path, monkeypatch):
    # WHY: when Docker services are enabled, ingest must be observable in both
    # runtime stores, not only in file exports or dry-run mapping tests.
    pytest.importorskip("psycopg")
    pytest.importorskip("qdrant_client")
    settings = load()
    settings.database.postgres_enabled = True
    settings.database.postgres_url = settings.database.postgres_url or "postgresql://vib:vib@localhost:5432/vibration"
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = f"test_ingest_{uuid.uuid4().hex}"

    try:
        pg_conn = postgres_client.connect(settings.database.postgres_url, connect_timeout=2.0)
    except Exception as exc:  # noqa: BLE001 - live Docker may be unavailable
        pytest.skip(f"Postgres instance is not available: {exc}")
    try:
        qdrant_client = create_client(
            url=settings.database.qdrant_url,
            api_key=settings.database.qdrant_api_key,
            timeout=settings.database.qdrant_timeout,
        )
        qdrant_client.get_collections()
    except Exception as exc:  # noqa: BLE001 - live Docker may be unavailable
        pg_conn.close()
        pytest.skip(f"Qdrant instance is not available: {exc}")

    marker = f"rt_{uuid.uuid4().hex}"
    result = _ingestion_result(tmp_path, marker)
    chunk_id = result["documents"][0]["chunks"][0]["chunk_id"]

    monkeypatch.setattr(
        storage_ingestion,
        "embed_texts",
        lambda texts, **kwargs: [
            EmbeddingRecord(text_hash="h1", vector=[1.0, 0.0], dimension=2, model_name="fake-model")
        ],
    )

    try:
        summary = storage_ingestion.persist_ingestion_result(result, settings=settings)

        assert summary["postgres"] == {"status": "ok", "documents": 1, "chunks": 1}
        assert summary["qdrant"]["status"] == "ok"
        assert summary["qdrant"]["points"] == 1
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT c.text FROM documents d JOIN chunks c ON c.doc_id = d.id WHERE d.hash = %s",
                (marker,),
            )
            assert cur.fetchone()[0] == result["documents"][0]["chunks"][0]["text"]

        hits = qdrant.search_chunks(qdrant_client, [1.0, 0.0], top_k=1, collection=settings.database.qdrant_collection)
        assert hits[0]["chunk"]["chunk_id"] == chunk_id
    finally:
        try:
            pg_conn.rollback()
            with pg_conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE hash = %s", (marker,))
            pg_conn.commit()
        except Exception:
            pg_conn.rollback()
        pg_conn.close()
        try:
            qdrant_client.delete_collection(settings.database.qdrant_collection)
        except Exception:
            pass
