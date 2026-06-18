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

### Obj3 - Optional OpenAI embedding provider (2026-06-15)

Embedding provider and configuration update.

- Added optional OpenAI embedding provider support in
  `src/vibration_agent/retrieval/embeddings.py`.
- Added `EmbeddingSettings.api_key_env` and `EmbeddingSettings.timeout`.
- Added embedding environment overrides:
  - `EMBEDDING_MODEL_VERSION`
  - `EMBEDDING_ENABLED`
  - `EMBEDDING_LOCAL_FILES_ONLY`
  - `EMBEDDING_FALLBACK_TO_TOKEN_FEATURES`
  - `EMBEDDING_API_KEY_ENV`
  - `EMBEDDING_TIMEOUT`
- Updated `configs/embeddings.yaml` and `.env.example` with the new embedding
  configuration fields.
- Added `openai>=1.30.0,<2.0.0` to the `embeddings` optional dependency extra
  in `pyproject.toml`.
- Added tests for injected OpenAI embedding clients, pytest fallback behavior,
  lazy SDK import, provider metadata, cache-safe provenance, and environment
  overrides.

Default behavior remains `provider: sentence_transformers` with local-files-only
token-feature fallback. No runtime retrieval implementation, Qdrant schema,
reindex behavior, API response, UI, or chain-order contract changed.

Rollback: remove the OpenAI branch in `embeddings.py`, remove the new
`EmbeddingSettings` fields and env overrides, restore `configs/embeddings.yaml`,
`.env.example`, and `pyproject.toml`, and remove the Obj3 embedding tests.

### Obj3 review polish - Embedding default-off hardening (2026-06-15)

Embedding provider safety polish after senior review.

- Changed `EmbeddingSettings.enabled` and `configs/embeddings.yaml` default from
  true to false, so real embedding providers require explicit enablement.
- Kept default dense retrieval warning-free by making the disabled embedding path
  return token-feature fallback records without warnings.
- Added a pytest guard before real `sentence_transformers` model loading.
- Added OpenAI embedding response tests for object and `model_dump` shapes.

No Qdrant schema, reindex behavior, API response, UI, or chain-order contract
changed.

Rollback: restore the previous embedding enabled default and disabled-warning
behavior, remove the sentence-transformers pytest guard, and remove the added
OpenAI response-shape tests.

### Obj3 follow-up - Dotenv single-source consolidation (2026-06-15)

Local configuration contract update.

- Consolidated local dotenv loading to `.env` only; `config.load()` no longer
  reads `.env.local`.
- Demoted `.env.example` to a sanitized historical configuration snapshot and
  added it to `.gitignore`.
- Updated README guidance so operator-owned provider keys and manual live flags
  live in `.env` or process environment variables, not `.env.local`.
- Added config tests proving `.env` is loaded, process environment values still
  win, dotenv loading can be disabled, and stale `.env.local` files no longer
  affect runtime behavior.
- Non-sensitive local check on 2026-06-15: `.env.local` is absent, and the
  OpenAI/Anthropic key entries are present in `.env`.

Rollback: restore `.env.local` loading in `config.py`, remove `.env.example`
from `.gitignore`, restore README `.env.local` guidance, and remove the
`.env.local` non-loading test.

### Obj4 - Qdrant reindex and retrieval replacement gate (2026-06-15)

Retrieval attribution and gate-runner update.

- Added retrieval attribution fields to hybrid `retrieval_context` rows:
  `retrieval_lanes`, `retrieval_contribution`, `lane_scores`, and
  `source_priority`.
- Extended retrieval eval diagnostics with `top_hit_contributions`.
- Added `scripts/qdrant_reindex_gate.py`, an offline gate runner that records
  whether Obj2/Obj3 evidence permits Qdrant reindex/retrieval replacement.
- Current gate output records `decision: non_replacement`, with
  `replacement.allowed: false`, `reindex.allowed: false`, and
  `reindex.executed: false`.

No Qdrant schema, live Qdrant write, default retrieval replacement, UI, or
chain-order contract changed. `retrieval_context` dict rows gained additive
attribution fields; `RetrievalHit`/`RetrievalOutput` Pydantic schemas and API
envelope shape are unchanged.

