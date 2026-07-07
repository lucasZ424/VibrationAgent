"""Reproducible PostgreSQL-to-Qdrant corpus reindex."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from vibration_agent.config import Settings
from vibration_agent.retrieval.embeddings import embed_texts
from vibration_agent.schemas import EmbeddingRecord

from . import qdrant
from .qdrant_client import collection_vector_contract

Embedder = Callable[..., list[EmbeddingRecord]]
RuntimeStateRefresher = Callable[[], None]


def _refresh_runtime_retrieval_state() -> None:
    from vibration_agent.retrieval.hybrid import clear_runtime_retrieval_state

    clear_runtime_retrieval_state()


def load_postgres_chunks(conn: Any) -> list[dict[str, Any]]:
    sql = """
        SELECT c.external_id, d.external_id, c.page_start, c.page_end, c.pages,
               c.chunk_type, c.text, c.citation_anchor, c.source_type, c.topic,
               d.title, d.file_path
          FROM chunks c JOIN documents d ON d.id = c.doc_id
         WHERE c.external_id IS NOT NULL AND btrim(c.text) <> ''
         ORDER BY c.external_id
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    except Exception as exc:
        raise RuntimeError(
            "Obj3 reindex schema is unavailable; apply migration 004 and re-ingest before reindex."
        ) from exc
    chunks: list[dict[str, Any]] = []
    for row in rows:
        source_path = str(row[11] or "")
        chunks.append(
            {
                "chunk_id": str(row[0]),
                "doc_id": str(row[1] or ""),
                "page_start": row[2],
                "page_end": row[3],
                "pages": list(row[4] or []),
                "chunk_type": row[5],
                "text": row[6],
                "citation_anchor": row[7],
                "source_type": row[8],
                "topic": row[9],
                "source_title": row[10],
                "source_path": source_path,
                "source_filename": source_path.replace("\\", "/").rsplit("/", 1)[-1],
            }
        )
    return chunks


def corpus_fingerprint(chunks: Sequence[Mapping[str, Any]]) -> str:
    """Fingerprint text plus payload identity that must reach Qdrant.

    WHY: Obj7B can change citation/source payloads without changing chunk text.
    Reusing an old checkpoint in that case would skip the upsert that refreshes
    Qdrant metadata.
    """
    fields = ("chunk_id", "text", "source_type", "source_filename", "source_title", "source_path", "title")
    material = "\n".join(
        json.dumps({field: chunk.get(field) for field in fields}, ensure_ascii=False, sort_keys=True)
        for chunk in chunks
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _source_counts(chunks: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(chunk.get("source_type") or "unknown") for chunk in chunks).items()))


