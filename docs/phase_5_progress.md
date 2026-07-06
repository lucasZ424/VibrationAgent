# Phase 5 Progress

Updated: 2026-07-06

## Status

Phase 5 is active. Obj0-Obj6 are complete. Phase 4,
including its R1-R3 local iteration, is formally closed
(`docs/phase_4_progress.md`, Obj0-18). Phase 5 exists to systematically close
the gaps that the R1-R3 iteration exposed on the real corpus. Shared, remote,
public, and multi-user deployment are deferred indefinitely and are not part of
this ledger.

The high-level decomposition and design decisions live in
`docs/phase_5_development_order.md`. The Phase 5 boundary and entry/exit gates
live in `docs/phase_5_scope.md`. Contract changes are recorded in
`docs/phase_5_migrations.md`. This file is the per-objective
execution ledger.

## Execution Model

Phase 5 proceeds one objective at a time. It starts from the frozen Phase-4
interface plus the R1-R3 reactive baseline (multilingual embedding model,
answer-quality heuristic, answer-first operator UI, asset cache-busting) and
must preserve deterministic/replay CI. Live provider calls, embedding reindex,
and large-corpus runs remain explicit local operations, but the implementation
agent may run them when needed as long as stdout/stderr/summary are captured
under `run_logs/` and provider/network approval requirements are respected.

Every objective must record, in this file:

1. Implementation notes.
2. Verification commands and results.
3. Review issues and fixes in `docs/issue_log_p5/issues_objN.txt`.
4. Residual risks.
5. Whether the next objective gate is cleared.

Issue logs are user-review artifacts. Implementation agents should not generate
or edit them unless explicitly asked.

Governance carried from Phase 4 (see `docs/phase_5_development_order.md`):
default-off live paths, migration-first for any schema/retrieval/embedding/UI
contract change, replay-first for any LLM, eval-gated promotion via the
Obj2/Obj4 replacement rule, V2 faithfulness as a hard gate, and PG:Qdrant parity
preserved on every reindex. Every fixed real miss becomes a permanent labeled
regression target.

## Objective Status

0. Phase-5 baseline and governance: complete
1. Real-question evaluation harness and baseline scorecard: complete
2. Answer-quality calibration and V2 hard gate: complete
3. Multilingual retrieval formalization and reindex tooling: complete
4. Independent lexical + ANN lanes, bilingual expansion, fusion: complete
5. Evidence selection, adjacent-passage expansion, reranking: complete
6. Controlled LLM synthesis lane (default-off, replay-first): complete
7. Corpus and taxonomy quality pass: planned
8. Backend reliability and operator ergonomics: planned
9. Local-reliability backend / eval freeze: planned
10. Phase-5 final interface freeze: planned

Ordering: Obj1 is a hard prerequisite for all later objectives (measurement
before change). Obj2 (the calibrated quality gate) is the measuring stick used
throughout Obj3-6. Retrieval recall (Obj3-4) is isolated before evidence
selection and synthesis (Obj5-6) so quality stays attributable. Obj7 mutates the
corpus and therefore runs separately after Obj6, with a full Obj1 scorecard
rerun after each corpus change. Obj8 follows the core retrieval and scoring
contracts. Obj9 freezes the local-reliability backend and eval
surface before Obj10 performs the final Phase-5 interface freeze.

## Obj0 - Phase-5 baseline and governance

Goal: stand up the Phase-5 ledger and carry the Phase-4 freeze discipline
forward so later objectives have an audit trail.

Scope: add `docs/phase_5_scope.md`, `docs/phase_5_development_order.md`,
`docs/phase_5_progress.md`, `docs/phase_5_migrations.md`, and the ignored
`docs/issue_log_p5/` directory.
Register the R1-R3 reactive changes (multilingual model, scoring heuristic,
operator UI redesign, asset cache-busting) as the Phase-5 starting baseline that
Obj1 must back-fill with evaluation coverage. Documentation-only.

Definition of Done: the four canonical Phase-5 docs exist; the R1-R3 baseline and its
known gaps are recorded; no runtime contract changes.

Dependencies: none.

Status: complete.

Implementation Notes:

- Added and aligned the canonical scope, development-order, progress, and
  migration documents.
- Expanded Obj0-Obj10 into the approved single-objective order with explicit
  files, functional blocks, acceptance criteria, dependencies, and release
  gates.
- Recorded the inherited Phase-4 R3 runtime baseline and its known gaps without
  changing runtime behavior.
- Made local single-user operation binding and deferred shared, remote, public,
  and multi-user deployment indefinitely.
- Reserved `docs/issue_log_p5/` as a user-owned ignored review-artifact path.

Verification:

- Confirmed all four canonical Phase-5 documents exist and cross-reference the
  same paths.
- Confirmed development order and progress both enumerate Obj0 through Obj10.
- Confirmed every development-order objective contains files, functional blocks,
  acceptance criteria, dependencies, and release conditions.
- Confirmed every progress objective contains Goal, Scope, Definition of Done,
  Dependencies, and Status.
- Confirmed no active Phase-5 remote/shared objective, candidate, or entry gate
  remains and `git diff --check` passes.

Residual Risk:

- Obj0 is documentation governance only. It does not prove retrieval recall,
  answer usability, scoring calibration, corpus quality, or live-model
  reliability.
- Numeric promotion thresholds remain intentionally unset until Obj1 produces
  the labeled baseline; later objectives must not invent thresholds before that
  review.

Next Objective Gate:

- Obj1 is cleared to start.
- Obj2-Obj8 remain blocked on the committed Obj1 fixture and baseline scorecard.

## Obj1 - Real-question evaluation harness and baseline scorecard

Goal: quantify what the current baseline retrieval + synthesis can and cannot
answer on the real corpus, so every later change is gated by measured misses.

Scope: a labeled real-question set `tests/fixtures/rag_qa/questions.json`
covering definition, mechanism, comparison, diagnosis, workflow, standards, and
formula intents, bilingual zh/en, each recording expected evidence doc(s)/
page(s), key facts, and an answer-completeness rubric. A deterministic
`scripts/rag_qa_eval.py` scorecard runner recording per question: retrieved
chunks, expected-evidence-in-top-k, final answer, V2 status, completeness, and
miss category (retrieval / ranking / cross-doc / synthesis / terminology).
Record the post-R3 baseline numbers.

