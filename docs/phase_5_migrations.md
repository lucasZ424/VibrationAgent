# Phase 5 Migrations

Updated: 2026-07-06

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

### Obj6A - Replay-first S3 client activation (2026-07-03)

Status: complete; replay gate and canonical non-large regression passed.

- The existing default-off `S3_LLM_ENABLED` flag now wires the normal
  `TutorOrchestrator` S3 path instead of requiring manual skill injection.
- With S3 enabled and `LLM_LIVE_ENABLED=false`, S3 uses `ReplayClient` from the
  configured replay directory. A replay miss remains visible and falls back to
  deterministic extraction.
- A live OpenAI client is constructed only when both flags are explicitly true.
  Construction is lazy-imported and uses the existing per-task/session
  `BudgetGuard`; pytest's provider guard remains authoritative.
- Prompt `s3_qa_summary.v1`, schema `s3.v1`, evidence allowlist, max output,
  request hash, usage, and cost contracts are unchanged.
- `phase5.obj6a.requests.v1` records the four semantic hard-case request files
  and stable hashes. `phase5.obj6a.gate.v1` requires global completeness gain,
  hard-case gain, V2 1.0, readability >= 0.890, citation alignment 1.0, corpus
  parity, and unchanged recall@10.
- Prompt `s3_qa_summary.v2` fixes output-language routing: a substantive English
  query requests English even when retrieved evidence is predominantly Chinese;
  language-neutral summary controls still inherit the evidence language. The
  prompt-version change intentionally invalidates v1 replay hashes.
- Manual capture now persists a response only after task-specific schema
  validation. Truncated or provider-level incomplete objects fail loud and do
  not become replay fixtures; valid raw usage and cost metadata remain stored.
- Prompt `s3_qa_summary.v3` separates user-facing language from the V2 support
  anchor: the answer follows query language, while each `claims[].text` must be
  a short source-language quotation from its cited evidence. Every factual
  answer sentence must map to a visible chunk and support-anchor claim. V2 is
  not weakened to accept unverifiable translated lexical overlap.
- Answer-quality readability now strips trailing V2-visible `[chunk_id]`
  references before checking sentence-final punctuation, matching its existing
  handling of deterministic `(evidence: chunk_id)` tags. The scoring threshold
  and sentence text are unchanged.
- For `synthesis_mode=llm` only, V4 reflows support-anchor whitespace and adds
  display punctuation in non-conclusion/evidence sections. Structured claims
  and citations remain unchanged for V2; deterministic rendering and the
  corrected Obj2 baseline are unaffected.
- S4 additively records `source_synthesis_mode` before applying its own analysis
  mode. V2 preserves this provenance and V4 uses it to recognize an LLM S3
  answer after deterministic S4 framing; V2 strictness still follows the active
  `synthesis_mode` contract.

Compatibility: no response-schema change. Both flags remain default-off.
Rollback: set `S3_LLM_ENABLED=false`; no corpus or reindex change is required.

Final validation:

- Promoted replay: prompt `s3_qa_summary.v3`, four comparison/diagnosis hard
  cases, completeness 0.804, V2 1.000, sentence completeness 0.921, citation
  alignment 1.000, and recall@10 0.607.
- Every Obj6A gate passed, including semantic hard-case gain and no complete
  case regression. The clean-environment canonical non-large suite passed with
  619 passed and 1 deselected in 13.00s.
- Obj6A remains default-off and independently attributable. No Opus supervisor
  result is included in this scorecard.

Post-review solidification:

- `tests/fixtures/rag_qa/post_r3_baseline.json` now stores the corrected fixed-S3
  selector-off floor used by Obj6A instead of the pre-leak-fix report.
- `tests/fixtures/eval/answer_quality/obj2_calibration.json` was regenerated from
  that same baseline. Production threshold 0.75 remains zero-error under the
  complete score+V2+completeness rule; no threshold or runtime behavior changed.
- The report's ranker prefers 0.85 on decision margin, while 0.75 retains the
  same zero-error confusion matrix under the hard gate. This migration records
  the measurement only and does not promote a threshold change.
- Obj6A gate thresholds, including readability, are read from the committed
  baseline. Prompt-v1/v2 captures are diagnostic-only; prompt-v3 is promoted.

Threshold 0.75 is PROVISIONAL (2026-07-03 decision):

- 0.75's score margin on the corrected baseline is negative (-0.041); the
  calibrator's max-margin rule selects 0.85. 0.75 is zero-error only because the
  hard `completeness == 1.0` condition blocks the higher-scoring unusable cases
  (formula_zh 0.791, standards_zh 0.748, mechanism_en 0.725). The wording
  "calibration selects/retains 0.75" is retired.
- Human re-review is complete under the complete-usable standard. The stale
  pre-fix reasons were refreshed, no labels flipped, and the label set remains
  1 usable / 13 unusable.
- Decision: keep 0.75 provisional, backstopped by the completeness hard gate;
  mark the Obj2 calibration provisional. Migrating to 0.85 on a single positive
  label would be brittle, so threshold promotion is deferred until Obj6 produces
  more complete-usable positives and the expanded calibration still supports 0.85
  without lowering usable recall. Obj6B may proceed independently. See
  docs/issue_log_p5/issues_obj6a.txt #4/#5.

### Obj6B - Supervisor correction contract verification (2026-07-06)

Status: complete in isolation. Local schema/replay/capture, replay gate, and
manual live Opus correction evidence are all recorded; combined-chain quality is
not claimed by this migration.

