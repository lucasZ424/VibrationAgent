# Phase 3 Progress

Updated: 2026-06-08

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
4. S3 real LLM synthesis: pending
5. S4 real engineering analysis: pending
6. S5 real formula derivation and cycle-check hardening: pending
7. Claude latest / Claude Opus 4.8 supervisor trial and correction executor: pending
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
