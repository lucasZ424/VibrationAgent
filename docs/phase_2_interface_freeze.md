# Phase-2 Interface Freeze

Updated: 2026-06-08

## Freeze Decision

Phase 2 is frozen as the local personal knowledge-base runtime. It extends the
Phase-1 chain without removing Phase-1 entry points or file contracts.

The frozen query path is:

```text
User query
  -> TutorOrchestrator
  -> S2 retrieval
  -> S3 evidence-bound synthesis
  -> optional S4 engineering analysis OR optional S5 formula derivation
  -> V2 citation check
  -> V4 style
  -> optional V3 reviewer for extreme tasks
  -> optional supervisor annotation/handoff
  -> SkillOutput/API/CLI JSON
```

S1 remains explicit ingestion. It prepares file-backed knowledge exports for S2
and is invoked through CLI/API/script ingestion entry points, not on every query.

## Frozen Active Skills

Active and available:

- `s1_ingestion`
- `s2_retrieval`
- `s3_qa_summary`
- `s4_engineering_analysis`
- `s5_formula_derivation`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`
- `v4_style`

Deferred and inactive:

- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`

V1 is active but not a chain step. It can normalize S2 input context before S3
and normalize V4 output after rendering. The default is input normalization off
and output normalization on.

V3 is active but advisory. It runs only when routing marks a task `extreme` and
does not block the answer by itself.

## Frozen Runtime Contracts

The following schemas remain the public contract surface:

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
- `EmbeddingRecord`
- `DocumentBibliography`
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

Phase-2 schema changes were additive. Deprecated names are not removed in this
freeze. The `phase0_pipeline` API/config field name is retained as a legacy
compatibility field even though its value now records the Phase-2 query chain.

## Frozen Structured Result Additions

`SkillOutput.structured_result` may now include these Phase-2 keys:

- `chain`: ordered skill execution summaries.
- `skill_results`: per-skill structured outputs.
- `unsupported_claims`: V2-blocked claims.
- `citation_check`: V2 visibility/ref summary.
- `reviewer_notes`: V3 advisory notes.
- `supervisor_status`: `not_triggered`, `approved`, or `fallback`.
- `supervisor_invocations`: supervisor review count.
- `supervisor_action`: supervisor action when applicable.
- `supervisor_issues`: serialized supervisor review issues when applicable.

`SkillOutput.citations` remains the locatable answer citation list. Unsupported
claims blocked by V2 do not appear in the final answer citations.

## Frozen File Outputs

Ingestion outputs remain structured files:

- `pages.jsonl`
- `chunks.jsonl`
- `api_context.json`
- `manifest.json`

PDF and DOCX sources both flow into the same `OcrPage`, `MemoryChunk`, and asset
contracts. DOCX pagination is logical page 1 unless a later phase adds rendered
pagination.

## Frozen Runtime Defaults

Defaults preserve local deterministic operation:

- S3 LLM synthesis is off unless `S3_LLM_ENABLED=true` or request constraints
  enable it with an injected/captured client path.
- Qdrant is off unless `QDRANT_ENABLED=true`.
- Postgres qa_logs persistence is off unless `POSTGRES_ENABLED=true`.
- API auth, CORS, and rate limiting are off unless configured.
- API ingestion paths must resolve inside the configured workspace.
- No online LLM, live Opus, live Postgres, or live Qdrant is required for the
  fast suite or local deterministic query path.

## Frozen Entry Points

- CLI: `python -m apps.cli.main`
- API: `apps.api.main:app`
- Legacy ingestion shim: `scripts/ingest_folder.py`
- Large-corpus benchmark: `scripts/bench_large_corpus.py`
- Manual Phase-2 E2E probe: `scripts/manual_e2e.py`

## Frozen Verification Gates

Local deterministic verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus"
```

Fast CI gate:

```powershell
python -m pytest tests -q -m "not integration"
python -m pytest tests/integration/test_phase2_end_to_end.py -q -m "not large_corpus"
```

Nightly CI gate:

```powershell
python -m pytest tests -q
python scripts/bench_large_corpus.py tests/fixtures/raw/small_vibration_native.pdf --workspace data/tmp/ci-large-corpus --output data/exports/ci/large_corpus_baseline.json --max-pages 1 --top-k 2
```

Nightly artifacts are uploaded from `data/exports/ci/` and must not be committed.

## Change Rule After Freeze

Any post-freeze change to schemas, entry points, chain order, structured result
keys, API request/response shape, or ingestion output shape must:

1. Start in `src/vibration_agent/schemas.py` when a schema is affected.
2. Add a migration note in `docs/phase_2_migrations.md`.
3. Update fixtures/tests that encode the affected shape.
4. Update downstream callers only after tests encode the new contract.
5. Record the change in this freeze document or a Phase-3 migration document.
