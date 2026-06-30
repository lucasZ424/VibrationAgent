# Phase 4 Migrations

Updated: 2026-06-18

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

### Obj16 - Remote/shared hardening decision (2026-06-18)

Documentation-only scope decision.

- Added `docs/phase_4_remote_shared_hardening_decision.md`.
- Decided that remote/shared hardening is deferred for Phase 4.
- Recorded that multi-user authorization, tenant isolation, durable distributed
  rate limits, remote/shared metrics, k8s/public ingress, remote secrets
  management, and multi-user audit trails are Phase-5 candidates only if product
  positioning changes from local-first/single-user.
- Added the revisit gate required before implementation: deployment target,
  identity/authorization model, tenant/data isolation boundary, secrets
  ownership, durable backend, retention/redaction policy, security tests, and
  rollback path.
- Updated README and architecture references to the Obj16 decision.

No runtime schema, API route, response shape, provider path, retrieval behavior,
chain order, CI workflow, deployment default, authorization model, or
observability contract changed.

Rollback: remove the Obj16 decision document and remove the Obj16 references
from README, architecture, progress, and the deferred/polish audit. No runtime
rollback is required.

### Obj16 review polish - retained local controls and Phase-5 candidate home (2026-06-18)

Documentation-only decision polish after senior review.

- Clarified in `docs/phase_4_remote_shared_hardening_decision.md` that the
  optional local API token and in-process rate limiter are retained
  single-user local controls.
- Added `docs/phase_5_scope.md` as the durable home for Phase-5
  candidates.
- Recorded that Phase 5 is not active and that the recommended next work is a
  local iteration cycle focused on backend operation, real-run testing,
  knowledge-base quality, retrieval/citation misses, and taxonomy coverage
  before remote/shared expansion.

No runtime schema, API route, response shape, provider path, retrieval behavior,
chain order, CI workflow, deployment default, authorization model, or
observability contract changed.

Rollback: remove the retained-local-controls clarification and delete
`docs/phase_5_scope.md`.

### Obj17 - Phase-4 final interface freeze (2026-06-18)

Documentation-only final freeze.

- Added `docs/phase_4_interface_freeze.md`.
- Froze Phase 4 as the local-first, single-user engineering-assistant baseline
  for real local iteration.
- Updated README and architecture to point to the Phase-4 final freeze as the
  current baseline.
- Recorded that Phase 4 includes the Obj13 backend freeze, Obj14 read-only
  operator UI, Obj15 local-first observability, Obj16 remote/shared defer
  decision, and the Phase-5 candidate scope.
- Recorded final verification: full non-large regression, replay LLM eval, and
  retrieval eval.

No runtime schema, API route, response shape, provider path, retrieval behavior,
chain order, CI workflow, deployment default, authorization model, observability
contract, or final-answer authority changed.

Rollback: remove `docs/phase_4_interface_freeze.md`, restore README and
architecture pointers to the prior Phase-4 in-progress language, and remove
the Obj17 progress/audit entries. No runtime rollback is required.

### Obj17 review polish - final freeze summary and API delta clarity (2026-06-18)

Documentation-only final-freeze polish after senior review.

- Updated `docs/phase_4_deferred_and_polish_audit.md` so its Freeze Summary
  says Phase 4 is fully frozen through Obj17 and points to
  `docs/phase_4_interface_freeze.md`.
- Added an explicit API-surface delta to `docs/phase_4_interface_freeze.md`:
  Obj14 added `/operator` and `/operator/assets/{path}`, Obj15 added
  `/diagnostics` and migrated `/health` to offline semantics, and `/query`,
  `/ingest`, `/scope`, chain order, retrieval, provider, and final-answer
  contracts did not change.

No runtime schema, API route, response shape, provider path, retrieval behavior,
chain order, CI workflow, deployment default, authorization model, observability
contract, or final-answer authority changed.

Rollback: restore the previous audit summary and remove the API-surface delta
paragraph from the final freeze.

### R1 Wave A - deterministic answer synthesis quality (2026-06-22)

Post-freeze local-iteration refinement driven by the first real-corpus answer
review.

- Reflow soft PDF/OCR line wraps inside each S3 evidence row before deterministic
  sentence extraction. Structural headings remain boundaries and text is never
  joined across chunks.
