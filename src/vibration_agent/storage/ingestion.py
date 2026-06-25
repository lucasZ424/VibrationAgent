"""Runtime persistence for structured ingestion exports."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from vibration_agent.config import Settings
from vibration_agent.retrieval.embeddings import embed_texts

from . import postgres_client, qdrant
from .postgres import prepare_ingestion_plan


def _storage_disabled_summary() -> dict[str, Any]:
    return {
        "postgres": {"status": "disabled", "documents": 0, "chunks": 0},
        "qdrant": {"status": "disabled", "collection": None, "points": 0, "chunks": 0, "embeddable_chunks": 0},
        "warnings": [],
    }


def _insert_returning_id(cur: Any, table: str, row: Mapping[str, Any]) -> int:
    columns = list(row.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    cur.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id",
        [row[column] for column in columns],
    )
    return int(cur.fetchone()[0])


def _upsert_document(cur: Any, row: Mapping[str, Any]) -> int:
    columns = list(row.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    values = [row[column] for column in columns]
    if row.get("hash"):
        assignments = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "hash")
        cur.execute(
            f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT (hash) DO UPDATE SET {assignments} RETURNING id",
            values,
        )
    else:
        cur.execute(
            f"INSERT INTO documents ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id",
            values,
        )
    return int(cur.fetchone()[0])


def _replace_postgres_document(conn: Any, manifest: Mapping[str, Any], chunks: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Replace one document's relational rows from the canonical manifest/chunks.

    WHY: ingestion is repeatable during corpus refinement. Re-ingesting the same
    hash should refresh sections/chunks instead of failing on documents.hash.
    """
    plan = prepare_ingestion_plan(manifest, chunks)
    rows = plan.rows
    sql_rows = plan.sql_rows()
    with conn.cursor() as cur:
        doc_db_id = _upsert_document(cur, sql_rows["documents"][0])
        cur.execute("DELETE FROM figures_tables WHERE doc_id = %s", (doc_db_id,))
        cur.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_db_id,))
        cur.execute("DELETE FROM document_sections WHERE doc_id = %s", (doc_db_id,))

        section_ids: dict[str, int] = {}
        for row in rows["document_sections"]:
            sql_row = {key: value for key, value in row.items() if key != "_meta"}
            sql_row["doc_id"] = doc_db_id
            section_id = _insert_returning_id(cur, "document_sections", sql_row)
            section_key = row.get("_meta", {}).get("section_key")
            if section_key:
                section_ids[str(section_key)] = section_id

        chunk_ids: dict[str, int] = {}
        for row in rows["chunks"]:
            meta = row.get("_meta", {})
            sql_row = {key: value for key, value in row.items() if key != "_meta"}
            sql_row["doc_id"] = doc_db_id
            section_key = meta.get("section_key")
            sql_row["section_id"] = section_ids.get(str(section_key)) if section_key else None
            chunk_db_id = _insert_returning_id(cur, "chunks", sql_row)
            if meta.get("chunk_id"):
                chunk_ids[str(meta["chunk_id"])] = chunk_db_id

        for row in rows["figures_tables"]:
            meta = row.get("_meta", {})
            sql_row = {key: value for key, value in row.items() if key != "_meta"}
            sql_row["doc_id"] = doc_db_id
            sql_row["related_chunk_ids"] = [
                chunk_ids[chunk_ref]
                for chunk_ref in meta.get("related_chunk_refs", [])
                if chunk_ref in chunk_ids
            ]
            _insert_returning_id(cur, "figures_tables", sql_row)
    conn.commit()
    counts = plan.counts()
    return {"documents": counts["documents"], "chunks": counts["chunks"]}