Rollback: remove `scripts/qdrant_reindex_gate.py`, remove
`top_hit_contributions` from retrieval eval diagnostics, remove the added
hybrid retrieval attribution fields, and remove the Obj4 tests/progress entry.

### Obj5 - Deterministic V2 evidence-support hardening (2026-06-15)

V2 deterministic support-check and calibration contract update.

- Added narrow deterministic support groups for calibrated vibration
  paraphrases, including damping/zeta and runup/passage wording.
- Added deterministic conflict checks for direction reversals and numeric/unit
  values bound to unsupported quantity terms.
- Updated `scripts/v2_calibration_eval.py` to report true-label pass/fail under
  `phase4.v2_calibration.report.v3`; `expected_current_supported` remains in
  the fixture/report as historical baseline context, not the Obj5 pass gate.
- Updated Obj1 V2 calibration fixture labels for the three pre-Obj5 known gaps.
- Added focused V2 tests for wrong-quantity numeric binding, direction reversal,
  and calibrated low-overlap paraphrase support.

No V2 structured result fields, API envelope, chain order, provider path, or
model-backed entailment checker changed.

Rollback: remove the new deterministic support/conflict helpers, restore
`scripts/v2_calibration_eval.py` to report schema v2 and baseline-relative
pass/fail, restore the pre-Obj5 calibration fixture labels, and remove the Obj5
V2 tests/progress entry.

### Obj5 review polish - V2 support-table cleanup and direction scoping (2026-06-15)

V2 deterministic rule polish after senior review.

- Removed corrupted damping-symbol entries from `_SUPPORT_GROUPS`.
- Replaced them with explicit damping vocabulary and symbols: `damping`,
  `damping ratio`, `zeta`, `ζ`, `阻尼`, and `阻尼比`.
- Scoped direction-conflict checks to evidence clauses sharing at least two
  non-direction anchors with the claim, avoiding false blocks when the same
  chunk discusses opposite trends for different quantities.
- Added focused tests for scoped direction checking and Chinese/Greek damping
  symbol paraphrase support.

No V2 structured result fields, API envelope, chain order, provider path, or
model-backed entailment checker changed.

Rollback: restore the previous support-group entries and whole-evidence
direction check, and remove the two review-polish tests.

### Obj6 - S6 literature search prototype (2026-06-15)

Default-off literature-search skill and replay fixture update.

- Added `src/vibration_agent/skills/s6_literature_search.py` with
  `LiteratureSearchSkill`.
- Exported `LiteratureSearchSkill` lazily from `vibration_agent.skills` so
  default imports do not load the deferred S6 module.
- Added `agent_skills/s6_literature_search/SKILL.md`.
- Added `prompts/skills/s6_literature_search.md`.
- Added replay fixtures:
  - `tests/fixtures/literature/semantic_scholar_replay.json`
  - `tests/fixtures/literature/arxiv_replay.json`
- S6 skill output schema version is `s6.literature_search.v1`.
- S6 replay fixture schema version is `phase4.s6_literature_fixture.v1`.
- Added redaction coverage for API keys, bearer tokens, local paths, and long
  raw text.
- Manual live sources are named as Semantic Scholar Graph API
  (`semantic_scholar`) and arXiv API (`arxiv`), but live search requires an
  explicit gate and injected client.

S6 remains outside the default TutorOrchestrator chain and remains listed in
`PHASE0_DEFERRED_SKILLS` until the later routing activation gate. No API
envelope, default chain order, V2/V4 contract, or live-provider CI dependency
changed.

Rollback: remove the S6 skill module/export, prompt, agent skill package,
literature fixtures, tests, and this progress entry.

### Obj7 - S7 model selection prototype (2026-06-15)

Default-off model-selection advisory skill update.

- Added `src/vibration_agent/skills/s7_model_selection.py` with
  `ModelSelectionSkill`.
- Exported `ModelSelectionSkill` lazily from `vibration_agent.skills` so default
  imports do not load the deferred S7 module.
