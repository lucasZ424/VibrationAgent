# Architecture Notes

This project implements `vibration_agent`, a personal engineering-oriented vibration-learning and knowledge-base agent. The design source is `docs/vibration_agent_design.md`; this file records the decisions that are already binding for code layout and Phase-0 development.

## Product Positioning

The product target is local personal deployment: one trusted user, local corpus files, localhost CLI/API access, and private engineering notes/exports. This positioning is binding for prioritization: retrieval quality, evidence traceability, bilingual engineering usability, and reproducible local workflows come before multi-user deployment hardening.

If the product moves to shared, remote, or public access, API path safety, authentication, authorization, rate limiting, and persistence readiness become new scope rather than implicit Phase-1 requirements.

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

Phase-0 is limited to four active skills:

- `s1_ingestion`: document ingestion and parsing
- `s2_retrieval`: knowledge-base retrieval
- `s3_qa_summary`: concept explanation, summary, and QA
- `v4_style`: output-style shaping

Reserved but inactive skills are:

- `s4_engineering_analysis`
- `s5_formula_derivation`
- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`

Deferred skills may appear in registries or scope declarations, but they must not be implemented inside S3 or called by the Phase-0 orchestrator.

Phase-0 S3 produces cited sentence selections from retrieved chunks. It deliberately avoids LLM synthesis so it cannot fill evidence gaps with model-world knowledge. Synthesized answer generation is deferred until the model/API integration objective.

Phase-0 V4 is a formatting layer. It can reorder and render upstream S3 content into the engineering answer template, preserve citations, and omit empty sections. It must not invent engineering meaning, assumptions, failure modes, formulas, or next actions; those belong to later deferred skills or future model-backed synthesis.

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
  -> if issues and loop_count < 2: GPT correction, then Opus review again
  -> if issues remain after two review loops: Opus takes ownership
```

The loop limit is binding. After two failed GPT correction loops, continuing to
ask GPT to patch the same issue is considered low-value iteration; ownership
moves to Opus or the task is paused for human clarification.

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

Phase-0 remains GPT-first and keeps S1/S2/S3/V4 as the only active domain chain.
The dual-API supervisor loop is a control-plane design addition. It should not
cause S4-S8 or V1-V3 to be implemented early.

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

Phase 1 is frozen as a Phase-0 implementation. The running chain is:

```text
S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style
```

The user query path is `TutorOrchestrator -> S2 -> S3 -> V4`. S1 is invoked explicitly by ingestion entry points and prepares file-backed knowledge exports for S2.

The frozen contract list, accepted limits, and Phase-2 candidate backlog are recorded in `docs/phase_1_interface_freeze.md`. Deferred skills S4-S8 and V1-V3 remain registry/documentation names only and are not called by the Phase-1 runtime.
