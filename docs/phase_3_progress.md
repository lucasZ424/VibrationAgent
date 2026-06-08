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
2. Token budget and cost estimation: pending
3. V2 LLM-output safety gate pre-hardening: pending
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
- Provider model ids remain configuration values. Obj1 defaults are
  `gpt-5.2` and `claude-opus-4-8`, based on current official provider docs
  checked during implementation.

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