- Ignore structural-only headings when ranking deterministic answer claims.
- Preserve the existing additive `structured_result.language` emitted by S3 and
  make deterministic S4 framing consume it, with content-based fallback for
  older payloads where the field is absent.
- Localize deterministic S4 engineering framing for Chinese while preserving the
  existing English wording for English evidence.

This changes deterministic claim text and rendered answer wording. It does not
change schemas, chain order, API routes, provider defaults, replay request shape,
or V2/V4 final-answer authority. LLM paths remain default-off.

Rollback: restore newline-delimited S3 sentence splitting and the English-only
deterministic S4 framing. Existing stored chunks do not require re-ingestion.

### R1 Wave B - retrieval scope and paper-reference compatibility (2026-06-22)

Post-freeze local-iteration compatibility record.

- Expanded deterministic query aliases for steam turbines, torsional vibration,
  order analysis, and shaft trains while excluding bare English `turbine` from
  the steam-turbine group to avoid gas-turbine query pollution.
- Gave standard-scope cues precedence over generic definition intent.
- Limited deterministic standard-scope synthesis to explicit applicability
  statements when such evidence is available, including common Chinese wording
  and English `This document/standard specifies...` clauses.
- Ignored numeric paper bibliography markers such as `[29]` and hyphenated
  ranges such as `[29-31]` when V2 parses Agent-visible chunk references.
  Non-bibliography invisible references remain blocked.
- Added labeled retrieval targets for the GB/T scope miss and order-analysis
  paper introduction, plus a V2 calibration case for numeric bibliography
  markers.

This changes deterministic retrieval expansion, intent labels, scope-claim
selection, and V2 parsing of numeric bibliography markers. It does not change
schemas, chain order, API routes, provider defaults, database data, or final
answer authority. No re-ingestion is required.

Rollback: remove the four alias groups and scope-intent precedence, restore
generic S3 ranking for scope queries, restore numeric bibliography parsing in V2,
and remove the associated retrieval/calibration fixtures and tests.

### R1 Wave A.2 - layout-aware deterministic claim extraction (2026-06-22)

Post-freeze local-iteration compatibility record.

- Added optional chunk `metadata.text_segments` containing page, character
  offsets, and paragraph block type without duplicating chunk text.
- Made S3 consume typed spans and skip explicit title segments.
- Preserved legacy blank-line layout boundaries while allowing bounded body
  continuation for visual block splits and the observed punctuated CJK word
  continuation.
- Added bounded legacy label detection for cover labels, revision identifiers,
  and bullet-separated taglines.
- Added page-relative font classification for native PDFs: one primary elevated
  title plus non-section `label` roles, preventing title-driven chunk explosion.
- Added bibliography layout roles and reference-section exclusion.
- Added alias-backed claim focus so a specific detected domain phrase outranks
  broad cross-document vibration vocabulary.

This is an additive ingestion metadata change and a deterministic synthesis
behavior change. It does not alter top-level schemas, chain order, API routes,
providers, database contracts, or final-answer authority. Existing chunks do
not require migration. The active manual, paper, and standard documents were
re-ingested to activate typed spans; external legacy chunks remain supported.

Rollback: remove font title/label and bibliography roles, remove text-segment
metadata emission, restore text-wide S3 reflow and ungated claim ranking, and
remove the A.2 regression tests.

Test-infrastructure follow-up: pytest startup no longer clears every child of
the shared safe temp root. PID-scoped basetemps remain isolated and each session
removes only its own path at shutdown. This resolves the concurrent-run race
observed during A.2 verification and does not change runtime behavior.

### R1 Wave C - direct UTF-8 CLI JSON output (2026-06-22)

Post-freeze local-iteration compatibility record.

- Added optional `--output PATH` to `ingest`, `parse-pages`, and `ask`.
- The CLI writes JSON directly as UTF-8 and suppresses stdout when an output
  path is supplied, avoiding Windows PowerShell 5.1 native-pipeline mojibake.
- The CLI best-effort reconfigures default stdout to UTF-8 at process start so
  redirected JSON does not crash on Windows non-UTF-8 code pages.
- Exit codes remain unchanged.

This is an additive CLI option plus a default stdout encoding hardening. It does
not alter JSON payloads, ingestion data, schemas, API routes, chain order,
providers, databases, or final-answer authority.

