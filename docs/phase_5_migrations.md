# Phase 5 Migrations

Updated: 2026-06-30

## Purpose

This file is the canonical migration log for Phase-5 schema, configuration,
retrieval, embedding, provider, replay, scoring, API, and UI contract changes.
Phase 5 inherits the frozen Phase-4 baseline and may change it only through an
explicit entry here before downstream callers rely on the change.

## Binding Boundary

Phase 5 is local-first and single-user. Shared, remote, public, and multi-user
deployment are deferred indefinitely and cannot be introduced through a
migration entry. Reopening that scope requires an explicit user-directed change
to `docs/vibration_agent_design.md` followed by a new phase plan.

## Canonical Change Checklist

For any objective that changes a schema, API response shape, structured-result
key, retrieval lane, embedding model/dimension, scoring rule, provider request,
replay fixture, prompt schema, chain order, UI contract, or downstream caller:

1. Update `src/vibration_agent/schemas.py` first when a schema is affected.
2. Add the migration entry before changing downstream callers.
3. Record compatibility behavior, default state, data/reindex requirements,
   rollback, and residual risk.
4. Add or update fixtures and tests that encode the contract.
5. Record verification and the next-objective gate in
   `docs/phase_5_progress.md`.
6. Leave issue-log authoring to the user unless explicitly requested.

Default policy: additive fields, deterministic/replay CI, live paths default-off,
and visible fallback. A replacement is promoted only when the Obj1 scorecard
shows no recall/faithfulness regression and at least one labeled miss is fixed.

## Retrieval And Model Checklist

1. Record embedding provider, model, version, dimension, distance, and collection.
2. Measure lexical and ANN lanes independently before fusion or replacement.
3. Preserve PG:Qdrant parity and provide a reproducible rollback/reindex path.
4. Record prompt/schema versions, provider/model, max output, token budgets,
   request hash, usage, and cost metadata for model-backed paths.
5. Keep live providers out of CI and require replay fixtures plus deterministic
   fallback.
6. Treat V2 faithfulness as a hard acceptance boundary for model output.

## Migration Log

### Obj0 - Phase-5 execution baseline (2026-06-30)

Documentation-only baseline.

- Added the Phase-5 scope, development order, progress, and migration ledgers.
- Reserved `docs/issue_log_p5/` in `.gitignore` for user-owned review artifacts.
- Inherited the Phase-4 R3 runtime baseline: multilingual Qdrant ANN,
  source-aware citations, heuristic answer telemetry, answer-first operator UI,
  and aligned live-model token budgets.
- Recorded that the R3 answer score is uncalibrated and that the default API does
  not yet construct live GPT/Opus clients.
- Replaced the former remote/shared decision objective with the Phase-5 final
  interface freeze and made remote/shared/public/multi-user scope indefinitely
  deferred.

No runtime schema, API, retrieval, provider, UI, database, or chain behavior is
changed by Obj0 documentation.

Verification: four canonical documents present; Obj0-Obj10 numbering aligned;
all development-order objectives contain the required functional and acceptance
sections; stale Phase-5 scope references and active remote/shared gates absent;
`git diff --check` passed. Code tests were not run because Obj0 is
documentation-only.

Rollback: revert the Phase-5 planning documents. The frozen Phase-4 runtime is
unaffected.

### Obj1 - Real-question evaluation contract (2026-06-30)

Status: implemented; baseline pending user review.

Additive artifacts:

- `tests/fixtures/rag_qa/questions.json` defines
  `phase5.rag_qa.questions.v1`: stable case ids, bilingual intent coverage,
  expected doc/page/chunk evidence, key-fact aliases, human completeness rubric,
  and evidence boundary.
- `scripts/rag_qa_eval.py` emits `phase5.rag_qa.report.v2`: per-case chain output
  and aggregate recall@5/@10, completeness, V2 faithfulness, sentence
  completeness, latency, V2 status counts, multi-label miss counts, mutually
  exclusive primary miss counts, and a deterministic fingerprint.
- `tests/fixtures/rag_qa/post_r3_baseline.json` freezes the 4,436-chunk post-R3
  scorecard and records corpus id, embedding model/dimension, retrieval config,
  and Git commit.

Execution boundary:

- The runner uses the existing S2 -> S3 -> V2 -> V4 runtime contracts and does
  not change any production schema, score, retrieval setting, or answer path.
- Live providers and Postgres logging are disabled for this evaluator. The
  sentence-transformer is resolved from an existing local snapshot and Qdrant
  is local read-only input; a missing corpus or model snapshot fails loud.
