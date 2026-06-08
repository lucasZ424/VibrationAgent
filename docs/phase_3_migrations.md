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
