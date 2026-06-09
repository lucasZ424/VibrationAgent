# Phase 3 Progress

Updated: 2026-06-09

## Execution Model

Phase 3 proceeds one Obj at a time. Each Obj must preserve the Phase-2
deterministic default path, keep live provider calls out of CI, verify replay
and fallback behavior, and pass review before the next Obj starts.

Every Obj must record:

1. Implementation notes.
2. Verification commands and results.
3. Review issues and fixes in `docs/issue_log_p3/issues_objN.txt`.
4. Residual risks.
5. Whether the next Obj gate is cleared.

## Objective Status

0. Phase-3 execution baseline: done
1. Provider client and record/replay baseline: done
2. Token budget and cost estimation: done
3. V2 LLM-output safety gate pre-hardening: done
4. S3 real LLM synthesis: done
5. S4 real engineering analysis: done
6. S5 real formula derivation and cycle-check hardening: done
7. Claude latest / Claude Opus 4.8 supervisor trial and correction executor: done
8. Golden-output eval minimum set and replay regression gate: pending
9. Manual live validation and capture lane: pending
10. Phase-3 interface freeze and Phase-4 planning: pending

## Obj0 Notes

- `docs/phase_3_development_order.md` is the approved Phase-3 development order.
- Phase 3 keeps the Phase-2 deterministic chain as the default behavior.
- Live OpenAI and Anthropic calls are manual-only and must not run in CI.
- OpenAI S3/S4/S5 and Claude supervisor paths remain default-off until their
  dedicated objectives add provider clients, replay fixtures, budget guards, and
  live-call guards.
- `docs/phase_3_migrations.md` is now the canonical log for Phase-3 schema,
  contract, replay-fixture, and LLM-settings changes.
- `docs/issue_log_p3/` is the Phase-3 issue-log directory.

## Obj0 Verification

- Verified command: `git diff --check -- docs\phase_3_development_order.md`
- Result: passed.
- Verified command: `git diff --check -- README.md docs\phase_3_progress.md docs\phase_3_migrations.md docs\issue_log_p3\issues_obj0.txt`
- Result: passed with README CRLF/LF normalization warning only.
- Code tests: not run; Obj0 is documentation-only.

## Obj0 Residual Risk

- Phase-3 boundary enforcement is currently document/process based. Obj1 must add
  automated live-call guards before any provider client can be used in tests.
- The concrete OpenAI and Anthropic model ids remain configuration values and must
  be resolved against current official provider docs during implementation.

## Obj0 Next Obj Gate

- Local documentation checks cleared. Obj1 may start after user review of Obj0.

## Obj1 Notes

- Added `configs/llm.yaml` and expanded `LlmSettings` with replay/capture/live
  gates, per-task/session token budget defaults, and provider profiles.
- Added `src/vibration_agent/llm/replay.py` with stable request hashing,
  fixture metadata, replay miss failures, manual-only recording, and fixture
  redaction.
- Added lazy OpenAI and Anthropic provider wrappers. SDK imports occur only in
  live `complete()` calls; importing the modules does not require either SDK.
- OpenAI exposes S3/S4/S5 structured-output seams through `synthesize`,
  `analyze_engineering`, and `derive_formula`.
- Anthropic exposes supervisor review/correction seams through `review` and
  `correct`.
- Added a pytest guard via `tests/conftest.py`; constructing live provider
  clients during pytest fails even when `allow_live=True`.
- Provider model ids remain configuration values. Obj1/Obj2 post-review defaults
  are `gpt-5.5` and `claude-opus-4-8`, based on current official provider docs
  checked during implementation and review.