Rollback: remove stdout reconfiguration, remove the output arguments and
direct-file branch from `_print_json`, then remove the UTF-8 CLI tests.

### R1 storage persistence - ingest runtime stores (2026-06-23)

Post-freeze local-iteration storage contract record.

- Added `src/vibration_agent/storage/ingestion.py` as the runtime persistence
  layer for structured ingestion exports.
- `chunk_documents()` now attaches a top-level `storage` summary and extends
  `warnings` with storage warnings after structured export.
- When `POSTGRES_ENABLED=true`, ingest writes each manifest/chunk batch to
  Postgres. Re-ingesting the same document hash refreshes sections, chunks, and
  figure/table rows instead of failing on `documents.hash`.
- When `QDRANT_ENABLED=true`, ingest embeds chunk text and upserts only chunks
  with non-empty vectors. If embeddings are disabled or only empty fallback
  vectors are produced, Qdrant indexing is reported as `skipped` with a warning.
- `ApiIngestionResult` gained additive `storage: dict[str, Any]`, mirroring CLI
  JSON output.
- Qdrant point ids changed from SHA1 hex strings to stable UUIDv5 strings so the
  live Qdrant HTTP API accepts writes.
- The Postgres live integration fallback now matches the local compose default:
  `postgresql://vib:vib@localhost:5432/vibration`.

This changes ingestion result shape by adding `storage`, adds opt-in live
Postgres/Qdrant write side effects, and changes the Qdrant point-id contract.
Defaults remain local/offline-first: Postgres and Qdrant are disabled unless
explicitly configured, and CI/offline tests do not require live services.

Migration note: any Qdrant collection populated with the former SHA1-hex point
ids must be reindexed. The same chunk ids now map to UUIDv5 point ids, so old
points are not overwritten by the new writer.

Rollback: remove the storage persistence call from `chunk_documents()`, remove
`ApiIngestionResult.storage`, restore SHA1-based `stable_point_id()`, and remove
the storage runtime/integration tests. If Qdrant had already been populated with
UUIDv5 ids, reindex again after rollback to avoid mixed point-id generations.

### R2 critical-speed outcome guard - retrieval and S3 claim gating (2026-06-23)

Post-freeze local-iteration answer-quality record.

- Changed deterministic BM25 tokenization for CJK text so multi-character
  Chinese segments no longer emit bare single-character tokens. Two-, three-,
  and four-character n-grams remain indexed so domain phrases such as critical
  speed stay searchable while broad single-character noise is reduced.
- Added deterministic critical-speed outcome query expansion. Questions that
  combine critical-speed terms with outcome markers now also search for
  response/amplitude amplification wording.
- Added deterministic S3 claim gating for critical-speed outcome questions.
  Definition-only critical-speed evidence is no longer accepted as support for
  "what happens" style questions. If retrieved evidence lacks response,
  amplitude, amplification, or equivalent outcome wording, S3 returns
  `insufficient` with a specific warning instead of synthesizing an answer from
  a definition.
- Added regression tests for CJK token noise, query expansion, definition-only
  rejection, and response-evidence preference.

This changes corpus-wide deterministic BM25 tokenization and narrow S3 claim
selection for critical-speed outcome queries. It does not alter schemas, API
routes, chain order, provider defaults, database contracts, Qdrant point ids, or
final-answer authority. Existing chunks do not require re-ingestion, but
operators should ingest rotor-dynamics material before expecting direct answers
to critical-speed outcome questions.

Residual design note: the outcome guard is intentionally narrow. Future
iteration should prefer a general outcome/causal-intent claim-ranking lens only
after multiple real misses justify it, rather than accumulating unrelated
per-topic guards.

Rollback: restore the previous CJK token emission in BM25, remove the
critical-speed outcome expansions and S3 outcome gate, and remove the R2
regression tests. If answers regress to definition-only critical-speed
synthesis, restore the guard or ingest direct outcome evidence before relying on
operator answers.

### R2 ingestion trial runbook and runtime-store utilities (2026-06-23)

Post-freeze local-operation support record.

