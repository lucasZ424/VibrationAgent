# Phase 3 Migrations

Updated: 2026-06-09

## Purpose

This file is the canonical migration log for Phase-3 schema, contract,
configuration, replay-fixture, and LLM-provider changes. Phase 2 froze the local
personal knowledge-base runtime; Phase 3 may extend that runtime, but every
public contract change must be traceable.

## Canonical Change Checklist

For any Phase-3 Obj that changes a frozen schema, API response shape,
structured result key, provider contract, replay-fixture layout, prompt schema,
or downstream caller contract:

1. Update `src/vibration_agent/schemas.py` first when a schema is affected.
2. Add a migration note in this file.
3. Update fixtures and tests that encode the affected shape.
4. Update downstream callers after the contract and tests are in place.
5. Record verification and residual risk in `docs/phase_3_progress.md`.
6. Record review findings in `docs/issue_log_p3/issues_objN.txt`.

Default policy: add fields as optional unless the Obj explicitly approves a
breaking migration. Deprecated fields are not removed until a freeze document
records the removal window.

## LLM And Replay-Specific Checklist

For any Obj that adds or changes live/replay model behavior:

1. Keep the live path default-off.
2. Add or update replay fixtures before adding CI assertions.
3. Include prompt version, schema version, provider, model, temperature,
   `max_tokens`, reasoning/verbosity settings where applicable, and request hash
   in the fixture metadata.
4. Redact API keys, local absolute paths, and long raw source text from captured
   fixtures.
5. Add fallback tests for missing key, timeout, budget denial, schema parse
   failure, refusal, and replay miss when applicable.
6. Confirm CI never constructs a live provider client.

## Migration Log

### Obj0 - Phase-3 execution baseline (2026-06-08)

Documentation-only. No schema, API, structured result, fixture, or runtime
contract changed.

- Added `docs/phase_3_progress.md` as the Phase-3 progress ledger.
- Added `docs/phase_3_migrations.md` as the Phase-3 contract and replay-change
  ledger.
- Added `docs/issue_log_p3/` as the Phase-3 review issue directory.
- README now documents that Phase-3 live provider calls are manual-only and that
  CI remains replay-only/default-off.

Rollback: remove the Obj0 docs and README Phase-3 planning paragraph. No runtime
state depends on this migration.

### Obj1 - Provider client and record/replay baseline (2026-06-08)

Runtime/provider contract additions:

- Added `configs/llm.yaml` as the Phase-3 LLM settings file.
- Expanded `LlmSettings` with `replay_dir`, `capture_enabled`, `live_enabled`,
  token-budget defaults, and `openai` / `anthropic` provider profiles.
- Added `LlmProviderSettings` for provider, model, API-key env name,
  temperature, max tokens, timeout, and provider-specific reasoning/verbosity
  knobs.
- Added `LlmRequest` and `LlmFixture` replay contracts in
  `src/vibration_agent/llm/replay.py`.
- Replay fixture metadata now includes request hash, prompt version, schema
  version, provider, model, temperature, max tokens, reasoning effort,
  text verbosity, and request body.
- Added `ReplayClient`, `RecordingClient`, `ReplayMissError`, and
  `RecordingDisabledError`.
- Added lazy `OpenAIClient` and `AnthropicClient` wrappers. Live construction
  requires an explicit `allow_live=True` manual gate and is forbidden under
  pytest.
- Added `tests/fixtures/llm/` as the replay fixture location.

No frozen Phase-2 API schema, ingestion file shape, query response shape, or
chain order changed.

Rollback: remove `configs/llm.yaml`, the new provider/replay modules, Obj1
tests, and the Obj1 additions to `LlmSettings`; restore `src/vibration_agent/llm/__init__.py`
to exporting only `chat`.

### Obj2 - Token budget and cost estimation (2026-06-08)

Runtime/provider contract additions:

- Added `LlmTokenUsage` and `LlmCostEstimate` schemas.
- Added `src/vibration_agent/llm/budget.py` with `BudgetGuard`,
  `BudgetDeniedError`, `BudgetDecision`, usage parsing, local cost estimation,
  and cost metadata attachment.
- Extended `LlmSettings` with `usd_budget_per_task`.
- Extended `LlmProviderSettings` with local rate fields:
  `input_usd_per_million_tokens`, `output_usd_per_million_tokens`, and
  `cached_input_usd_per_million_tokens`.
- Provider live clients now accept an optional `budget_guard` and reserve budget
  before SDK import/API key checks. A budget denial raises
  `BudgetDeniedError`, allowing callers to fall back before any live provider
  call.
- Provider responses with usage now get `token_cost` and `cost` metadata.
- `configs/llm.yaml` now carries default local pricing estimates and token
  budget defaults.
