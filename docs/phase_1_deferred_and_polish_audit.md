# Phase-1 Deferred and Polish Audit

Updated: 2026-05-26

## Purpose

This document consolidates the deferred items and polish notes from `docs/issue_log/issues*.txt` before Phase 1 wrap-up. It is the handoff ledger for Objective 20: freeze Phase-0 interfaces, confirm what is complete, and make later scope explicit. The frozen interface contract itself is recorded in `docs/phase_1_interface_freeze.md`.

Phase 1 remains bounded to S1 ingestion, S2 retrieval, S3 evidence-bound QA/summary, V4 output style, CLI/API entry points, fixtures, and end-to-end validation. Deferred skills S4-S8 and V1-V3 are intentionally not part of the running chain.

## Phase 1 Closure Decision

Phase 1 can be treated as functionally complete after the current regression suite passes, with the following constraints:

- The production runtime path is still file-backed and deterministic; it does not yet use live Postgres/Qdrant/Redis writes for answers.
- OCR and native parsing are wired, but full-quality validation against the large Bently corpus is not a default automated test.
- S3 is evidence selection and cited summarization, not model-synthesized engineering reasoning.
- The API is a localhost development surface; it is not deployment-hardened.

These constraints are acceptable for Phase 1 because they do not violate the documented Phase-0 scope.

## Resolved During Phase 1

- Formal pipeline now produces `pages.jsonl`, `chunks.jsonl`, `api_context.json`, and `manifest.json`; Markdown is not the formal intermediate.
- Page/chunk/schema contracts live in `schemas.py`; `Citation`, `SkillInput`, `SkillOutput`, page blocks, assets, chunks, retrieval outputs, and API models are centralized.
- OCR threshold/config routing no longer depends on scattered hardcoded defaults.
- The urgent OCR script has been demoted to compatibility behavior; formal ingestion code lives in package modules.
- `chunk_pages()` carries page anchors, section metadata, OCR confidence summaries, review pages, and structured asset references.
- Body assets are filtered out of top-level `api_context.assets[]`; body text remains owned by `chunk.text`.
- Storage preparation has dry-run Postgres/Qdrant/Redis plans with no inline DDL.
- S1, S2, S3, and V4 all use `SkillInput`/`SkillOutput` and return `insufficient` instead of inventing evidence.
- Retrieval no longer double-counts `api_context` in BM25/dense feature text; hyphenated/slash/dot terms are indexed as whole and split tokens.
- Tutor scope handling includes negative filters and explicit scope override.
- CLI/API both expose structured ingestion and query paths with status semantics and workspace reporting.
- API errors use a project error envelope; common runtime exceptions map to appropriate HTTP 4xx/5xx responses.
- Agent-owned skill packages exist under `agent_skills/`; prompt-side skill files are legacy aliases, not the runtime source of truth.
- Test fixtures cover small PDF, OCR page JSONL, chunk JSONL, retrieval JSON, fixture drift, S1 -> S2 -> S3 -> V4 integration, CLI/API E2E, and legacy shim chunk export.
- Makefile now separates fast and full test targets and points at the correct requirements file.

## Explicitly Deferred To Phase 2 Or Later

### Document And Corpus Coverage

- DOCX ingestion remains deferred. Lock-file skip behavior is in place, but no DOCX parser is active.
- Full Bently corpus validation is manual/heavy validation, not a default automated test fixture.
- Multi-page and bilingual fixture packs are useful but not required for Phase 1 closure.
- Bibliographic extraction for `documents.year`, `documents.authors`, and richer citation metadata is deferred.

### Retrieval And Storage

- Dense retrieval is still a deterministic token-feature fallback, not a real embedding/Qdrant semantic lane.
- Runtime Postgres/Qdrant/Redis writes are prepared as dry-run plans; live persistence and read paths are later work.
- `qa_logs` write helpers are not implemented yet because Phase 1 does not persist live QA sessions.
- Section hierarchy parent linking is not fully modeled in storage rows; current Phase 1 section grouping is flat enough for retrieval.

### Reasoning, Review, And Model Runtime

