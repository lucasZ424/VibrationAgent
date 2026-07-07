# Phase 5 Interface Freeze

Date: 2026-07-07
Status: FROZEN / CLOSED AFTER OBJ10

## Freeze Decision

Phase 5 is frozen as the local single-user RAG answer-reliability baseline for
`vibration_agent`.

This freeze closes Phase 5. No new Phase-5 feature objective remains open. Any
future change to runtime authority, retrieval, scoring, corpus identity,
provider defaults, UI/API contract, or deployment boundary must enter a
successor phase with a new migration/freeze record.

This final freeze is additive on top of:

- `docs/phase_4_interface_freeze.md`
- `docs/phase_5_backend_interface_freeze.md`
- `docs/phase_5_scope.md`
- `docs/phase_5_migrations.md`
- `docs/phase_5_progress.md`

## Product Boundary

The frozen product is local-first and single-user:

- trusted local files and local corpus exports;
- localhost API/CLI/operator access;
- local Postgres and Qdrant stores when configured;
- default deterministic answering without live provider construction.

Shared, remote, public, SaaS, and multi-user deployment remain indefinitely
deferred. Phase 5 did not add identity/authorization, tenant isolation, public
ingress, remote key management, distributed rate limiting, or multi-user audit.
There is no hidden Phase-5 entry gate that can activate that scope.

## Frozen Runtime Authority

The default answer path remains:

```text
S2 retrieval -> S3 deterministic synthesis -> optional S4/S5 -> V2 hard gate -> V4
```

V2 remains the hard faithfulness authority. V4 is a renderer/style layer and
does not add claims. Optional V3/supervisor, GPT synthesis, and Opus correction
lanes remain opt-in, replay-first, and default-off.

Production truth for Obj10 is the deterministic backend baseline, not the Obj6
LLM/supervisor lane scorecard.

## Frozen Backend / Eval Baseline

The backend/eval contract is frozen by
`docs/phase_5_backend_interface_freeze.md` and is incorporated here by
reference. Load-bearing values:

- corpus: 4,436 chunks;
- source distribution: book 939 / manual 928 / paper 1,780 / standard 789;
- embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`;
- embedding dimension: 384;
- retrieval: hybrid BM25+dense, independent lanes, RRF, final top 10;
- reranker: disabled;
- evidence selection: disabled by default;
- standing baseline: `tests/fixtures/rag_qa/post_r3_baseline.json`;
- calibration artifact:
  `tests/fixtures/eval/answer_quality/obj2_calibration.json`.

Frozen deterministic scorecard:

- recall@5: 0.643;
- recall@10: 0.821;
- completeness: 0.720;
- sentence completeness: 0.867;
- V2 faithfulness: 1.000;
- citation alignment: 1.000.

The 0.821 recall@10 value is an in-sample regression net. Obj7 aliases and
corpus repairs were derived from Obj1 misses and measured on the same 14-case
fixture. It is correct to freeze this as the breakage detector, but it is not a
held-out generalization claim.

The sentence completeness value is 0.867, lower than the earlier pre-Obj7
deterministic 0.890 floor because Obj7 taxonomy/source changes surfaced
different production evidence and deterministic answers. This is recorded as
the true production baseline, not as an Obj10 defect.

## Frozen Scoring Contract

`phase5.answer_quality.v2` remains the production answer-quality schema.
Runtime threshold `0.75` remains provisional and is backstopped by:

- `faithfulness_status == ok`;
- `completeness == 1.0`;
- explicit `gate_status=pass`.

The Obj9 deterministic calibration artifact ranks threshold 0.85 as the best
observed candidate, but this does not migrate runtime behavior. The label set
still has one usable and thirteen unusable cases, and the Obj6 combined-chain
calibration showed degraded threshold discrimination for LLM-style answers.

Any threshold migration requires human label re-review, regenerated calibration,
a migration entry, and regression across deterministic plus LLM lanes.

## Frozen LLM / Supervisor Contract

Obj6 validated GPT S3 synthesis and Opus supervisor/correction lanes:

- Obj6A replay reached completeness 0.804, V2 1.000, sentence completeness
  0.921, citation alignment 1.000, recall@10 0.607.
- Obj6B live Opus correction gate passed with supervisor approval, correction
  count, usage/cost, and residual risk recorded.
- Combined live and promoted replay gates passed with all four hard cases
  supervisor-approved and post-supervisor V2 `ok`.

These lanes remain default-off. `S3_LLM_ENABLED=false` and normal supervisor
bypass restore the deterministic path. No Obj10 change promotes LLM or
supervisor output to default production authority.

## Frozen API / Operator / Observability Surface

The local API/operator surface remains the Phase-4 local surface plus additive
Phase-5 diagnostics and operator ergonomics:

- `GET /health`
- `GET /diagnostics`
- `GET /scope`
- `POST /ingest`
- `POST /query`
- `GET /operator`
- `GET /operator/assets/{path}`

Obj8 diagnostics are local-only and use
`phase5.obj8.local_diagnostics.v1`. They expose retrieval source, embedding
model/dimension, store configured/reachable state, Qdrant collection/vector
size, and runtime lexical-cache stats. They do not change answer authority.

The operator UI remains local. Asset cache-busting and `Cache-Control: no-store`
are retained. UI and observability changes in Phase 5 did not alter retrieval,
scoring, provider defaults, corpus identity, or final-answer authority.

## Reindex / Cache Contract

After any out-of-process corpus reindex, Qdrant rebuild, or
`taxonomy/corpus_standards.yaml` catalog rebuild, restart the API before
trusting retrieval results:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py --restart
```