- Post-review correction: OpenAI defaults were updated from stale `gpt-5.2`
  pricing to `gpt-5.5`; Anthropic Opus 4.8 defaults were updated to the
  published Opus 4.8 price level. Replay redaction was narrowed so token-count
  fields remain available in captured fixtures.

No DB migration was added. Phase-2 migration `002_qa_logs_runtime.sql` already
added `qa_logs.token_cost`, and Obj2 continues to write total tokens through
that existing nullable column. No frozen API request/response shape, ingestion
file shape, or chain order changed.

Rollback: remove `src/vibration_agent/llm/budget.py`, Obj2 tests, the Obj2
schema additions, provider `budget_guard` hooks, and Obj2 additions to
`LlmSettings` / `LlmProviderSettings` / `configs/llm.yaml`.

### Obj3 - V2 LLM-output safety gate pre-hardening (2026-06-08)

Runtime/quality contract additions:

- `v2_citation_check` now applies strict number/unit/symbol support checks when
  `structured_result.synthesis_mode == "llm"`.
- LLM claims containing visible numbers, units, or common engineering symbols
  are blocked unless those exact significant items appear in the cited visible
  evidence chunk text.
- Deterministic mode keeps the Phase-2 lexical/citation behavior and does not
  use the new strict significant-item blocker.
- Added LLM negative fixtures under `tests/fixtures/llm/v2_negative_*.json`.

No frozen API request/response shape, ingestion file shape, database schema, or
chain order changed. Unsupported LLM claims continue to use the existing
`structured_result.unsupported_claims` and `citation_check` surfaces.

Rollback: remove the significant-item checks from
`src/vibration_agent/skills/v2_citation_check.py` and remove the Obj3 V2 tests
and negative fixtures.

### Obj4 - S3 real LLM synthesis (2026-06-09)

Runtime/provider contract additions:

- S3 LLM requests now pass prompt version `s3_qa_summary.v1`, schema version
  `s3.v1`, model settings, timeout, task id, query, mode, language, prompt, and
  evidence through the Obj1 `synthesize()` seam.
- The S3 prompt contract now requires JSON with `status`, `answer`, `claims[]`,
  and optional `warnings`. Each claim must include `text`, `chunk_id`, `doc_id`,
  `pages`, and `evidence_type`.
- LLM S3 `structured_result` remains additive and now may include `cost` when
  provider/replay metadata supplies a local cost estimate. `token_cost` keeps
  storing total tokens.
- S3 no longer drops LLM claims merely because the cited `chunk_id` is not
  visible in S2 evidence. It preserves the claim and citation metadata so V2 can
  block the unsupported output before V4.
- Added S3 LLM response fixtures under `tests/fixtures/llm/s3_*.json` for
  replay-visible, invisible chunk, and fabricated numeric outputs.
- Post-review addition: `S3LlmClaim` and `S3LlmResponse` schemas now formalize
  the S3 LLM response contract. Missing mandatory claim fields fail validation
  and degrade to deterministic S3.
- Post-review addition: `request_from_kwargs()` is the public replay request
  builder for tests/manual fixture preparation that need to mirror convenience
  client methods.
- Post-review correction: S3 preserves invisible-chunk claims for V2 but no
  longer emits pre-V2 `Citation` objects for those invisible chunks.

No database migration was added. The default S3 path remains deterministic while
`s3_enabled` is false or no injected replay/live client is available.

Rollback: remove the Obj4 S3 prompt/request metadata changes, restore S3 to
dropping non-visible LLM claims before V2, remove `S3LlmClaim` /
`S3LlmResponse`, remove `request_from_kwargs()`, remove the Obj4 S3
fixtures/tests, and remove the additive `cost` field from S3 LLM structured
results.

### Obj5 - S4 real engineering analysis (2026-06-09)

Runtime/provider contract additions:

- Added `LlmSettings.s4_enabled`, `configs/llm.yaml` default `s4_enabled:
  false`, and `S4_LLM_ENABLED` environment override.
- Added `S4LlmResponse` as the S4 LLM response contract. S4 LLM output must
  include `answer`, `engineering_meaning`, `premises`, `failure_modes`,
  `next_action`, and cited `claims[]`.
- S4 LLM requests now pass prompt version `s4_engineering_analysis.v1`, schema
  version `s4.v1`, model settings, task id, query, S3 answer, visible S3
  claims, and visible evidence through the Obj1 `analyze_engineering()` seam.
- S4 LLM `structured_result` remains additive and may include `token_cost` and
  `cost` when provider/replay metadata supplies usage and local cost estimates.
- V2 now clears engineering section fields when unsupported claims are blocked,
  preventing V4 from rendering unsupported S4 LLM section prose.
- Added S4 LLM response fixtures under `tests/fixtures/llm/s4_*.json` for
  replay-visible engineering analysis and fabricated threshold output.
- Post-review correction: `S4LlmResponse` now permits clean
  `status="insufficient"` responses while still requiring non-empty engineering
  fields for `ok` responses at runtime.
