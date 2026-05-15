"""Hybrid retrieval: query-normalize → BM25 ∪ dense → rerank → source-priority fusion.

Source priority (design doc §8):
    standard > textbook > review > single_paper > webpage
"""
from __future__ import annotations

SOURCE_PRIORITY = {
    "standard": 5,
    "textbook": 4,
    "review": 3,
    "paper": 2,
    "webpage": 1,
}


def search(query: str, top_k: int = 10) -> dict:
    """Returns a `RetrievalOutput`-shaped dict (see schemas.RetrievalOutput)."""
    # TODO: run normalize → bm25.search ∪ dense.search → rerank.run → source fusion
    raise NotImplementedError