- Added `docs/ingestion_trial_runbook.md`, a manual runbook for small
  Postgres/Qdrant ingestion trials before full-corpus ingestion. It records
  storage/embedding configuration, no-parallel-OCR rules, disk checks,
  log-to-file commands, acceptance criteria, clean baseline reset, full-ingestion
  ordering, bounded OCR batches for `standard` and `book`, failure recovery, and
  Qdrant vector-size constraints.
- Added `scripts/reset_runtime_stores.py`, a dry-run-default local utility that
  truncates regenerated Postgres ingestion tables and deletes the configured
  Qdrant collection only when `--execute` is supplied. This lets operators reset
  stale pre-fix Postgres/Qdrant divergence before steady full ingestion.
- Added `scripts/persist_ingestion_exports.py`, which loads existing
  `data/exports/<source_type>/<doc_id>/manifest.json` plus matching
  `data/chunks/<source_type>/<doc_id>/chunks.jsonl` artifacts and persists them
  through the existing `persist_ingestion_result(...)` storage path.
- The utility supports resumable long-book OCR by allowing the file-based
  `book_workflow` exports to be written to Postgres/Qdrant after OCR completes,
  without re-running the same long OCR document through non-resumable ingestion.
- Qdrant ingestion summaries gained additive `embeddable_chunks`. Runtime Qdrant
  upsert now skips chunks whose `text` is empty or whitespace-only, so full-run
  validation should compare Qdrant points with embeddable chunks rather than
  total chunks.
- Added unit coverage for pairing manifests with chunk files, reset SQL/Qdrant
  deletion targeting, and blank-text Qdrant skip behavior.

This adds operator-run support scripts and an additive storage summary field. It
does not change ingestion export schemas, API routes, chain order, provider
defaults, database table schemas, Qdrant point-id rules, retrieval behavior, or
final-answer authority. Storage writes remain controlled by existing `.env`
settings.

Rollback: remove `scripts/reset_runtime_stores.py`, remove
`scripts/persist_ingestion_exports.py`, remove their tests, remove
`embeddable_chunks` from Qdrant summaries, restore embedding of all chunks, and
delete the runbook. Existing database rows or Qdrant points written by the
utilities should be refreshed by a normal re-ingest or removed manually if the
operator wants to discard that trial state.

### R2 page-level visual recovery and hybrid OCR (authorized 2026-06-25)

Post-freeze ingestion-behavior migration record. Steps 1-6 are implemented and
verified; the new stable knowledge-base baseline is not active until Step 7
clears and rebuilds all generated stores.

Implemented behavior:

- Replace per-image-block retention judgment with deterministic page-level
  feature analysis and bounded spatial clustering.
- Route each page through one exclusive primary path:
  - suspected occasional scanned page: full-page PaddleOCR with conditional
    Tesseract fallback, then skip cluster recovery;
  - native/mixed page: preserve native text and recover accepted direct or
    fragmented visual regions as assets.
- Never export microscopic image blocks individually.
- Recover dense tiny-block clusters by rendering their combined bbox directly
  from the source PDF page.
- Keep region OCR additive and bounded. Empty OCR does not invalidate a
  visually meaningful retained engineering figure.
- Suppress repeated header/footer decoration and keep uncertain candidates in
  bounded debug-only Level-2 metadata rather than runtime stores.
- Calibrate thresholds against labeled must-retain and must-reject visual
  fixtures before accepting implementation.

Expected output impact:

- Page metadata gains additive visual-analysis, route, filtered-fragment,
  cluster, OCR-status, and review information.
- Page assets may gain cluster provenance and region-OCR metadata.
- Native/mixed page assets, chunk asset references, manifests, Postgres
  figure/table rows, and answer-visible evidence may change.
- Occasional scanned pages may gain OCR-derived body text, changing chunk text,
  chunk boundaries, chunk ids, embeddings, and citations.
- Top-level API routes, orchestration chain order, provider defaults, database
  table schemas, and final-answer authority do not change.

Re-ingestion requirement:

- Existing local OCR/chunk/export/extracted artifacts are incompatible with the
  new visual-evidence baseline.
- Existing Postgres ingestion rows and the Qdrant `chunks` collection must be
  cleared after implementation acceptance.
- Full-corpus ingestion must restart from a clean baseline. Mixing
  emergency-guard-only documents with visual-recovery documents is not an
  accepted steady state.
- Full ingestion remains gated until Steps 1-6 and the labeled visual-decision
  evaluation pass.

