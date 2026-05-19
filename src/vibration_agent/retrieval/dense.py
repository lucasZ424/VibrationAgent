"""Local dense-like recall lane.

True embedding generation and Qdrant runtime reads are deferred. This module keeps
the hybrid contract alive in Phase-0 by using normalized token/character features
as a deterministic semantic fallback over S1 chunk rows.

This lane is intentionally not a real semantic embedding lane: because it shares
BM25 tokenization, it is correlated with keyword recall. Treat it as a temporary
Phase-0 fallback until the Qdrant embedding path is activated.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .bm25 import tokenize


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


def search(query: str, *, chunks: Sequence[Mapping[str, Any]] | None = None, top_k: int = 50) -> list[dict[str, Any]]:
    corpus = list(chunks or [])
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