- Added `agent_skills/s7_model_selection/SKILL.md`.
- Added `prompts/skills/s7_model_selection.md`.
- S7 output schema version is `s7.model_selection.v1`.
- Added deterministic model-family recommendations for critical-speed/runup
  response, rotor-unbalance synchronous response, and bearing-fault envelope
  analysis.

S7 remains outside the default TutorOrchestrator chain and remains listed in
`PHASE0_DEFERRED_SKILLS` until the later routing activation gate. No API
envelope, default chain order, V2/V4 contract, live-provider path, or modeling
execution pipeline changed.

Rollback: remove the S7 skill module/export, prompt, agent skill package, tests,
and this progress entry.

### Obj8 - S8 experiment advice prototype (2026-06-17)

Default-off experiment-advice skill update.

- Added `src/vibration_agent/skills/s8_experiment_advice.py` with
  `ExperimentAdviceSkill`.
- Exported `ExperimentAdviceSkill` lazily from `vibration_agent.skills` so
  default imports do not load the deferred S8 module.
- Added `agent_skills/s8_experiment_advice/SKILL.md`.
- Added `prompts/skills/s8_experiment_advice.md`.
- S8 output schema version is `s8.experiment_advice.v1`.
- Added deterministic measurement-plan advice for runup/resonance validation,
  bearing-fault measurement planning, and synchronous-unbalance validation.
- Unsupported numeric query terms that are not visible in evidence are omitted
  from plan text and recorded in `omitted_unsupported_thresholds`.

S8 remains outside the default TutorOrchestrator chain and remains listed in
`PHASE0_DEFERRED_SKILLS` until the later routing activation gate. No API
envelope, default chain order, V2/V4 contract, live-provider path, sensor
integration, or data-acquisition pipeline changed.

Rollback: remove the S8 skill module/export, prompt, agent skill package, tests,
and this progress entry.

### Obj8 review polish - bilingual S8 evidence keywords (2026-06-17)

S8 deterministic rule coverage polish after senior review.

- Added Chinese evidence keywords for the runup/resonance, bearing-fault, and
  synchronous-unbalance advice rules.
- Added focused coverage proving Chinese evidence rows can trigger all three S8
  experiment-plan families while S8 remains default-off and explicit-call-only.
- Recorded the Obj9 carry-forward that `omitted_unsupported_thresholds` is an
  audit field and must not be rendered as measurement advice by future routing.

No API envelope, default chain order, V2/V4 contract, routing activation, live
provider path, sensor integration, or data-acquisition pipeline changed.

Rollback: remove the added Chinese keyword entries and the Chinese evidence
coverage test.

### Obj9 - S6/S7/S8 routing activation gate (2026-06-17)

Default-off advisory routing gate update.

- Added `AdvisoryRoutingDecision` and `route_advisory_skills(...)` in
  `src/vibration_agent/agent/routing.py`.
- Added routing settings:
  - `advisory_routing_enabled` (default `false`)
  - `advisory_intent_routing_enabled` (default `false`)
  - `advisory_allowed_skills` (default empty)
- Exported the advisory routing helper from `vibration_agent.agent`.
- Updated `TutorOrchestrator` to run a post-V4 advisory lane only when the gate
  selects S6/S7/S8.
- Advisory lane output is structured handoff context under
  `structured_result["advisory_routing"]`; it does not rewrite the V4 final
  answer and is marked `structured_handoff_only`.
- Added deterministic routing and orchestrator tests for disabled default,
  explicit skill-list activation, intent activation, and enabled-with-no-skill
  behavior.

Default behavior is unchanged when `advisory_routing_enabled` is false. S6/S7/S8
remain absent from ordinary answers unless the operator or caller explicitly
enables the advisory gate. No live-provider path, API envelope, V2/V4 checker,
or final-answer renderer changed.

Rollback: remove the advisory routing settings/helper/export, remove the
TutorOrchestrator advisory lane, and remove Obj9 routing/orchestrator tests.

### Obj9 review polish - routing overhead and extreme/advisory coverage (2026-06-17)

Low-cost routing-gate polish after senior review.

- Reused a single settings object inside each `TutorOrchestrator._run_chain`
  execution for both model routing and advisory routing, avoiding an extra
  Obj9 config load on the default path while still honoring config-enabled
  advisory routing.