Definition of Done: scorecard committed; baseline recall@k, completeness rate,
V2 faithfulness rate, and miss-category counts recorded; dominant miss category
identified to drive Obj3-6 scope.

Dependencies: Obj0 (measurement only, no runtime contract change). Hard
prerequisite for all later objectives.

Status: complete.

Implementation Notes:

- Added 14 human-labeled questions covering definition, mechanism, comparison,
  diagnosis, workflow, standards, and formula intents in Chinese and English.
- Added `scripts/rag_qa_eval.py`, which runs the existing S2 -> S3 -> V2 -> V4
  chain and records per-case retrieval hits, answer, citations, V2 status,
  completeness, sentence completeness, latency, evidence-boundary checks,
  primary miss category, and co-occurring miss signals.
- Kept the evaluator offline: it resolves the existing multilingual embedding
  snapshot from the local Hugging Face cache, disables Postgres logging, injects
  no live LLM client, and reads the local Qdrant corpus once per run.
- Stored the generated post-R3 report at
  `tests/fixtures/rag_qa/post_r3_baseline.json` with corpus, embedding,
  retrieval-config, Git-commit, and deterministic-fingerprint metadata.

Baseline Results:

- Corpus: 4,436 chunks; multilingual MiniLM-L12-v2; 384 dimensions; hybrid RRF
  with BM25 50, ANN 50, final top 10, rerank disabled.
- Recall@5: 0.429; recall@10: 0.571; completeness: 0.316; V2 faithfulness:
  0.429; sentence completeness: 0.703.
- Multi-label miss signals: synthesis 13, retrieval 4, ranking 3, terminology 2,
  cross-doc 2, pass 1. Primary categories: synthesis 4, retrieval 4, ranking 3,
  terminology 2, pass 1. Multi-label counts intentionally expose co-occurring
  early-rank and downstream synthesis failures instead of hiding them behind one
  mutually exclusive category.
- Terminology is measured symmetrically: a Chinese/English pair must target the
  same labeled evidence, and only the failing language is tagged when its peer
  reaches full recall@10. Pairs where both languages fail remain retrieval.
- V2 statuses: ok 6, insufficient 6, unknown 2. The 0.429 faithfulness rate
  remains an all-case baseline; Obj2 must calibrate unknown separately from an
  explicit insufficient verdict.
- Two consecutive full-corpus runs produced the same deterministic fingerprint
  (`9ca91eb77f18dd84099196ff16b0689fb0170af3ff10e0a09f3b8df6daaf30d2`).
  Observed total latency was 49.6 s on both review-fix runs; latency is intentionally not
  part of the deterministic fingerprint.

Verification:

- `.venv\\Scripts\\python.exe -m pytest tests/eval/test_rag_qa_eval.py -q`:
  8 passed.
- `.venv\\Scripts\\python.exe scripts\\rag_qa_eval.py`: 14 cases completed
  against the local 4,436-chunk Qdrant snapshot; second run exited 0 and matched
  the first deterministic fingerprint.
- `.venv\\Scripts\\python.exe -m pytest tests -q -m "not large_corpus"
  --basetemp=.pytest_obj1_full2 -p no:cacheprovider`: 549 passed, 1 deselected,
  exit code 0. The deselected test is the registered large-corpus test.

Residual Risk:

- The 14-case set is a deliberately small engineering baseline, not a claim of
  broad domain coverage. New real misses must become permanent labeled cases.
- Completeness is transparent phrase/section coverage until Obj2 calibrates it
  against human usable/unusable labels; it must not be used as a product-quality
  threshold yet.
- Exact chunk ids are backed by doc/page matching to tolerate ranking among
  neighboring chunks. Report v2 records the binding rule as `exact chunk id OR
  same doc id with page overlap`; changing it requires a report version bump.
  Any corpus mutation still requires a new snapshot and a full scorecard rerun.

Next Objective Gate:

- Obj1 implementation and measurement are complete.
- Obj2 remains blocked until the user reviews and accepts the question labels,
  evidence boundaries, and post-R3 scorecard. Obj3-Obj8 remain blocked by the
  same gate.

## Obj2 - Answer-quality calibration and V2 hard gate

Goal: make the `answer_quality` score a trustworthy acceptance signal rather
than a display field, with V2 faithfulness as a blocking gate.

Scope: human usable/unusable labels on the Obj1 set; calibrate the deterministic
score (the R3 cross-lingual `question_coverage` and evidence-tag `readability`
fixes get formal labels and regression coverage); promote V2 faithfulness from
an unweighted display field to a hard gate, defining when the score blocks
versus warns. Calibration report.

Definition of Done: score correlates with human labels on the Obj1 set; V2 hard
gate wired without weakening the existing chain authority; calibration report
committed; additive fields, migration-recorded.

Dependencies: Obj1.

Status: complete.

Implementation Notes:

- Added explicit `usable` / `unusable` labels and review reasons to all 14 Obj1
  cases. The frozen baseline contains 1 minimally usable and 13 unusable
  answers; the imbalance is retained rather than manufacturing positive cases.
- Upgraded the Obj1 report contract to v3 so every case preserves the production
  `answer_quality` score and subscores required for calibration.
- Added `scripts/answer_quality_calibration.py`. It reads only the labeled
  questions and frozen report, evaluates candidate thresholds, emits confusion
  matrices, and models the proposed hard rule that `v2_status == ok` is required
  for an answer to be classified usable.
- No production score, threshold, V2 behavior, schema, or API response has been
  changed at this checkpoint.

Checkpoint Verification:

- Focused deterministic tests for the Obj1 report and Obj2 calibration runner:
  11 passed.
- Broader focused regression covering the evaluator, legacy V2 calibration,
  Tutor-Orchestrator, and citation checker: 63 passed.
- The calibration runner rejects the existing report v2 and requires a fresh v3
  full-corpus run. This is intentional fail-loud behavior, not a test failure.

Blocking Prerequisite:

- The v3 Obj1 baseline and Obj2 threshold report must be generated under
  `run_logs/`. Their confusion matrix determines whether the current score can be
  calibrated, which threshold candidates remain viable, and what production
  scoring changes are justified.
- Development paused at this checkpoint; no threshold, score replacement, or
  V2 hard gate was implemented before the operator result was reviewed.

Operator Calibration Result (2026-07-01):

- The v3 run completed for all 14 cases. The old score is not calibratable:
  the usable case scored 0.871, while unusable cases scored as high as 0.897
  and 0.866. Thresholds 0.75-0.85 produced two false allows; thresholds 0.90+
  blocked the only usable case.
