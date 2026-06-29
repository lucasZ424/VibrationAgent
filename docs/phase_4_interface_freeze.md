# Phase 4 Interface Freeze

Date: 2026-06-18

Closure confirmed: 2026-06-29

## Freeze Decision

Phase 4 is frozen as the local-first, single-user engineering assistant
baseline for real local iteration.

Phase 4 and its post-freeze R1-R3 local iterations are formally closed. This is
an interface/framework closure, not an engineering-answer usability claim. Real
question audits show that retrieval and deterministic answer synthesis still
require a successor reliability phase before the product can be described as
engineering-usable.

This freeze is additive on top of:

- `docs/phase_3_interface_freeze.md`
- `docs/phase_4_backend_interface_freeze.md`
- `docs/phase_4_remote_shared_hardening_decision.md`

Phase 4 does not redefine the product as remote, shared, public, or multi-user.
The next recommended work is local operation against real vibration-engineering
corpora: knowledge-base growth, taxonomy expansion, retrieval/citation miss
analysis, and backend reliability polishing from actual use.

## Frozen Runtime Position

The default query path remains:

```text
S2 retrieval
  -> S3 evidence-bound synthesis
  -> optional S4 engineering analysis OR optional S5 formula derivation
  -> V2 citation check
  -> V4 style
  -> optional V3 reviewer / supervisor for extreme or flagged outputs
```

S1 ingestion remains an explicit corpus-building entry point. S6/S7/S8 remain
default-off advisory handoff skills unless an explicit advisory routing gate is
enabled; their outputs do not become final-answer authority.

The system is suitable for local engineering-assistant trial use, not for
unsupervised engineering truth, remote deployment, or multi-user production.

## Frozen Phase-4 Additions

Phase 4 freezes these additions:

- broader replay eval, V2 calibration, and retrieval target fixtures;
- offline retrieval recall audit and replacement gate;
- optional/default-off embedding provider support;
- Qdrant reindex/replacement gate with explicit non-replacement baseline;
- deterministic V2 evidence-support hardening;
- default-off S6 literature search, S7 model selection, and S8 experiment
  advice prototypes;
- controlled advisory routing gate for S6/S7/S8;
- optional rendered DOCX pagination metadata and rich asset anchors;
- formula rendering metadata with plain-text fallback;
- CAS/symbolic-proof defer decision;
- backend interface freeze through Obj13;
- read-only local operator UI at `/operator`;
- local-first observability with offline `/health`, default-off dependency
  probing through `/diagnostics`, and structured redacted logs;
- remote/shared hardening decision: deferred;
- Phase-5 candidate scope document.

## Frozen API And UI Surface

Frozen local API routes:

- `GET /health`
- `GET /diagnostics`
- `GET /scope`
- `POST /ingest`
- `POST /query`
- `GET /operator`
- `GET /operator/assets/{path}`

Relative to the Obj13 backend freeze, Obj14 added the additive `/operator` and
`/operator/assets/{path}` routes. Obj15 added the additive `/diagnostics` route
and migrated `/health` to offline semantics with additive
`ApiHealthResponse.diagnostics` and `ApiDiagnosticsResponse` schemas. No
`/query`, `/ingest`, `/scope`, chain order, retrieval, provider, or
final-answer contract changed.

`/health` is a local liveness/config probe and must not require Postgres,
Qdrant, external network services, or live model providers.

`/diagnostics` is read-only. By default it does not probe external dependencies;
`probe_dependencies=true` is an explicit operator action for configured
Postgres/Qdrant reachability checks.

`/operator` is read-only. It may query existing local API contracts and display
diagnostics, citations, chain state, warnings, supervisor metadata, cost
metadata, and raw response JSON. It must not expose ingestion, delete, admin,
provider-key, live-provider, remote deployment, or multi-user management
controls without a future migration.

## Frozen Local Configuration Boundary

`.env` is the only local dotenv file read by `config.load()`. `.env.local` and
`.env.example` are not runtime sources.

Live model providers, external search, OpenAI embeddings, Qdrant, Postgres, and
rendered DOCX backends remain opt-in/manual or explicitly configured. CI must
continue to pass without live provider keys, external network services, Qdrant,
Postgres, or LibreOffice.

## Accepted Residual Risks

Accepted Phase-4 residual risks are recorded in
`docs/phase_4_deferred_and_polish_audit.md`. The important current risks are:

- V2 is deterministic evidence support, not general semantic entailment.
- S5 is evidence-bound derivation support, not formal symbolic proof.
- Formula rendering metadata is render-attempt metadata, not proof metadata.
- S6 external literature candidates are not final-answer evidence unless later
  ingested or covered by a V2-compatible external-evidence contract.
