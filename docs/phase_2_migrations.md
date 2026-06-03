# Phase 2 Migrations

Updated: 2026-05-28

## Purpose

This file is the canonical migration log for Phase-2 schema and contract changes. It exists because Phase 1 froze public contracts in `src/vibration_agent/schemas.py`; Phase 2 may extend those contracts, but every change must be traceable.

## Canonical Schema-Change Checklist

For any Phase-2 Obj that changes a frozen schema, API response shape, structured export, or downstream caller contract:

1. Update `src/vibration_agent/schemas.py` first.
2. Add a migration note in this file.
3. Update fixtures and tests that encode the affected shape.
4. Update downstream callers after the contract and tests are in place.
5. Record verification and residual risk in `docs/phase_2_progress.md`.

Default policy: add fields as optional unless the Obj explicitly approves a breaking migration. Deprecated fields are not removed until a freeze document records the removal window.

## Migration Log

### Obj3 — bibliography metadata + section parent linking (2026-06-02)

Additive / optional only. No frozen field renamed, removed, or retyped; Phase-1
contracts are byte-compatible when the new data is absent.

- `schemas.py`: new `DocumentBibliography` model (`year: int | None`,
  `authors: list[str]`, `publisher: str | None`). Standalone — not embedded in
  any frozen model. Maps to the future `documents` table columns.
- `MemoryChunk.metadata` (free-form `dict[str, Any]`, so no model change) gains
  four optional keys:
  - `bibliography`: `{"year", "authors", "publisher"}`, defaulting to
    `{null, [], null}` when no bibliography is extracted.
  - `section_parent_keys`: `list[str]` of ancestor section keys (root → parent),
    `[]` for front-matter / top-level / heading-less content.
  - `section_hierarchy_source`: `"heading_level"` or `"unsectioned"`, documenting
    that parent links come from heading-level heuristics.
  - `section_hierarchy_warnings`: `list[str]` of non-blocking hierarchy warnings,
    currently including `section_level_gap`.
- `citation_anchor` display string: now renders `"Author (Year), p. N"` when the
  chunk's document has **both** author and year; otherwise the Phase-1
  `"Title, p. N"` / `"pp. N-M"` form is unchanged. The frozen `Citation` model is
  untouched (it never carried the anchor; `citation_anchor` is a display field).

Rollback: dropping the two metadata keys and reverting `_citation_anchor`
restores Phase-1 output exactly; no stored frozen field depends on them.

### Obj4 - DOCX ingestion (2026-06-02)

Additive / optional only. PDF, image, text, and unsupported classification
values keep their existing behavior.

- `SupportedKind` gains `"docx"`.
- `ProcessingStrategy` gains `"docx"`.
- DOCX page parsing emits the existing `OcrPage`, `PageBlock`, and
  `DocumentAsset` schemas; no new schema object is introduced.
- `DocumentAsset.object_type` is unchanged. DOCX tables use `"table"` assets;
  embedded images use `"figure"` assets.
- `IngestionManifest.input.kind` and `.processing_strategy` may now contain
  `"docx"` for DOCX sources.

Rollback: remove the two literal values and the DOCX parser/pipeline branch.
Existing PDF/text/image ingestion outputs are independent of this path.

### Obj5 - embedding generation layer (2026-06-02)

Additive / optional only. Existing retrieval outputs keep the same public
`RetrievalOutput` shape.

- `schemas.py`: new standalone `EmbeddingRecord` model with `text_hash`,
  `vector`, `dimension`, `model_name`, `model_version`, `provider`, and
  `warnings`.
- `config.py`: new `EmbeddingSettings` section loaded from
  `configs/embeddings.yaml`.
- Dense retrieval may now use real embedding vectors when a configured local
  model is available. When the default local model path is not configured, it
  silently falls back to the deterministic token-feature lane. Explicit
  disablement and real load/encode failures still record warnings.
- `RetrievalOutput.warnings` may now include actionable embedding fallback
  warnings. This is additive and does not change hit/citation schemas.

Rollback: remove `EmbeddingRecord`, `EmbeddingSettings`, `configs/embeddings.yaml`,
and revert `dense.py` to token-feature-only search.

### Obj6 - Qdrant write/read chain (2026-06-03)

Additive / optional only. Existing retrieval outputs keep the same public
`RetrievalOutput` shape.

- `config.py`: `DatabaseSettings` gains Qdrant runtime controls:
  `qdrant_enabled`, `qdrant_collection`, `qdrant_vector_size`, and
  `qdrant_timeout`. The default vector size is 384 to match the default
  `all-MiniLM-L6-v2` embedding model; runtime upsert derives the size from
  actual vectors when available.
- `storage/qdrant.py`: existing dry-run point planning remains available; runtime
  helpers now initialize the collection, upsert chunk vectors, and map vector
  search hits back into dense-lane retrieval candidates. Ingestion-time
  population is not wired in Obj6; Obj8 owns cold-start / corpus population.
- `storage/qdrant_client.py`: new optional adapter around `qdrant-client`.
  Missing dependency or unavailable Qdrant must not block the default chain.
- `dense.py`: when Qdrant is explicitly enabled and a real query embedding is
  available, dense retrieval may use Qdrant. Qdrant failures are converted into
  warnings and the deterministic token-feature fallback remains available.
  Qdrant hits are filtered to the caller-supplied corpus.

Rollback: set `qdrant_enabled=false`, remove `storage/qdrant_client.py`, and
revert `dense.py` to Obj5 local embedding/token-feature behavior. Dry-run point
planning can remain because it predates Obj6 and is still useful for inspection.