- No threshold was approved. The result justified replacing token-overlap,
  citation-confidence, and generic section-presence scoring before another
  calibration run.

Score v2 Implementation:

- Added bilingual query-aspect coverage, intent-specific answer slots, and
  retrieval-hit rank/score relevance. Repeated keywords no longer satisfy a
  mechanism answer, formula answers require an equation and variable
  definitions, and missing citations receive zero evidence relevance.
- Added `gate_status`: any V2 status other than `ok`, or any incomplete intent
  rubric, is `blocked`; faithful complete answers remain `diagnostic_only` until
  a threshold is approved.
- Updated operator telemetry to label the score `diagnostic` and display the
  gate status without a pass state.
- Focused regression covering scoring, V2, API/operator, logging, evaluator,
  and calibration: 103 passed. Additional stale-score-schema calibration gate:
  46 focused tests passed after the guard was added.

Next Blocking Prerequisite:

- Regenerate the full Obj1 baseline with `phase5.answer_quality.v2`, then rerun
  Obj2 calibration. The calibration runner rejects old inner score schemas even
  when the outer report is already v3.
- Threshold selection and final hard-gate promotion remain paused pending that
  operator result.

Recalibration Run Note (2026-07-01):

- The score-v2 full baseline completed successfully for all 14 cases with
  fingerprint `45a0609b75ca771efc23dc5ca778652bdf698c971221755b879fdc981730ee5f`.
- Calibration then stopped because two standards scope early-returns correctly
  had no score, while the schema guard initially required a score on every case.
- The guard now accepts unscored cases only when V2 is not `ok`, records them as
  `not_scored`, and keeps them blocked. A V2-`ok` unscored case still fails loud.
  Focused regression: 14 passed.
- The full baseline does not need to be repeated; only calibration must be rerun.

Updated Calibration Review (2026-07-01):

- The fixed calibration completed with zero errors at thresholds 0.75 and 0.80:
  usable 0.812, highest unusable 0.706, V2 statuses ok 6 / insufficient 6 /
  unknown 2.
- A required regression then showed that keyword repetition can score exactly
  0.75 while intent completeness is zero. The production gate therefore added
  completeness as a hard prerequisite, which changes the calibration contract.
- Threshold approval remains paused. Candidate ranking now maximizes decision
  margin after minimizing false allows/blocks. The existing score-v2 baseline
  already contains completeness, so only the lightweight calibration command
  must be rerun.
- Focused regression after the rule change: 108 passed.

Final Gate Implementation (2026-07-01):

- Final calibration under score + V2 + completeness selected threshold 0.75:
  decision margin 0.044, accuracy 1.0, false allow 0, false block 0, usable
  recall 1.0, and unusable block rate 1.0.
- Implemented `gate_status=pass` only when score >= 0.75, V2 is `ok`, and all
  intent completeness slots are covered. The operator renders only this explicit
  status as pass and never infers acceptance from the numeric score.
- Focused implementation regression, including legacy V2 calibration assets:
  112 passed.

Final Validation Prerequisite:

- Required operator checks were the final full baseline/calibration, legacy V2
  calibration, retrieval eval, and canonical non-large suite. All were run and
  passed before Obj2 was marked complete.

Final Validation Result (2026-07-01):

- Final Obj1 baseline: 14 cases, report v3, score v2. The sole labeled usable
  case is the sole `pass`; 11 scored cases are `blocked`; two scope early-return
  cases are `not_scored` with V2 `unknown` and cannot pass.
- Final answer-quality calibration: threshold 0.75, decision margin 0.044,
  accuracy 1.0, false allow 0, false block 0, usable recall 1.0, unusable block
  rate 1.0.
- Legacy V2 calibration: 12/12 passed, supported precision/recall 1.0,
  unsupported block rate 1.0, false allow 0, false block 0.
- Retrieval fixture regression: recall@5 1.0, recall@10 1.0, no missing
  evidence case; no retrieval implementation changed in Obj2.
- Canonical non-large suite: 562 passed, 1 deselected. The deselected case is
  the registered `large_corpus` test.

Residual Risk:

- Human calibration has one usable and thirteen unusable cases. Threshold 0.75
  is accepted for the current fixture, not as a universal statistical claim.
- Every new labeled usable answer must rerun calibration; a threshold change
  requires a new migration and cannot be inferred from the numeric score alone.

Post-Review Hardening:

- Added the durable, machine-readable calibration report at
  `tests/fixtures/eval/answer_quality/obj2_calibration.json` and a deterministic
  equality regression. Obj2 no longer relies on prose plus ignored run logs to
  satisfy the committed-report DoD.
- Unknown/general intent now fails completeness instead of passing by answer
  length. Added direct regressions for this path and for empty citations yielding
  zero evidence relevance.
- Audited current `answer_quality` consumers: operator acceptance reads
  `gate_status`; no runtime consumer treats `score >= threshold` alone as pass.
- The single-positive calibration risk remains accepted and requires
  recalibration as Obj3-Obj6 add new labeled usable answers.
- Post-review focused regression: 115 passed. No full-corpus rerun was required
  because the scoring change affects only previously unrecognized general
  intent, which is absent from the 14-case calibration fixture.

Next Objective Gate:

- Obj2 completion cleared Obj3; Obj3 has since passed its hybrid no-regression
  validation and Obj4 is now ready.

## Obj3 - Multilingual retrieval formalization and reindex tooling

Goal: turn the R3 reactive model swap into a documented, tested default with
first-class, reproducible reindex tooling.

