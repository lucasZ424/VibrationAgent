"""BM25 keyword recall lane."""
from __future__ import annotations


def search(query: str, top_k: int = 50) -> list[dict]:
    # TODO: postgres FTS or rank_bm25 over chunks.normalized_text
    raise NotImplementedError
