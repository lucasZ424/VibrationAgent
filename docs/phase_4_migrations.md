# Phase 4 Migrations

Updated: 2026-06-15

## Purpose

This file is the canonical migration log for Phase-4 schema, contract,
configuration, replay-fixture, retrieval, skill, API, and UI changes.

Phase 3 is frozen in `docs/phase_3_interface_freeze.md`. Phase 4 may supersede
Phase-3 contracts only through an explicit migration entry in this file.

## Canonical Change Checklist

For any Phase-4 objective that changes a frozen schema, API response shape,
structured result key, provider request shape, replay-fixture layout, retrieval
contract, prompt schema, chain order, UI/API contract, or downstream caller
contract:

1. Update `src/vibration_agent/schemas.py` first when a schema is affected.
2. Add a migration note in this file.
3. Update fixtures and tests that encode the affected shape.
4. Update downstream callers after the contract and tests are in place.
5. Record verification and residual risk in `docs/phase_4_progress.md`.
6. Record review findings in `docs/issue_log_p4/issues_objN.txt`.

Default policy: add fields as optional unless the objective explicitly approves
a breaking migration. Deprecated fields are not removed until a freeze document
or migration entry records the removal window.

## Replay / Provider / Retrieval Checklist

For any objective that changes replay, provider, retrieval, or live/manual
behavior:

1. Keep live paths default-off unless the objective explicitly changes that
   boundary.
2. Add or update replay fixtures before adding CI assertions.
3. Include prompt version, schema version, provider/model, retrieval provider,
   embedding model/dimension, max-token settings, request body, and request hash
   where those fields are part of the request.
4. Redact API keys, local absolute paths, long raw source text, and bearer tokens
   from captured fixtures and reports.
5. Add fallback tests for missing key, timeout, budget denial, schema parse
   failure, replay miss, unavailable retrieval provider, and unavailable storage
   dependency when applicable.
6. Confirm CI never constructs a live provider client or requires a live network
   service unless the test is explicitly skipped when unavailable.

## Migration Log

### Obj0 - Phase-4 execution baseline (2026-06-12)

Documentation-only baseline.

- Added `docs/phase_4_development_order.md` as the proposed Phase-4 objective
  order.
- Added `docs/phase_4_progress.md` as the Phase-4 progress ledger.
- Added `docs/phase_4_migrations.md` as the Phase-4 contract and migration
  ledger.
- Reserved `docs/issue_log_p4/` as the local ignored Phase-4 review issue
  directory.

No runtime schema, API, replay fixture, retrieval, provider request, UI, or
chain-order contract changed.

Rollback: remove the Phase-4 baseline docs. The ignored issue-log directory can
be cleaned locally if no review artifacts need to be kept.

### Obj0 review update - Phase-4 plan hardening (2026-06-15)

Documentation-only review update before Obj1 implementation.

- Chose deterministic V2 evidence-support hardening for Obj5. Model-backed
  entailment remains out of Obj5 and requires a separate default-off,
  replay-first objective if pursued later.
- Moved V2 calibration labels and retrieval recall targets into Obj1 so later
  Obj4/Obj5 gates can be numeric.
- Named optional/manual external dependencies:
  Semantic Scholar Graph API and arXiv API for S6 live literature search, and
  headless LibreOffice (`soffice`) for rendered DOCX pagination.
- Added an explicit S6/S7/S8 routing activation gate.
- Split backend interface freeze from final Phase-4 freeze.
- Split local-first observability essentials from remote/shared hardening
  decision, with remote/shared hardening defaulting to deferred unless product
  positioning changes.

No runtime schema, API, replay fixture, retrieval, provider request, UI, or
chain-order contract changed.

Rollback: revert the Phase-4 planning docs to the 2026-06-12 objective list.

### Obj1 - Replay eval, V2 calibration, and retrieval targets (2026-06-15)

Eval-asset and fixture-contract update.