In-process reindex callers clear runtime retrieval state directly. A separately
running API process does not receive that in-process cache clear.

## Phase-5 Objective Summary

- Obj0 established Phase-5 governance, local single-user boundary, and the
  migration-first/replay-first/V2-gate discipline.
- Obj1 created the 14-case bilingual real-question scorecard and offline
  evaluator.
- Obj2 replaced uncalibrated quality display with the
  `phase5.answer_quality.v2` gate and durable calibration artifact.
- Obj3 formalized multilingual ANN reindexing, parity, and independent ANN
  evaluation.
- Obj4 promoted independent BM25+dense lanes and RRF/weighted fusion after the
  replacement gate passed.
- Obj5 evaluated deterministic evidence selection and kept it default-off
  because it did not meet the strict promotion gate.
- Obj6 validated default-off GPT synthesis and Opus supervisor/correction lanes
  with replay/live gates, without default promotion.
- Obj7 fixed corpus/source/taxonomy quality and rebuilt runtime stores with
  clean PG:Qdrant parity.
- Obj8 hardened local backend reliability and operator diagnostics without
  changing answer authority.
- Obj9 froze backend/eval contracts and promoted the in-sample Obj1 scorecard as
  the standing regression net.
- Obj10 freezes Phase 5 as a whole.

## Final Verification Evidence

- Final deterministic Obj1 baseline:
  `run_logs/obj9_backend_freeze_rag_qa_20260707_113520.json`, exit code 0.
- Final answer-quality calibration:
  `run_logs/obj9_answer_quality_calibration_20260707_113809.json`, exit code 0.
- Final non-large regression:
  `run_logs/obj10_final_nonlarge_20260707_120720.log`, 652 passed,
  1 registered large-corpus deselection, exit code 0.
- Retrieval lane replacement evidence:
  Obj4 final hybrid recall@10 0.607, above BM25 0.429, ANN 0.500, and the
  0.571 runtime baseline; canonical non-large regression 591 passed.
- Corpus/runtime parity:
  `run_logs/obj7c_final_runtime_corpus_audit_20260706_184103.json`; file,
  Postgres, and Qdrant all contain 4,436 chunks with no extra/missing ids.
- Obj6 combined live gate:
  `run_logs/obj6_combined_live_gate_20260706_152132.json`, eligible true.
- Obj6 promoted replay gate:
  `run_logs/obj6_combined_replay_promoted_gate_20260706_152530.json`,
  eligible true.

## Accepted Residual Risks

| Risk | Accepted Boundary / Owner |
| --- | --- |
| 0.821 recall@10 is in-sample | Accepted as a fixed-miss regression net only; held-out generalization belongs to a successor eval phase. |
| Sentence completeness is 0.867 | Accepted as the true post-Obj7 production baseline; future improvements require a new scorecard/migration. |
| Runtime quality threshold 0.75 is provisional | Owner is a future label/recalibration objective; no automatic migration to 0.85. |
| LLM/supervisor lanes are validated but dormant | Owner is a future default-promotion objective with replay/live gates and cost/budget review. |
| Out-of-process reindex requires API restart | Owner is operator procedure; hot reload/cross-process cache invalidation is not part of Phase 5. |
| Runtime lexical backend is process-cached | Accepted for local corpus scale; persistent lexical indexing is future scalability work. |
| Generic internal ids remain | Accepted because user-facing source identity resolves; id rename requires explicit corpus/fixture migration. |
| Remote/shared/public/multi-user deployment is absent | Intentionally deferred indefinitely; reopening requires explicit product-position revision before a new phase. |

## Change Rule After Freeze

After Obj10, do not add Phase-5 objectives. Any new capability or breaking
change must start a successor phase and update the relevant migration/freeze
documents before callers are changed.

At minimum, successor migration is required for:

- schema/API response changes;
- chain-order or final-answer authority changes;
- retrieval lane, top-k, fusion, reranker, or evidence-selection default
  changes;
- corpus count, embedding model/dimension, collection, or parity contract
  changes;
- `answer_quality` schema/threshold/gate changes;
- live provider default changes or replay hash/request-shape changes;
- operator/UI changes that change backend authority;
- any remote/shared/public/multi-user deployment scope.
