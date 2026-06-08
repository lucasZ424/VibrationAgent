# Phase-3 Development Order — "Make the scaffolds real (OpenAI)"

Draft: 2026-06-08 · Status: PROPOSED (awaiting sign-off on the open questions at the end)

## North Star

Phase 2 shipped the full chain as **deterministic scaffolds behind injectable LLM
seams**. Phase 3 makes the four model-shaped stages genuinely intelligent using
**OpenAI** — S3 synthesis, S4 engineering analysis, S5 derivation, and the Opus
supervisor (review + correction) — while:

- keeping the product **local-personal** (no new deployment surface);
- keeping **every default deterministic** (the Phase-2 local path and the fast
  suite stay byte-identical when LLM flags are off);
- **capping cost** with a token/cost budget governor;
- guaranteeing **CI never makes a live API call** (record / replay).

The single sentence: *turn S3/S4/S5/supervisor from placeholders into real
OpenAI implementations — safely, cheaply, and CI-replayable.*

## Non-goals (explicitly deferred to Phase 4+)

- Deferred skills S6 literature search / S7 model selection / S8 experiment advice.
- Web UI, k8s, shared/remote, multi-tenant authz, durable rate limiting, full
  observability stack.
- Deep semantic entailment beyond the **minimal** V2 hardening needed for safety.
- LaTeX/MathML generation and full symbolic proof.
- Switching embeddings/retrieval to OpenAI (retrieval stays as-is unless the
  Phase-3 eval shows it is the bottleneck — see Open Question 3).

## Design invariants (apply to EVERY objective)

1. **Seam + deterministic fallback.** Every live path degrades to the Phase-2
   deterministic output on error, timeout, missing key, or budget exhaustion.
   Answering never breaks; the supervisor/V2/V3 fail-safe posture is preserved.
2. **Default-off.** `s3_enabled`, `s4_llm_enabled`, `s5_llm_enabled`,
   `supervisor_llm_enabled` all default `false`. Local deterministic operation
   and the fast suite are unchanged.
3. **Additive + schemas-first.** Any contract change starts in `schemas.py`, gets
   a note in `docs/phase_3_migrations.md`, then tests, then callers (the Phase-2
   change rule carries forward).
4. **Record/replay is CI law.** No live OpenAI call in any pytest run. Live calls
   happen ONLY in the manual probe / capture tool, which write response fixtures
   that CI replays. A pytest autouse guard hard-fails the suite if a live client
   is ever constructed.
5. **Budget-governed.** Every live call passes through `BudgetGuard` (per-task +
   per-session token/cost ceilings, configurable). Exceeding fails loud (warning
   + degrade), never silently truncates.
6. **Cost observability.** Token usage + USD estimate are attached to
   `SkillOutput` and persisted to `qa_logs.token_cost` (currently always null).
7. **Secrets via env only.** `OPENAI_API_KEY` from env; non-secret knobs (model,
   temperature, max_tokens, timeout, budgets, prices) in `configs/llm.yaml` +
   `LlmSettings`. Never commit a key or a captured response containing one.
8. **Structured outputs.** Use OpenAI structured outputs (`response_format`
   json_schema) so S3/S4/S5 emit exactly the `claims`/`derivation_steps` schema
   V2 consumes — removes brittle parsing and tightens the V2 gate.

## Objectives (recommended order)

Dependency spine: **P3-1 (client+replay) → P3-2 (budget) → P3-3 (S3) → P3-4 (V2
hardening) → P3-5 (S4) → P3-6 (S5) → P3-7 (supervisor) → P3-8 (eval) → P3-9
(manual/cost) → P3-10 (freeze).** Each is independently gated and logged to
`docs/issue_log_p3/issues_objN.txt` under the existing supervisor-review workflow.

### P3-1. OpenAI provider client + record/replay harness
- Files: `src/vibration_agent/llm/openai_client.py` (new), `.../llm/replay.py` (new),
  `.../llm/__init__.py`, `configs/llm.yaml`, `config.py` (LlmSettings),
  `tests/unit/test_openai_client.py`, `tests/fixtures/llm/` (captured responses).
