"""Dense retrieval lane with explicit token-feature fallback."""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from vibration_agent.config import Settings
from vibration_agent.storage import qdrant

from .bm25 import tokenize
from .embeddings import embed_texts


def _features(text: str) -> Counter[str]:
    tokens = tokenize(text)
    counter: Counter[str] = Counter(tokens)
    for token in tokens:
        if len(token) >= 5 and token.isascii():
            counter[token[:4]] += 0.5
            counter[token[-4:]] += 0.5
    return counter


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector_cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
    return "\n".join(
        [
            str(chunk.get("title") or ""),
            str(chunk.get("topic") or ""),
            str(metadata.get("section_title") or ""),
            str(chunk.get("text") or ""),
        ]
    )


def _fallback_search(query: str, *, corpus: Sequence[Mapping[str, Any]], top_k: int) -> list[dict[str, Any]]:
    query_features = _features(query)
    if not corpus or not query_features or top_k <= 0:
        return []

    results: list[dict[str, Any]] = []
    for chunk in corpus:
        score = _cosine(query_features, _features(_chunk_text(chunk)))
        if score > 0:
            results.append({"chunk": dict(chunk), "score": score, "lane": "dense_local"})
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def search(
    query: str,
    *,
    chunks: Sequence[Mapping[str, Any]] | None = None,
    top_k: int = 50,
    settings: Settings | None = None,
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    corpus = list(chunks or [])
    if not corpus or not query or top_k <= 0:
        return []

    if settings is not None and settings.database.qdrant_enabled:
        allowed_chunk_ids = {str(chunk["chunk_id"]) for chunk in corpus if chunk.get("chunk_id")}
        query_records = embed_texts([query], settings=settings)
        query_warnings = list(dict.fromkeys(warning for record in query_records for warning in record.warnings))
        query_record = query_records[0] if query_records else None
        if query_record and query_record.vector and query_record.provider != "fallback_token_features":
            try:
                qdrant_results = qdrant.search_chunks(
                    qdrant.runtime_client(settings),
                    query_record.vector,
                    top_k=top_k,
                    collection=settings.database.qdrant_collection,
                )
                qdrant_results = [
                    result
                    for result in qdrant_results
                    if str(result.get("chunk", {}).get("chunk_id")) in allowed_chunk_ids
                ]
                if qdrant_results:
                    return qdrant_results
                return _fallback_search(query, corpus=corpus, top_k=top_k)
            except Exception as exc:
                if warnings is not None:
                    warning = f"Qdrant dense retrieval unavailable; using token-feature fallback: {type(exc).__name__}: {exc}"
                    if warning not in warnings:
                        warnings.append(warning)
                return _fallback_search(query, corpus=corpus, top_k=top_k)
        if query_warnings:
            if warnings is not None:
                warnings.extend(warning for warning in query_warnings if warning not in warnings)
            return _fallback_search(query, corpus=corpus, top_k=top_k)

    texts = [query, *(_chunk_text(chunk) for chunk in corpus)]
    records = embed_texts(texts, settings=settings)
    record_warnings = list(dict.fromkeys(warning for record in records for warning in record.warnings))
    uses_fallback = any(record.provider == "fallback_token_features" or not record.vector for record in records)
    if uses_fallback:
        if warnings is not None:
            warnings.extend(warning for warning in record_warnings if warning not in warnings)
        return _fallback_search(query, corpus=corpus, top_k=top_k)

    query_vector = records[0].vector
    results: list[dict[str, Any]] = []
    for chunk, record in zip(corpus, records[1:], strict=True):
        score = _vector_cosine(query_vector, record.vector)
        if score > 0:
            results.append({"chunk": dict(chunk), "score": score, "lane": "dense_embedding"})
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
