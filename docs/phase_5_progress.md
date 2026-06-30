# Phase 5 Progress

Updated: 2026-06-30

## Status

Phase 5 is active. Obj0 and Obj1 are complete; the Obj1 baseline is ready for
user review before Obj2 is released. Phase 4, including its R1-R3 local
iteration, is formally closed
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
and large-corpus runs remain local/operator-only unless an objective changes
that boundary through an explicit migration.

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
2. Answer-quality calibration and V2 hard gate: planned
3. Multilingual retrieval formalization and reindex tooling: planned
4. Independent lexical + ANN lanes, bilingual expansion, fusion: planned
5. Evidence selection, adjacent-passage expansion, reranking: planned
6. Controlled LLM synthesis lane (default-off, replay-first): planned
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

Status: planned.

## Obj3 - Multilingual retrieval formalization and reindex tooling

Goal: turn the R3 reactive model swap into a documented, tested default with
first-class, reproducible reindex tooling.

Scope: formalize `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, no collection
recreate) as the supported default; make the batched, long-timeout re-embed a
first-class script with tests (permanently removing the WinError 10053 bulk
upsert failure); record embedding model/dimension in a migration; measure
cross-lingual recall on the Obj1 set; verify PG:Qdrant parity after reindex.

Definition of Done: reindex script with tests; cross-lingual recall@10 >=
baseline with at least one real miss fixed; parity (points == embeddable_chunks)
verified; migration recorded.

Dependencies: Obj1, Obj2.

Status: planned.

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

Status: planned.

## Obj5 - Evidence selection, adjacent-passage expansion, reranking

Goal: hand S3 a cleaner, better-ordered evidence subset so synthesis stops
failing on noise and on outcome statements that sit in neighbor chunks.

Scope: deterministic-first evidence selection and ordering; adjacent-passage
expansion (the outcome/definition statement may be in an adjacent chunk);
optional reranking of the fused top-N before S3. Measured on the Obj1 set.

Definition of Done: answer-completeness on the Obj1 set improves over Obj4; V2
faithfulness rate does not drop; deterministic and reproducible.

Dependencies: Obj1, Obj4.

Status: planned.

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

Status: planned.

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
`retrieval_source` and the active embedding model; asset cache-busting retained.

Definition of Done: bulk reindex completes within timeout; qa_logs failure adds
no query latency; operator surfaces retrieval source and model; diagnostics
reflect the multilingual ANN path.

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
