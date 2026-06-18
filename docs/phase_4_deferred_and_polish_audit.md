# Phase 4 Deferred And Polish Audit

Updated: 2026-06-18

## Freeze Summary

Phase 4 is fully frozen through Obj17. The final interface freeze is recorded
in `docs/phase_4_interface_freeze.md`, with the backend freeze recorded in
`docs/phase_4_backend_interface_freeze.md`. Items below are accepted residual
risks, explicit later-phase scope, or operator-only work. They should not be
treated as forgotten Phase-4 implementation tasks.

## Completed Polish Before Backend Freeze

- Obj1 tightened V2 calibration labels and fixed retrieval target resolution.
- Obj2 added the retrieval replacement gate and synthetic miss detection.
- Obj3 made real embedding providers default-off and guarded pytest from real
  model/provider construction.
- Obj5 cleaned V2 support tables and scoped direction-conflict checks.
- Obj8 added bilingual evidence keywords for S8 advice triggers.
- Obj9 reduced routing settings overhead and covered extreme plus advisory
  routing.
- Obj10 redacted local paths from rendered-DOCX fallback warnings and documented
  anchor semantics.
- Obj11 bounded LaTeX validation beyond brace balance for common malformed
  cases while preserving plain-text fallback.
- Obj12 grounded the CAS defer decision in domain fit, current S5 fixture
  counts, timeout/complexity risks, and event-driven revisit triggers.
- Obj15 added local-first structured logs, redacted health/diagnostics surfaces,
  and basic operator diagnostics without adding remote/shared hardening.
- Obj15 review follow-up added explicit workspace-prefix path redaction for
  custom POSIX workspace roots.
- Obj16 explicitly deferred remote/shared hardening and recorded the revisit
  gate required before implementation.
- Obj16 review follow-up added `docs/phase_5_candidate_scope.md` as the durable
  home for deferred Phase-5 candidates and recommended a local real-run /
  knowledge-base / taxonomy iteration before remote/shared expansion.
- Obj17 added the final Phase-4 interface freeze and closed Phase 4 as the
  local-first, single-user engineering-assistant baseline.

## Accepted Runtime Limits

- V2 is a deterministic evidence-support gate, not a general semantic
  entailment checker.
- S5 validates structure, cited evidence, and axiomatic-step shape, but it is
  not a formal symbolic proof engine.
- Obj11 `FormulaRender.status = "renderable"` means clients may attempt
  rendering. It does not guarantee a TeX renderer will succeed.
- DOCX rendered pagination can record rendered page counts, but multi-page
  block-to-page mapping still falls back to logical anchors.
- S6/S7/S8 advisory output is structured handoff context only. It is not final
  answer authority.
- S6 external literature candidates are not V2-compatible internal evidence
  unless later ingested or covered by a future external-evidence contract.
- Supervisor approval remains model-generated review, not proof of engineering
  truth.

## Accepted Dependency And Provider Limits

- OpenAI and Anthropic live paths remain manual, default-off, budget-governed,
  and replay/capture-gated.
- OpenAI embeddings are optional and default-off; disabled embeddings fall back
  to token-feature retrieval.
- Qdrant remains opt-in. Obj4 did not justify retrieval replacement or live
  reindex on the current fixture baseline.
- LibreOffice (`soffice`) is optional for rendered DOCX pagination and not
  required by CI or default ingestion.
- No mandatory CAS or symbolic proof dependency is part of the Phase-4 backend
  freeze.

## Accepted Eval And Corpus Limits

- The Phase-4 replay eval and retrieval targets are fixture-sized regression
  nets, not a full large-corpus benchmark.
- The V2 calibration set is intentionally narrow and should grow only with
  labeled evidence.
- The current S5 replay fixture count is small: three fixture files, seven
  derivation steps, four `axiomatic` steps. It grounds the CAS decision locally
  but is not a statistical corpus measurement.
- Large-corpus baselines remain operator-run only through
  `scripts/bench_large_corpus.py`.

## Deferred To Later Objectives Or Phases

- UI read-only operator surface: Obj14.
- V2 model-backed entailment or broader semantic support checks.
- Retrieval replacement or Qdrant reindex after a real recall gap and candidate
  improvement satisfy the Obj2/Obj4 gate.
- V2-compatible external-evidence contract for S6 literature records.
- Rendering UI for DOCX anchors and `FormulaRender` metadata.
- Multi-page DOCX block-to-rendered-page mapping.
- Production symbolic checker, only if event-driven demand and labeled eval
  cases justify an optional default-off implementation.
- Multi-user authz, durable rate limiting, remote deployment, k8s, and
  shared-service security hardening. Obj16 records these as deferred until the
  product target explicitly changes from local-first/single-user; the durable
  candidate list is `docs/phase_5_candidate_scope.md`.

## Freeze Follow-Up Notes

- Obj14 UI work should treat backend outputs as read-only contracts and must
  cite `docs/phase_4_backend_interface_freeze.md` before depending on a new API
  field.
- Obj15 observability preserves redaction rules for API keys, bearer tokens,
  prompt secrets, long raw source text, and local absolute paths in logs.
- Obj16 decided remote/shared hardening is deferred. Until a future objective
  changes product positioning, the product remains local-first and single-user.
- Before starting Phase 5, prefer a local iteration cycle: real operator runs,
  corpus ingestion, retrieval/citation miss analysis, backend friction fixes,
  and taxonomy expansion from actual misses.
- Any future backend contract change must be recorded in
  `docs/phase_4_migrations.md` before callers are updated.