- Latency is reported but excluded from the deterministic fingerprint. Any
  future field or scoring change requires a report-schema version bump and a
  regenerated baseline rather than silently overwriting this contract.
- Report v2 supersedes the pre-review v1 baseline. It makes ranking reachable
  whenever recall improves from top 5 to top 10, derives terminology from
  asymmetric bilingual-pair recall instead of English-only hints, and records
  the stable evidence rule `exact chunk id OR same doc id with page overlap`.

Compatibility: additive evaluation-only contract; no runtime consumer changes.
Data migration: none. Rollback: remove the Obj1 evaluator, fixtures, baseline,
and tests; the Phase-4 runtime remains unchanged.

### Obj2 - Calibration checkpoint contract (2026-06-30)

Status: additive checkpoint; awaiting operator-run calibration.

- `phase5.rag_qa.questions.v2` adds required `usability_label` and
  `usability_reason` fields to each frozen question.
- `phase5.rag_qa.report.v3` adds each case's raw production `answer_quality`
  object so score and subscore calibration does not reconstruct hidden values.
- `phase5.answer_quality_calibration.report.v1` records label/V2 distributions,
  candidate-threshold confusion matrices, and the proposed rule that a usable
  classification requires both threshold passage and `v2_status == ok`.
- The final machine-readable report is versioned at
  `tests/fixtures/eval/answer_quality/obj2_calibration.json`; a regression test
  requires exact equality with a fresh deterministic run.
- These are evaluation-only additions. No production threshold, score formula,
  V2 behavior, API response, or UI contract changes at this checkpoint.
- The v3 full-corpus report and calibration output are operator-run prerequisites
  for the next Obj2 implementation decision. A missing/stale report fails loud.
- Calibration also validates each nested `answer_quality.schema_version`; an
  outer report v3 containing old v1 scores is rejected and must be regenerated.
- Scope/degraded early returns with no score are accepted only when V2 is not
  `ok`; they are recorded as `not_scored` and remain blocked. A V2-`ok` case
  without a score fails loud.

Rollback: remove the v2 labels and calibration runner and restore report v2.
No runtime or stored corpus migration is required.

### Obj2 - Diagnostic score v2, pre-threshold implementation (2026-07-01)

Status: implementation in progress; threshold remains unapproved.

- `answer_quality.schema_version` changes from `r3.answer_quality.v1` to
  `phase5.answer_quality.v2`.
- `question_coverage` becomes bilingual query-aspect coverage rather than raw
  query-token overlap. `completeness` becomes intent-specific required-slot
  coverage for definition, mechanism, comparison, diagnosis, workflow,
  standards, and formula answers.
- `evidence_relevance` uses cited chunk rank and score from S2 retrieval hits;
  citation confidence is no longer accepted as a retrieval-relevance proxy.
- Additive fields expose detected intent, required/covered slots, `gate_status`,
  and `gate_reasons`. `faithfulness_status != ok` always yields `blocked`.
- The operator labels the numeric value `diagnostic` and renders `gate_status`;
  it does not display a pass state before threshold approval.
- Faithful answers remain `diagnostic_only`; no pass threshold is introduced
  until the operator reruns Obj1/Obj2 calibration and the result is reviewed.

Compatibility: existing score/subscore and faithfulness keys remain present,
but score values are intentionally not numerically comparable with v1.
Rollback: restore the v1 scoring helpers and schema marker. No data migration or
corpus change is required.

### Obj2 - Completeness hard gate recalibration checkpoint (2026-07-01)

Status: threshold approval pending operator recalibration.

- The first score-v2 calibration found zero-error score+V2 candidates at 0.75
  and 0.80. A regression then proved that keyword repetition can score exactly
  0.75 while satisfying none of the intent slots.
- The gate now blocks `faithfulness_status != ok` and incomplete intent slots.
  Faithful, complete answers remain `diagnostic_only`; no production pass or
  threshold is exposed until calibration is rerun with this full rule.
- Candidate ranking now uses decision margin after minimizing false allows and
  false blocks, instead of selecting the highest zero-error threshold.

Residual risk: calibration contains one usable and thirteen unusable answers.
Every new human-labeled usable case must rerun calibration; threshold promotion
requires explicit review of the updated confusion matrix and decision margin.

### Obj2 - Final calibrated acceptance gate (2026-07-01)

Status: implemented and final operator regression passed.

- Operator calibration under the complete score+V2+completeness rule selected
  threshold `0.75` with decision margin `0.044`, accuracy 1.0, false allow 0,
  false block 0, usable recall 1.0, and unusable block rate 1.0.