## Obj1 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_anthropic_client.py -q -p no:cacheprovider`
- Result: passed, 14 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_anthropic_client.py tests\unit\test_s3_llm_synthesis.py tests\unit\test_supervisor_loop.py -q -p no:cacheprovider`
- Result: passed, 28 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_llm_synthesis.py tests\unit\test_supervisor_loop.py -q -p no:cacheprovider`
- Result: passed, 12 tests.
- Attempted command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=data\exports\pytest-p3-obj1-fast -p no:cacheprovider`
- Result: environment-blocked by Windows sandbox `PermissionError` during
  pytest temp cleanup at `data\exports\pytest-p3-obj1-fast`.
- Attempted unsandboxed retry of the same broader fast gate with
  `--basetemp=data\exports\pytest-p3-obj1-fast-escalated`.
- Result: escalation approval timed out twice, so the broader fast gate was not
  completed.
- Post-sandbox-fix verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=data\exports\pytest-p3-obj1-fast -p no:cacheprovider`
- Result: passed, 308 tests; 13 deselected.
- Post-sandbox-fix verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-nonlarge-safe -p no:cacheprovider`
- Result: passed, 318 tests; 2 skipped, 1 deselected, 1 qdrant compatibility
  warning.

## Obj1 Residual Risk

- Provider live-call methods are scaffolds and remain unexercised by CI; live
  validation is intentionally deferred to the manual capture lane.
- Replay fixtures record a redacted request body plus the original request hash.
  The hash binds the unredacted runtime request; fixture replay still validates
  the stored hash but does not recompute it from redacted metadata.
- The local pytest/tempfile ACL issue was traced to Python/pytest and stdlib
  temp helpers creating Windows temp directories with restrictive permissions
  that the sandbox token could not later enumerate or clean.
- Tests now redirect pytest `tmp_path` and stdlib `tempfile` roots to
  `data\exports\.pytest_tmp_safe`, clean that run directory at session finish,
  and avoid global user Temp pollution.
- Replay tests still use ignored workspace-local scratch files for fixture
  writing, but the general pytest `tmp_path` path is now verified by the full
  non-large suite.

## Obj1 Post-Review Fixes

- Fixed provider package import coupling by changing `src/vibration_agent/llm/__init__.py`
  to lazy re-exports through `__getattr__`.
- Moved live-provider pytest guard and `LiveProviderDisabledError` into shared
  `src/vibration_agent/llm/_guards.py`.
- Added `ReplayClient.correct()` for supervisor correction replay symmetry.
- Changed replay convenience default model from `openai:unknown` to
  `unknown:unknown`.
- Added a sandbox-local pytest/tempfile temp-root patch in `tests/conftest.py`.
- Removed unnecessary external `TemporaryDirectory()` creation from PaddleOCR
  and Tesseract paths when an `image_dir` is already supplied.

## Obj1 Next Obj Gate

- Obj1 focused replay/provider tests and nearby seam regressions passed.
- Full non-large suite passed after the sandbox temp-root fix.
- Obj2 may start after user review of Obj1.

## Obj2 Notes

- Added `src/vibration_agent/llm/budget.py` with `BudgetGuard`,
  `BudgetDeniedError`, usage parsing, prompt-token estimation, and local cost
  estimation.
- Added additive `LlmTokenUsage` and `LlmCostEstimate` schemas.
- Extended `configs/llm.yaml` and `LlmSettings` with token budgets, optional
  per-task USD ceiling, and provider token-rate settings.
- Provider clients now reserve budget before SDK import/API key checks and
  attach `token_cost` plus local `cost` metadata when provider usage is present.
- Deterministic paths still leave `token_cost` null unless an LLM-backed path
  returns usage.
- No DB migration was needed. Phase-2 already added `qa_logs.token_cost`; Obj2
  continues to write total tokens through that existing column.
- Cost estimates are local operational estimates only, not billing facts.
  Default rates were checked against current official provider pages during
  implementation.

## Obj2 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_budget.py tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_anthropic_client.py -q -p no:cacheprovider`
- Result: passed, 25 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_budget.py tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_anthropic_client.py -q -p no:cacheprovider`
- Result: passed, 26 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_llm_synthesis.py tests\unit\test_supervisor_loop.py tests\unit\test_qa_logs.py tests\unit\test_tutor_orchestrator.py -q -p no:cacheprovider`
- Result: passed, 42 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj2-nonlarge -p no:cacheprovider`
- Result: passed, 327 tests; 2 skipped, 1 deselected, 1 qdrant compatibility
  warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj2-postreview -p no:cacheprovider`
