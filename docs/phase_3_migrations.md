# Phase 3 Migrations

Updated: 2026-06-08

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
