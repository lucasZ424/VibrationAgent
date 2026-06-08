# Phase 3 Session Handoff

Updated: 2026-06-08

## Purpose

This handoff lets a new session start Phase-3 formal development without
reconstructing the whole Phase-1/Phase-2 history.

Phase 3 starts after Phase 2 was frozen as the local personal knowledge-base
runtime. Obj0 for Phase 3 has been completed as a documentation-only execution
baseline. The next implementation target is Obj1.

## Files To Read First

Read these in order:

1. `AGENTS.md` or the active session instructions.
2. `docs/phase_2_interface_freeze.md`
3. `docs/phase_2_deferred_and_polish_audit.md`
4. `docs/phase_3_development_order.md`
5. `docs/phase_3_progress.md`
6. `docs/phase_3_migrations.md`
7. `docs/issue_log_p3/issues_obj0.txt`

Then read the code files needed for the current objective. For Obj1, start with:

- `src/vibration_agent/config.py`
- `src/vibration_agent/schemas.py`
- `src/vibration_agent/agent/supervisor.py`
- `src/vibration_agent/skills/s3_qa_summary.py`
- `tests/unit/test_s3_llm_synthesis.py`
- `tests/unit/test_supervisor_loop.py`

## Current Product State

Phase 2 frozen query path:

```text
User query
  -> TutorOrchestrator
  -> S2 retrieval
  -> S3 evidence-bound synthesis
  -> optional S4 engineering analysis OR optional S5 formula derivation
  -> V2 citation check
  -> V4 style
  -> optional V3 reviewer for extreme tasks
  -> optional supervisor annotation/handoff
  -> SkillOutput/API/CLI JSON
```

S1 remains explicit ingestion and is not run on every query.

Active Phase-2 skills:

- `s1_ingestion`
- `s2_retrieval`
- `s3_qa_summary`
- `s4_engineering_analysis`
- `s5_formula_derivation`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`
- `v4_style`

Deferred through Phase 3 unless explicitly split later:

- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`
- Web UI
- k8s/shared/remote deployment
- multi-tenant authz
- production observability stack
- OpenAI embeddings/retrieval replacement unless eval proves S2 recall is the
  bottleneck
- deep semantic entailment
- LaTeX/MathML and symbolic proof

## Phase 3 Direction

Phase 3 is the first usable engineering-assistant intelligence upgrade on top of
Phase 2. It turns the Phase-2 deterministic scaffolds into real, replayable,
budget-governed model paths:

```text
OpenAI S3/S4/S5 live/replay path
  -> V2 minimal faithfulness hardening
  -> Claude latest / Claude Opus 4.8 supervisor live/replay trial
  -> golden eval
  -> manual live validation
  -> Phase-3 freeze
```

Default behavior must remain the Phase-2 deterministic path. All live provider
paths are default-off.

Confirmed decisions:

- OpenAI S3/S4/S5 default profile: latest high-capability model,
  `reasoning_effort=high`, `text_verbosity=high`; model id lives in config, not
  business code.
- Claude supervisor default: Anthropic latest model, initial trial target Claude
  Opus 4.8; model id lives in config, not business code.
- Token budget remains `4000/task` and `30000/session`.
- Cost is a local estimate for this personal Agent, not a billing source of truth.
- OpenAI embeddings/retrieval remains deferred unless eval/manual validation
  proves retrieval recall is the bottleneck.

## Phase 3 Objective Status

0. Phase-3 execution baseline: done
1. Provider client and record/replay baseline: next
2. Token budget and cost estimation: pending
3. V2 LLM-output safety gate pre-hardening: pending
4. S3 real LLM synthesis: pending
5. S4 real engineering analysis: pending
6. S5 real formula derivation and cycle-check hardening: pending
7. Claude latest / Claude Opus 4.8 supervisor trial and correction executor: pending
8. Golden-output eval minimum set and replay regression gate: pending
9. Manual live validation and capture lane: pending
10. Phase-3 interface freeze and Phase-4 planning: pending