- Added orchestrator coverage for `difficulty=extreme` with advisory routing
  enabled, proving advisory handoff runs before V3 reviewer and does not change
  the V4 final answer.

No API envelope, default-off policy, V2/V4 checker, final-answer renderer,
live-provider path, or advisory rendering contract changed.

Rollback: restore separate route settings lookup and remove the
extreme-plus-advisory orchestrator test.

### Obj10 - Rendered DOCX pagination and rich asset anchoring (2026-06-17)

Optional DOCX pagination and asset-anchor update.

- Added optional `metadata` to `OcrPage` with a default empty object.
- Added `src/vibration_agent/ingestion/assets.py` with
  `asset_anchor_metadata(...)` and anchor schema version
  `p4.rich_asset_anchor.v1`.
- Extended `parse_docx(...)` with explicit `pagination_mode="logical|rendered"`.
  Logical mode remains the default.
- Added optional headless LibreOffice (`soffice`) DOCX-to-PDF rendering support
  for rendered page-count metadata.
- Missing LibreOffice, rendered-PDF inspection failures, and missing
  block-to-page layout mapping fall back to logical DOCX pagination with
  explicit `metadata["docx_pagination"]` reasons/warnings.
- DOCX table/image assets now carry optional rich anchor metadata including
  source, page anchor type, block id or DOCX relationship id, and rendered page
  number when known.

Existing DOCX/PDF ingestion contracts remain backward compatible. The default
pipeline does not require LibreOffice and does not enable rendered DOCX
pagination unless explicitly requested. No chunk schema, retrieval schema,
V2/V4 contract, or final-answer renderer changed.

Rollback: remove `OcrPage.metadata`, remove the asset-anchor helper, restore
`parse_docx(...)` to logical-only behavior, and remove Obj10 DOCX rendered
fallback/anchor tests.

### Obj10 review polish - DOCX warning redaction and anchor semantics (2026-06-17)

Low-cost rendered-DOCX polish after senior review.

- Redacted local filesystem paths from rendered DOCX fallback warnings before
  storing them in `OcrPage.metadata["warnings"]`.
- Added focused coverage for nonzero `soffice` stderr containing Windows and
  POSIX local paths.
- Documented rich anchor semantics: `anchor.page_no` is the parser's logical page
  anchor, while `anchor.rendered_page_no` is only present when a rendered backend
  can locate the asset without guessing.

No schema field, default pagination behavior, chunk contract, LibreOffice
requirement, or rendered-page fallback policy changed.

Rollback: remove the local-path redaction helper/test and restore the previous
anchor helper docstring.

### Obj11 - LaTeX/MathML rendering contract (2026-06-17)

Formula-rendering schema and V4 contract update.

- Added `FormulaRender` with schema version `p4.formula_render.v1`.
- Added additive `structured_result["formula_renders"]` output for S5 formula
  derivations and V4 styled answers.
- `formula_renders` records `plain_text` as the stable CLI/API fallback and may
  include valid `latex` or `mathml` markup for render-capable clients.
- Invalid formula markup is marked with `status: invalid_markup`; invalid
  `latex`/`mathml` fields are omitted from the render record, `plain_text`
  remains available, and warnings are surfaced.
- V4 preserves the plain-text final answer and citations. Formula markup is
  structured metadata only and is not rendered into the answer body.

No symbolic proof, CAS dependency, frontend renderer, provider path, chain order,
or citation contract changed.

Rollback: remove `FormulaRender`, remove the formula-rendering helper, stop
writing `formula_renders` from S5/V4, and remove Obj11 S5/V4 tests.

### Obj11 review polish - bounded LaTeX structure checks (2026-06-17)

Low-cost formula-rendering hardening after senior review.

- Extended deterministic LaTeX validation beyond brace balance for two common
  malformed-but-brace-balanced cases:
  - `\frac` must have two braced arguments.
  - `\begin{...}` / `\end{...}` environments must be matched and nested.
- Added V4 coverage proving those malformed LaTeX records degrade to
  `status: invalid_markup` while retaining `plain_text` and citations.