def _write_checkpoint(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_reindex(
    chunks: Sequence[Mapping[str, Any]],
    *,
    client: Any,
    settings: Settings,
    execute: bool,
    checkpoint_path: Path,
    recreate_collection: bool = False,
    embedder: Embedder = embed_texts,
    refresh_runtime_state: RuntimeStateRefresher = _refresh_runtime_retrieval_state,
) -> dict[str, Any]:
    if not chunks:
        raise RuntimeError("No reindexable chunks found; apply migration 004 and re-ingest before reindex.")
    expected_dimension = settings.database.qdrant_vector_size
    collection = settings.database.qdrant_collection
    fingerprint = corpus_fingerprint(chunks)
    source_counts = _source_counts(chunks)
    contract = collection_vector_contract(client, collection=collection)
    if contract and (contract["size"] != expected_dimension or contract["distance"].casefold() != "cosine"):
        if not recreate_collection:
            raise RuntimeError(
                f"Qdrant vector contract mismatch: existing={contract}, expected="
                f"{{'size': {expected_dimension}, 'distance': 'Cosine'}}; explicit recreate required."
            )
    report: dict[str, Any] = {
        "schema_version": "phase5.obj3_reindex.report.v1",
        "status": "dry_run" if not execute else "running",
        "collection": collection,
        "embedding_model": settings.embeddings.model_name,
        "embedding_version": settings.embeddings.model_version,
        "embedding_dimension": expected_dimension,
        "distance": qdrant.VECTOR_DISTANCE,
        "corpus_fingerprint": fingerprint,
        "embeddable_chunks": len(chunks),
        "source_type_counts": source_counts,
        "processed_chunks": 0,
        "errors": [],
    }
    if not execute:
        return report
    if not settings.embeddings.enabled or not settings.database.qdrant_enabled:
        raise RuntimeError("Reindex execution requires both embeddings and Qdrant to be enabled.")
    start = 0
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        identity = (
            checkpoint.get("corpus_fingerprint"),
            checkpoint.get("collection"),
            checkpoint.get("embedding_model"),
            checkpoint.get("embedding_version"),
            checkpoint.get("embedding_dimension"),
        )
        expected_identity = (
            fingerprint,
            collection,
            settings.embeddings.model_name,
            settings.embeddings.model_version,
            expected_dimension,
        )
        if identity != expected_identity:
            raise RuntimeError("Checkpoint does not match the active corpus/model; remove it or use another path.")
        start = int(checkpoint.get("processed_chunks", 0))
    if recreate_collection:
        if start:
            raise RuntimeError("Collection recreation cannot resume a partially completed checkpoint.")
        if contract:
            client.delete_collection(collection_name=collection)
        qdrant.initialize_collection(client, collection=collection, vector_size=expected_dimension)
    batch_size = settings.embeddings.batch_size
    try:
        for offset in range(start, len(chunks), batch_size):
            batch = list(chunks[offset : offset + batch_size])
            records = embedder([str(chunk["text"]) for chunk in batch], settings=settings)
            if any(record.provider == "fallback_token_features" or not record.vector for record in records):
                raise RuntimeError("Embedding fallback cannot be written or reported as ANN.")
            dimensions = {record.dimension for record in records}
            if dimensions != {expected_dimension}:
                raise RuntimeError(
                    f"Embedding dimension mismatch: got {sorted(dimensions)}, "
                    f"expected {expected_dimension}."
                )
            embeddings = {str(chunk["chunk_id"]): record.vector for chunk, record in zip(batch, records, strict=True)}
            qdrant.upsert_chunk_points(
                client,
                batch,
                embeddings=embeddings,
                collection=collection,
                embedding_model=settings.embeddings.model_name,
                embedding_version=settings.embeddings.model_version,
                batch_size=batch_size,
                retry_attempts=2,
            )
            report["processed_chunks"] = offset + len(batch)
            _write_checkpoint(checkpoint_path, report)
    except Exception as exc:
        report["status"] = "failed"
        report["errors"] = [f"{type(exc).__name__}: {exc}"]
        _write_checkpoint(checkpoint_path, report)
        raise
    payloads = qdrant.load_chunk_payloads(client, collection=collection)
    qdrant_counts = _source_counts(payloads)
    provenance_mismatches = [
        str(payload.get("chunk_id") or "unknown")
        for payload in payloads
        if payload.get("embedding_model") != settings.embeddings.model_name
        or payload.get("embedding_version") != settings.embeddings.model_version
        or payload.get("embedding_dimension") != expected_dimension
    ]
    report["qdrant_points"] = len(payloads)
    report["qdrant_source_type_counts"] = qdrant_counts
    report["provenance_mismatch_chunk_ids"] = provenance_mismatches
    report["parity"] = (
        len(payloads) == len(chunks)
        and qdrant_counts == source_counts
        and not provenance_mismatches
    )
    report["status"] = "complete" if report["parity"] else "parity_failed"
    report["runtime_state_refreshed"] = False
    if report["status"] == "complete":
        refresh_runtime_state()
        report["runtime_state_refreshed"] = True
    _write_checkpoint(checkpoint_path, report)
    return report
