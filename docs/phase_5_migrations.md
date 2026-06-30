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
  evidence boundary, and diagnostic hints.
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
