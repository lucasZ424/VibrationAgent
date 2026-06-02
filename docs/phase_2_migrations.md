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