Rollback:

- Remove page visual analysis, cluster recovery, page-level scanned routing,
  region OCR enrichment, and repeated-decoration suppression.
- Restore native text parsing plus direct non-tiny image extraction with the
  emergency minimum-bbox and per-page asset caps.
- Clear local generated artifacts, Postgres ingestion rows, and the Qdrant
  collection, then re-ingest. Stored data generated under the visual-recovery
  contract must not be mixed with rollback output.

Residual risk:

- Thresholds and grid size remain corpus-sensitive. They are accepted only
  through the labeled calibration gate, not by inspection of the Zhao thesis
  alone.
- VLM figure description remains deferred and is not part of this migration.

Verification: labeled visual-decision evaluation 5/5; unit suite 500 passed;
full non-large-corpus suite 522 passed with 1 deselected; real Zhao and B&K PDF
regressions passed; live Paddle image OCR passed. Detailed measurements are
recorded in `docs/refinements/r2_page_level_visual_recovery.md`.

### R3 answer usability additive runtime fields (authorized 2026-06-26)

Post-freeze operator-usability migration record. This change is additive and
does not alter chain order, provider defaults, database table schemas, final
answer authority, or V2 faithfulness policy.

Implemented behavior:

- `Citation` gains optional `source_filename` and `source_title` fields.
- `Citation` gains optional `snippet` (a single-line, length-bounded preview of
  the cited chunk text) for file-named evidence rows in the operator UI.
- `_source_filename` (evidence and hybrid) resolves the basename of
  `source_path` when no explicit `*_filename` field exists, so file-backed
  chunks surface the original document filename instead of falling back to the
  title or `doc_id`.
- S2 `retrieval_context` carries optional `source_filename` and `source_title`
  when present in chunk payloads or metadata.
- Qdrant chunk payload mapping preserves the same optional source fields for
  future runtime-store reads.
- Final `/query` structured output gains additive
  `structured_result.answer_quality` with schema
  `r3.answer_quality.v1`, a bounded score, deterministic sub-scores, V2
  faithfulness status, and citation count.
- Final `/query` structured output gains additive
  `structured_result.retrieval_source` (`file_chunks`,
  `runtime_qdrant_payloads`, or `runtime_qdrant_ann`) and
  `structured_result.retrieval_hits` so the operator can see whether semantic
  (ANN) or lexical retrieval served the answer.
- `answer_quality`, `retrieval_source`, and `retrieval_hits` are attached on the
  degraded early-return path (insufficient/failed S2 or S3) as well, with
  `faithfulness_status: "not_run"`. The telemetry remains visible when retrieval
  is weakest; previously `_early_return` omitted it exactly on degraded answers.
- Operator UI renders answer quality, retrieval-source provenance, and
  file-named evidence (filename · pages · relevance · snippet) first, while
  chain, warnings, supervisor, cost, health, and raw JSON collapse into a single
  demoted diagnostics disclosure.

Rollback:

- Remove the optional `Citation` source/snippet fields and their propagation in
  evidence, S2, S3, V4, and Qdrant payload mapping.
- Remove the `source_path` basename fallback in `_source_filename`.
- Remove `structured_result.answer_quality`, `retrieval_source`, and
  `retrieval_hits` generation from the orchestrator.
- Restore the previous operator UI citation/debug layout.

Residual risk:

- Existing Qdrant points only contain filename/title if they were previously
  stored in chunk payloads; otherwise the UI falls back to title or `doc_id`.
  The `source_path` basename fallback only fires on the file-backed chunk path
  (file chunks carry `source_path`); legacy Qdrant payloads still require a
  re-ingest to carry filename/title/source_path.
- `retrieval_source` reports `runtime_qdrant_ann` only when both
  `database.qdrant_enabled` and `embeddings.enabled` are true and the query
  embeds against matching-dimension ingested vectors; otherwise it reports a
  lexical source. The semantic lane stays default-off pending the R3
  real-question promotion gate.
- `answer_quality` is deterministic telemetry, not an authority gate. Promotion
  to acceptance gating still requires the R3 real-question scorecard.
