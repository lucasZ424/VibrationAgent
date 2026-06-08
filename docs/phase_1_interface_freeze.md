# Phase-1 Interface Freeze

Updated: 2026-05-28

## Freeze Decision

Phase 1 is frozen as a Phase-0 runtime implementation. The stable chain is:

```text
S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style -> user/API/CLI
```

The user-facing query path remains:

```text
User query -> TutorOrchestrator -> S2 -> S3 -> V4 -> SkillOutput/API/CLI JSON
```

S1 prepares the knowledge base and is invoked explicitly through ingestion entry points. It is not automatically invoked by every query.

## Frozen Interfaces

The following contracts are frozen for Phase 1 consumers:

- `Citation`
- `SkillInput`
- `SkillOutput`
- `DocumentClassification`
- `OcrPage`
- `PageBlock`
- `DocumentAsset`
- `MemoryChunk`
- `RetrievalHit`
- `RetrievalOutput`
- `IngestionManifest`
- `ApiContextPack`
- `PhaseScope`
- `ApiHealthResponse`
- `ApiScopeResponse`
- `ApiErrorItem`
- `ApiErrorResponse`
- `ApiIngestionRequest`
- `ApiIngestionResult`
- `ApiIngestionResponse`
- `ApiQueryRequest`
- `ApiQueryResponse`

Any Phase-2 change to these contracts must start in `src/vibration_agent/schemas.py`, include migration notes, and update tests/fixtures that encode the affected shape.

## Frozen Directory Layout

The following directories are part of the Phase-1 structure and should remain stable for Phase-2 callers and contributors:

- `apps/{api,cli,worker}/`
- `src/vibration_agent/`
- `src/vibration_agent/skills/`
- `src/vibration_agent/ingestion/`
- `src/vibration_agent/retrieval/`
- `src/vibration_agent/knowledge/`
- `src/vibration_agent/storage/`
- `agent_skills/<skill_id>/SKILL.md`
- `prompts/`
- `configs/`
- `taxonomy/`
- `db/`
- `tests/fixtures/`
- `data/{raw,ocr,extracted,chunks,embeddings,exports}/`

Moving these locations is a Phase-2 migration and must include caller/test updates.

## Prompt And Skill Markdown Ownership

- `agent_skills/<skill_id>/SKILL.md` is the project-owned agent-facing skill package. It defines runtime skill behavior for model/tool orchestration, but it is not itself a Pydantic/API schema.
- `src/vibration_agent/skills/*.py` is the deterministic implementation layer and remains governed by `SkillInput` / `SkillOutput`.
- `prompts/orchestrator.md` and `prompts/templates/engineering_answer.md` are runtime/design prompt assets.
- `prompts/skills/*.md` are legacy/design aliases. The runtime source of truth for project-owned skill packages is `agent_skills/`.
- Phase-2 prompt or skill-markdown changes must not alter frozen JSON/API shapes unless `schemas.py`, fixtures, and this freeze document are updated together.

## Frozen Runtime Entrypoints

- CLI: `python -m apps.cli.main`
- API: `apps.api.main:app`
- Worker: `apps.worker.main` is a stub/operational placeholder, not a frozen Phase-1 query runtime path.
- Legacy shim: `scripts/ingest_folder.py` remains compatibility-only and delegates to the canonical CLI.

## Frozen Output Files

Formal ingestion produces structured files, not Markdown intermediates:

- `pages.jsonl`
- `chunks.jsonl`
- `api_context.json`
- `manifest.json`

These outputs are enough for Phase-1 S2 retrieval and API/CLI query flows.

## Active And Deferred Skills

Active:

- `s1_ingestion`
- `s2_retrieval`
- `s3_qa_summary`
- `v4_style`

Deferred and inactive:

- `s4_engineering_analysis`
- `s5_formula_derivation`
- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`

Deferred skills may remain in registries, docs, and scope declarations. They must not be called by the Phase-1 Tutor-Orchestrator, CLI query path, or API query path.

## Verified Acceptance

Phase 1 verifies:

- raw fixture PDF -> structured chunks and manifest
- chunks -> retrieval hits with citations
- real in-scope vibration question -> engineering-template answer with citation
- in-scope evidence gap -> `insufficient`
- out-of-scope query -> `out_of_scope`
- CLI/API/legacy ingestion paths
- fast and full regression suite split

## Known Non-Blocking Limits

The following are explicitly outside the Phase-1 freeze:

- live Postgres/Qdrant/Redis persistence and retrieval
- production API hardening such as auth, CORS, rate limiting, path sandboxing, and dependency readiness probes
- LLM-backed synthesis, citation checking, reviewer, and Opus execution loop
- S4-S8 and V1-V3 runtime behavior
- DOCX parsing
- full large-book corpus regression as a default test

See `docs/phase_1_deferred_and_polish_audit.md` for the detailed deferred/polish ledger.

## Phase 2 Approved Development Boundary

Phase 2 is now governed by `docs/phase_2_development_order.md`. It extends the Phase-1 skeleton toward a locally usable personal knowledge-base Agent, but it does not retroactively change the frozen Phase-1 chain.

The authoritative Phase-2 scope, exclusions, order, and risk controls live in `docs/phase_2_development_order.md`. This freeze document only records the compatibility rule: none of the Phase-2 scope changes the Phase-1 frozen chain until a specific Obj completes the canonical schema-change process in `docs/phase_2_migrations.md`. Work proceeds one Obj at a time, with review before the next Obj starts.

## Phase 2 Freeze Cross-Reference

Phase 2 is frozen separately in `docs/phase_2_interface_freeze.md`. That file is
the authority for the current Phase-2 runtime chain and active skills. This
Phase-1 document remains the compatibility baseline for older consumers.