- Result: passed, 328 tests; 2 skipped, 1 deselected, 1 qdrant compatibility
  warning.

## Obj2 Residual Risk

- Provider usage shapes are parsed for common OpenAI/Anthropic forms, but live
  provider validation remains deferred to the manual capture lane.
- Prompt-token reservation uses a deterministic character-based estimate because
  Obj2 intentionally avoids adding tokenizer dependencies.
- Provider rates can change; they remain configuration values and can be
  overridden by YAML or environment variables.

## Obj2 Post-Review Fixes

- Corrected stale OpenAI default from `gpt-5.2` to `gpt-5.5` to match the
  project model lane and current OpenAI docs.
- Updated local pricing defaults to OpenAI `gpt-5.5` standard short-context
  rates and Anthropic Claude Opus 4.8 published rates.
- Narrowed replay fixture redaction so secret auth tokens are still redacted but
  budget fields such as `input_tokens`, `output_tokens`, `total_tokens`, and
  `token_cost` are preserved.

## Obj2 Next Obj Gate

- Obj2 focused and compatibility tests passed.
- Full non-large suite passed.
- Obj3 may start after user review of Obj2.

## Obj3 Notes

- Hardened `v2_citation_check` for `synthesis_mode=="llm"` claims.
- LLM claims still must cite visible chunks and include visible `[chunk_id]`
  references.
- LLM claims now also require numbers, units, and common engineering symbols
  appearing in the claim to be present in the cited visible evidence text.
- Deterministic mode keeps Phase-2 behavior and does not enable the new strict
  number/unit/symbol blocking path.
- Added negative LLM fixtures for fabricated number, fabricated unit, and
  fabricated symbol cases.

## Obj3 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py -q -p no:cacheprovider`
- Result: passed, 18 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_llm_synthesis.py tests\unit\test_tutor_orchestrator.py tests\unit\test_v4_style_skill.py -q -p no:cacheprovider`
- Result: passed, 31 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj3-nonlarge -p no:cacheprovider`
- Result: passed, 333 tests; 2 skipped, 1 deselected, 1 qdrant compatibility
  warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py -q -p no:cacheprovider`
- Result: passed, 18 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj3-postreview -p no:cacheprovider`
- Result: passed, 333 tests; 2 skipped, 1 deselected, 1 qdrant compatibility
  warning.

## Obj3 Residual Risk

- The added check is explicit-string support for visible numbers, units, and
  symbols. It is not semantic entailment and does not prove engineering truth.
- Unit/symbol extraction is intentionally conservative and can be extended by
  later eval failures without changing the Obj3 contract.
- LLM-mode fail-closed checks may over-block legitimate paraphrases or rounded
  values. Obj8 eval should calibrate whether bare-number/bare-unit blocking
  needs narrowing.
- S5 derivation-step numeric/unit/symbol hardening remains Obj6 scope.

## Obj3 Post-Review Fixes

- Wired `tests/fixtures/llm/v2_negative_*.json` into the V2 negative tests so
  the fixtures are covered and cannot drift from inline test data.

## Obj3 Next Obj Gate

- Obj3 focused and nearby compatibility tests passed.
- Full non-large suite passed.
- Obj4 may start after user review of Obj3.

## Obj4 Notes

- S3 LLM synthesis now sends replay/live requests through the Obj1 client seam
  with prompt version `s3_qa_summary.v1`, schema version `s3.v1`, model,
  temperature, `max_tokens`, reasoning effort, text verbosity, timeout, task id,
  query, mode, language, prompt, and evidence bound into the replay request body.
- The S3 prompt contract now requires JSON output with `status`, `answer`,
  `claims[]`, and optional `warnings`. Each claim must carry `text`, `chunk_id`,
  `doc_id`, `pages`, and `evidence_type`.
- S3 preserves structured LLM claims that cite unknown chunks instead of
  silently dropping them, so V2 can block invisible citations before V4.
- Provider cost metadata is propagated from LLM responses into S3
  `structured_result.cost`; deterministic S3 still leaves `token_cost` and
  `cost` null.
