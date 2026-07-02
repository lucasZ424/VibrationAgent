"""Evidence mapping helpers for chunks, pages, and assets.

Target 7 gives retrieval and answer layers a single representation for text and
visual evidence. The helpers here intentionally stay deterministic: they do not
perform claim extraction or model-based citation checking yet.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from math import ceil
from typing import Any, Iterable, Mapping, Sequence

from vibration_agent.schemas import Citation, DocumentAsset

logger = logging.getLogger(__name__)
_FINAL_SENTENCE_RE = re.compile(r"[。！？!?；;.…．][\"'”’）】》]*$")
_PREVIOUS_CONTEXT_PREFIXES = (
    "当",
    "因此",
    "所以",
    "并且",
    "同时",
    "其中",
    "则",
    "而",
    "从而",
    "when ",
    "therefore ",
    "and ",
    "also ",
)


def _evidence_text(chunk: Mapping[str, Any]) -> str:
    return str(chunk.get("text") or chunk.get("api_context") or "").strip()


def _evidence_tokens(chunk: Mapping[str, Any]) -> int:
    value = chunk.get("token_estimate")
    return max(1, int(value)) if value not in (None, "") else max(1, ceil(len(_evidence_text(chunk)) / 4))


def _dedupe_text(value: str) -> str:
    return re.sub(r"\W+", "", value.casefold())


def _is_duplicate(value: str, selected: list[str]) -> bool:
    normalized = _dedupe_text(value)
    if not normalized:
        return True
    for existing in selected:
        if normalized == existing:
            return True
        shorter, longer = sorted((normalized, existing), key=len)
        if len(shorter) >= 80 and shorter in longer:
            return True
        if min(len(normalized), len(existing)) >= 120 and SequenceMatcher(None, normalized, existing).ratio() >= 0.94:
            return True
    return False


def _starts_continuation(text: str) -> bool:
    stripped = text.strip()
    return stripped.casefold().startswith(_PREVIOUS_CONTEXT_PREFIXES) or bool(
        stripped and stripped[0].isascii() and stripped[0].islower()
    )


def _ends_incomplete(text: str) -> bool:
    return not bool(_FINAL_SENTENCE_RE.search(text.strip()))


def _adjacent_offsets(text: str, window: int) -> tuple[int, ...]:
    offsets: list[int] = []
    for distance in range(1, window + 1):
        if _starts_continuation(text):
            offsets.append(-distance)
        if _ends_incomplete(text):
            offsets.append(distance)
    return tuple(offsets)


def _is_continuous_neighbor(seed_text: str, neighbor_text: str, offset: int) -> bool:
    if offset < 0:
        return _starts_continuation(seed_text) and _ends_incomplete(neighbor_text)
    return _ends_incomplete(seed_text) and _starts_continuation(neighbor_text)


def select_evidence_candidates(
    candidates: Sequence[Mapping[str, Any]],
    corpus: Sequence[Mapping[str, Any]],
    *,
    seed_chunks: int,
    max_chunks: int,
    token_budget: int,
    adjacent_window: int,
    intent: str = "unknown",
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Select bounded, traceable evidence without changing retrieval ranking."""

    by_position: dict[tuple[str, int], dict[str, Any]] = {}
    for chunk in corpus:
        if chunk.get("doc_id") and chunk.get("chunk_index") is not None:
            by_position[(str(chunk["doc_id"]), int(chunk["chunk_index"]))] = dict(chunk)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    selected_texts: list[str] = []
    used_tokens = 0
    dropped_budget = 0
    dropped_duplicate = 0

    def add(candidate: Mapping[str, Any], *, kind: str, seed_id: str | None = None) -> None:
        nonlocal used_tokens, dropped_budget, dropped_duplicate
        if len(selected) >= max_chunks:
            return
        chunk = candidate.get("chunk") if isinstance(candidate.get("chunk"), Mapping) else candidate
        chunk_id = str(chunk.get("chunk_id") or "")
        text = _evidence_text(chunk)
        if not chunk_id or chunk_id in selected_ids or _is_duplicate(text, selected_texts):
            dropped_duplicate += 1
            return
        tokens = _evidence_tokens(chunk)
        if used_tokens + tokens > token_budget:
            dropped_budget += 1
            return
        item = dict(candidate)
        item["chunk"] = dict(chunk)
        item["selection_kind"] = kind
        if kind == "seed":
            lanes = "+".join(str(value) for value in item.get("lanes", []) or []) or "unknown"
            pages = chunk.get("pages") or []
            item["selection_reason"] = (
                f"fused_rank_seed;intent:{intent};lanes:{lanes};"
                f"source:{chunk.get('source_type') or 'unknown'};pages:{pages}"
            )
        else:
            item["selection_reason"] = f"same_doc_adjacent_to:{seed_id}"
        item["selection_token_estimate"] = tokens
        selected.append(item)
        selected_ids.add(chunk_id)
        selected_texts.append(_dedupe_text(text))
        used_tokens += tokens

    seeds = [dict(candidate) for candidate in candidates[: min(seed_chunks, max_chunks)]]
    for candidate in seeds:
        add(candidate, kind="seed")
    if adjacent_window:
        for seed in seeds:
            chunk = seed.get("chunk") if isinstance(seed.get("chunk"), Mapping) else seed
            if not chunk.get("doc_id") or chunk.get("chunk_index") is None:
                continue
            seed_id = str(chunk.get("chunk_id") or "")
            index = int(chunk["chunk_index"])
            for offset in _adjacent_offsets(_evidence_text(chunk), adjacent_window):
                neighbor = by_position.get((str(chunk["doc_id"]), index + offset))
                if neighbor is not None and _is_continuous_neighbor(_evidence_text(chunk), _evidence_text(neighbor), offset):
                    add({"chunk": neighbor, "score": seed.get("score", 0.0), "lanes": []}, kind="adjacent", seed_id=seed_id)

    warnings: list[str] = []
    if dropped_budget:
        warnings.append(f"Evidence selector dropped {dropped_budget} chunk(s) over the {token_budget}-token budget.")
    report = {
        "selected_chunk_ids": [str(item["chunk"]["chunk_id"]) for item in selected],
        "selected_count": len(selected),
        "token_estimate": used_tokens,
        "token_budget": token_budget,
        "max_chunks": max_chunks,
        "dropped_budget": dropped_budget,
        "dropped_duplicate": dropped_duplicate,
        "intent": intent,
    }
    return selected, report, warnings


