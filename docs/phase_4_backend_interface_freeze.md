# Phase 4 Backend Interface Freeze

Updated: 2026-06-17

## Freeze Decision

Phase 4 backend work through Obj12 is frozen as the post-Phase-3 backend
baseline. This freeze covers eval assets, retrieval gates, optional embedding
configuration, deterministic V2 hardening, S6/S7/S8 advisory skill prototypes
and routing gate, rendered DOCX metadata, formula rendering metadata, and the
CAS feasibility decision.

This document is additive on top of the inherited Phase-3 freeze recorded in
`docs/phase_3_interface_freeze.md`; it does not restate or replace the
Phase-3 LLM, replay, supervisor, provider, and deterministic-default
contracts except where Phase 4 explicitly migrated them.

Obj14 and later may add UI and local observability on top of this backend. They
must not silently change backend schemas, chain order, retrieval defaults,
provider behavior, or final-answer authority.

## Frozen Default Runtime Path

The default user query path remains evidence-bound:

```text
User query
  -> TutorOrchestrator
  -> S2 retrieval
  -> S3 evidence-bound synthesis
  -> optional S4 engineering analysis OR optional S5 formula derivation
  -> V2 citation check
  -> V4 style
  -> optional V3 reviewer for extreme tasks
  -> optional supervisor annotation/correction loop
  -> SkillOutput/API/CLI JSON
```

S1 ingestion remains explicit. It prepares local corpus exports for S2 and is
not called on every query.

S6/S7/S8 are not part of the final-answer path by default. When the advisory
gate is explicitly enabled, they run after V4 as structured handoff context and
do not rewrite the V4 answer.

## Frozen Active And Deferred Skills

Active or available backend skills:

- `s1_ingestion`
- `s2_retrieval`
- `s3_qa_summary`
- `s4_engineering_analysis`
- `s5_formula_derivation`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`
- `v4_style`

Deferred/advisory skills:

- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`

S6/S7/S8 may be present in registries and lazy exports, but ordinary user
queries reach them only through the Phase-4 advisory routing gate. Their output
is `structured_handoff_only` and carries
`v2_v4_policy = "do_not_render_as_final_answer"`.

## Frozen Structured Result Additions

Phase 4 adds or freezes these additive structured-result surfaces:

- Retrieval context attribution fields:
  - `retrieval_lanes`
  - `retrieval_contribution`
  - `lane_scores`
  - `source_priority`
- Advisory routing handoff:
  - `structured_result["advisory_routing"]`
  - `advisory_routing.enabled`
  - `advisory_routing.selected_skills`
  - `advisory_routing.rendering`
  - `advisory_routing.v2_v4_policy`
  - `advisory_routing.outputs`
  - `advisory_routing.limitations`
- Formula rendering metadata:
  - `structured_result["formula_renders"]`
  - `FormulaRender.schema_version = "p4.formula_render.v1"`
  - `FormulaRender.status = "renderable" | "plain_text_fallback" |
    "invalid_markup"`
- DOCX rendered pagination metadata:
  - `OcrPage.metadata["docx_pagination"]`
  - optional rich asset anchor metadata schema
    `p4.rich_asset_anchor.v1`
- S6/S7/S8 skill-specific structured results:
  - `s6.literature_search.v1`
  - `s7.model_selection.v1`
  - `s8.experiment_advice.v1`

All additions are backward-compatible dictionary fields unless the corresponding
Pydantic schema explicitly names a new optional field. Consumers must tolerate
absence of these fields when a feature is disabled or unavailable.

## Frozen Schema And Metadata Additions

Phase 4 freezes these schema additions:

- `FormulaRender`
- `FormulaRenderStatus`
- `FormulaRenderSource`
- `OcrPage.metadata`
- optional `DocumentAsset.metadata["anchor"]` shape from
  `asset_anchor_metadata(...)`

`SkillOutput` remains the public skill envelope:

- `status`
- `summary`
- `structured_result`
- `citations`
- `warnings`
- `handoff_recommendation`

Formula render metadata is not symbolic proof metadata. It is for UI/API
render-capable clients and must retain a `plain_text` fallback or be omitted.

## Frozen Eval And Gate Assets

Obj1 froze the Phase-4 eval labels and targets:

- V2 calibration fixture:
  `tests/fixtures/eval/v2_calibration/cases.json`
- V2 calibration runner:
  `scripts/v2_calibration_eval.py`
- Retrieval target fixture:
  `tests/fixtures/retrieval/targets.json`
- Replay eval fixtures under `tests/fixtures/llm/`

Obj2 froze the retrieval recall audit runner:

- `scripts/retrieval_eval.py`
- report schema `phase4.retrieval_eval.report.v1`

Obj4 froze the Qdrant reindex/replacement gate:

- `scripts/qdrant_reindex_gate.py`
- replacement requires baseline `top_k_recall@10 < 0.80` or
  `missing_evidence_cases >= 1`
- a candidate must fix at least one miss without lowering recall on other
  evidence targets

Current fixture baseline does not justify retrieval replacement or Qdrant
reindex.

## Frozen Retrieval And Embedding Boundary

The default retrieval path remains hybrid/local and deterministic. Retrieval
context rows may include lane attribution, but the retrieval implementation is
not replaced by Phase 4.