## Obj0 Completed

Obj0 was documentation-only. It added or updated:

- `docs/phase_3_development_order.md`
- `docs/phase_3_progress.md`
- `docs/phase_3_migrations.md`
- `docs/issue_log_p3/issues_obj0.txt`
- `README.md`

Obj0 established:

- one-Obj-at-a-time execution
- Phase-3 progress ledger
- Phase-3 migration ledger
- Phase-3 issue-log directory
- CI replay-only rule
- manual-live-only rule
- default-off provider paths

Obj0 verification:

```powershell
git diff --check -- README.md docs\phase_3_development_order.md docs\phase_3_progress.md docs\phase_3_migrations.md docs\issue_log_p3\issues_obj0.txt
```

Result: passed with README CRLF/LF normalization warning only.

## Next Target: Obj1

Obj1 name:

```text
Provider client 与 record/replay 基线
```

Scope from `docs/phase_3_development_order.md`:

- `src/vibration_agent/llm/openai_client.py` new
- `src/vibration_agent/llm/anthropic_client.py` new
- `src/vibration_agent/llm/replay.py` new
- `src/vibration_agent/llm/__init__.py`
- `src/vibration_agent/config.py`
- `configs/llm.yaml`
- `tests/unit/test_llm_replay.py`
- `tests/unit/test_openai_client.py`
- `tests/unit/test_anthropic_client.py`
- `tests/fixtures/llm/`

Obj1 required behavior:

- OpenAI client supports S3/S4/S5 structured-output seams.
- Anthropic client supports Claude supervisor review/correction seams.
- SDK imports are lazy; fast suite must not require OpenAI or Anthropic SDKs.
- ReplayClient returns fixture responses by stable request hash.
- Replay miss fails explicitly and must not fall back to live call.
- RecordingClient is manual-only and writes redacted fixtures.
- pytest guard fails if tests construct a live provider client.
- fixture hash metadata includes prompt version, schema version, model,
  temperature, max_tokens, reasoning/verbosity settings where applicable, and
  request body.

Do not implement real S3/S4/S5/supervisor behavior in Obj1 beyond provider and
replay scaffolding.

## Development Rules For The New Session

- Keep changes surgical and Obj-scoped.
- Before each Obj implementation, state assumptions and success criteria.
- For every issue plan, prefix items with issue numbers so the user can locate
  them quickly.
- Update `docs/phase_3_progress.md` after meaningful steps.
- Write or update `docs/issue_log_p3/issues_objN.txt` during review.
- Any schema or contract change must be recorded in `docs/phase_3_migrations.md`.
- Never put API keys in chat, fixtures, logs, README examples, or commits.
- Live API calls are allowed only in manual/capture commands after the relevant
  objective explicitly adds that path.
- CI and pytest must remain replay-only.
- If Windows sandbox pytest temp-dir permissions fail during validation, record
  the full command and reason in progress; do not treat it as a product failure.

## Useful Verification Commands

Full non-large suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\tmp\pytest-p3 -p no:cacheprovider
```

Fast suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=data\tmp\pytest-p3-fast -p no:cacheprovider
```

Phase-2 contract E2E:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_phase2_end_to_end.py -q -m "not large_corpus" -p no:cacheprovider -p no:tmpdir
```

Obj0 documentation check:

```powershell
git diff --check -- README.md docs\phase_3_development_order.md docs\phase_3_progress.md docs\phase_3_migrations.md docs\issue_log_p3\issues_obj0.txt
```

## Current Working Tree Note

At the time this handoff was created, the relevant Phase-3 files are uncommitted.
There is also a pre-existing deletion state for:

```text
docs/session_handoff_2026_05_27.md
```

That deletion was not made for this handoff. Do not restore or remove it unless
the user explicitly asks.