def _as_asset(value: DocumentAsset | dict[str, Any]) -> DocumentAsset:
    return value if isinstance(value, DocumentAsset) else DocumentAsset.model_validate(value)


def _pages_from_chunk(chunk: Mapping[str, Any]) -> list[int] | None:
    pages = chunk.get("pages")
    if isinstance(pages, list):
        return [int(page) for page in pages]
    if "page_start" in chunk and "page_end" in chunk:
        return list(range(int(chunk["page_start"]), int(chunk["page_end"]) + 1))
    return None


def _chunk_confidence(chunk: Mapping[str, Any]) -> float:
    if chunk.get("confidence") is not None:
        return float(chunk["confidence"])
    if chunk.get("ocr_confidence_min") is not None:
        return float(chunk["ocr_confidence_min"])
    if chunk.get("score") is not None:
        return max(0.0, min(float(chunk["score"]), 1.0))
    return 1.0


def _source_metadata(chunk: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = chunk.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


def _basename(value: Any) -> str | None:
    text = _first_text(value)
    if text is None:
        return None
    name = text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return name or None


def _source_filename(chunk: Mapping[str, Any]) -> str | None:
    metadata = _source_metadata(chunk)
    explicit = _first_text(
        chunk.get("source_filename"),
        chunk.get("input_filename"),
        chunk.get("filename"),
        metadata.get("source_filename"),
        metadata.get("input_filename"),
        metadata.get("filename"),
    )
    if explicit is not None:
        return explicit
    return _basename(chunk.get("source_path")) or _basename(metadata.get("source_path"))


def snippet_text(value: Any, *, limit: int = 180) -> str | None:
    """Return a single-line, length-bounded preview of evidence text."""
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _source_title(chunk: Mapping[str, Any]) -> str | None:
    metadata = _source_metadata(chunk)
    return _first_text(chunk.get("source_title"), chunk.get("title"), metadata.get("source_title"), metadata.get("title"))


def asset_evidence_row(
    asset: DocumentAsset | dict[str, Any],
    *,
    chunk_id: str | None = None,
    evidence_type: str = "documented",
) -> dict[str, Any]:
    """Return a retrieval-friendly evidence row for one asset."""
    item = _as_asset(asset)
    return {
        "evidence_kind": "asset",
        "asset_id": item.asset_id,
        "chunk_id": chunk_id,
        "doc_id": item.doc_id,
        "pages": [item.page_no],
        "object_type": item.object_type,
        "asset_path": item.asset_path,
        "bbox": item.bbox,
        "text": item.text,
        "evidence_type": evidence_type,
        "confidence": item.confidence if item.confidence is not None else 1.0,
        "metadata": item.metadata,
    }


def chunk_text_evidence_row(chunk: dict[str, Any]) -> dict[str, Any]:
    """Return the text evidence row represented by a memory chunk."""
    return {
        "evidence_kind": "text",
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "pages": _pages_from_chunk(chunk),
        "source_filename": _source_filename(chunk),
        "source_title": _source_title(chunk),
        "object_type": "body",
        "asset_path": f"chunk://{chunk['doc_id']}/{chunk['chunk_id']}/body",
        "bbox": None,
        "text": chunk.get("text", ""),
        "evidence_type": "documented",
        "confidence": _chunk_confidence(chunk),
        "metadata": {
            "citation_anchor": chunk.get("citation_anchor"),
            "needs_review_pages": chunk.get("needs_review_pages", []),
        },
    }


def retrieval_evidence_row(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize one S2 hit/context row into answer-ready text evidence."""
    source = item.get("chunk") if isinstance(item.get("chunk"), Mapping) else item
    chunk_id = source.get("chunk_id")
    doc_id = source.get("doc_id")
    if not chunk_id or not doc_id:
        logger.warning("Skipping evidence row without chunk_id/doc_id: %s", item)
        return None
    text = str(source.get("text") or source.get("api_context") or "").strip()
    return {
        "evidence_kind": "text",
        "chunk_id": str(chunk_id),
        "doc_id": str(doc_id),
        "pages": _pages_from_chunk(source),
        "source_type": source.get("source_type"),
        "source_filename": _source_filename(source),
        "source_title": _source_title(source),
        "topic": source.get("topic"),
        "language": source.get("language") or source.get("doc_language") or source.get("source_language"),
        "text": text,
        "reason": source.get("reason") or item.get("reason", ""),
        "evidence_type": "documented",
        "confidence": _chunk_confidence(source),
        "metadata": dict(_source_metadata(source)),
        "assets": source.get("assets", []) if isinstance(source.get("assets"), list) else [],
    }


def chunk_asset_evidence_rows(chunk: dict[str, Any], *, include_body_asset: bool = False) -> list[dict[str, Any]]:
    """Return asset evidence rows attached to a chunk."""
    rows: list[dict[str, Any]] = []
    for asset in chunk.get("assets", []):
        if not isinstance(asset, dict):
            continue
        if not include_body_asset and asset.get("object_type") == "body":
            continue
        rows.append(asset_evidence_row(asset, chunk_id=chunk.get("chunk_id")))
    return rows


def chunk_evidence_rows(chunk: dict[str, Any], *, include_body_asset: bool = False) -> list[dict[str, Any]]:
    """Return text evidence plus visual/structured asset evidence for a chunk."""
    return [chunk_text_evidence_row(chunk), *chunk_asset_evidence_rows(chunk, include_body_asset=include_body_asset)]


def filter_assets_by_type(
    assets: Iterable[DocumentAsset | dict[str, Any]],
    object_types: set[str],
) -> list[DocumentAsset]:
    """Filter assets by object type while preserving order."""
    return [asset for asset in (_as_asset(item) for item in assets) if asset.object_type in object_types]


def citation_from_chunk(chunk: Mapping[str, Any], *, evidence_type: str = "documented") -> Citation:
    """Build the current Phase-0 Citation model from a chunk or retrieval hit."""
    return Citation(
        chunk_id=str(chunk["chunk_id"]),
        doc_id=str(chunk["doc_id"]),
        pages=_pages_from_chunk(chunk),
        evidence_type=evidence_type,  # type: ignore[arg-type]
        confidence=max(0.0, min(_chunk_confidence(chunk), 1.0)),
        source_filename=_source_filename(chunk),
        source_title=_source_title(chunk),
        snippet=snippet_text(chunk.get("text") or chunk.get("api_context")),
    )


def citation_from_evidence(evidence: Mapping[str, Any], *, evidence_type: str = "documented") -> Citation:
    """Build a citation from normalized retrieval evidence."""
    return citation_from_chunk(evidence, evidence_type=evidence_type)


def attach_citations(answer_text: str, hits: list[dict]) -> list[dict]:
    """Return citation rows for retrieved hits.

    Claim-level alignment is deferred to V2/V3. For now each hit maps directly to
    one documented citation and can carry separate asset evidence rows.
    """
    del answer_text
    citations: list[dict] = []
    for hit in hits:
        if "chunk_id" not in hit or "doc_id" not in hit:
            logger.warning("Skipping citation hit without chunk_id/doc_id: %s", hit)
            continue
        citations.append(citation_from_chunk(hit).model_dump(mode="json"))
    return citations