- `gate_status=pass` now requires score >= 0.75, V2 status `ok`, and completeness
  1.0. Every failed condition is listed in `gate_reasons`; the threshold is
  exposed as `answer_quality.threshold`.
- The operator colors only explicit `gate_status=pass` as pass. A numeric score
  alone never implies acceptance.

Residual risk: the positive calibration population contains one case. The gate
is approved for the current Obj1 fixture, not as a universal statistical claim.
New labeled positives require recalibration before changing this threshold.

Post-review hardening:

- Unknown/general intent is fail-closed for completeness; answer length alone
  cannot satisfy the hard gate.
- Empty citations have a direct zero-relevance regression test.
- Current consumer audit found no numeric-score acceptance consumer. The
  operator uses `gate_status`; eval/calibration code treats the score as input
  and applies the full gate rule explicitly.

Final verification: Obj1 report v3/score v2 regenerated; answer-quality
calibration accuracy 1.0 with zero false allows/blocks; legacy V2 calibration
12/12 passed; retrieval fixture recall@5/@10 1.0; canonical non-large suite
562 passed with one registered large-corpus deselection.

### Obj3 - Stable reindex identity and vector-space contract (2026-07-01)

Status: complete; operator parity, ANN baseline, and hybrid no-regression
validation reviewed.

- Migration `004_phase5_obj3_reindex_identity.sql` adds stable external document
  and chunk ids plus chunk pages/source type/topic to Postgres. Existing exports
  must be persisted again after migration so old rows receive these fields; no
  OCR, chunking, or corpus-content change is required.
- The supported baseline remains
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions,
  and cosine distance. Qdrant payloads now record model, version, and dimension.
- `scripts/qdrant_reindex.py` is dry-run by default. Execution is explicit,
  batched, idempotent by stable chunk UUID, and resumable from a checkpoint bound
  to corpus fingerprint, collection, model/version, and dimension.
- Existing collections with a different dimension or distance fail loud.
  Recreate requires the explicit `--recreate-collection` option and cannot resume
  a partially completed checkpoint.
- Token-feature fallback is never written or reported as ANN. Completion requires
  exact Postgres/Qdrant point and source-type parity.
- `scripts/ann_retrieval_eval.py` measures only query embedding plus Qdrant ANN.
  It reports recall@10 overall/by language, paired zh/en recall, and cold/steady
  latency; lexical, hybrid, rerank, and token fallback paths are not imported.

Compatibility: additive Postgres columns and Qdrant payload field. Query and
answer contracts are unchanged. Rollback: stop using the reindex command and
retain the existing collection; the additive database columns may remain.

Post-validation measurement correction:

- `phase5.obj3_ann_eval.report.v2` records post-R3 hybrid recall as an
  informational, non-comparable reference. ANN-only recall is no longer failed
  against a hybrid score that includes lexical/fusion compensation.
- The accepted independent ANN baseline is recall@10 0.500, zh 0.643, en 0.357,
  paired zh/en 0.286. Obj4 must compare ANN and lexical lanes independently;
  replacement still requires fused recall not below the better lane and at least
  one real miss fixed.
- The user ratified this Obj3/Obj4 scope split on 2026-07-01. Obj3 still requires
  a post-reindex hybrid scorecard against the unchanged 0.571 hybrid baseline;
  the operator result held at 0.571 and closed the runtime no-regression loop.

### Obj4 - Independent retrieval lane candidate (2026-07-01)

Status: complete; replacement, full RAG/V2, and canonical non-large gates passed.

- `RETRIEVAL_INDEPENDENT_LANES_ENABLED` is additive and defaults false. The
  existing ANN-candidate-scoped runtime path remains active until the Obj4
  replacement gate passes.
- When enabled, ANN queries Qdrant directly while BM25 searches the complete
  Qdrant payload corpus. Payloads are cached once per process/client/collection;
  ingestion or reindex requires explicit cache clear or process restart.
- `phase5.retrieval_aliases.v1` is the only bilingual lexical expansion source.
  Free-form/model query rewrite is not used.
- Retrieval output adds mode-specific lane telemetry: source, latency, fallback,
  rank, raw/normalized score, and per-candidate RRF contribution.
- Hybrid uses RRF for general intents. Explicit standard identifiers use a
  deterministic lexical 0.9 / ANN 0.1 candidate fusion because the first lane
  run proved BM25 fixed the Chinese standard miss while plain RRF discarded it.
