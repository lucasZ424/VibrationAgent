"""Thin runtime adapter around the optional qdrant-client package."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Sequence


class QdrantDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class QdrantSearchHit:
    id: str
    score: float
    payload: dict[str, Any]


def _models() -> Any:
    try:
        from qdrant_client import models  # type: ignore
    except ModuleNotFoundError as exc:
        raise QdrantDependencyError("qdrant-client is not installed.") from exc
    return models


@lru_cache(maxsize=8)
def create_client(*, url: str, api_key: str = "", timeout: float = 2.0) -> Any:
    try:
        from qdrant_client import QdrantClient  # type: ignore
    except ModuleNotFoundError as exc:
        raise QdrantDependencyError("qdrant-client is not installed.") from exc
    return QdrantClient(url=url, api_key=api_key or None, timeout=timeout)


def _distance(distance: str) -> Any:
    models = _models()
    normalized = distance.upper()
    if normalized == "COSINE":
        return models.Distance.COSINE
    if normalized == "DOT":
        return models.Distance.DOT
    if normalized == "EUCLID":
        return models.Distance.EUCLID
    return distance


def ensure_collection(
    client: Any,
    *,
    collection: str,
    vector_size: int,
    distance: str,
) -> None:
    if hasattr(client, "collection_exists") and client.collection_exists(collection):
        return
    if not hasattr(client, "collection_exists"):
        try:
            client.get_collection(collection)
            return
        except Exception:
            pass

    models = _models()
    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(size=vector_size, distance=_distance(distance)),
    )


def upsert_points(client: Any, *, collection: str, points: Sequence[Any]) -> int:
    usable_points = [point for point in points if point.vector]
    if not usable_points:
        return 0

    models = _models()
    client.upsert(
        collection_name=collection,
        points=[
            models.PointStruct(id=point.id, vector=list(point.vector), payload=dict(point.payload))
            for point in usable_points
        ],
    )
    return len(usable_points)


def delete_points_by_doc_ids(client: Any, *, collection: str, doc_ids: Sequence[str]) -> int:
    unique_ids = sorted({str(doc_id) for doc_id in doc_ids if str(doc_id)})
    if not unique_ids:
        return 0
    if hasattr(client, "collection_exists") and not client.collection_exists(collection):
        return 0
    if not hasattr(client, "collection_exists"):
        try:
            client.get_collection(collection)
        except Exception:
            return 0
    models = _models()
    client.delete(
        collection_name=collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id",
                        match=models.MatchAny(any=unique_ids),
                    )
                ]
            )
        ),
        wait=True,
    )
    return len(unique_ids)


def search_points(
    client: Any,
    *,
    collection: str,
    query_vector: Sequence[float],
    top_k: int,
) -> list[QdrantSearchHit]:
    if top_k <= 0 or not query_vector:
        return []

    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection,
            query=list(query_vector),
            limit=top_k,
            with_payload=True,
        )
        raw_hits = getattr(response, "points", response)
    else:
        raw_hits = client.search(
            collection_name=collection,
            query_vector=list(query_vector),
            limit=top_k,
            with_payload=True,
        )

    return [
        QdrantSearchHit(
            id=str(getattr(hit, "id", "")),
            score=float(getattr(hit, "score", 0.0) or 0.0),
            payload=dict(getattr(hit, "payload", {}) or {}),
        )
        for hit in raw_hits
    ]
