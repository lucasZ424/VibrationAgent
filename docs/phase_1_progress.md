# Phase 1 Progress

Updated: 2026-05-19

## Objective Status

1. Phase boundary: done
2. Data and interface contracts: done; cleaned after issues review
3. Project config and entry points: done; YAML/env loading active
4. Document input layer: done; classification model unified in schemas.py
5. Page-level OCR and parsing: done; render helper decoupled and OCR thresholds routed
6. Layout-object recognition: done; lightweight block classification and native PDF image assets active
7. Unified asset model: done; chunks carry structured body/formula/figure/table assets
8. Chunking strategy: done; section-aware page/paragraph chunking with stable IDs and boundary metadata
9. Structured document export: done; pages/chunks/api_context/manifest outputs active in formal pipeline
10. Storage write preparation: done; Postgres/Qdrant/Redis mapping plans and dry-runs active
11. S1 document ingestion skill: done; SkillInput/SkillOutput wrapper around structured ingestion exports active
11.5. Agent-owned skill registry and model routing design: done; GPT-first routing and Opus-only extreme supervisor schemas active
12. S2 hybrid retrieval skill: done; local chunk-export retrieval with query normalization, BM25, dense-like recall, RRF fusion, source priority, and insufficient recall handling active
13. S3 QA/summary skill: done; evidence-bound QA, section summary, whole-document summary, language matching, and citation emission active

## Notes

- `schemas.py` is the source of truth for document classification, citations, retrieval hits, pages, assets, and chunks.
- Markdown is not part of the formal Agent ingestion path.
- H3 resolved: `scripts/ocr_raw_books_with_paddle.py` is now a thin compatibility CLI; implementation lives in `src/vibration_agent/ingestion/book_workflow.py`.
- Issues follow-up: M6 remains explicitly deferred; M12 now has direct classify/router unit tests; L13 is documented in the native PyMuPDF parser docstring.
- Objective 6 complete: page JSON now carries block types (`body`, `title`, `formula`, `figure`, `table`) and page-level `assets[]`; native PyMuPDF image blocks are exported under `data/extracted/` when parsing through the pipeline.
- Objective 7 complete: `chunk_pages()` now attaches a body asset plus page-range formula/figure/table assets to each chunk; `api_context.json` exports structured `assets[]`; `knowledge/evidence.py` can emit separate text and asset evidence rows.
- Issues OJ6-7 resolved: fixed formula/title false positives, asset-only body fallback, body text duplication, page enumeration, formal parse-to-chunk pipeline wiring, schema asset invariants, API asset index, OCR confidence propagation, native image-page review flag, configurable render DPI, and citation warnings.
- Objective 8 complete: chunking now preserves title-derived section boundaries, keeps page enumeration, records boundary metadata, supports structured `chunk_sections()`, and keeps repeat runs stable for the same document.
- Objective 9 complete: `chunk_document_pages()` now writes `pages.jsonl`, `chunks.jsonl`, `api_context.json`, and `manifest.json`; `scripts/ingest_folder.py --chunk-documents` exposes the full structured export path.
- Objective 10 complete: storage adapters now prepare dry-run write plans for Postgres rows, Qdrant chunk payloads, and Redis cache items without inline DDL or runtime DB dependencies.
- Objective 11 complete: `IngestionSkill` now wraps the formal structured ingestion pipeline, returns document/chunk/output-path summaries, and converts missing inputs or pipeline failures into `SkillOutput` statuses instead of leaking raw exceptions.
- Objective 11.5 complete: project-owned `agent_skills/` packages, GPT-first difficulty routing, model role registry, and extreme-task supervisor-loop schemas are in place without real API calls.
- Objective 12 complete: `RetrievalSkill` wraps the hybrid retrieval pipeline over S1 `chunks.jsonl` exports, returns `RetrievalOutput` fields plus `retrieval_context`, emits citations from real hits, and returns `insufficient` without invented chunk ids when recall is weak.
- Objective 13 complete: `QASummarySkill` now produces deterministic evidence-bound QA/summary outputs from S2 `retrieval_context`, returns `insufficient` without retrieved evidence, matches dominant source language, and binds every extracted claim to documented citations.