- Added replay eval fixtures:
  - `tests/fixtures/llm/eval_fabricated_unit.json`
  - `tests/fixtures/llm/eval_unstructured_answer.json`
- Added V2 calibration fixture schema
  `phase4.v2_calibration.v2` at
  `tests/fixtures/eval/v2_calibration/cases.json`.
- Added V2 calibration report schema
  `phase4.v2_calibration.report.v2` through
  `scripts/v2_calibration_eval.py`.
- Added retrieval target fixture schema
  `phase4.retrieval_targets.v1` at
  `tests/fixtures/retrieval/targets.json`.
- Updated eval tests to require the broader replay set and validate Obj1
  calibration/target fixtures.

No runtime schema, API response, provider request, retrieval implementation,
UI, or chain-order contract changed. CI remains replay/deterministic and does
not require API keys, external search, Qdrant, or a large corpus.

Rollback: remove the Obj1 fixture files and runner, restore the previous
`tests/eval/test_llm_eval.py` case-count assertion, and delete the Obj1
progress entry.

### Obj1 review polish - Calibration headroom and target resolution (2026-06-15)

Eval-asset polish after senior review.

- Converted V2 calibration from exact truth-label pass/fail to
  baseline-relative assertions with separate `expected_supported` and
  `expected_current_supported` fields.
- Added hard calibration cases that current deterministic V2 intentionally does
  not handle perfectly:
  - wrong quantity with the same visible value
  - meaning-flipping paraphrase with lexical overlap
  - legitimate low-lexical-overlap engineering paraphrase
- Fixed the Chinese retrieval target to reference the real fixture chunk
  `fixture_rotor_zh_doc_p0001_00001` / `fixture_rotor_zh_doc`.
- Added test coverage that retrieval target chunk ids resolve against
  `tests/fixtures/chunks/*.jsonl`.
- Tightened the replay eval case-count guard to the current exact count of 7.

No runtime schema, API response, provider request, retrieval implementation,
UI, or chain-order contract changed.

Rollback: remove the hard calibration cases, restore the V2 calibration fixture
and report schema versions to v1, restore the previous retrieval target ids if
needed, and relax the replay eval case-count assertion.

### Obj2 - Retrieval recall audit runner (2026-06-15)

Eval-runner and report-contract update.

- Added `scripts/retrieval_eval.py`, an offline retrieval recall audit runner
  over labeled retrieval targets and fixture chunks.
- Added retrieval eval report schema
  `phase4.retrieval_eval.report.v1`.
- Added `tests/eval/test_retrieval_eval.py` to validate top-k recall metrics,
  expected-miss handling, per-case diagnostics, and no-synthesis attribution.
- The runner uses the existing `vibration_agent.retrieval.hybrid.search()` path
  and does not alter runtime retrieval behavior.

No runtime schema, API response, provider request, retrieval implementation,
embedding provider, UI, or chain-order contract changed. CI remains
replay/deterministic and does not require API keys, external search, Qdrant, or
a large corpus.

Rollback: remove `scripts/retrieval_eval.py`,
`tests/eval/test_retrieval_eval.py`, and the Obj2 progress entry.

### Obj2 review polish - Replacement gate and miss detection (2026-06-15)

Eval-report polish after senior review.

- Added `replacement_gate` to the retrieval eval report with a written Obj4
  decision rule:
  `top_k_recall@10 < 0.80` or `missing_evidence_cases >= 1` is required before
  replacement is justified, and a candidate must fix at least one miss without
  lowering recall on other evidence targets.
- Added synthetic test coverage for a real `retrieval_miss` case where the
  expected chunk exists in the corpus but is not retrieved.
- Kept the default fixture audit unchanged: current baseline recall remains
  `top_k_recall@5 = 1.0`, `top_k_recall@10 = 1.0`, with no missing evidence
  cases and replacement not justified.

No runtime schema, API response, provider request, retrieval implementation,
embedding provider, UI, or chain-order contract changed.

Rollback: remove `replacement_gate` from the eval report and remove the
synthetic retrieval-miss test.
