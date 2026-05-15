"""Cross-encoder / LLM rerank on merged candidate pool."""
from __future__ import annotations


def run(query: str, candidates: list[dict], top_k: int = 10) -> list[dict]:
    # TODO: cross-encoder model (e.g. BGE-reranker) or LLM rerank prompt
    raise NotImplementedError