Embedding provider support is optional:

- `configs/embeddings.yaml` has `enabled: false`.
- Explicit enablement is required for real embedding providers.
- OpenAI embeddings require explicit provider selection and API key env wiring.
- Pytest must not construct a live embedding provider.
- Disabled or unavailable embeddings fall back to token-feature retrieval.

Qdrant remains opt-in. Obj4 did not run a live reindex because the replacement
gate did not justify it.

## Frozen Evidence And V2 Boundary

V2 remains deterministic and evidence-bound. Phase 4 hardens V2 with calibrated
support groups and conflict checks, but it is not a general semantic entailment
engine.

Frozen V2 boundary:

- visible citations and claims remain required;
- unsupported claims are blocked before V4;
- S5 `axiomatic` steps are allowed as algebraic steps, but evidence steps must
  cite visible chunks;
- direction-reversal and wrong-quantity numeric conflicts are blocked by the
  current deterministic rules;
- future semantic entailment must be a separate default-off, replay-first
  objective.

## Frozen Advisory Routing Boundary

Advisory routing defaults:

- `advisory_routing_enabled = false`
- `advisory_intent_routing_enabled = false`
- `advisory_allowed_skills = []`

Activation paths:

- explicit caller/operator skill list through `advisory_skills`,
  `routed_skills`, or `activate_skills`;
- optional intent routing only when both advisory routing and advisory intent
  routing are enabled.

Advisory output rules:

- runs after V4 and before optional V3 reviewer;
- appends chain entries and `skill_results` for selected S6/S7/S8 skills;
- writes `structured_result["advisory_routing"]`;
- does not rewrite `structured_result["answer"]`;
- does not bypass V2/V4 for final user-facing claims.

## Frozen Rendering Boundary

DOCX rendered pagination:

- default `parse_docx(...)` pagination is `logical`;
- `pagination_mode="rendered"` is explicit;
- headless LibreOffice (`soffice`) is optional;
- missing renderer, failed PDF inspection, or missing block-to-page layout map
  falls back to logical pagination with metadata warnings;
- local paths are redacted from rendered-DOCX fallback warnings.

Formula rendering:

- `FormulaRender` is structured metadata only;
- V4 keeps the final answer as markdown/plain text;
- invalid LaTeX/MathML is fail-loud through warnings and
  `status = "invalid_markup"`;
- `status = "renderable"` is a client-attempt contract, not a guaranteed TeX
  render success;
- symbolic proof or CAS checks remain out of Obj11.

## Frozen CAS Decision

Obj12 freezes the Phase-4 CAS decision:

- no mandatory CAS or symbolic proof dependency is added in Phase 4;
- S5 is not a formal proof engine;
- future production symbolic checking, if justified, must be optional,
  default-off, narrow scalar algebra only, timeout/complexity bounded, and
  gated by labeled derivation-equivalence eval cases;
- external CAS services are rejected for the local-first backend freeze
  baseline.

## Frozen Manual And Live Boundaries

Live provider behavior remains manual-only:

- LLM live/capture defaults are false.
- S4/S5 LLM branches default false.
- Provider SDK clients are lazy and must not be constructed in pytest.
- Captured live outputs require redaction and human review before promotion.
- `.env` is the local dotenv source; `.env.local` is not loaded.
- API keys must stay in `.env` or process env, not in chat, logs, fixtures, or
  commits.

S6 live literature search remains manual and injected-client only. Named manual
sources are Semantic Scholar Graph API and arXiv API. S6 external records do
not become final answer evidence unless a future objective defines a
V2-compatible external-evidence contract or ingests them into the local corpus.

## Frozen Verification Gates

The Phase-4 backend freeze gate records:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj13 -p no:cacheprovider
```

Result at freeze: passed, 444 tests; skipped 2; deselected 1; one Qdrant
compatibility warning.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase4_obj13_llm_eval.json
```

Result at freeze: 7 cases, 7 passed, 0 failed, pass rate 1.0, citation
faithfulness pass rate 1.0, unsupported numeric block rate 1.0.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj13_retrieval_eval.json
```

Result at freeze: 4 cases, 3 evidence cases, 1 expected-miss case,
`top_k_recall@5 = 1.0`, `top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_llm_eval.py tests\eval\test_retrieval_eval.py tests\unit\test_tutor_orchestrator.py tests\unit\test_v2_citation_check.py tests\unit\test_v4_style_skill.py tests\unit\test_s5_derivation.py -q -p no:cacheprovider
```

Result at freeze: passed, 77 tests.

Large-corpus and live-provider checks remain operator-run only and are not
required for this freeze.

## Change Rule After Freeze

Any post-freeze change to backend schemas, structured result keys, API response
shape, chain order, routing defaults, retrieval replacement behavior, eval
fixture schema, replay fixture layout, provider request shape, ingestion output
shape, or final-answer authority must:

1. Start in `src/vibration_agent/schemas.py` when a schema is affected.
2. Add a migration note in `docs/phase_4_migrations.md`.
3. Update tests or fixtures that encode the affected shape.
4. Update downstream callers only after tests encode the new contract.
5. Record the change in `docs/phase_4_progress.md`.
6. If the change affects UI or observability assumptions, cite this freeze
   document and explain why the backend contract remains compatible.
