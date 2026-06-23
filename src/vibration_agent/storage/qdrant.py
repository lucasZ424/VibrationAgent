"""Qdrant payload mapping, dry-run planning, and runtime read/write helpers."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from vibration_agent.config import Settings

from .mappings import normalize_chunk_type
from .qdrant_client import create_client, ensure_collection, search_points, upsert_points

COLLECTION_CHUNKS = "chunks"
VECTOR_DISTANCE = "Cosine"
VECTOR_SIZE = 384


@dataclass(frozen=True)
class QdrantPoint:
    id: str
    vector: list[float] | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class QdrantWritePlan:
    collection: str
    points: list[QdrantPoint]
    vector_size: int = VECTOR_SIZE

    def dry_run(self, *, preview: int = 3) -> dict[str, Any]:
        missing_vectors = sum(1 for point in self.points if point.vector is None)
        return {
            "status": "dry_run",
            "target": "qdrant",
            "collection": self.collection,
            "distance": VECTOR_DISTANCE,
            "vector_size": self.vector_size,
            "point_count": len(self.points),
            "missing_vector_count": missing_vectors,
            "preview": [
                {"id": point.id, "has_vector": point.vector is not None, "payload": point.payload}
                for point in self.points[:preview]
            ],
        }


def stable_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vibration-agent:chunk:{chunk_id}"))


def chunk_payload(
    chunk: Mapping[str, Any],
    *,
    embedding_model: str | None = None,
    embedding_version: str | None = None,
) -> dict[str, Any]:
    metadata = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), Mapping) else {}
    return {
        "chunk_id": chunk.get("chunk_id"),
        "doc_id": chunk.get("doc_id"),
        "source_type": chunk.get("source_type"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "pages": chunk.get("pages", []),
        "chunk_type": normalize_chunk_type(chunk.get("chunk_type", "body")),
        "topic": chunk.get("topic"),
        "title": chunk.get("title"),
        "text": chunk.get("text"),
        "api_context": chunk.get("api_context"),
        "assets": chunk.get("assets", []),
        "section_key": metadata.get("section_key"),
        "citation_anchor": chunk.get("citation_anchor"),
        "token_estimate": chunk.get("token_estimate"),
        "needs_review_pages": chunk.get("needs_review_pages", []),
        "embedding_model": embedding_model,
        "embedding_version": embedding_version,
    }


def prepare_chunk_points(
    chunks: Iterable[Mapping[str, Any]],
    *,
    embeddings: Mapping[str, Sequence[float]] | None = None,
    embedding_model: str | None = None,
    embedding_version: str | None = None,
) -> QdrantWritePlan:
    vectors = embeddings or {}
    points = [
        QdrantPoint(
            id=stable_point_id(str(chunk["chunk_id"])),
            vector=list(vectors[str(chunk["chunk_id"])]) if str(chunk["chunk_id"]) in vectors else None,
            payload=chunk_payload(chunk, embedding_model=embedding_model, embedding_version=embedding_version),
        )
        for chunk in chunks
    ]
    vector_size = next((len(point.vector) for point in points if point.vector), VECTOR_SIZE)
    return QdrantWritePlan(collection=COLLECTION_CHUNKS, points=points, vector_size=vector_size)


def dry_run_chunks(
    chunks: Iterable[Mapping[str, Any]],
    *,
    embeddings: Mapping[str, Sequence[float]] | None = None,
    embedding_model: str | None = None,
    embedding_version: str | None = None,
) -> dict[str, Any]:
    return prepare_chunk_points(
        chunks,
        embeddings=embeddings,
        embedding_model=embedding_model,
        embedding_version=embedding_version,
    ).dry_run()


def runtime_client(settings: Settings):
    return create_client(
        url=settings.database.qdrant_url,
        api_key=settings.database.qdrant_api_key,
        timeout=settings.database.qdrant_timeout,
    )


def initialize_collection(
    client: Any,
    *,
    collection: str = COLLECTION_CHUNKS,
    vector_size: int = VECTOR_SIZE,
    distance: str = VECTOR_DISTANCE,
) -> None:
    ensure_collection(client, collection=collection, vector_size=vector_size, distance=distance)


def upsert_chunk_points(
    client: Any,
    chunks: Iterable[Mapping[str, Any]],
    *,
    embeddings: Mapping[str, Sequence[float]],
    collection: str = COLLECTION_CHUNKS,
    embedding_model: str | None = None,
    embedding_version: str | None = None,
) -> int:
    plan = prepare_chunk_points(
        chunks,
        embeddings=embeddings,
        embedding_model=embedding_model,
        embedding_version=embedding_version,
    )
    initialize_collection(client, collection=collection, vector_size=plan.vector_size)
    return upsert_points(client, collection=collection, points=plan.points)


def search_chunks(
    client: Any,
    query_vector: Sequence[float],
    *,
    top_k: int,
    collection: str = COLLECTION_CHUNKS,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for hit in search_points(client, collection=collection, query_vector=query_vector, top_k=top_k):
        payload = dict(hit.payload)
        if not payload.get("chunk_id"):
            continue
        results.append({"chunk": payload, "score": hit.score, "lane": "dense_qdrant"})
    return results


def client(url: str, api_key: str | None = None):
    return create_client(url=url, api_key=api_key or "")
