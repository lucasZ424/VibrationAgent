"""Hybrid retrieval over Phase-0 chunk exports.

Runtime Postgres/Qdrant reads are deferred. This module consumes S1 `chunks.jsonl`
rows and preserves the production retrieval shape: normalize -> BM25 + dense lane
-> RRF fusion -> optional rerank -> source-priority tie boost.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

from vibration_agent.config import Settings, load
from vibration_agent.schemas import RetrievalHit, RetrievalOutput

from . import bm25, dense, query_normalize, rerank

RRF_K = 60
SOURCE_PRIORITY_BOOST = 0.0001
_CHUNK_FILE_PATTERNS = ("**/chunks.jsonl", "**/chunks_*.jsonl")
SOURCE_PRIORITY = {
    "standard": 5,
    "textbook": 4,
    "book": 4,
    "manual": 4,
    "review": 3,
    "paper": 2,
    "webpage": 1,
    "note": 1,
}


@lru_cache(maxsize=1)
def _default_settings() -> Settings:
    return load()


def default_retrieval_settings() -> Settings:
    return _default_settings()


def clear_default_settings_cache() -> None:
    _default_settings.cache_clear()


def read_chunks_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8-sig") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL row in {source} line {line_no}: {exc}") from exc
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _chunk_files(root: str | Path) -> list[Path]:
    paths: dict[str, Path] = {}
    root_path = Path(root)
    for pattern in _CHUNK_FILE_PATTERNS:
        for path in root_path.glob(pattern):
            paths[str(path.resolve())] = path
    return [paths[key] for key in sorted(paths)]


def load_chunks(
    *,
    chunks: Sequence[Mapping[str, Any]] | None = None,
    chunk_paths: Sequence[str | Path] | None = None,
    chunks_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    loaded = [dict(chunk) for chunk in chunks or []]
    for path in chunk_paths or []:
        loaded.extend(read_chunks_jsonl(path))
    if chunks_dir is not None:
        for path in _chunk_files(chunks_dir):
            loaded.extend(read_chunks_jsonl(path))
    return _dedupe_chunks(loaded)


def _dedupe_chunks(chunks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        if chunk_id:
            by_id[str(chunk_id)] = dict(chunk)
    return list(by_id.values())


def _source_priority(chunk: Mapping[str, Any], configured: Mapping[str, int]) -> int:
    source_type = str(chunk.get("source_type") or "").lower()
    return int(configured.get(source_type, SOURCE_PRIORITY.get(source_type, 0)))


def _order_lane_results(
    results: Sequence[Mapping[str, Any]],
    source_priority: Mapping[str, int],
) -> list[Mapping[str, Any]]:
    return sorted(
        results,
        key=lambda item: (
            float(item.get("score") or 0.0),
            _source_priority(
                item.get("chunk", {}) if isinstance(item.get("chunk"), Mapping) else {},
                source_priority,
            ),
        ),
        reverse=True,
    )


def _rrf_candidates(
    *,
    bm25_results: Sequence[Mapping[str, Any]],
    dense_results: Sequence[Mapping[str, Any]],
    source_priority: Mapping[str, int],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    lanes = (
        ("bm25", _order_lane_results(bm25_results, source_priority)),
        ("dense", _order_lane_results(dense_results, source_priority)),
    )
    for lane_name, results in lanes:
        max_lane_score = max((float(item.get("score") or 0.0) for item in results), default=0.0)
        for rank, result in enumerate(results, start=1):
            chunk = result.get("chunk")
            if not isinstance(chunk, Mapping) or not chunk.get("chunk_id"):
                continue
            chunk_id = str(chunk["chunk_id"])
            candidate = candidates.setdefault(
                chunk_id,
                {
                    "chunk": dict(chunk),
                    "score": 0.0,
                    "lanes": [],
                    "lane_scores": {},
                    "matched_terms": [],
                },
            )
            candidate["score"] += 1.0 / (RRF_K + rank)
            if max_lane_score > 0:
                candidate["score"] += 0.01 * (float(result.get("score") or 0.0) / max_lane_score)
            candidate["lanes"].append(lane_name)
            candidate["lane_scores"][lane_name] = float(result.get("score") or 0.0)
            for term in result.get("matched_terms", []) or []:
                if term not in candidate["matched_terms"]:
                    candidate["matched_terms"].append(term)

    for candidate in candidates.values():
        priority = _source_priority(candidate["chunk"], source_priority)
        candidate["source_priority"] = priority
        candidate["score"] += priority * SOURCE_PRIORITY_BOOST
    return sorted(candidates.values(), key=lambda item: item["score"], reverse=True)


def _reason(candidate: Mapping[str, Any]) -> str:
    lanes = "+".join(candidate.get("lanes", [])) or "retrieval"
    chunk = candidate.get("chunk", {}) if isinstance(candidate.get("chunk"), Mapping) else {}
    priority = candidate.get("source_priority", 0)
    matched = candidate.get("matched_terms", []) or []
    pieces = [f"{lanes} match"]
    if matched:
        pieces.append("matched: " + ", ".join(str(term) for term in matched[:4]))
    if chunk.get("topic"):
        pieces.append(f"topic: {chunk['topic']}")
    if priority:
        pieces.append(f"source priority {priority}")
    return "; ".join(pieces)


def _hit_from_candidate(candidate: Mapping[str, Any]) -> RetrievalHit:
    chunk = candidate.get("chunk", {}) if isinstance(candidate.get("chunk"), Mapping) else {}
    pages = chunk.get("pages")
    if pages is None and chunk.get("page_start") is not None and chunk.get("page_end") is not None:
        pages = list(range(int(chunk["page_start"]), int(chunk["page_end"]) + 1))
    return RetrievalHit(
        chunk_id=str(chunk.get("chunk_id")),
        doc_id=str(chunk.get("doc_id")),
        source_type=str(chunk.get("source_type") or "note"),
        pages=list(pages or []),
        score=round(float(candidate.get("score") or 0.0), 6),
        reason=_reason(candidate),
    )


def _context_from_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    chunk = candidate.get("chunk", {}) if isinstance(candidate.get("chunk"), Mapping) else {}
    return {
        "chunk_id": chunk.get("chunk_id"),
        "doc_id": chunk.get("doc_id"),
        "pages": chunk.get("pages"),
        "source_type": chunk.get("source_type"),
        "topic": chunk.get("topic"),
        "score": round(float(candidate.get("score") or 0.0), 6),
        "reason": _reason(candidate),
        "text": chunk.get("api_context") or chunk.get("text") or "",
        "assets": chunk.get("assets", []),
    }


def search(
    query: str,
    *,
    top_k: int | None = None,
    chunks: Sequence[Mapping[str, Any]] | None = None,
    chunk_paths: Sequence[str | Path] | None = None,
    chunks_dir: str | Path | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return a RetrievalOutput-shaped dict plus retrieval_context."""
    active_settings = settings or _default_settings()
    final_top_k = active_settings.retrieval.final_top_k if top_k is None else top_k
    normalized = query_normalize.normalize(query)
    normalized_query = normalized["normalized_query"]
    warnings: list[str] = []

    corpus = load_chunks(chunks=chunks, chunk_paths=chunk_paths, chunks_dir=chunks_dir)
    if not normalized_query:
        output = RetrievalOutput(
            normalized_query="",
            intent="unknown",
            status="insufficient",
            warnings=["Empty query."],
        )
        return {**output.model_dump(mode="json"), "retrieval_context": []}
    if not corpus:
        output = RetrievalOutput(
            normalized_query=normalized_query,
            intent=normalized["intent_hint"],
            status="insufficient",
            warnings=["No chunk corpus supplied for S2 retrieval."],
        )
        return {**output.model_dump(mode="json"), "retrieval_context": []}
    if final_top_k <= 0:
        output = RetrievalOutput(
            normalized_query=normalized_query,
            intent=normalized["intent_hint"],
            status="insufficient",
            warnings=["top_k must be greater than 0 for retrieval hits."],
        )
        return {**output.model_dump(mode="json"), "retrieval_context": []}

    bm25_results = bm25.search(normalized_query, chunks=corpus, top_k=active_settings.retrieval.bm25_top_k)
    dense_results = dense.search(
        normalized_query,
        chunks=corpus,
        top_k=active_settings.retrieval.dense_top_k,
        settings=active_settings,
        warnings=warnings,
    )
    candidates = _rrf_candidates(
        bm25_results=bm25_results,
        dense_results=dense_results,
        source_priority=active_settings.retrieval.source_priority,
    )
    if active_settings.retrieval.rerank_enabled:
        candidates = rerank.run(normalized_query, candidates, top_k=final_top_k)
    else:
        candidates = candidates[:final_top_k]

    hits = [_hit_from_candidate(candidate) for candidate in candidates]
    if not hits:
        warnings.insert(0, "Weak recall: no matching chunks found.")
    output = RetrievalOutput(
        normalized_query=normalized_query,
        intent=normalized["intent_hint"],
        hits=hits,
        status="ok" if hits else "insufficient",
        warnings=warnings,
    )
    return {
        **output.model_dump(mode="json"),
        "detected_terms": normalized.get("detected_terms", []),
        "detected_symbols": normalized.get("detected_symbols", []),
        "retrieval_context": [_context_from_candidate(candidate) for candidate in candidates],
    }