def _persist_postgres(documents: Sequence[Mapping[str, Any]], settings: Settings) -> dict[str, Any]:
    database = settings.database
    if not database.postgres_enabled:
        return {"status": "disabled", "documents": 0, "chunks": 0}
    if not documents:
        return {"status": "skipped", "documents": 0, "chunks": 0}
    if not database.postgres_url:
        raise RuntimeError("POSTGRES_ENABLED is true but POSTGRES_URL is empty.")

    migrations_dir = settings.paths.workspace / "db" / "postgres" / "migrations"
    total_documents = 0
    total_chunks = 0
    conn = postgres_client.connect(database.postgres_url, connect_timeout=database.postgres_timeout)
    try:
        postgres_client.apply_migrations(conn, migrations_dir)
        for document in documents:
            manifest = document.get("manifest")
            chunks = document.get("chunks") or []
            if not isinstance(manifest, Mapping) or not chunks:
                continue
            counts = _replace_postgres_document(conn, manifest, list(chunks))
            total_documents += counts["documents"]
            total_chunks += counts["chunks"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"status": "ok", "documents": total_documents, "chunks": total_chunks}


def _persist_qdrant(documents: Sequence[Mapping[str, Any]], settings: Settings) -> tuple[dict[str, Any], list[str]]:
    database = settings.database
    if not database.qdrant_enabled:
        return {"status": "disabled", "collection": None, "points": 0, "chunks": 0, "embeddable_chunks": 0}, []

    chunks = [chunk for document in documents for chunk in document.get("chunks", []) or []]
    doc_ids = sorted(
        {
            str(manifest.get("doc_id"))
            for document in documents
            if isinstance((manifest := document.get("manifest")), Mapping) and manifest.get("doc_id")
        }
    )
    client = qdrant.runtime_client(settings)
    qdrant.delete_chunk_points_for_documents(
        client,
        doc_ids,
        collection=database.qdrant_collection,
    )
    embeddable_chunks = [chunk for chunk in chunks if str(chunk.get("text") or "").strip()]
    if not chunks:
        return {
            "status": "skipped",
            "collection": database.qdrant_collection,
            "points": 0,
            "chunks": 0,
            "embeddable_chunks": 0,
        }, []
    if not embeddable_chunks:
        return {
            "status": "skipped",
            "collection": database.qdrant_collection,
            "points": 0,
            "chunks": len(chunks),
            "embeddable_chunks": 0,
        }, ["Qdrant enabled but no chunks with non-empty text were available; vector upsert skipped."]

    records = embed_texts([str(chunk.get("text") or "") for chunk in embeddable_chunks], settings=settings)
    warnings = list(dict.fromkeys(warning for record in records for warning in record.warnings))
    embeddings = {
        str(chunk["chunk_id"]): record.vector
        for chunk, record in zip(embeddable_chunks, records, strict=True)
        if chunk.get("chunk_id") and record.vector
    }
    if not embeddings:
        warnings.append("Qdrant enabled but no non-empty embeddings were produced; vector upsert skipped.")
        return {
            "status": "skipped",
            "collection": database.qdrant_collection,
            "points": 0,
            "chunks": len(chunks),
            "embeddable_chunks": len(embeddable_chunks),
        }, warnings

    point_count = qdrant.upsert_chunk_points(
        client,
        chunks,
        embeddings=embeddings,
        collection=database.qdrant_collection,
        embedding_model=settings.embeddings.model_name,
        embedding_version=settings.embeddings.model_version,
    )
    return {
        "status": "ok",
        "collection": database.qdrant_collection,
        "points": point_count,
        "chunks": len(chunks),
        "embeddable_chunks": len(embeddable_chunks),
    }, warnings


def persist_ingestion_result(result: Mapping[str, Any], *, settings: Settings) -> dict[str, Any]:
    """Persist a ``chunk_documents`` result to enabled runtime stores."""
    documents = [document for document in result.get("documents", []) if isinstance(document, Mapping)]
    if not settings.database.postgres_enabled and not settings.database.qdrant_enabled:
        return _storage_disabled_summary()

    summary = _storage_disabled_summary()
    summary["postgres"] = _persist_postgres(documents, settings)
    qdrant_summary, warnings = _persist_qdrant(documents, settings)
    summary["qdrant"] = qdrant_summary
    summary["warnings"] = warnings
    return summary


__all__ = ["persist_ingestion_result"]
