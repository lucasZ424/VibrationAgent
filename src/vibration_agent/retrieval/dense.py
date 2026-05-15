"""Dense (vector) recall lane against Qdrant."""
from __future__ import annotations


def search(query: str, top_k: int = 50) -> list[dict]:
    # TODO: embed(query) → qdrant.search(collection="chunks", ...)
    raise NotImplementedError