- Replay miss, timeout, quota/runtime exception, budget denial, refusal, schema
  parse failure, and model-insufficient responses continue to degrade to the
  deterministic S3 path with warnings.
- Added small S3 LLM response fixtures for visible citation, invisible chunk,
  and fabricated numeric cases.
- `docs/issue_log_p3/issues_obj4.txt` was not generated in this implementation
  pass; Obj4 issue log remains pending user review.

## Obj4 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_llm_synthesis.py -q -p no:cacheprovider`
- Result: passed, 14 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py -q -p no:cacheprovider`
- Result: passed, 18 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_tutor_orchestrator.py tests\unit\test_v4_style_skill.py tests\unit\test_qa_logs.py -q -p no:cacheprovider`
- Result: passed, 38 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_budget.py -q -p no:cacheprovider`
- Result: passed, 22 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj4-nonlarge -p no:cacheprovider`
- Result: passed, 338 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_llm_synthesis.py -q -p no:cacheprovider`
- Result: passed, 16 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_llm_replay.py tests\unit\test_v2_citation_check.py -q -p no:cacheprovider`
- Result: passed, 26 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s3_qa_summary_skill.py -q -p no:cacheprovider`
- Result: passed, 15 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj4-postreview -p no:cacheprovider`
- Result: passed, 340 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.

## Obj4 Residual Risk

- Live OpenAI S3 behavior remains unvalidated by CI and is still deferred to the
  manual capture lane.
- V2's LLM-mode significant-item check is intentionally string-based and can
  over-block legitimate paraphrases or rounded values; Obj8 eval remains the
  calibration point.

## Obj4 Post-Review Fixes

- Added `S3LlmClaim` and `S3LlmResponse` schemas and routed S3 LLM parsing
  through that validated response shape. Missing mandatory claim fields now
  raise validation errors and fall back to deterministic S3.
- Kept invisible-chunk LLM claims available for V2, but stopped emitting
  pre-V2 `Citation` objects for those invisible chunks.
- Added public `request_from_kwargs()` for replay request construction and
  updated Obj4 replay tests to avoid importing the private helper.
- Added tests for schema failure and refusal-flag fallback.

## Obj4 Next Obj Gate

- Obj4 focused replay/provider seam tests and nearby S3/V2/V4 compatibility
  tests passed.
- Full non-large suite passed.
- Obj5 may start after user review of Obj4.

## Obj5 Notes

- Added default-off S4 LLM enablement through `LlmSettings.s4_enabled`,
  `configs/llm.yaml`, and `S4_LLM_ENABLED`.
- Added `S4LlmResponse` as the validated response contract for S4 LLM analysis.
  Responses must include `answer`, `engineering_meaning`, `premises`,
  `failure_modes`, `next_action`, and cited `claims[]`.
- S4 now accepts an injected replay/live `llm_client` and calls
  `analyze_engineering()` with prompt version `s4_engineering_analysis.v1`,
  schema version `s4.v1`, model settings, task id, query, S3 answer, visible
  claims, and visible evidence.
- S4 LLM output remains routed through V2 before V4. When V2 blocks unsupported
  claims, it now also clears engineering section fields so V4 cannot render
  unsupported S4 analysis.
- Replay miss, budget denial, refusal, schema validation failure, and other
  provider/runtime exceptions degrade to deterministic S4 with warnings.
- Added small S4 LLM fixtures for visible engineering analysis and fabricated
  threshold output.
- `docs/issue_log_p3/issues_obj5.txt` was not generated in this implementation
  pass; Obj5 issue log remains pending user review.

## Obj5 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s4_engineering.py -q -p no:cacheprovider`
- Result: passed, 13 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\unit\test_v4_style_skill.py tests\unit\test_tutor_orchestrator.py tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_budget.py -q -p no:cacheprovider`
- Result: passed, 62 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s4_engineering.py tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_budget.py -q -p no:cacheprovider`
- Result: passed, 36 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj5-nonlarge -p no:cacheprovider`
- Result: passed, 348 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s4_engineering.py tests\unit\test_v2_citation_check.py tests\unit\test_v4_style_skill.py -q -p no:cacheprovider`
- Result: passed, 41 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_budget.py tests\unit\test_tutor_orchestrator.py -q -p no:cacheprovider`
- Result: passed, 37 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj5-postreview -p no:cacheprovider`
- Result: passed, 350 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.