Scope: formalize `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, no collection
recreate) as the supported default; make the batched, long-timeout re-embed a
first-class script with tests (permanently removing the WinError 10053 bulk
upsert failure); record embedding model/dimension in a migration; measure
cross-lingual recall on the Obj1 set; verify PG:Qdrant parity after reindex.

Definition of Done: reindex script with tests; independent ANN recall/latency
baseline recorded; post-reindex hybrid recall@10 not below the post-R3 hybrid
baseline on the same fixture/corpus; parity (points == embeddable_chunks)
verified; migration recorded. Recall improvement plus at least one fixed real
miss belongs to Obj4's replacement gate.

Dependencies: Obj1, Obj2.

Status: complete.

Implementation Notes:

- Added migration 004 so Postgres preserves canonical document/chunk ids and
  chunk provenance required to reproduce Qdrant stable UUIDs.
- Added a dry-run-default PostgreSQL-to-Qdrant reindex CLI with bounded batches,
  timeout overrides, atomic checkpoint progress, idempotent resume, explicit
  collection recreation, dimension/distance guards, and error summaries.
- Qdrant payloads now carry the configured embedding dimension in addition to
  model/version. Token-feature fallback is rejected as a reindex input.
- Successful execution compares Postgres embeddable chunk count and source-type
  distribution with the final Qdrant payload set; mismatch returns
  `parity_failed`.
- Added an ANN-only evaluator that directly embeds each Obj1 query and searches
  Qdrant. It reports overall and zh/en recall@10, paired cross-lingual recall,
  missing cases, first-query cold latency, and steady p50/p95 latency without
  importing lexical, fusion, rerank, or fallback retrieval.

Checkpoint Verification:

- Storage identity/migration mapping: 13 focused tests passed.
- Reindex, ANN evaluator, embedding, Qdrant, CLI, and storage regressions: 57
  focused tests passed.

Operator Validation Result (2026-07-01):

- Reindex completed 4436/4436 with exact point/source-type parity, no errors, and
  no model/version/dimension provenance mismatch. Corpus fingerprint:
  `1d4be4aed716a0849a120f19384aebbfab38429d043d243f109e7b1155f565ab`.
- ANN-only recall@10 is 0.500 (zh 0.643, en 0.357); paired zh/en recall is
  0.286. Cold-start latency is 4785.320 ms; steady p50/p95 are 21.660/44.038 ms.
- The prior 0.571 post-R3 score is hybrid retrieval and is not a valid ANN-only
  pass/fail comparator. The accepted ANN baseline is 0.500 and is versioned at
  `tests/fixtures/eval/retrieval/obj3_ann_baseline.json` for Obj4 lane comparison.
- Diagnostic top-50 checks confirmed stored vectors exactly match fresh
  embeddings. Remaining misses map to Obj4 query normalization/fusion and Obj5
  cross-doc/neighbor ranking; they are not reindex corruption.
- The user explicitly ratified the Obj3/Obj4 scope split on 2026-07-01: Obj3
  records the independent ANN baseline; Obj4 owns retrieval improvement and the
  fixed-miss requirement.
- The post-reindex hybrid scorecard completed on 2026-07-01 with report v3,
  14 cases, and 4436/4436 chunks. Recall@5/@10 remained 0.429/0.571, exactly
  matching the post-R3 hybrid baseline at the Obj3 decision threshold.

Next Objective Gate:

- Obj3 is complete. Obj4 may start with ANN recall@10 0.500 as its ANN lane floor
  and hybrid recall@10 0.571 as the runtime no-regression reference.

## Obj4 - Independent lexical + ANN lanes, bilingual expansion, fusion

Goal: remove the architectural limit where BM25 is confined to the ANN candidate
set, and let an English query reach Chinese evidence through the lexical lane.

Scope: independent, separately measured BM25 and ANN lanes; bilingual query
expansion so the lexical lane bridges zh/en key terms; RRF fusion of the lanes;
evaluation against the Obj1 set under the Obj2/Obj4 replacement gate.

Definition of Done: each lane's recall measured independently; fused recall >=
best single lane; replacement gate satisfied (recall not lowered, >= 1 real miss
fixed); contract changes migration-recorded.

Dependencies: Obj1, Obj3.

Status: complete.

Implementation Notes:

- Added a default-off independent-lane runtime candidate. ANN remains a direct
  Qdrant query; BM25 now receives the complete payload corpus rather than ANN
  top-N candidates.
- Added a process cache for the lexical payload corpus. Refresh is explicit via
  `clear_runtime_lexical_cache()` or service restart after ingestion/reindex.
- Moved bilingual retrieval aliases into versioned
  `taxonomy/retrieval_aliases.yaml`; query expansion reports its schema version
  and retains negative ambiguity behavior for generic/gas turbine queries.
- BM25 now indexes Qdrant `source_title`/`source_filename`, allowing exact
  standard identifiers to participate in lexical recall.
- Added lane telemetry and normalized RRF contributions, plus a three-mode
  evaluator with the frozen replacement gate. Full RAG/V2 validation remains a
  second prerequisite and is not run unless the lane candidate first qualifies.

Blocking Prerequisite:

- The user must run the Obj4 three-mode evaluator against the 4436-chunk corpus.
  If the candidate does not match the best lane, hold the feature flag false and
  use the per-case report to decide the next scoped implementation change.

First Lane Result and Fusion Adjustment (2026-07-01):

- BM25/dense/hybrid recall@10 was 0.429/0.500/0.536. Plain RRF exceeded both
  single lanes but remained below the 0.571 runtime baseline and fixed no frozen
  miss, so replacement stayed blocked.
- The Chinese GB/T 33199 scope case was fixed by BM25 but dropped by plain RRF;
  global RRF K/raw-score scans did not change the result, while global lexical
  weighting regressed a definition case.
- Added a scoped deterministic fusion for explicit standard lookup only:
  lexical 0.9 / ANN 0.1. Other intents remain RRF. The revised candidate requires
  another three-mode operator evaluation before any full RAG/V2 run.

Revised Lane Result (2026-07-01):

- BM25/dense/hybrid recall@10 remained 0.429/0.500 and improved to 0.607 for
  hybrid. Hybrid now exceeds the best single lane and the 0.571 runtime baseline.
- The candidate fixed frozen miss `p5_standards_zh_gbt33199_scope` and produced
  no complete miss regression among existing baseline passes.
- The lane replacement candidate is eligible. Full RAG/V2 validation with the
  default-off flag explicitly enabled is now the blocking prerequisite for
  promotion; the checked-in default remains false.

First Full-Chain Result and Scope Fix (2026-07-01):

- Full-chain recall@10 was 0.536 and V2 faithfulness remained 0.429. Both frozen
  GB/T 33199 cases returned before S2 with empty retrieval hits, so the lane fix
  was unreachable in production despite passing the isolated evaluator.
- Added a provisional narrow scope allowlist for `GB/T 33199`; the final review
  replaced it with versioned `taxonomy/corpus_standards.yaml`, generated from
  Qdrant document identity metadata. This admits all cataloged standard families
  without treating standards merely cited in document bodies as corpus members.

Final Full-Chain Result and Promotion (2026-07-01):

- Final report v3 covered 14 cases and 4436/4436 chunks. Recall@5/@10 improved
  from 0.429/0.571 to 0.500/0.607. The frozen Chinese GB/T 33199 miss reached
  `status=ok`, recall@10 1.0, and V2 `ok`.
- V2 faithfulness improved from 0.429 to 0.500; completeness improved from 0.316
  to 0.339; sentence completeness improved from 0.767 to 0.902.
- Independent lanes are promoted as the checked-in default. Explicit rollback is
  `RETRIEVAL_INDEPENDENT_LANES_ENABLED=false`. The compact evidence artifact is
  `tests/fixtures/eval/retrieval/obj4_replacement_baseline.json`.

Final Blocking Prerequisite (completed):

- Run the canonical non-large suite after default promotion. Obj4 closes and
  Obj5 is released only after that operator result is reviewed.

Final Regression Result (2026-07-01):

- Canonical non-large suite: 591 passed, 1 deselected, 0 failed in 12.63s. The
  deselected test is the registered `large_corpus` case.

Review Follow-up (2026-07-01):

- Removed the fixture-specific `GB/T 33199` scope constant. Scope admission now
  reads the corpus-derived standard catalog; regression coverage includes
  `GB/T 11348`, `GB/T 33199`, `ISO 10816`, and the non-corpus `GB/T 19001`
  negative case.
- `scripts/build_corpus_standard_catalog.py` refreshes the catalog after corpus
  replacement/reindex. It extracts identifiers only from source identity fields,
  never from body references, and fails if no standard documents are found.
- The gas-turbine/steam-turbine negative expansion required by AC6 was already
  present and remains green. The frozen 14-case scorecard was not expanded with
  unreviewed labels; additional standard retrieval cases require a separately
  reviewed fixture/calibration update.

Next Objective Gate:

- Obj4 is complete. Obj5 is cleared to start.

## Obj5 - Evidence selection, adjacent-passage expansion, reranking

Goal: hand S3 a cleaner, better-ordered evidence subset so synthesis stops
failing on noise and on outcome statements that sit in neighbor chunks.

Scope: deterministic-first evidence selection and ordering; adjacent-passage
expansion (the outcome/definition statement may be in an adjacent chunk);
optional reranking of the fused top-N before S3. Measured on the Obj1 set.

Definition of Done: answer-completeness on the Obj1 set improves over Obj4; V2
faithfulness rate does not drop; deterministic and reproducible.

Dependencies: Obj1, Obj4.

Status: complete within deterministic scope; the candidate remains default-off.

Implementation Notes (2026-07-02):

- Added a deterministic evidence selector after Obj4 fusion. Raw `hits` and
  `retrieval_context` remain unchanged for retrieval attribution; selected S3
  input is exposed separately as `evidence_context` and `evidence_selection`.
- Selection keeps bounded fused-rank seeds, expands only verifiable
  `doc_id + chunk_index` neighbors, removes exact/near duplicate text, and
  enforces hard chunk/token limits. Every row retains chunk/page/source identity
  plus seed/adjacent selection reason.
- S2 citations and S3 now follow selected evidence when enabled. The old handoff
  remains intact when `EVIDENCE_SELECTION_ENABLED=false` (the checked-in default).
- Model reranking remains disabled so this scorecard measures only deterministic
  selection and adjacency.
- Added `phase5.obj5_evidence_gate.v1`: candidate requires unchanged corpus,
  recall@10 >= 0.607, completeness > 0.339, V2 faithfulness >= 0.500, selector
  enabled, model reranker disabled, and sentence completeness >= 0.902.

Verification:

- Focused S2/S3/S4/V2/orchestrator/eval tests after fifth-result refinement: 167 passed.

First Candidate Result and Refinement (2026-07-02):

- The 4436-chunk run preserved recall@10 at 0.607 and improved measured
  completeness 0.339 -> 0.387 and V2 faithfulness 0.500 -> 0.571.
- Sentence completeness regressed 0.902 -> 0.888. Inspection localized the
  failure to the English workflow case: unconditional adjacency injected noisy
  OCR abstract/neighbor passages and inflated keyword completeness while making
  the answer less usable. The initial gate therefore produced a false approval.
- The gate now rejects sentence-completeness regression. Adjacency now requires
  a boundary signal: a continuation-style prefix for previous context or a
  missing terminal sentence marker for following context. Complete seed chunks
  do not expand.
- Re-evaluating the old JSON with the corrected gate returns ineligible solely
  on `sentence_completeness_preserved=false`. A fresh Obj1 run is required.

Second Candidate Result and OCR Sentence Fix (2026-07-02):

- The boundary-trigger retry reproduced completeness 0.387, V2 0.571, and
  sentence completeness 0.888; the corrected gate rejected it as intended.
- The low sentence score includes a pre-existing OCR behavior concentrated in
  English evidence: U+FF0E fullwidth periods were neither sentence boundaries
  nor valid terminal punctuation, causing whole abstracts to become one claim.
- S3 extraction, selector boundary detection, and answer readability scoring now
  consistently recognize U+FF0E. The retry report predates this fix and cannot
  be used for promotion; a third candidate run is required.

Third Candidate Result and Citation Alignment Fix (2026-07-02):

- The third candidate passed the numeric gate: recall@10 0.607, completeness
  0.387, V2 0.571, sentence completeness 0.923, and mean latency 4.128s.
- Structural review found 8/14 final answers whose inline evidence tags were not
  fully represented in final citations. V2 recognized only `[chunk_id]`, while
  deterministic S3 emits `(evidence: chunk_id)` / `（证据：chunk_id）`; S4 can
  narrow structured claims while retaining the original conclusion text.
- V2 now recognizes deterministic inline evidence tags and preserves a citation
  for every referenced S2-visible chunk. The eval reports
  `citation_alignment_rate`; Obj5 promotion requires 1.000.
- The third report predates this contract fix and is not promotable. A fourth
  candidate run is the current blocking prerequisite.

Fourth Candidate Result and V2 Visibility Fix (2026-07-02):

- Citation alignment reached 1.000, but V2 marked all 14 cases insufficient,
  reducing completeness to 0.054 and faithfulness to 0.000; the gate rejected
  the candidate.
- Root cause: S3 consumes Obj5 `evidence_context`, while V2 still validated only
  Obj4 `retrieval_context`. Legitimate selected/adjacent chunks were therefore
  treated as invisible.
- V2 now uses `evidence_context` when present and falls back to
  `retrieval_context` for the default-off/legacy path. Retrieval hits remain an
  additional identity fallback. A fifth candidate run is required.

Fifth Candidate Result and Full-Corpus Handoff Leak Fix (2026-07-02):

- The fifth run still produced 14 V2-insufficient cases. A one-case diagnostic
  exposed `s3.evidence_count=4382`: the eval passes all 4436 chunks to S2 through
  `context.chunks`, and S3 also consumed that raw corpus as fallback evidence
  even though an S2 handoff existed.
- S3 now consumes direct/S2 evidence first and uses `context.chunks` only when no
  retrieval handoff exists. S4 and V2 both use `evidence_context` when present.
  The same diagnostic now reports evidence_count 6, V2 unsupported [], status
  ok, and three aligned citations.
- This leak affected historical full-chain completeness/V2/readability metrics,
  including the Obj4 answer-quality floor. Obj4 retrieval recall@10 0.607 remains
  valid because retrieval hits were scored independently; the old 0.339/0.500/
  0.902 answer-quality floor is no longer comparable.
- The next prerequisite is a paired run on the corrected code: selector-off
  corrected baseline followed by selector-on candidate. The Obj5 gate now
  requires baseline selector disabled, corpus parity, and complete citation
  alignment on both reports.

Corrected Pair Result and Conservative Selector Revision (2026-07-02):

- Corrected selector-off established the valid floor: completeness 0.708,
  V2 1.000, sentence completeness 0.890, citation alignment 1.000, recall@10
  0.607. The selector-on candidate regressed to 0.697/1.000/0.888/1.000 and was
  rejected.
- The regression came from retaining only six seeds while adding loosely
  triggered neighbors. The selector now retains raw top10, permits at most two
  additions under a 6000-token budget, and requires two-sided boundary
  continuity before adding an adjacent chunk.
- Targeted off/on checks for the three changed cases now have identical
  completeness, readability, V2 status, citation alignment, and citation ids.
  The corrected selector-off report remains comparable; only a revised
  selector-on run is required.

Conservative Candidate Result and Rerank Decision (2026-07-02):

- The revised selector exactly matched corrected-off on all 14 cases:
  completeness 0.708, V2 1.000, sentence completeness 0.890, citation alignment
  1.000, and recall@10 0.607. The gate correctly rejected it because there was
  no strict completeness improvement. It remains default-off.
- Offline miss analysis found no uncovered Obj1 key fact in a raw top10
  neighbor at offset +/-1, so adjacent expansion cannot demonstrate an Obj1
  completeness gain on this fixture.
- Ten cases do contain uncovered fact aliases inside raw top10 itself, proving
  the remaining Obj5 opportunity is claim/evidence reranking. A trial generic
  query-aspect keyword diversification regressed representative comparison and
  standards cases and was removed.
- Next development slice: evaluate a stronger deterministic semantic/structural
  reranker against the corrected-off baseline. Do not rerun the current selector
  or promote it by relaxing the gate.

Closure Decision (2026-07-03):

- Obj5's deterministic search space is closed without promoting the selector.
  The corrected selector-off floor is the accepted baseline; the candidate
  remains default-off because it produced no strict completeness gain.
- Further intent-specific reranking would encode the 14-case fixture rather than
  establish a general evidence-selection rule. Semantic completeness improvement
  moves to Obj6's controlled synthesis lane instead of relaxing the Obj5 gate.
- The canonical non-large suite passed with 611 passed and 1 deselected after the
  V2 blocked-answer citation fix. Obj5 therefore closes as an attributable
  negative result, not as a claim that its original improvement criterion passed.
- Historical Obj1/Obj2 answer-quality results generated before the full-corpus
  S3 handoff fix are stale. Retrieval-only recall remains valid.

## Obj6 - Controlled LLM synthesis lane (default-off, replay-first)

Goal: enable coherent prose synthesis on the hard cases where deterministic
extraction caps readability, under strict budgets and faithfulness control.

Scope: sequential sub-gates. Obj6A constructs and evaluates the GPT S3 synthesis
client with provider/model/usage/cost traces, budget, replay capture, V2 hard
gate, and deterministic fallback. Obj6B separately evaluates Opus review and
correction, including malformed correction-schema fallback. Obj6B is not enabled
until Obj6A passes; combined-chain quality is not claimed until both pass. CI
never constructs a live provider.

Definition of Done: separate GPT and Opus replay fixtures and scorecards; budget,
trace, and schema fallback enforcement tested; V2 faithfulness unchanged; both
lanes default-off; answer-completeness improves on hard cases; Opus correction
no longer schema-falls back; migration recorded.

Dependencies: Obj1, Obj2, Obj5.

Status: complete. Obj6A and Obj6B are complete in isolation, the Obj6
combined-chain replay/live gate passed, and the final non-large regression is
green. The prior user-only validation-running rule is lifted, so the agent may
run needed validations directly while writing `run_logs/`.

Approved Entry Sequence (2026-07-03):

- Regenerate the 14-case Obj1 baseline with fixed S3, selector disabled, and no
  live provider. Re-run Obj2 calibration and explicitly verify that threshold
  0.75 still has zero false allows and zero false blocks.
- Keep Obj6 before Obj7. OCR/mojibake may be inventoried now, but no corpus
  mutation is allowed before the Obj6 baseline and replay comparisons complete.
- After the prerequisite passes, implement Obj6A locally and replay-first. Obj6B
  remains blocked until Obj6A passes its isolated gate.

Corrected Entry Result (2026-07-03):

- The 4,436-chunk selector-off run reproduced completeness 0.708, V2 1.000,
  sentence completeness 0.890, citation alignment 1.000, and recall@10 0.607.
  It constructed no live provider.
- Threshold 0.75 remains zero-error (accuracy 1.0, zero false allows/blocks) on
  the corrected baseline, but ONLY because the hard `completeness == 1.0` condition
  blocks the unusable cases that now score above 0.75 (formula_zh 0.791,
  standards_zh 0.748, mechanism_en 0.725). Its score margin is now negative
  (-0.041) and the calibrator's max-margin rule selects 0.85; this can no longer be
  described as "calibration selects 0.75". Production stays 0.75 PROVISIONALLY,
  backstopped by the completeness gate, and the calibration is marked provisional.
  Human re-review used the stricter complete-usable standard, refreshed the stale
  reasons, and kept labels unchanged at 1 usable / 13 unusable. Migration to 0.85
  is deferred until Obj6 produces more complete-usable positives and the expanded
  label set still supports that threshold without lowering usable recall.
- Obj6A-0 now wires the default orchestrator to replay when S3 is enabled and
  live mode is off. Live construction requires both explicit flags and retains
  the existing budget and pytest guards.
- Added `scripts/obj6_synthesis_eval.py`: `prepare` generates exact S3 request
  JSON and hashes for the four comparison/diagnosis hard cases; `evaluate` runs
  the 14-case chain using replay only; `gate` compares it with the corrected
  baseline under the Obj6A quality contract.
- The four request files were generated from the unchanged 4,436-chunk corpus.
  Development pauses for explicit operator live capture before replay scoring;
  no live provider was called during request preparation.
- The first replay improved completeness to 0.732 and preserved recall,
  readability, and citation alignment, but failed V2 at 0.857. Both failures
  were English hard cases whose prompts incorrectly requested Chinese because
  evidence language overrode query language. S3 prompt v2 makes substantive
  query language authoritative; v1 captures are retained only as failed-run
  evidence and must not be used for promotion.
- During v2 capture, one response reached `max_output_tokens` and returned a
  provider-level incomplete object. The capture command now validates the
  task-specific response schema before writing a fixture, so transport success
  can no longer be reported as a valid replay capture.
- The v2 replay scored completeness 0.685 and V2 0.929 and was rejected. The
  remaining English comparison failures all cited Chinese chunks and failed
  lexical support after translation. Prompt v3 keeps the English answer but
  requires source-language extractive support anchors, preserving V2's strict
  evidence check instead of adding a cross-language allow rule.
- The v3 replay reached completeness 0.804, V2 1.000, recall@10 0.607, and
  citation alignment 1.000. Its sole failed gate was readability 0.770 because
  the scorer stripped deterministic `(evidence: id)` suffixes but not V2-valid
  `[chunk_id]` suffixes. Readability now treats both citation syntaxes equally;
  the existing replay must be rerun before Obj6A can close.
- The final v3 replay passed every Obj6A gate: completeness 0.804 versus the
  0.708 floor, V2 1.000, sentence completeness 0.921, citation alignment 1.000,
  and recall@10 0.607. All four comparison/diagnosis hard cases improved in
  aggregate and no previously non-empty case became a complete miss.
- Obj6A is quality-gate complete and remains default-off. Obj6B is held until
  the canonical non-large suite confirms the runtime/provenance/rendering
  changes do not regress unrelated paths.
- Clean-environment canonical non-large regression passed with 619 passed and
  1 deselected in 13.00s. The preceding single failure was traced solely to
  `LLM_LIVE_ENABLED=true` left in the operator shell after manual capture;
  clearing capture-only environment overrides restored the checked-in default
  contract.
- **Obj6A status: complete.** Prompt v3 replay fixtures are the promoted GPT S3
  scorecard. The lane remains default-off; rollback is
  `S3_LLM_ENABLED=false`. Obj6B is now cleared to begin its isolated Opus
  review/correction work.
- Post-review solidification replaced the stale standing Obj1 fixture with the
  corrected selector-off report (0.708 completeness, V2 1.000, sentence 0.890,
  citation alignment 1.000, recall@10 0.607) and regenerated the committed Obj2
  calibration from that same report. Threshold 0.75 retains zero false allows
  and zero false blocks; the production threshold is unchanged.
- The recalibration ranker reports 0.85 as the best observed candidate because
  it has a larger score-only decision margin; 0.75 has the same zero-error
  confusion matrix once the completeness hard gate is applied. This result does
  not authorize an implicit threshold migration. Production remains 0.75 until
  a separately reviewed threshold change is requested.
- Human re-review of the corrected answers is complete. The adopted standard is
  complete-usable rather than splice-relevance; no labels flipped, but the stale
  pre-fix usability reasons were refreshed in `questions.json`.
- The Obj6A readability gate now reads its floor from the versioned baseline
  instead of embedding 0.890. Only `tests/fixtures/llm/obj6a_v3/` is eligible
  for promotion; v1/v2 captures are explicitly quarantined as failed diagnostic
  history.
- Obj6B local contract verification is implemented. Runtime now has explicit
  tests that a malformed `status=ok` correction carrying neither `answer` nor
  `structured_result` falls back visibly instead of being approved, while a
  `structured_result.answer`-only correction remains valid. Manual capture
  validation rejects the same malformed correction before writing a replay
  fixture. Approved/fallback outputs now preserve `supervisor_residual_risk`,
  and manual E2E summaries expose supervisor corrections and residual risk for
  operator review. Focused verification: `tests/unit/test_supervisor_loop.py`,
  `tests/unit/test_manual_live_lane.py`, and `tests/unit/test_llm_replay.py`
  passed with 31 passed.
- Added `scripts/obj6b_supervisor_eval.py`, which generates hash-addressed
  supervisor replay fixtures and then replays reject -> correct -> approve
  through `ReplayClient`. Final promoted replay report:
  `run_logs/obj6b_supervisor_replay_final_20260706_141221.json`, passed, with
  `supervisor_status=approved`, 2 invocations, 1 correction, residual risk
  recorded, and supervisor token cost 60. Promoted fixtures are under
  `tests/fixtures/llm/obj6b/`.
- The first explicit live correction gate exposed a real schema prompt gap:
  Opus returned a correction-shaped review payload with `status="revised"`.
  Runtime correctly fell back; trace:
  `run_logs/obj6b_live_correction_20260706_140712.summary.json`. The supervisor
  review/correction prompts now pin allowed status values and forbid review
  responses from returning revised answers; this is covered by
  `tests/unit/test_supervisor_loop.py`.
- Final live Opus correction gate passed:
  `run_logs/obj6b_live_correction_20260706_140930.json`, with
  `supervisor_status=approved`, 2 review invocations, 1 correction, residual risk
  recorded, token cost 14,213, and all gate checks true. The earlier direct live
  approve run (`run_logs/obj6b_live_supervisor_20260706_140342.summary.json`) is
  retained only as evidence that approve-only live review works; it is not the
  promoted Obj6B correction gate.
- Final local non-large regression after Obj6B live/schema changes passed:
  `run_logs/obj6b_final_nonlarge_20260706_141053.json`, 625 passed and
  1 warning in 17.51s.
- The previous user-only validation-running prerequisite is lifted. Future full,
  large-corpus, reindex, and eval runs may be executed by the agent when needed,
  with stdout/stderr/summary recorded under `run_logs/` for error tracing. This
  does not lift the Obj6 manual live acceptance evidence: GPT and Opus live
  checks still need provider/model/status/usage/cost and residual risk recorded
  before Obj6 close.
- The approval reviewer initially blocked external transfer of workspace-derived
  query/evidence/review content to Anthropic. After explicit user approval, the
  live correction gate above was run and passed. **Obj6B status: complete.**

Combined-Chain Gate (2026-07-06):

- Added `scripts/obj6_combined_eval.py` to evaluate Obj6A GPT S3 replay plus
  Obj6B Opus supervisor on the same 14-case Obj1 fixture. The supervisor is
  triggered only on the four semantic hard cases; every hard case is rechecked
  by V2 after supervisor approval/correction.
- The first combined live runs exposed two real robustness gaps: Anthropic
  review payloads can place text locations in `issues[].line`, and correction
  responses can return a complete correction JSON inside `answer`. The
  supervisor now normalizes nonnumeric locations into the recommendation text
  and unwraps nested correction JSON before applying it. Both paths have unit
  tests. Replay capture now preserves long response strings while still
  redacting/truncating metadata.
- Anthropic timeout is raised from 30s to 120s in checked-in config because the
  combined supervisor prompts legitimately exceed the old default. This affects
  live supervisor calls only; replay and default-off behavior are unchanged.
- Final live combined capture:
  `run_logs/obj6_combined_live_20260706_151827.json`; live gate:
  `run_logs/obj6_combined_live_gate_20260706_152132.json`, eligible true.
  Metrics: recall@10 0.607, completeness 0.804, V2 faithfulness 1.000,
  sentence completeness 0.921, citation alignment 1.000. All four hard cases
  were supervisor approved and post-supervisor V2 `ok`.
- Promoted replay after fixture cleanup:
  `run_logs/obj6_combined_replay_promoted_20260706_152431.json`; gate:
  `run_logs/obj6_combined_replay_promoted_gate_20260706_152530.json`,
  eligible true with the same acceptance metrics. Promoted combined fixtures
  live under `tests/fixtures/llm/obj6_combined/`.
- `scripts/answer_quality_calibration.py` now also accepts
  `phase5.obj6.combined_report.v1` and uses
  `combined_chain.post_supervisor_v2_status` when present, so combined-chain
  threshold checks include the post-supervisor V2 result.
- Combined-chain answer-quality recalibration:
  `run_logs/obj6_combined_answer_quality_calibration_20260706_153015.json`.
  With the current human labels still at 1 usable / 13 unusable, thresholds
  0.75 and 0.85 both produce 3 false allows
  (`p5_comparison_en_unbalance_misalignment`,
  `p5_diagnosis_zh_fault_discrimination`,
  `p5_diagnosis_en_fault_discrimination`). Threshold 0.95 blocks those but also
  blocks the only labeled usable case. Therefore no threshold migration is
  authorized by the combined run; the three now-pass-like hard cases require
  explicit human label re-review before any 0.75-vs-0.85 decision changes.
- Final non-large regression:
  `run_logs/obj6_combined_final_nonlarge_20260706_153100.log`, 631 passed,
  1 registered large-corpus deselection, exit code 0.
- **Obj6 status: complete.** The controlled synthesis/supervisor lane remains
  default-off and replay-first. Obj7 is cleared to begin as the next objective;
  any corpus/taxonomy mutation must create a new corpus baseline before later
  comparisons.

## Obj7 - Corpus and taxonomy quality pass

Goal: remove the data-quality drags that forced workarounds during R1-R3 and
expand bilingual taxonomy from real misses.

Scope: re-ingest so chunks carry `source_filename`/`title` directly (removing the
`source_path` basename fallback dependency); address generic document names
(`document_*`) and OCR mojibake where they block retrieval or citation; expand
taxonomy terms/symbols/units/aliases and bilingual mappings (currently 12
families) from the Obj1 misses. This objective does not run in parallel with
Obj3-6. Every corpus mutation creates a versioned corpus baseline and reruns the
full Obj1 scorecard before later comparisons.

Definition of Done: citations render real filenames from chunk data; alias
coverage measured against Obj1 misses; re-ingest reproducible; parity preserved.

Dependencies: Obj1 and Obj6.

Status: planned.

## Obj8 - Backend reliability and operator ergonomics

Goal: make the R1-R3 reactive backend fixes durable and reduce operator
friction.

Scope: Qdrant client timeout/batching for bulk operations; PG `qa_logs`
fast-fail when Postgres is unavailable (no per-query timeout latency); operator
hot-reload or a clear restart contract; health/diagnostics surfacing
`retrieval_source` and the active embedding model; asset cache-busting retained;
replace or formally capacity-bound Obj4's process-cached full-payload lexical
backend, including enforced cache/catalog refresh after reindex.

Definition of Done: bulk reindex completes within timeout; qa_logs failure adds
no query latency; operator surfaces retrieval source and model; diagnostics
reflect the multilingual ANN path; lexical memory/refresh behavior is measured
and no stale payload or standard catalog survives the supported restart flow.

Dependencies: Obj3 and Obj7.

Status: planned.

## Obj9 - Local-reliability backend / eval freeze

Goal: freeze the RAG-reliability backend and eval contracts before the final
Phase-5 interface freeze, mirroring the Phase-4 backend-freeze split.

Scope: freeze the retrieval lanes, evidence-selection, scoring gate, and
synthesis-lane contracts in `docs/phase_5_backend_interface_freeze.md`; lock the
Obj1 baseline as the standing regression net.

Definition of Done: freeze document written; eval baseline locked; no open
local-reliability contract drift.

Dependencies: Obj2-8.

Status: planned.

## Obj10 - Phase-5 final interface freeze

Goal: close Phase 5 with one authoritative local single-user RAG reliability
baseline.

Scope: consolidate Obj0-9 scope, migrations, accepted defaults, scorecard gates,
rollback paths, and residual risks into `docs/phase_5_interface_freeze.md`.
Confirm that remote/shared/public/multi-user scope did not enter implementation.

Definition of Done: full deterministic/replay suite and approved real-question
scorecard pass; backend/eval freeze is referenced; migration ledger is complete;
Phase 5 is marked closed; no remote/shared entry gate or candidate remains.

Dependencies: Obj9.

Status: planned.