- Documented that `status: renderable` remains a client-attempt contract, not a
  full TeX-render success guarantee.

No full LaTeX parser, symbolic proof, CAS dependency, frontend renderer,
provider path, chain order, or citation contract changed.

Rollback: remove the extra LaTeX structure checks and the added malformed
LaTeX assertions; the original brace-balance-only Obj11 contract remains
backward compatible.

### Obj12 - Symbolic proof / CAS feasibility spike (2026-06-17)

Documentation-only feasibility decision.

- Added `docs/phase_4_symbolic_proof_spike.md`.
- Decided not to add a mandatory CAS or symbolic proof dependency in Phase 4.
- Recorded that a future production checker, if justified, should be a narrow,
  optional, default-off S5 algebra-equivalence checker with a labeled eval gate.
- Clarified that symbolic checking is separate from V2 evidence support and
  Obj11 formula rendering.
- Rejected external CAS services for the local-first backend freeze baseline.

No runtime schema, API response, dependency, replay fixture, retrieval behavior,
provider path, chain order, UI, citation contract, or S5 implementation changed.

Rollback: remove `docs/phase_4_symbolic_proof_spike.md` and the Obj12 progress
entry. No code rollback is required.

### Obj12 review polish - CAS decision grounding (2026-06-17)

Documentation-only reasoning polish after senior review.

- Added a domain-fit conclusion: a narrow scalar algebra checker would cover
  only a minority of high-value vibration derivations because transfer
  functions, differential equations, modal/eigenvalue forms, damping
  assumptions, approximations, and unit-bearing physical models dominate the
  hard cases.
- Added the current S5 replay fixture count: three S5 fixture files, seven total
  derivation steps, and four `axiomatic` steps. The count is explicitly treated
  as a small fixture signal, not a corpus-wide demand measurement.
- Clarified that SymPy can be local/offline while still producing cross-version
  canonical-form differences or inconclusive equivalence results.
- Added a future production requirement for timeout or complexity bounds.
- Replaced the vague demand trigger with event-driven revisit signals:
  repeated reviewer burden, user-reported algebra errors, or a labeled eval set
  with enough scalar rearrangement cases.

No runtime schema, dependency, code path, chain order, provider path, citation
contract, or tests changed.

Rollback: remove the Obj12 review-polish additions from the spike and progress
entry. No code rollback is required.

### Obj13 - Backend interface freeze (2026-06-17)

Documentation-only backend freeze.

- Added `docs/phase_4_backend_interface_freeze.md`.
- Added `docs/phase_4_deferred_and_polish_audit.md`.
- Updated `README.md` and `docs/architecture.md` to point to the Phase-4
  backend freeze.
- Froze Obj1-Obj12 backend contracts, eval gates, retrieval gates, advisory
  routing boundary, V2 hardening boundary, rendered DOCX metadata, formula
  rendering contract, and CAS spike conclusion before UI/observability work.
- Recorded that S6/S7/S8 are default-off advisory handoff skills, not default
  final-answer renderers.
- Recorded that Obj11 formula rendering is metadata only and Obj12 keeps
  symbolic proof/CAS deferred unless a future optional checker objective
  satisfies the documented eval gate.

No runtime schema, dependency, code path, provider path, replay fixture,
retrieval behavior, chain order, citation contract, or API response shape
changed.

Rollback: remove the Obj13 freeze/audit docs and Obj13 references from README,
architecture, and progress. No code rollback is required.

### Obj13 review polish - Phase-3 freeze inheritance pointer (2026-06-17)

Documentation-only freeze clarity polish after senior review.

- Added an explicit pointer from `docs/phase_4_backend_interface_freeze.md` to
  the inherited Phase-3 freeze in `docs/phase_3_interface_freeze.md`.
- Clarified that the Phase-4 backend freeze is additive and does not restate or
  replace Phase-3 LLM, replay, supervisor, provider, and deterministic-default
  contracts except where Phase 4 explicitly migrated them.

No runtime schema, dependency, code path, chain order, API shape, provider path,
retrieval behavior, replay fixture, or citation contract changed.

Rollback: remove the Phase-3 inheritance sentence from the Obj13 freeze doc.

