# Architecture Notes

This project implements `vibration_agent`, a personal engineering-oriented vibration-learning and knowledge-base agent. The design source is `docs/vibration_agent_design.md`; this file records the decisions that are already binding for code layout, Phase-0 runtime, frozen Phase-2/Phase-4 development, and the frozen Phase-5 reliability baseline.

## Product Positioning

The product target is local personal deployment: one trusted user, local corpus files, localhost CLI/API access, and private engineering notes/exports. This positioning is binding: retrieval quality, evidence traceability, bilingual engineering usability, and reproducible local workflows are the product boundary.

Shared, remote, public, and multi-user deployment are deferred indefinitely. They are not Phase-5 candidates and no planned objective may activate them through a revisit gate. Reopening that scope requires an explicit user-directed revision of `docs/vibration_agent_design.md` before a new phase is designed.

Phase 4 established that boundary. The later product-discipline decision makes
the deferral indefinite and supersedes the old future-objective revisit path in
`docs/phase_4_remote_shared_hardening_decision.md`.

## Layer To Code Map

| Layer | Code Location |
| --- | --- |
| Interaction | `src/vibration_agent/orchestrator/` and `apps/*` |
| Task skills | `src/vibration_agent/skills/` |
| Quality control | `src/vibration_agent/quality/` and `src/vibration_agent/skills/v4_style.py` |
| Knowledge | `src/vibration_agent/knowledge/` and `taxonomy/` |
| Data | `src/vibration_agent/storage/`, `db/`, and `data/` |

## Src Layout

The importable package lives under `src/vibration_agent`. Runtime entry points under `apps/*` stay thin and delegate to the library. This keeps package imports stable and prevents app runners from becoming hidden business logic.

## OCR Ownership

OCR belongs under `src/vibration_agent/ingestion/ocr/` because OCR is only one branch of document ingestion. It should not become an independent top-level feature. The ingestion pipeline owns routing between native PDF parsing, PaddleOCR, and Tesseract fallback.

## Phase-0 Scope

Phase-2 current query runtime has nine active/available skills:

- `s1_ingestion`: document ingestion and parsing
- `s2_retrieval`: knowledge-base retrieval
- `s3_qa_summary`: concept explanation, summary, and QA
- `s4_engineering_analysis`: optional engineering framing after S3 and before V2
- `s5_formula_derivation`: optional evidence-bound formula derivation after S3 and before V2
- `v1_term_symbol_unit_normalizer`: optional term/symbol/unit normalization at S3 input and V4 output
- `v2_citation_check`: deterministic citation and visible-evidence guard
- `v4_style`: output-style shaping after V2 filtering
- `v3_reviewer`: advisory reviewer after V4, executed only for extreme tasks

Reserved but inactive skills are:

- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`

Deferred skills may appear in registries or scope declarations, but they must not be implemented inside S3 or called by the Phase-0 orchestrator.

Phase-0 S3 produces cited sentence selections from retrieved chunks by default.
Phase 3 added an optional default-off LLM synthesis branch, but it still
requires retrieved evidence and structured citations before V2/V4 consume it.

Phase-2 S4 is a deterministic engineering analysis layer. It runs only for
`user_mode="engineering"` and enough cited evidence, adds engineering meaning,
premises, caveats, and next actions from existing S3 claims, and then hands the
result to V2. S4 must not invent numeric values or operating conditions.
Phase 3 added an optional default-off LLM S4 analysis path. V2 remains the gate
before any S4 prose can reach V4.

Phase-2 S5 is a deterministic formula derivation layer. It runs only for
`user_mode="derivation"` and enough cited evidence, emits premise -> steps ->
conclusion, and allows only visible evidence steps plus `axiomatic` math steps.
S5 must not invent formulas, units, parameters, or measured values.
Phase 3 added an optional default-off LLM S5 derivation path. Deep symbolic
algebra and LaTeX/MathML generation remain future capabilities.

Phase-0 V2 is a deterministic quality layer. It checks S3/S4/S5 claims against chunks visible to S2, removes unsupported claims, allows S5 `axiomatic` steps, and lets V4 render only checked content.

Phase-0 V1 is an optional deterministic normalization layer. It can normalize
in-memory S2 retrieval context before S3 and normalize the final V4 answer, but
both call points are independently configurable and V1 is not a chain step. The
safer default is input normalization off and output normalization on.

Phase-0 V4 is a formatting layer. It can reorder and render upstream V2/S3/S4/S5 content into the engineering answer template, preserve citations, and omit empty sections. It must not invent engineering meaning, assumptions, failure modes, formulas, or next actions; those belong to upstream skills or future model-backed synthesis.

Phase-2 V3 is an advisory reviewer. It runs after V4 only when routing marks
the query as `extreme`, checks conclusion/evidence/limits completeness, topic
relevance, and overclaiming risk, and writes `reviewer_notes`. V3
`insufficient` does not block the V4 answer.

Phase-2 Obj13 added a fail-safe supervisor entry point. Phase 3 wired a
default-off Anthropic review/correction lane for manual live/replay validation.
The supervisor is
triggered only for `extreme` routed queries or when reviewer notes require
escalation. If no supervisor client is available, or if the supervisor loop
does not approve within two review passes, the system returns the deterministic
V4 answer and marks `structured_result.supervisor_status = "fallback"`.
Non-supervised answers carry `supervisor_status = "not_triggered"` when the full
answer chain reaches V4.

The supervisor entry point is dependency-injected. Live Anthropic construction
is explicit manual/capture behavior and is forbidden under pytest. Without an
injected `SupervisorClient`, extreme answers are deliberately marked as
supervisor `fallback` rather than silently pretending that Opus reviewed them.

## Development Order Rule

Targets 1-3 establish the control plane for later work:

1. Scope and boundary are documented before new capability work.
2. `src/vibration_agent/schemas.py` is the single source of truth for skill I/O, ingestion objects, retrieval hits, and file export contracts.
3. `src/vibration_agent/config.py` is the single entry point for runtime settings. Business modules should not read `configs/*.yaml` or environment variables directly.

Emergency scripts under `scripts/` can be used as migration references, but stable behavior should move into `src/vibration_agent/` modules.

## Model Orchestration And Agent-Owned Skills

Detailed control-plane design is also recorded in `docs/model_orchestration.md`.

### Binding Decision

The agent uses a vendor-neutral skill system owned by this project. Model vendors
are reasoning/execution backends, not the source of truth for skills.

Two layers must remain separate:

- `agent_skills/<skill_id>/SKILL.md`: agent-facing skill package. This layer
  defines when a skill should be used, required inputs, allowed outputs, failure
  behavior, and references. It is intended to be readable by any capable model.
- `src/vibration_agent/skills/*.py`: deterministic runtime implementation. This
  layer executes stable Python code and returns `SkillInput` / `SkillOutput`
  compatible results.

Claude-native Skills and OpenAI tools are integration mechanisms, not project
architecture. The project should be able to expose the same skill package to
OpenAI, Anthropic, or a local orchestrator without rewriting the domain logic.

### Dual-API Routing Policy

The default model path is GPT-first. Low, medium, and high difficulty tasks are
handled end-to-end by the GPT model path unless a stakeholder-defined routing
policy explicitly marks the task as extreme.

Opus is reserved for extreme tasks because of its higher latency and token cost.
It is not part of the default path for ordinary high-complexity work.

The difficulty router must be policy-driven, not left to unrestricted model
self-judgment. A model may produce a routing recommendation, but the final
thresholds should come from project configuration and stakeholder-defined rules.

Recommended difficulty actions:

| Difficulty | Default owner | Notes |
| --- | --- | --- |
| low | GPT | Simple QA, small edits, narrow checks. |
| medium | GPT | Normal implementation and documentation work. |
| high | GPT | Complex but bounded engineering tasks; optional local review only. |
| extreme | Opus-supervised loop | Architecture, math, safety, schema, or persistent failure risk. |

### Extreme Task Loop

Extreme tasks use a senior-supervisor loop:

```text
User task
  -> policy router marks task as extreme
  -> Claude Opus: framework design, decomposition, risk definition
  -> GPT: implementation, tests, candidate answer
  -> Claude Opus: senior supervisor review
  -> if no issues: final answer
  -> if issues and loop_count < 2: correction executor, then Opus review again
  -> if issues remain after two review loops: deterministic fallback with warning
```

The loop limit is binding. After two failed correction loops, continuing to
patch the same issue is considered low-value iteration; the runtime returns the
original deterministic answer with `correction_limit_fallback` metadata and a
warning.

### Extreme Triggers

The exact triggers should live in configuration later, but the design baseline is:

- cross-cutting architecture changes affecting multiple layers or contracts
- mathematical derivation or engineering reasoning where a wrong conclusion has
  high downstream cost
- schema, database, retrieval, or citation-contract changes with long-term
  compatibility impact
- tasks explicitly marked by the stakeholder as extreme
- repeated failure: the same issue remains after two GPT correction attempts
- review-sensitive work where a senior framework critique is more valuable than
  fast execution

Non-triggers:

- ordinary high-complexity implementation that is well scoped
- adding tests for known behavior
- normal refactors with clear acceptance criteria
- routine documentation updates

### Phase-0 Implication

Phase-0 remains GPT-first and keeps S1/S2/S3/V2/V4 as the active domain chain,
with V1 as an optional normalization layer outside the chain.
The dual-API supervisor loop is a control-plane design addition. It should not
cause S4-S8 or V3 to be implemented early.

Before implementing the dual-API runtime, add a small control-plane objective:

```text
Obj11.5 - Agent-owned skill registry and model routing design
```

Acceptance should require:

- a vendor-neutral `agent_skills/` package layout
- a difficulty enum and stakeholder-owned routing policy
- a model registry abstraction for GPT and Opus clients
- an extreme-task supervisor-loop schema
- no mandatory Opus call for low, medium, or high tasks

## Phase-1 Interface Freeze

Phase 1 was frozen with this baseline runtime chain:

```text
S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style
```

As of Phase-2 Obj15, the current user query path is `TutorOrchestrator -> S2 -> S3 -> optional S4/S5 -> V2 -> V4`, with optional V1 normalization before S3 and after V4, V3 reviewer after V4 for extreme tasks only, and a fail-safe supervisor handoff for extreme/reviewer-flagged answers. S1 is invoked explicitly by ingestion entry points and prepares file-backed knowledge exports for S2.

The Phase-1 compatibility baseline is recorded in
`docs/phase_1_interface_freeze.md`. The Phase-2 frozen contract list, accepted
limits, and Phase-3 candidate backlog are recorded in
`docs/phase_2_interface_freeze.md` and
`docs/phase_2_deferred_and_polish_audit.md`. Deferred skills S6-S8 remain
registry/documentation names only and are not called by the current runtime.

## Phase-2 Development Boundary

The approved Phase-2 development order is recorded in `docs/phase_2_development_order.md`. Phase 2 keeps the Phase-1 frozen interfaces as the migration base while moving the product toward a locally usable personal knowledge-base Agent.

At architecture level, Phase 2 activates three kinds of work: local-corpus usability, real retrieval/storage, and citation-guarded reasoning/quality layers. Later product surfaces remain outside Phase 2 unless a new boundary decision changes the scope.

Phase-2 execution is Obj-based. Each Obj must define verification, preserve a fallback path for external dependencies, update progress notes, and pass review before the next Obj starts. The binding fallback and feature-flag rules are recorded under "执行模型与风险控制" in `docs/phase_2_development_order.md`. Schema or API contract changes follow the canonical process in `docs/phase_2_migrations.md`; until a specific Obj completes that process, the Phase-1 runtime chain remains the stable baseline.

As of Obj19, Phase 2 is frozen. The Phase-2 compatibility baseline remains
recorded in `docs/phase_2_interface_freeze.md`.

## Phase-3 Interface Freeze

As of Obj10, Phase 3 is frozen as the default-off model-backed
engineering-assistant upgrade on top of the Phase-2 runtime. The frozen
contract list, replay/capture layout, manual live lane, accepted residual risks,
and Phase-4 candidate backlog are recorded in
`docs/phase_3_interface_freeze.md` and
`docs/phase_3_deferred_and_polish_audit.md`.

Future schema/API/chain/replay/provider-contract changes must follow
`docs/phase_3_interface_freeze.md` and `docs/phase_3_migrations.md`.

## Phase-4 Interface Freeze

Phase 4 is frozen in `docs/phase_4_interface_freeze.md` as the local-first,
single-user engineering-assistant baseline for real local iteration.

Phase-4 changes that affect schemas, provider requests, replay hashes,
structured-result keys, chain order, retrieval contracts, API shapes, or
ingestion outputs must be recorded in `docs/phase_4_migrations.md` before
callers are updated.

The final Phase-4 freeze includes the Obj13 backend freeze, Obj14 read-only
operator UI, Obj15 local-first observability, and Obj16 remote/shared hardening
defer decision. Accepted residual risks and deferred work are recorded in
`docs/phase_4_deferred_and_polish_audit.md`; the successor local reliability
boundary is defined in `docs/phase_5_scope.md`.

The default answer path remains V2/V4-bound. S6/S7/S8 are default-off advisory
handoff skills, Obj11 formula rendering is metadata only, Obj12 keeps symbolic
proof/CAS deferred, and remote/shared hardening remains indefinitely out of
scope under the binding product discipline.

## Phase-5 Backend / Eval Freeze

As of Obj9, Phase 5 has frozen the local RAG reliability backend/eval subset in
`docs/phase_5_backend_interface_freeze.md`. The frozen backend baseline uses the
4,436-chunk local corpus, multilingual MiniLM embeddings, hybrid BM25+dense
retrieval with RRF fusion, deterministic S3 by default, V2 as the hard
faithfulness gate, and `tests/fixtures/rag_qa/post_r3_baseline.json` as the
standing real-question regression net.

Phase-5 changes after Obj9 must not alter retrieval lanes, embedding/corpus
identity, answer-quality gate semantics, provider defaults, replay/live
contracts, or the Obj1 baseline without a successor migration and updated freeze
evidence. GPT synthesis and Opus supervisor lanes remain default-off and
replay-first; they are validated lanes, not the default production authority.

## Phase-5 Final Freeze

As of Obj10, Phase 5 is closed in `docs/phase_5_interface_freeze.md`. The final
freeze incorporates the backend/eval freeze, records the local API/operator
surface, accepted residual risks, and the rule that future runtime authority,
retrieval, scoring, provider, corpus, UI/API, or deployment-boundary changes
belong to a successor phase.