- DOCX rendered pagination lacks multi-page block-to-rendered-page mapping.
- The operator UI is a minimal read-only local surface, not a full workbench.
- Remote/shared hardening is deferred and not implemented.
- Fixture evals are regression nets, not proof of real-corpus reliability.

## Phase-5 And Local Iteration

`docs/phase_5_candidate_scope.md` is the durable home for future candidates.
Phase 5 is not active.

Before any remote/shared expansion, the project should run a local iteration
cycle:

- ingest a representative vibration-engineering corpus;
- expand taxonomy terms, symbols, units, aliases, and bilingual mappings from
  real misses;
- run real operator/API questions;
- collect retrieval misses, unsupported citation examples, false blocks, false
  allows, and workflow friction;
- improve local backend behavior only where real evidence justifies it.

## Final Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-final-freeze -p no:cacheprovider
```

Result: passed, 453 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase4_final_llm_eval.json
```

Result: 7 cases, 7 passed, 0 failed, pass rate 1.0, citation faithfulness pass
rate 1.0, unsupported numeric block rate 1.0.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_final_retrieval_eval.json
```

Result: 4 cases, 3 evidence cases, 1 expected-miss case,
`top_k_recall@5 = 1.0`, `top_k_recall@10 = 1.0`, no missing evidence cases,
and `replacement_justified_by_baseline = false`.

## Change Rule After Freeze

### Post-freeze local iteration R1 - Wave A

The 2026-06-22 R1 Wave-A refinement improves deterministic answer quality by
reflowing soft PDF/OCR line wraps before S3 claim extraction and localizing S4
deterministic framing. S4 now consumes the existing additive
`structured_result.language` field emitted by S3, with a content-based fallback
for older payloads where that field is absent. The change does not alter chain
order, schemas, API routes, provider defaults, retrieval behavior, or V2/V4
final-answer authority. Details and rollback are recorded in
`docs/phase_4_migrations.md`.

### Post-freeze local iteration R1 - Wave B

The 2026-06-22 R1 Wave-B refinement expands deterministic retrieval aliases,
corrects standard-scope intent precedence and claim selection, and prevents V2
from treating numeric paper bibliography markers and ranges as Agent chunk
references. It adds retrieval and V2 calibration fixtures without changing
schemas, chain order, API routes, providers, database contracts, or final-answer
authority. Details and rollback are recorded in `docs/phase_4_migrations.md` and
`docs/refinements/r1_wave_b_retrieval_scope.md`.

### Post-freeze local iteration R1 - Wave A.2

The 2026-06-22 R1 Wave-A.2 refinement adds optional offset-based typed text
segments to chunk metadata and makes deterministic S3 claim extraction consume
them while retaining a bounded fallback for existing chunks. Native layout now
distinguishes primary titles, labels, and bibliography blocks using page-relative
font evidence, and S3 applies alias-backed claim focus. This additive
metadata change does not alter top-level schemas, chain order, API routes,
providers, database contracts, or final-answer authority. Details and rollback
are recorded in `docs/phase_4_migrations.md` and
`docs/refinements/r1_wave_a2_layout_aware_claims.md`.

### Post-freeze local iteration R1 - Wave C

The 2026-06-22 R1 Wave-C refinement adds optional direct UTF-8 JSON file output
to the three data-producing CLI commands and best-effort UTF-8 stdout
reconfiguration for redirected CLI JSON. Payload contracts and exit codes remain
unchanged. Details and rollback are recorded in
`docs/phase_4_migrations.md` and
`docs/refinements/r1_wave_c_cli_utf8.md`.

### Post-freeze local iteration R1 - storage persistence

The 2026-06-23 R1 storage refinement wires structured ingestion exports into
opt-in runtime stores. `chunk_documents()` and API `/ingest` now include an
additive `storage` summary; Postgres/Qdrant writes remain disabled by default
and require explicit configuration. Qdrant point ids are now stable UUIDv5 ids,
which requires reindexing any collection previously populated with SHA1-hex
point ids. Details and rollback are recorded in `docs/phase_4_migrations.md`
and `docs/refinements/r1_wave_c_storage_persistence.md`.

### Post-freeze local iteration R2 - critical-speed answer quality

The 2026-06-23 R2 refinement changes deterministic retrieval and S3 synthesis
behavior for a real operator miss: critical-speed outcome questions must be
supported by outcome evidence, not definition-only evidence. BM25 CJK
tokenization now avoids single-character noise for multi-character Chinese
segments, and critical-speed outcome queries add response/amplitude expansion
terms. The change does not alter schemas, API routes, chain order, provider
defaults, database contracts, or final-answer authority. Details and rollback
are recorded in `docs/phase_4_migrations.md` and
`docs/refinements/r2_critical_speed_answer_quality.md`.

### Post-freeze local iteration R2 - ingestion trial operations

The 2026-06-23 R2 ingestion runbook adds a manual, log-to-file trial procedure
for validating Postgres/Qdrant ingestion on a small batch before full-corpus
ingestion. It also adds local support scripts for resetting regenerated runtime
stores and for persisting existing file-based ingestion exports through the
existing storage path, enabling resumable OCR workflows without changing
ingestion schemas, API routes, chain order, provider defaults, database schemas,
retrieval behavior, or final-answer authority. Qdrant ingestion summaries gain
the additive `embeddable_chunks` field so full-run validation compares vector
points with chunks that contain non-empty text. Details and rollback are
recorded in `docs/phase_4_migrations.md`.

### Post-freeze local iteration R2 - page-level visual recovery

The 2026-06-25 R2 refinement is authorized to change native-PDF ingestion
behavior from per-image-block handling to deterministic page-level visual
analysis. The approved boundary is:

- scanned-page classification has precedence and uses one full-page
  PaddleOCR/Tesseract recovery path;
- native/mixed pages preserve native body text and may recover fragmented
  engineering figures through bounded spatial clustering and region rendering;
- microscopic blocks are never exported individually;
- region OCR is optional additive asset metadata, not a retention gate;
- VLM description remains out of scope.

This refinement may change page metadata, assets, chunk text and boundaries,
chunk ids, embeddings, citations, and persisted figure/table rows. It does not
change top-level schemas, API routes, orchestration chain order, database table
schemas, provider defaults, or final-answer authority.

Full ingestion is temporarily gated. Implementation must first pass the labeled
visual-decision calibration set, deterministic clustering tests, scanned-page
route tests, real-corpus regressions, storage parity checks, and representative
asset inspection defined in
`docs/refinements/r2_page_level_visual_recovery.md`. After acceptance, all
generated local artifacts, Postgres ingestion rows, and Qdrant points must be
cleared and rebuilt. Emergency-guard-only and visual-recovery outputs must not be
mixed as the stable knowledge-base baseline.

Details, re-ingestion requirements, residual risk, and rollback are recorded in
`docs/phase_4_migrations.md`.

### Post-freeze local iteration R3 - answer usability telemetry

The 2026-06-26 R3 refinement may add optional source-display metadata to
citations and deterministic answer-quality telemetry to final structured
results. These fields are additive operator-usability signals. They do not
change top-level API routes, orchestration chain order, database table schemas,
provider defaults, V2 faithfulness authority, or final-answer authority.

Details and rollback are recorded in `docs/phase_4_migrations.md`.

### Formal closure after R3

R3 closes the Phase-4 local iteration ledger with additive runtime ANN
retrieval, source-aware citations, heuristic answer telemetry, and an
answer-first operator surface. The closure preserves these boundaries:

- `answer_quality` is diagnostic telemetry only and has no acceptance threshold;
- V2 remains the faithfulness authority;
- live GPT/Opus clients are not wired into the default API orchestrator;
- fixture and unit success does not establish real-question usability;
- retrieval/synthesis reliability work moves to the Phase-5 candidate scope.

No further feature iteration should be recorded against Phase 4. Corrections to
the frozen contracts require a migration; new answer-reliability capability
requires activation of a successor phase with its own acceptance gates.

Closure verification on 2026-06-29:

- non-large-corpus suite: 541 passed, 1 deselected;
- replay LLM eval: 7/7 passed, citation faithfulness 1.0, unsupported numeric
  block rate 1.0;
- deterministic retrieval fixture eval with `EMBEDDING_ENABLED=false`: 6 cases,
  recall@5 1.0, recall@10 1.0, no missing evidence cases;
- live GPT-5.5 S3 completed with provider usage/cost metadata;
- live Opus calls were reachable and no longer budget-denied after token-budget
  alignment, but correction-response validation still fell back. This is an
  explicit successor-phase reliability gap, not a Phase-4 closure blocker.

Any post-freeze change to schemas, API routes or response shapes, chain order,
retrieval replacement behavior, provider request shape, replay/eval fixture
layout, ingestion output shape, operator UI contract, observability contract, or
final-answer authority must:

1. Record a migration in `docs/phase_4_migrations.md`.
2. Add or update tests/fixtures before downstream callers depend on the change.
3. Preserve local-first deterministic defaults unless a new objective explicitly
   changes the product boundary.
4. Update this freeze or a successor freeze if the change becomes part of a new
   stable baseline.
