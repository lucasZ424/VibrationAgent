"""Evidence mapping helpers for chunks, pages, and assets.

Target 7 gives retrieval and answer layers a single representation for text and
visual evidence. The helpers here intentionally stay deterministic: they do not
perform claim extraction or model-based citation checking yet.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from vibration_agent.schemas import Citation, DocumentAsset

logger = logging.getLogger(__name__)


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
