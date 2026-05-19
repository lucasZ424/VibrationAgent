"""BM25 keyword recall lane over in-memory chunk dictionaries."""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z0-9_]+(?:[-./][A-Za-z0-9_]+)*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese/English engineering text without external deps.

    English hyphen/slash/dot compounds are indexed as both whole compounds and
    split terms, so `rotor-bearing-system` can match `rotor bearing`. Chinese
    text emits unigrams plus 2/3-grams; this intentionally improves phrase recall
    for short engineering terms at the cost of higher term frequency.
    """
    lowered = text.lower()
    tokens: list[str] = []
    for token in _WORD_RE.findall(lowered):
        tokens.append(token)
        if any(separator in token for separator in ("-", "/", ".")):
            tokens.extend(part for part in re.split(r"[-./]+", token) if part)
    for segment in _CJK_RE.findall(text):
        tokens.extend(segment)
        tokens.extend(segment[index : index + 2] for index in range(max(len(segment) - 1, 0)))
        tokens.extend(segment[index : index + 3] for index in range(max(len(segment) - 2, 0)))
    return [token for token in tokens if token.strip()]


def _chunk_text(chunk: Mapping[str, Any]) -> str:
    parts = [
        str(chunk.get("title") or ""),
        str(chunk.get("topic") or ""),
        str(chunk.get("text") or ""),
    ]
    metadata = chunk.get("metadata")
    if isinstance(metadata, Mapping):
        parts.append(str(metadata.get("section_title") or ""))
    return "\n".join(parts)


def search(query: str, *, chunks: Sequence[Mapping[str, Any]] | None = None, top_k: int = 50) -> list[dict[str, Any]]:
    """Return BM25-ranked chunk hits.

    Runtime Postgres FTS is deferred; Phase-0 runs against S1 `chunks.jsonl` rows.
    """
    corpus = list(chunks or [])
    query_tokens = tokenize(query)
    if not corpus or not query_tokens or top_k <= 0:
        return []

    documents = [tokenize(_chunk_text(chunk)) for chunk in corpus]
    doc_count = len(documents)
    avg_len = sum(len(document) for document in documents) / doc_count if doc_count else 0.0
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))

    query_counter = Counter(query_tokens)
    results: list[dict[str, Any]] = []
    k1 = 1.5
    b = 0.75
    for chunk, document in zip(corpus, documents, strict=True):
        if not document:
            continue
        term_frequency = Counter(document)
        score = 0.0
        matched: list[str] = []
        for token, query_weight in query_counter.items():
            tf = term_frequency.get(token, 0)
            if tf <= 0:
                continue
            matched.append(token)
            df = document_frequency[token]
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * len(document) / max(avg_len, 1.0))
            score += query_weight * idf * (tf * (k1 + 1)) / denominator
        if score > 0:
            results.append({"chunk": dict(chunk), "score": score, "lane": "bm25", "matched_terms": matched[:8]})

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