- S4 engineering analysis, S5 derivation, S6 literature search, S7 model selection, S8 experiment advice, V1 normalizer, V2 citation check, and V3 reviewer stay reserved but inactive.
- LLM-backed S3 synthesis is deferred. Current S3 extracts cited evidence sentences deterministically.
- Claude Opus supervisor execution is schema/routing-ready only; no real Opus takeover executor is active.
- Real OpenAI/Anthropic API runtime and API-key handling are not required for Obj20 closure.

### Deployment Hardening

- API path sandboxing/whitelisting is deferred while the product remains local personal deployment; it becomes mandatory before shared, remote, or public access.
- API auth, CORS, rate limiting, and production readiness checks are deferred.
- `/health` reports app runtime configuration, not live Postgres/Qdrant/Redis readiness.
- CI workflow is not required for Phase 1 closure, though `make test-fast` and `make test-full` are now available locally.

## Accepted Phase 1 Tradeoffs

- Chunk IDs are repeat-run stable for unchanged input, but not designed for incremental insertion stability.
- `section_boundary_crossed` is mostly future-proof metadata because the current chunker flushes before crossing sections.
- V4 has aliases for sections that Phase-0 S3 does not yet populate; this is intentional to keep the template contract stable.
- `prompts/skills/*.md` and `agent_skills/*/SKILL.md` overlap. Runtime ownership is `agent_skills/`; prompt files are compatibility/design aliases until Phase 2 decides whether to generate or retire them.
- The API returns HTTP 2xx for successfully handled Agent calls even when body `status` is `insufficient`; this is documented behavior.

## Low-Cost Items Completed In This Audit

- Added `make test-fast` for non-integration feedback.
- Added `make test-full` for complete Phase-1 regression coverage.
- Changed `make test` to default to fast tests.
- Fixed `Makefile install` to use `requirements-full.txt`.

## Obj20 Preconditions

Before marking Obj20 complete, verify:

1. `pytest tests -q` passes.
2. `git diff --check` has no whitespace errors, ignoring CRLF warnings if exit code is zero.
3. `README.md`, `docs/phase_1_progress.md`, and this audit document agree on Phase-1 scope.
4. No Phase-2 skill is called by `TutorOrchestrator` or CLI/API query paths.
5. `schemas.py` is treated as frozen unless Obj20 explicitly updates the interface freeze note.

## Local Personal Deployment Baseline

These notes are not a Phase-2 design. They define the product position and the main validation gaps that should remain visible after Phase-1 closure.

Product baseline: `vibration_agent` is a local personal deployment for one engineering user working with trusted local documents and a private knowledge base. The API is a localhost development/control surface. Multi-user, remote, or public deployment is outside the current product position and requires explicit hardening scope.

Follow-up validation notes:

- Bilingual E2E gap: Phase-0 claims Chinese and English usability, but the full S1 -> S2 -> S3 -> V4 stack is currently validated with an English fixture path. Add a minimal Chinese fixture before model-synthesized S3 work so Chinese tokenization, retrieval, V4 template rendering, and citation formatting stay debuggable while the chain is deterministic.
- Deterministic stand-ins: S3 performs evidence selection rather than synthesis, dense retrieval is a deterministic token-feature fallback rather than real embeddings, storage adapters produce dry-run plans rather than live persistence, and the API is localhost-only. These are intentional Phase-1 scaffolds, but they are the main surfaces that can look more complete than they are.
- Single-chunk fixture: the current end-to-end fixture proves the minimum path, not multi-page chunking, cross-chunk citation collation, or section aggregation through the full stack. The first real corpus regression should include a small multi-page, multi-chunk document.
- API hardening and persistence: because the product is local personal deployment, API hardening should not outrank corpus/retrieval quality by default. If usage expands beyond localhost and one trusted user, path safety, auth, request limits, and readiness checks become priority work before broader access.

## Phase 2 Candidate Backlog

- Real embedding generation and Qdrant read/write integration.
- Postgres live writes plus QA log persistence.
- V1 term/symbol/unit normalization.
- V2 citation checking against retrieved chunks.
- V3 reviewer and Opus supervisor executor loop.
- S4/S5 engineering analysis and derivation skills.
- DOCX and richer document metadata extraction.
- Large-corpus Bently smoke tests outside the default fast suite.
- Deployment hardening for API path access, auth, CORS, rate limiting, and readiness probes.