## Obj5 Residual Risk

- Live OpenAI S4 behavior remains unvalidated by CI and is deferred to the
  manual capture lane.
- V2's strict significant-item check remains string-based and may over-block
  legitimate S4 paraphrases or rounded values; Obj8 eval should calibrate this.
- S4 LLM prompt compliance depends on every engineering judgment being mirrored
  in `claims[]`. V2 cannot verify uncaptured section prose beyond clearing
  sections when any unsupported claim is detected.

## Obj5 Post-Review Fixes

- Relaxed `S4LlmResponse` defaults so `status="insufficient"` can validate and
  use the clean insufficient fallback branch.
- Kept `ok` S4 LLM responses strict by explicitly failing when required
  engineering fields are empty.
- Hardened V2's unsupported-output path from a section denylist to a conservative
  safe-key rebuild, preventing future free-text fields from leaking to V4 after
  V2 blocks unsupported claims.
- Added tests for clean S4 insufficient fallback and unknown free-text field
  stripping.

## Obj5 Next Obj Gate

- Obj5 focused replay/provider seam tests and nearby S4/V2/V4 compatibility
  tests passed.
- Full non-large suite passed.
- Obj6 may start after user review of Obj5.

## Obj6 Notes

- Added default-off S5 LLM enablement through `LlmSettings.s5_enabled`,
  `configs/llm.yaml`, and `S5_LLM_ENABLED`.
- Added `S5DerivationStep` and `S5LlmResponse` as the validated response
  contract for S5 LLM derivation. Responses must include `answer`, `premises`,
  `minimal_model`, `conclusion`, `derivation_steps[]`, and cited `claims[]`.
- S5 now accepts an injected replay/live `llm_client` and calls
  `derive_formula()` with prompt version `s5_formula_derivation.v1`, schema
  version `s5.v1`, model settings, task id, query, visible claims, and visible
  evidence.
- S5 LLM step graphs reuse the existing structural validator. Missing
  dependencies, self-loops, and multi-node cycles reject the LLM response and
  degrade to deterministic S5.
- V2 now checks significant numbers/units/symbols in LLM evidence derivation
  steps against the cited evidence chunk. Axiomatic steps remain citation-free
  but must be marked `source_type="axiomatic"`.
- Replay miss, budget denial, refusal, schema validation failure, model
  insufficient, and cycle/missing-dependency failures degrade to deterministic
  S5 with warnings.
- Added small S5 LLM fixtures for visible multi-step derivation, two-node cycle,
  and fabricated evidence-step numeric output.
- Obj6 issue log review is recorded in `docs/issue_log_p3/issues_obj6.txt`.

## Obj6 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py -q -p no:cacheprovider`
- Result: passed, 17 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\unit\test_v4_style_skill.py tests\unit\test_tutor_orchestrator.py tests\unit\test_llm_replay.py tests\unit\test_openai_client.py tests\unit\test_budget.py tests\unit\test_s4_engineering.py -q -p no:cacheprovider`
- Result: passed, 79 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj6-nonlarge -p no:cacheprovider`
- Result: passed, 359 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py -q -p no:cacheprovider`
- Result: passed, 17 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py -q -p no:cacheprovider`
- Result: passed, 18 tests.

## Obj6 Residual Risk

- Live OpenAI S5 behavior remains unvalidated by CI and is deferred to the
  manual capture lane.
- S5 derivation is still not a formal symbolic proof engine. Axiomatic steps are
  trusted when structurally valid and may need Obj8 eval calibration.
- The cycle detector rejects cyclic derivations correctly; its warning text may
  over-label pure dependents of a cycle, but the invalid LLM derivation is still
  blocked before rendering.
- LaTeX/MathML rendering and full symbol-proof validation remain out of Phase-3
  scope as documented in the development order.

## Obj6 Post-Review Fixes

