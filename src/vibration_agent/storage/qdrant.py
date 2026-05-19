"""Qdrant payload mapping and dry-run write preparation.

Collection shape is documented in ``db/qdrant/collections.md``. Target 10 only
prepares points; embedding generation and runtime writes are activated later.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .mappings import normalize_chunk_type

COLLECTION_CHUNKS = "chunks"
VECTOR_DISTANCE = "Cosine"
VECTOR_SIZE = 1024


@dataclass(frozen=True)
class QdrantPoint:
    id: str
    vector: list[float] | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class QdrantWritePlan:
    collection: str
    points: list[QdrantPoint]

    def dry_run(self, *, preview: int = 3) -> dict[str, Any]:
        missing_vectors = sum(1 for point in self.points if point.vector is None)
        return {
            "status": "dry_run",
            "target": "qdrant",
            "collection": self.collection,
            "distance": VECTOR_DISTANCE,
            "vector_size": VECTOR_SIZE,
            "point_count": len(self.points),
            "missing_vector_count": missing_vectors,
            "preview": [
                {"id": point.id, "has_vector": point.vector is not None, "payload": point.payload}
                for point in self.points[:preview]
            ],
        }


def stable_point_id(chunk_id: str) -> str:
    return hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()


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
    return QdrantWritePlan(collection=COLLECTION_CHUNKS, points=points)


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


def client(url: str, api_key: str | None = None):
    """Client creation is deferred until runtime vector storage is enabled."""
    raise NotImplementedError("Qdrant runtime writes are deferred; use prepare_chunk_points(...).dry_run() for Target 10.")