- Post-review correction: V2's unsupported-output path now rebuilds the checked
  payload from a conservative safe-key allowlist instead of blanking a fixed
  section denylist. This prevents future S4/S5 free-text fields from reaching V4
  after unsupported claims are blocked.

No database migration was added. The default S4 path remains deterministic while
`s4_enabled` is false or no injected replay/live client is available.

Rollback: remove `S4LlmResponse`, remove `LlmSettings.s4_enabled` and the YAML
/ env override, remove the S4 prompt/request metadata changes, restore V2 to
clearing only `answer`, remove Obj5 S4 fixtures/tests, restore the old S4
insufficient/schema behavior, and remove S4 LLM `token_cost` / `cost`
structured result additions.

### Obj6 - S5 real formula derivation and cycle-check hardening (2026-06-09)

Runtime/provider contract additions:

- Added `LlmSettings.s5_enabled`, `configs/llm.yaml` default `s5_enabled:
  false`, and `S5_LLM_ENABLED` environment override.
- Added `S5DerivationStep` and `S5LlmResponse` as the S5 LLM response contract.
  S5 LLM output must include `answer`, `premises`, `minimal_model`,
  `conclusion`, `derivation_steps[]`, and cited `claims[]`.
- S5 LLM requests now pass prompt version `s5_formula_derivation.v1`, schema
  version `s5.v1`, model settings, task id, query, visible S3 claims, and
  visible evidence through the Obj1 `derive_formula()` seam.
- S5 LLM `structured_result` remains additive and may include `token_cost` and
  `cost` when provider/replay metadata supplies usage and local cost estimates.
- S5 LLM derivation steps reuse the existing step validator; invalid source
  types, missing dependencies, self-loops, and multi-node dependency cycles
  reject the LLM response and degrade to deterministic S5.
- V2 now applies LLM-mode significant-item checks to evidence derivation steps,
  while axiomatic steps remain allowed without citations.
- Added S5 LLM response fixtures under `tests/fixtures/llm/s5_*.json` for
  replay-visible multi-step derivation, two-node cycle rejection, and fabricated
  evidence-step numeric output.
- Post-review correction: V2's unsupported-output safe-key allowlist now keeps
  Obj6's actual `s5_derivation` metadata field instead of the unused
  `s5_analysis` placeholder.

No database migration was added. The default S5 path remains deterministic while
`s5_enabled` is false or no injected replay/live client is available.

Rollback: remove `S5DerivationStep` / `S5LlmResponse`, remove
`LlmSettings.s5_enabled` and the YAML / env override, remove the S5
prompt/request metadata changes, restore V2 derivation-step checking to
visibility/source-type only, restore the old V2 safe-key placeholder if needed,
remove Obj6 S5 fixtures/tests, and remove S5 LLM `token_cost` / `cost`
structured result additions.

### Obj7 - Claude supervisor trial and correction executor (2026-06-09)

Runtime/provider contract additions:

- `SupervisorLoop` now accepts an optional injected `correction_client`. If no
  explicit correction client is supplied, the review client is reused when it
  exposes `correct()`.
- Supervisor review/correction LLM requests now bind prompt version, schema
  version, provider/model settings, task id, query, candidate output, loop
  count, reviewer notes, and review issues through the Obj1 replay request
  shape.
- Added `SupervisorCorrectionResponse` as the structured correction response
  contract. An `ok` correction must include either `answer` or
  `structured_result`.
- A rejecting supervisor review now triggers a correction call before the next
  review. The loop still permits at most two correction attempts and falls back
  to the original deterministic answer if approval is not reached.
- Supervisor annotations may now include additive
  `structured_result.supervisor_corrections`,
  `structured_result.supervisor_token_cost`, optional
  `structured_result.supervisor_cost`, and aggregate top-level `token_cost`.
- Added supervisor replay response fixtures under `tests/fixtures/llm/` for
  reject, correction, and approve responses.
- Added `scripts/llm_capture.py` as the manual-only Anthropic capture helper.
  It refuses to run unless live and capture are explicitly enabled and the
  configured Anthropic API key environment variable is present.
- Post-review correction: the recorded correction-loop exhaustion action was
  renamed from `opus_takeover` to `correction_limit_fallback`, because the
  actual runtime behavior is deterministic fallback after the bounded
  correction loop is exhausted.

No database migration was added. Existing `qa_logs.token_cost` and
`qa_logs.supervisor_invocations` fields continue to carry nullable runtime
metadata. The default local runtime still constructs no live Anthropic client.

Rollback: remove `SupervisorCorrectionResponse`, remove the correction-client
branch from `SupervisorLoop`, restore the old repeat-review loop behavior,
restore the previous supervisor action value if compatibility requires it,
remove supervisor replay fixtures/tests, and remove `scripts/llm_capture.py`.