- Reconciled V2's unsupported-output safe-key allowlist with Obj6's actual
  metadata field by replacing the dead `s5_analysis` entry with
  `s5_derivation`.
- Added S5 coverage proving V2 unsupported-output blocks still preserve safe S5
  metadata while stripping unsupported derivation prose such as `minimal_model`.

## Obj6 Next Obj Gate

- Obj6 focused replay/provider seam tests and nearby S5/V2/V4 compatibility
  tests passed.
- Full non-large suite passed.
- Obj7 may start after user review of Obj6.

## Obj7 Notes

- Added a real supervisor correction executor to `SupervisorLoop`. A rejecting
  review now calls an injected `correct()` client and re-reviews the revised
  candidate instead of repeatedly reviewing the same deterministic answer.
- Supervisor review/correction remains dependency-injected and default-off. The
  loop does not construct a live Anthropic client by itself.
- Replay/live supervisor requests now carry prompt version, schema version,
  provider/model settings, task id, query, serialized candidate, loop count,
  reviewer notes, and review issues where applicable.
- Added `SupervisorCorrectionResponse` for structured correction output.
  Correction responses must provide either `answer` or `structured_result`.
- Supervisor annotations now include `supervisor_corrections`,
  `supervisor_token_cost`, optional `supervisor_cost`, and aggregate top-level
  `token_cost` when replay/live supervisor responses report usage.
- Budget denial, replay miss, provider exception, refusal/insufficient review,
  and correction schema failure degrade to the original deterministic answer
  with `supervisor_status="fallback"`.
- Added `scripts/llm_capture.py` as a manual-only Anthropic capture helper for
  supervisor review/correction replay fixtures. It requires explicit live and
  capture config plus the configured Anthropic API key environment variable.
- Added small supervisor replay response fixtures for reject, correction, and
  approve paths.
- Obj7 issue log review is recorded in `docs/issue_log_p3/issues_obj7.txt`.

## Obj7 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_supervisor_loop.py tests\unit\test_llm_replay.py tests\unit\test_anthropic_client.py -q -p no:cacheprovider`
- Result: passed, 22 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_tutor_orchestrator.py tests\unit\test_agent_control_plane.py tests\unit\test_qa_logs.py -q -p no:cacheprovider`
- Result: passed, 46 tests.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj7-nonlarge -p no:cacheprovider`
- Result: passed, 364 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_supervisor_loop.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider`
- Result: passed, 23 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_supervisor_loop.py tests\unit\test_llm_replay.py tests\unit\test_anthropic_client.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider`
- Result: passed, 38 tests.
- Post-review verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-obj7-polish -p no:cacheprovider`
- Result: passed, 364 tests; 2 skipped, 1 deselected, 1 qdrant
  compatibility warning.

## Obj7 Residual Risk

- Live Anthropic supervisor behavior remains unvalidated by CI and is deferred
  to the manual capture lane. This implementation did not require or use an API
  key.
- The configured Anthropic model id remains a configuration value
  (`claude-opus-4-8`). Business code does not hard-code it. Operators should
  override `ANTHROPIC_MODEL` or `configs/llm.yaml` if the provider's current
  official model id differs.
- Correction output is still a model-generated rewrite, not a proof of factual
  correctness. It remains bounded by the follow-up supervisor review and the
  two-correction loop limit.
- Extreme/V3-flagged default local queries still annotate
  `supervisor_status="fallback"` when no supervisor client is injected. This is
  intentional fail-loud behavior for manual-select mode.

## Obj7 Post-Review Fixes

- Renamed the correction-loop exhaustion action from the misleading
  `opus_takeover` value to `correction_limit_fallback`, matching the actual
  behavior: the loop returns the original deterministic answer after the
  correction limit is reached.
- Updated supervisor control-plane and loop tests to assert the new recorded
  action value before the Phase-3 freeze.

## Obj7 Next Obj Gate

- Obj7 focused replay/provider seam tests and nearby supervisor/orchestrator
  compatibility tests passed.
- Full non-large suite passed.
- Obj8 may start after user review of Obj7.