- `phase5.obj4_retrieval_eval.report.v1` compares bm25/dense/hybrid independently.
  Candidate replacement requires hybrid recall@10 >= both single lanes and the
  0.571 runtime baseline, at least one frozen miss fixed, and no existing pass
  becoming a complete miss. A passing candidate still requires full RAG/V2
  validation before default promotion.

Compatibility: output/config fields are additive; the runtime retrieval default
intentionally changes after both replacement gates passed. Rollback: set
`RETRIEVAL_INDEPENDENT_LANES_ENABLED=false`; no corpus change is required.

Lane calibration result:

- First plain-RRF candidate scored hybrid recall@10 0.536 and failed replacement.
- Standard-lookup weighted fusion scored 0.607 versus BM25 0.429, ANN 0.500,
  and runtime baseline 0.571; it fixed the frozen Chinese GB/T 33199 scope miss
  without turning an existing pass into a complete miss.
- This releases only the full RAG/V2 prerequisite. Default promotion remains
  blocked until faithfulness and answer-quality checks pass.
- The first full-chain run exposed a pre-S2 scope mismatch: `GB/T 33199` queries
  were rejected before retrieval. The scope boundary now narrowly admits that
  frozen rotating-machinery standard identifier while retaining an unrelated
  GB/T negative regression; at that checkpoint default promotion awaited a rerun.

Final promotion:

- The rerun produced hybrid recall@10 0.607 and V2 faithfulness 0.500, both above
  the post-R3 0.571/0.429 references. Completeness and sentence completeness also
  improved to 0.339/0.902.
- `independent_lanes_enabled` is now true by default. Operators can immediately
  roll back with `RETRIEVAL_INDEPENDENT_LANES_ENABLED=false`; no data migration or
  reindex is required.
- Final canonical non-large regression: 591 passed, 1 registered large-corpus
  deselection, 0 failed.

Review hardening:

- Standard scope is no longer a literal `GB/T 33199` exception. The versioned
  `taxonomy/corpus_standards.yaml` snapshot is derived from Qdrant
  `source_title`, `source_filename`, `doc_id`, and `title` fields.
- After replacing or reindexing the corpus, run
  `python scripts/build_corpus_standard_catalog.py` before restarting the service.
  Body-text references are intentionally excluded so a cited, non-ingested
  standard does not widen the scope boundary.

### Obj5 - Deterministic evidence-selection candidate (2026-07-02)

Status: default-off candidate awaiting Obj1 completeness/V2 validation.

- Retrieval output additively exposes `evidence_context` and
  `evidence_selection`; Obj4 `hits` and `retrieval_context` retain their existing
  meaning.
- `EVIDENCE_SELECTION_ENABLED=true` enables bounded seed selection, same-document
  adjacency, duplicate removal, and the configured evidence token/chunk limits.
- S2/S3 use selected evidence and citations only when the candidate is enabled.
  Model reranking remains disabled and is explicitly rejected by the Obj5 gate.
- The first candidate exposed that unconditional adjacency can increase keyword
  completeness with unusable OCR fragments. Expansion now requires a verifiable
  boundary signal, and promotion also requires sentence completeness not below
  the Obj4 value of 0.902.
- OCR U+FF0E fullwidth periods are now treated consistently as sentence endings
  by S3 extraction, evidence boundary detection, and answer readability scoring.
- V2 now recognizes deterministic S3 inline evidence tags in addition to square
  bracket refs and retains citations for every referenced S2-visible chunk.
  Obj5 promotion requires `citation_alignment_rate == 1.0`.
- Under Obj5, V2 validates against `evidence_context`, matching the evidence S3
  actually consumed; when absent, it retains the prior `retrieval_context`
  behavior.
- S3 no longer treats a raw `context.chunks` corpus as answer evidence when an S2
  handoff exists. This fixes a full-corpus leakage in local evaluation and
  invalidates historical full-chain answer-quality comparisons; retrieval recall
  remains independently valid. Obj5 promotion uses a corrected selector-off/on
  paired baseline.
- After the corrected pair rejected the six-seed candidate, the selector budget
  was revised to preserve raw top10 (`seed_chunks=10`, `max_chunks=12`, token
  budget 6000). Adjacent expansion requires continuity signals on both sides of
  the chunk boundary.
- The conservative candidate was metric-identical to selector-off and therefore
  remains disabled. Generic keyword-aspect diversification was tested, regressed
  representative cases, and was removed; promotion now depends on a separately
  evaluated reranking strategy rather than gate relaxation.

Compatibility: additive output/config fields. Rollback:
`EVIDENCE_SELECTION_ENABLED=false`; no reindex or corpus mutation is required.