- Feature blocks:
  - `OpenAIClient` implementing the **existing** seams: S3 synth protocol
    (`.synthesize(**kwargs) -> dict`) and supervisor protocol
    (`.review(...) -> ReviewReport`). The `openai` SDK is imported **lazily inside
    methods** (no top-level import), matching the qdrant/psycopg pattern.
  - `ReplayClient` serves responses from `tests/fixtures/llm/<hash>.json` keyed by
    a stable hash of the request; `RecordingClient` calls live + writes the
    fixture (redacting secrets). CI uses `ReplayClient` only.
  - A pytest **autouse guard** that raises if a live `OpenAIClient` is built during
    the suite (enforces invariant 4).
  - `LlmSettings`: `provider`, `model`, `temperature`, `max_tokens`,
    `request_timeout`, `base_url`, budget fields; env overrides
    (`OPENAI_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, …). `s3_enabled` stays false.
- Acceptance:
  - Replay returns the captured response for a known request hash; an unknown hash
    raises explicitly (no silent live call).
  - The live-client guard makes the suite fail if any test constructs a real client.
  - No top-level `import openai` anywhere (grep-asserted); fast CI installs without
    the `openai` extra and stays green.
  - Unit tests: request→hash determinism, replay hit, replay miss, recording writes
    a **redacted** fixture (no key).

### P3-2. Token-budget governor + cost accounting
- Files: `src/vibration_agent/llm/budget.py` (new), `config.py`,
  `storage/qa_logs.py` + a `db/postgres/migrations/004_*.sql` (optional
  `tokens_in`/`tokens_out`; `token_cost` already exists), `schemas.py` (optional
  cost fields), `tests/unit/test_budget.py`.
- Feature blocks:
  - `BudgetGuard(per_task_tokens, per_session_tokens, usd_ceiling?)` — each call
    checks-and-reserves; a would-exceed returns a deny → caller degrades to
    deterministic + warning (`"LLM budget exhausted; deterministic fallback"`).
  - Cost accounting from OpenAI `usage` (prompt/completion tokens) → `token_cost`
    + USD estimate via a configurable price table; attached to
    `SkillOutput.structured_result.cost` and `qa_logs`.
  - Session-scoped accumulation keyed by task/session id.
- Acceptance:
  - A call that would exceed the per-task budget is denied and the orchestrator
    returns the deterministic answer with the budget warning (test).
  - `token_cost` populated in qa_logs when an LLM path ran; null otherwise (test).
  - Budgets configurable via env/yaml; seeded defaults 4000/task, 30000/session.

### P3-3. S3 real LLM synthesis
- Files: `skills/s3_qa_summary.py`, `prompts/skills/s3_qa_summary.md` (versioned),
  `agent_skills/s3_qa_summary/SKILL.md`, `tests/unit/test_s3_llm_synthesis.py`,
  `tests/fixtures/llm/s3_*.json`.
- Feature blocks:
  - When `s3_enabled` and a client is wired, S3 calls OpenAI with structured
    output `{answer, claims:[{text,chunk_id,doc_id,pages,evidence_type}]}`
    constrained to cite **only** chunk_ids present in `s2.retrieval_context`;
    `synthesis_mode="llm"`. Prompt enforces evidence-binding, no fabricated
    numbers/units, and language match (zh/en).
  - Deterministic fallback on error/budget/empty; output still flows through V2.
- Acceptance:
  - Recorded response citing only visible chunks → status ok, visible chunk_ids,
    passes V2 (replay test).
  - Recorded response citing a **non-visible chunk or fabricated number** → V2
    blocks it, conclusion stripped (the load-bearing safety test).
  - `s3_enabled=false` → byte-identical deterministic output (regression).
  - No live call in the suite.

### P3-4. V2 faithfulness hardening for LLM output  *(safety prerequisite — see Open Q4)*
- Files: `skills/v2_citation_check.py`, `tests/unit/test_v2_citation_check.py`.
- Rationale: once S3 is a real model, V2 becomes the only hallucination gate. This
  is **minimal** hardening, not full semantic entailment (which stays deferred).
- Feature blocks:
  - For `synthesis_mode=="llm"`: require each claim to (a) carry a visible
    chunk_id AND (b) have its salient numerics/units/symbols appear in the cited
    chunk text (extend the existing lexical overlap with a numeric/unit
    cross-check). Unsupported → blocked as today.
  - Deterministic-mode behavior unchanged (no regression to S3/S4/S5 deterministic).
- Acceptance:
  - LLM claim with a number absent from the cited chunk → blocked (test).
  - All existing Phase-2 V2 tests stay green.
  - Strictness is a flag; default strict for llm mode only.

### P3-5. S4 real engineering analysis (LLM)
- Files: `skills/s4_engineering_analysis.py`, prompt + `SKILL.md`, tests, fixtures.
- Feature blocks: real impact / typical-scenario / countermeasure reasoning
  grounded in cited claims, structured into the existing
  `engineering_meaning/premises/failure_modes/next_action` keys; `s4_llm_enabled`
  default off; deterministic framing remains the fallback; V2-gated.
- Acceptance: recorded response yields richer engineering sections that still pass
  V2; a fabricated-threshold response is blocked; mode-mismatch / insufficient
  evidence still skip; deterministic fallback intact.

### P3-6. S5 real formula derivation (LLM) + cycle-check hardening
- Files: `skills/s5_formula_derivation.py`, prompt + `SKILL.md`, tests, fixtures.
- Feature blocks: real premise→steps→conclusion, each step typed
  `evidence|axiomatic`, structured output; `s5_llm_enabled` default off;
  deterministic fallback. **Fold in the Phase-2 Obj15 M1 carryforward**: replace
  the self-loop-only validator with a real DAG / topological cycle check (+ a
  2-node-cycle test). LaTeX/symbolic proof stays deferred.
- Acceptance: recorded multi-step derivation passes V2 axiomatic handling; a
  genuine 2-node cycle is now rejected (test); insufficient / mode-mismatch skip;
  deterministic fallback intact.

### P3-7. Supervisor real reviewer + GPT correction executor
- Files: `agent/supervisor.py`, `prompts/orchestrator.md`, tests, fixtures.
- Feature blocks: wire OpenAI as the supervisor reviewer (`.review`) AND implement
  the **real `GPT_CORRECTION` executor** that actually rewrites the candidate
  (Phase-2 left it structural, re-reviewing the same candidate). Keep the bounded
  loop (max 2) and full fail-safe (no client/budget/exception → deterministic).
  `supervisor_llm_enabled` default off; only runs for extreme / V3-flagged tasks.
- Acceptance: recorded review→reject→correct→approve path improves the candidate
  and finalizes (test); budget/exception → fallback (test); normal queries never
  call it (test); supervisor_status/invocations/cost recorded.

### P3-8. Golden-output eval harness + CI replay regression gate
- Files: `tests/eval/` (new) with a curated set (zh + en, PDF + DOCX evidence) and
  recorded responses; `scripts/llm_eval.py`; nightly CI step.
- Feature blocks: replay-based eval asserting per case — citation faithfulness (no
  claim without visible support), no fabricated numerics, correct scope/status,
  reviewer_notes presence; emits a faithfulness scorecard. Runs in nightly via
  replay (no live calls).
- Acceptance: eval set green on recorded fixtures; a deliberately-hallucinated
  fixture is **caught** (negative case); scorecard emitted as a nightly artifact.

### P3-9. Manual live-validation lane + cost report
- Files: `scripts/manual_e2e.py` (extend), `scripts/llm_capture.py` (new), README,
  docs.
- Feature blocks: a local, env+budget-gated mode that makes **real** OpenAI calls,
  captures responses as fixtures (feeding P3-3/5/6/7/8), and prints a token/cost
  report. Stays out of CI — the only place live calls happen.
- Acceptance: with `OPENAI_API_KEY` set, the probe runs a real call within budget,
  writes a redacted fixture, prints cost; without the key it falls back to replay;
  documented in the README Testing section.

### P3-10. Phase-3 interface freeze + Phase-4 planning
- Files: `docs/phase_3_interface_freeze.md`, `docs/phase_3_deferred_and_polish_audit.md`,
  `docs/phase_3_migrations.md`, `schemas.py` (if needed), README, architecture.
- Feature blocks: freeze the LLM client contracts, structured-output schemas, cost
  fields, budget config, and replay-fixture layout; record residual risks; list
  Phase-4 candidates (S6/S7/S8, UI, deploy/observability, deep entailment, OpenAI
  embeddings, LaTeX/symbolic). Same discipline as Phase-2 Obj19.

## Verification strategy

- **Fast CI**: unchanged deterministic suite + replay-only LLM tests; no live
  calls; under 5 minutes.
- **Nightly**: full suite + the replay eval scorecard artifact; still no live calls.
- **Local manual**: `scripts/manual_e2e.py` / `scripts/llm_capture.py` for real
  OpenAI within budget.
- **Per-objective gate**: full suite green + the objective's recorded-response
  tests + the deterministic-fallback regression, reviewed and logged to
  `docs/issue_log_p3/issues_objN.txt`.

## Cross-cutting risks & mitigations

- Hallucinated citations/numbers → P3-4 V2 hardening + P3-8 eval negative cases
  (this is why V2 hardening is sequenced immediately after S3).
- Cost blowups → `BudgetGuard` (P3-2) + never-in-CI.
- CI non-determinism → record/replay + live-client guard (P3-1).
- Silent quality regressions / prompt drift → golden eval (P3-8) in nightly.
- Schema churn → schemas-first change rule + `phase_3_migrations.md`.

## Assumptions made (correct me)

- **Models**: a cost-efficient model for S3/S4/S5 (e.g. `gpt-4o-mini`) and a
  stronger model for the supervisor (e.g. `gpt-4o` / an o-series), both
  configurable. *(Open Q1)*
- **Budgets**: seeded at the house-rule values (4k/task, 30k/session),
  configurable. *(Open Q2)*
- **Embeddings/Qdrant unchanged** this phase. *(Open Q3)*
- **Local-personal = single user**; `OPENAI_API_KEY` in local env only; no new
  network exposure.
- **P3-4 (minimal V2 hardening) is in-scope** as a safety prerequisite even though
  "deepen quality" was not the chosen theme. *(Open Q4 — cut it for a pure
  scaffold-swap if you prefer.)*

## Open questions for sign-off

1. Which OpenAI models for (a) S3/S4/S5 and (b) the supervisor? Any **USD** ceiling
   per query/session on top of the token budget?
2. Keep the house-rule token budgets (4k/task, 30k/session) or set project numbers?
3. In-scope to also move embeddings to OpenAI (better recall), or leave the
   sentence-transformers/Qdrant lane as-is for Phase 3?
4. Keep the minimal V2 faithfulness hardening (P3-4) inside Phase 3, or split it
   into a separate quality phase and ship live S3 on the existing lexical V2?