- The existing `SupervisorCorrectionResponse` contract is now covered directly:
  a `status=ok` correction must provide either top-level `answer` or a
  `structured_result` update. An empty `ok` correction raises validation, returns
  the deterministic answer with `supervisor_status=fallback`, and does not count
  as an approved correction.
- `structured_result.answer`-only corrections remain valid and update the final
  answer and nested V4 answer consistently.
- Manual capture validation rejects malformed supervisor corrections before
  replay fixture write, matching the Obj6A capture rule that transport success is
  not a valid replay unless the task schema validates.
- Supervisor approval/fallback annotations now preserve `supervisor_residual_risk`.
  Manual E2E summaries expose `supervisor_corrections` and residual risk so the
  required Obj6 live Opus run records status, usage/cost, remaining risk, and
  errors in one run log.
- Focused verification passed: `tests/unit/test_supervisor_loop.py`,
  `tests/unit/test_manual_live_lane.py`, and `tests/unit/test_llm_replay.py`
  reported 31 passed.
- `scripts/obj6b_supervisor_eval.py` adds a replay-only Obj6B gate. It writes the
  current supervisor review/correction request hashes to `tests/fixtures/llm/obj6b/`
  and verifies reject -> correct -> approve through `ReplayClient`.
- Promoted local replay report:
  `run_logs/obj6b_supervisor_replay_final_20260706_141221.json`; all checks
  passed, with `supervisor_status=approved`, two supervisor invocations, one
  correction, residual risk recorded, and supervisor token cost 60.
- The first live correction attempt revealed a prompt/schema gap rather than a
  runtime defect: Opus returned a correction-shaped review object with
  `status="revised"`. Runtime rejected it and fell back. The review/correction
  prompt now enumerates allowed statuses, forbids revised answers in review
  payloads, and tells correction not to use `status="revised"`. This is guarded
  by `tests/unit/test_supervisor_loop.py`.
- Final live Opus correction gate:
  `run_logs/obj6b_live_correction_20260706_140930.json`; all checks passed, with
  `supervisor_status=approved`, two review invocations, one correction, residual
  risk recorded, token cost 14,213, and captured review/correction fixture hashes
  under `tests/fixtures/llm/obj6b/`.
- Final local non-large regression after Obj6B live/schema changes:
  `run_logs/obj6b_final_nonlarge_20260706_141053.json`, 625 passed and
  1 warning in 17.51s.

Compatibility: no runtime default changes; supervisor remains opt-in and
default-off unless explicitly triggered. Rollback is the existing supervisor
fallback path; no corpus, retrieval, or S3 behavior changed.

### Obj6 - Combined-chain replay/live gate and threshold retake (2026-07-06)

Status: combined replay/live gate passed; default-off runtime contract retained.

- `phase5.obj6.combined_report.v1` evaluates Obj6A S3 replay and Obj6B
  supervisor together on the 14-case Obj1 fixture. The supervisor lane is
  triggered only for the four semantic hard cases and every supervised answer is
  rechecked by V2 after the correction/approval loop.
- `phase5.obj6.combined_gate.v1` extends the Obj6A quality gate with two
  hard-case supervisor checks: every hard case must have
  `supervisor_status=approved`, and every hard case must have
  `combined_chain.post_supervisor_v2_status=ok`.
- `scripts/answer_quality_calibration.py` now accepts both
  `phase5.rag_qa.report.v3` and `phase5.obj6.combined_report.v1` baselines. For
  combined reports it prefers `combined_chain.post_supervisor_v2_status` over
  the row-level `v2_status`, preventing threshold calibration from ignoring the
  post-supervisor faithfulness gate.
- Supervisor review issue normalization now treats nonnumeric `issues[].line`
  values as textual locations and preserves them in `recommendation` rather
  than failing Pydantic validation. Correction application also unwraps a
  nested correction JSON object when a provider returns it as the `answer`
  string. Malformed corrections still fail visibly and fall back.
- Replay fixture writing still redacts secrets and local paths, but no longer
  truncates long response strings. Metadata prompts may be truncated for size;
  replay responses remain byte-complete so long corrected answers can replay.
- Anthropic request timeout is raised from 30s to 120s in `configs/llm.yaml`.
  The change is scoped to live Anthropic calls and was required by the combined
  supervisor prompt size; replay and default-off behavior are unchanged.

Validation:

- Final live combined gate:
  `run_logs/obj6_combined_live_gate_20260706_152132.json`, eligible true.
  Candidate metrics were recall@10 0.607, completeness 0.804, V2 1.000,
  sentence completeness 0.921, citation alignment 1.000, with all four hard
  cases supervisor-approved and post-supervisor V2 `ok`.
- Final promoted replay gate:
  `run_logs/obj6_combined_replay_promoted_gate_20260706_152530.json`, eligible
  true with the same acceptance metrics using fixtures under
  `tests/fixtures/llm/obj6_combined/`.
- Threshold retake:
  `run_logs/obj6_combined_answer_quality_calibration_20260706_153015.json`.
  With current labels still 1 usable / 13 unusable, 0.75 and 0.85 both produce
  three false allows, while 0.95 blocks the sole labeled usable case. No
  threshold migration is approved. The three now-pass-like hard cases require
  explicit human label re-review before any threshold decision changes.
- Final non-large regression:
  `run_logs/obj6_combined_final_nonlarge_20260706_153100.log`, 631 passed,
  1 registered large-corpus deselection, exit code 0.

Compatibility: no default model path is enabled by this migration. Obj6 remains
default-off and replay-first; disabling `S3_LLM_ENABLED` or omitting
`use_opus`/supervisor constraints restores deterministic extraction and normal
supervisor bypass. No corpus, retrieval, API response, or database migration is
required.
