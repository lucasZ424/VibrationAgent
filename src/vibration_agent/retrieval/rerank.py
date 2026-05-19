"""Optional rerank stage for merged retrieval candidates."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def run(query: str, candidates: Sequence[Mapping[str, Any]], top_k: int = 10) -> list[dict[str, Any]]:
    """Return candidates unchanged, sorted by current score.

    Cross-encoder/LLM reranking is intentionally deferred. Keeping this function
    deterministic lets the hybrid pipeline call it when config enables rerank
    without inventing a model dependency.
    """
    _ = query
    ranked = [dict(candidate) for candidate in candidates]
    ranked.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return ranked[:top_k]