- The current heuristic is not calibrated against usable/unusable labels. A
  2026-06-29 adversarial audit produced `score=1.0` for a keyword-repeating
  non-answer with `faithfulness_status="insufficient"`. The operator therefore
  labels the value `heuristic` and gives it no pass/fail color. Question-intent
  coverage, cited-hit relevance, completeness rubrics, and faithfulness gating
  are successor-phase work.

### R3 multilingual embedding model swap + corpus re-embed (authorized 2026-06-26)

Resolves the RAG plan [D7] embedding-model decision. Measured root cause of
"insufficient / unusable" answers once ANN retrieval was live: the dense model
`sentence-transformers/all-MiniLM-L6-v2` is English-monolingual and could not
rank the Chinese-majority corpus. Diagnostic: 64 critical-speed-outcome chunks
exist and are all in Qdrant (parity 4436=4436), yet ANN returned 0 of them in
top-50 for BOTH English and Chinese queries, so S3's faithfulness gate correctly
returned insufficient.

Implemented behavior:

- Embedding model changed `all-MiniLM-L6-v2` -> `paraphrase-multilingual-MiniLM-L12-v2`
  in `configs/embeddings.yaml` and `.env` (`EMBEDDING_MODEL`). Both are 384-dim,
  so `QDRANT_VECTOR_SIZE` and the existing collection are unchanged (no collection
  recreate).
- Corpus re-embedded: all 4436 chunks re-encoded with the multilingual model and
  re-upserted to Qdrant (same UUIDv5 point ids, overwrite-in-place). Final count
  4436 = chunk corpus (parity preserved). Postgres untouched during the re-embed.
- `chunk_payload` now also stores `source_path`, so the `_source_filename`
  basename fallback resolves a filename on the runtime Qdrant ANN path (not only
  the file-backed path).
- `answer_quality` scoring made language-aware so cross-lingual answers score
  truthfully (no schema change; same `r3.answer_quality.v1` shape):
  `question_coverage` now credits bilingual domain-term families
  (`critical speed` <-> `临界转速`/`共振`) via `query_normalize.alias_family_coverage`
  instead of raw token overlap, and `readability` strips the trailing
  `(evidence: ...)` / `(证据: ...)` tag before the sentence-completion check. The
  English critical-speed answer's composite rose 0.49 -> 0.93 with no change to the
  underlying answer.

Verification:

- Cross-lingual sanity: cos(EN query, ZH critical-speed outcome chunk) = 0.62 vs
  0.06 for unrelated text (was effectively non-discriminating under MiniLM).
- "What happens near critical speed" EN: status ok, 2 citations, outcome chunks
  6/10, Bently book at rank 0 (was insufficient / 0). ZH: ok, 3 citations.
- Full suite green (539 passed).

Rollback:

- Restore `EMBEDDING_MODEL` / `model_name` to `all-MiniLM-L6-v2` and re-embed.

Residual risk:

- The operator API process caches the embedding model at startup; it MUST be
  restarted after a model swap or it embeds queries with the stale model against
  the new vectors. (Server restart required.)
- `paraphrase-multilingual-MiniLM-L12-v2` is a lightweight multilingual model; if
  recall on the real-question set is still short, the next [D7] step is a stronger
  multilingual model (e5 / bge-m3), which is higher-dim and DOES require a Qdrant
  collection recreate.

### R3 live-model token budget alignment (authorized 2026-06-29)

The provider output cap and Agent chain budget are separate controls. High
reasoning/verbosity does not override either control.

Implemented behavior:

- GPT-5.5 `max_tokens`: 1024 -> 8192.
- Claude Opus 4.8 `max_tokens`: 1024 -> 4096.
- Per-task chain budget: 4000 -> 60000.
- Per-session chain budget: 30000 -> 180000.
- Live/capture remain opt-in; this changes capacity, not provider activation.

Verification:

- Provider/config/budget tests: 30 passed.
- A manual Opus extreme-task run completed two provider calls totaling 17667
  tokens without `BudgetDeniedError`.

Residual risk:

- The same live run fell back because the model correction omitted the required
  `answer` or `structured_result`, causing response validation to fail. More
  tokens do not fix this contract problem; it belongs to successor-phase prompt,
  validation, and retry work.
- Larger limits raise the potential per-request cost. Usage/cost telemetry and
  an explicit USD budget should be configured before unattended live operation.

Rollback:

- Restore provider max output to 1024 and chain budgets to 4000/30000.
