# Phase-3 Interface Freeze

Updated: 2026-06-11

## Freeze Decision

Phase 3 is frozen as the default-off model-backed engineering-assistant
upgrade on top of the Phase-2 local knowledge-base runtime. The deterministic
Phase-2 query path remains the default behavior. Live OpenAI and Anthropic calls
are manual-only, budget-governed, replayable, and forbidden from CI.

The frozen default query path is:

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

S1 remains explicit ingestion. It prepares file-backed knowledge exports for S2
and is invoked through CLI/API/script ingestion entry points, not on every
query.

## Frozen Active Skills

Active and available:

- `s1_ingestion`
- `s2_retrieval`
- `s3_qa_summary`
- `s4_engineering_analysis`
- `s5_formula_derivation`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`
- `v4_style`

Deferred and inactive:

- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`

Phase 3 adds optional LLM-backed branches for S3, S4, and S5, plus an optional
Anthropic supervisor review/correction loop. These branches are not default
runtime behavior. They require explicit feature flags, dependency injection or
manual live/capture wiring, provider keys, and budget allowance.

## Frozen Runtime Contracts

The Phase-2 public schema surface remains active. Phase 3 adds these schema and
runtime contracts:

- `LlmTokenUsage`
- `LlmCostEstimate`
- `S3LlmClaim`
- `S3LlmResponse`
- `S4LlmResponse`
- `S5DerivationStep`
- `S5LlmResponse`
- `LlmRequest`
- `LlmFixture`
- `ReviewReport`
- `ReviewIssue`
- `SupervisorCorrectionResponse`
- `SupervisorLoopResult`

LLM output contracts are structured JSON contracts. Schema parse failure,
provider refusal, insufficient response, replay miss, timeout, budget denial,
or provider exception must fail loud through warnings and fall back to the
deterministic Phase-2 answer path.

The deprecated provider sampling parameter removed during Obj9 is not part of
the frozen Phase-3 request contract. Replay hashes bind prompt version, schema
version, provider, model, `max_tokens`, reasoning/verbosity settings where
applicable, and request body.

## Frozen Supervisor Client Contract

The supervisor loop supports two frozen client calling conventions:

- Legacy injected clients expose `review(query, output, loop_count,
  reviewer_notes) -> ReviewReport` and optionally `correct(query, output,
  review, loop_count, reviewer_notes) -> dict | SkillOutput`.
- Replay/live LLM clients expose `review(**kwargs)` and `correct(**kwargs)` and
  accept the Phase-3 LLM request kwargs, including prompt/schema versions,
  provider model, task id, candidate output, loop count, reviewer notes, and
  review payloads.

The loop chooses the LLM-kwargs convention when the method accepts `**kwargs` or
declares `prompt_version`; otherwise it uses the legacy protocol. Changing these
method signatures or selection rules is a post-freeze contract change.

## Frozen Structured Result Additions

`SkillOutput.structured_result` may now include these Phase-3 additive keys:

- `token_cost`: total model tokens when an LLM-backed skill reports usage.
- `cost`: local cost estimate metadata for the skill that actually called a
  provider.
- `synthesis_mode`: deterministic or LLM-backed synthesis marker. Frozen
  values are `deterministic` and `llm`.
- `s4_analysis`: S4 LLM analysis metadata and warnings when applicable.
- `s5_derivation`: S5 LLM derivation metadata and warnings when applicable.
- `supervisor_corrections`: number of supervisor correction attempts.
- `supervisor_token_cost`: total supervisor model tokens.
- `supervisor_cost`: local supervisor cost estimate metadata.

Existing Phase-2 keys such as `chain`, `skill_results`,
`unsupported_claims`, `citation_check`, `reviewer_notes`,
`supervisor_status`, `supervisor_invocations`, `supervisor_action`, and
`supervisor_issues` remain valid.

Frozen `supervisor_action` values are `finalize`, `gpt_correction`, and
`correction_limit_fallback`.

V2 remains the faithfulness gate for model-generated claims. Unsupported LLM
claims and unsupported LLM derivation evidence steps are blocked before V4
rendering.

## Frozen LLM Defaults

Defaults preserve local deterministic operation:

- `llm.live_enabled: false`
- `llm.capture_enabled: false`
- `llm.s4_enabled: false`
- `llm.s5_enabled: false`
- S3 LLM synthesis has no global YAML enable flag. It remains disabled unless
  request constraints explicitly enable it and the runtime supplies an injected
  replay/live client.
- Provider clients lazy-import SDKs only inside live calls.
- Pytest disables local `.env` loading through `VIBRATION_AGENT_DISABLE_DOTENV`.
- Live provider construction is forbidden under pytest.
- Manual live/capture requires explicit CLI flags plus live/capture config gates.

Frozen provider defaults are configuration values:

- OpenAI: `openai:gpt-5.5`
- Anthropic: `anthropic:claude-opus-4-8`

Operators may override current provider aliases and pricing through YAML or
environment variables without changing the frozen runtime contract.

## Frozen Replay And Capture Layout

Replay fixtures live under `tests/fixtures/llm/` and use:

```json
{
  "metadata": {
    "prompt_version": "...",
    "schema_version": "...",
    "provider": "...",
    "model": "...",
    "max_tokens": 1024,
    "reasoning_effort": "...",
    "text_verbosity": "...",
    "request_body": {},
    "request_hash": "..."
  },
  "response": {}
}
```

Manual capture writes redacted fixtures through `RecordingClient` and
`write_fixture()`. Capture redaction must remove API keys, authorization
tokens, bearer tokens, local absolute paths, and long raw text before fixtures
are promoted from `data\exports\manual_llm_fixtures` into committed replay
fixtures.

## Frozen Manual Entry Points

Replay-only eval:

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase3_eval_scorecard.json
```

Deterministic manual probe:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --difficulty low
```

Manual OpenAI S3/S4/S5 live probe:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --live-openai --user-mode engineering --fixture-dir data\exports\manual_llm_fixtures
```

Manual Anthropic supervisor live probe:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --live-supervisor --difficulty extreme --fixture-dir data\exports\manual_llm_fixtures
```

Single-request capture from prepared kwargs:

```powershell
.\.venv\Scripts\python.exe scripts\llm_capture.py s3_qa_summary --request-json data\exports\manual_s3_request.json --fixture-dir data\exports\manual_llm_fixtures
```

## Frozen Verification Gates

Local deterministic and replay verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-freeze -p no:cacheprovider
```

Replay eval:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_llm_eval.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase3_eval_scorecard.json
```

Manual live verification is local/operator-only and must not be added to CI.
Obj9 recorded successful OpenAI S3/S4/S5 and Anthropic supervisor live runs.

## Change Rule After Freeze

Any post-freeze change to schemas, entry points, chain order, structured result
keys, replay fixture layout, provider request shape, API request/response shape,
or ingestion output shape must:

1. Start in `src/vibration_agent/schemas.py` when a schema is affected.
2. Add a migration note in `docs/phase_3_migrations.md`.
3. Update fixtures/tests that encode the affected shape.
4. Update downstream callers only after tests encode the new contract.
5. Record the change in this freeze document or in the next phase migration
   document.