### Obj14 - Read-only operator UI surface (2026-06-17)

Local UI/API surface update.

- Added a static read-only operator UI under `apps/ui/`.
- Added FastAPI static routes:
  - `GET /operator`
  - `GET /operator/assets/{path}`
- The UI calls the existing `POST /query` contract and displays existing
  `ApiQueryResponse.output` fields:
  - `structured_result.answer`
  - `structured_result.chain`
  - `citations`
  - `warnings`
  - supervisor metadata
  - token/cost metadata when present
  - raw response JSON for inspection
- The UI includes no ingestion, delete, admin, authz, rate-limit, provider-key,
  or live-provider control surface.
- Optional API auth remains the existing API token mechanism; no live provider
  key is required by the UI.

No runtime schema, `/query` response shape, provider path, retrieval behavior,
chain order, final-answer authority, or write/admin API contract changed.

Rollback: remove the `/operator` static routes, remove `apps/ui/` assets, and
remove Obj14 API smoke tests and docs.

### Obj14 review polish - dotenv and Claude artifact cleanup (2026-06-17)

Repository hygiene polish after senior review.

- Removed the tracked `.env.example` file. This supersedes the earlier Obj3
  follow-up that kept it as a historical sanitized snapshot.
- Removed the tracked `.claude/worktrees/serene-satoshi-01115b` artifact and
  added `.claude/` to `.gitignore`.
- Updated README guidance to state the current runtime rule: `.env` is the only
  local dotenv source; `.env.local` and `.env.example` are not read.
- Kept `.env` ignored and local-only.

No runtime schema, API shape, UI route, provider path, chain order, retrieval
behavior, or citation contract changed.

Rollback: restore `.env.example` from history only if a future objective decides
to reintroduce a tracked sanitized template; remove `.claude/` from `.gitignore`
only if Claude artifacts intentionally become repo-owned files.

### Obj15 - Local-first observability essentials (2026-06-17)

Local observability API and logging update.

- Added deterministic redaction and structured-log helpers in
  `src/vibration_agent/observability.py`.
- Added API request structured logging with schema version
  `p4.local_observability.v1`.
- Converted the query supervisor observability log to structured JSON while
  avoiding raw query text, request bodies, headers, API keys, bearer tokens,
  prompt secrets, long raw text, and local absolute paths.
- Added additive `ApiHealthResponse.diagnostics`.
- Added `ApiDiagnosticsResponse`.
- Migrated `GET /health` semantics: it is now a local liveness/config probe and
  does not run Postgres, Qdrant, external network, or live-provider checks.
- Added `GET /diagnostics`. Default behavior reports local diagnostics and
  configured/disabled dependency status without external probes. Passing
  `probe_dependencies=true` explicitly runs the existing Postgres/Qdrant
  reachability checks and returns redacted dependency details.
- Added a read-only Diagnostics panel to `/operator` that consumes `/health`.

No `/query` response shape, retrieval behavior, provider path, chain order,
final-answer authority, write/admin API, live-provider default, or remote/shared
hardening contract changed.

Rollback: remove the observability helper, remove the request/query structured
logging calls, remove `ApiDiagnosticsResponse`, remove
`ApiHealthResponse.diagnostics`, restore `/health` dependency probing if needed,
remove `/diagnostics`, remove the operator Diagnostics panel, and restore Obj15
tests/docs.

### Obj15 review polish - explicit workspace path redaction (2026-06-18)

Low-cost redaction polish after senior review.

- Extended local observability redaction so callers can pass explicit local path
  prefixes.
- API workspace and diagnostics redaction now pass the configured workspace
  path, covering custom POSIX roots such as `/opt/...` or `/srv/...` without
  broadening fixed POSIX path matching enough to catch ordinary URL/API paths.
- Added unit coverage for explicit custom POSIX workspace-prefix redaction.

No API route, response shape, logging schema, health/diagnostics semantics,
provider path, retrieval behavior, chain order, or final-answer contract
changed.

Rollback: remove the explicit `path_prefixes` support from observability
helpers, restore API redaction calls to the default path regexes, and remove the
custom POSIX prefix tests.
