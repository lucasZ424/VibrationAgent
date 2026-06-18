# Phase-3 Session Handoff

Updated: 2026-06-12

## Current State

Phase 3 is complete and frozen. The canonical freeze documents are:

- `docs/phase_3_interface_freeze.md`
- `docs/phase_3_deferred_and_polish_audit.md`
- `docs/phase_3_migrations.md`
- `docs/phase_3_progress.md`

The frozen default runtime remains the deterministic Phase-2 path:

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

Phase-3 LLM paths are default-off, replayable, budget-governed, and
manual-live-only. CI must remain replay/deterministic and must not call live
OpenAI or Anthropic providers.

## Objective Status

- Obj0 Phase-3 execution baseline: done.
- Obj1 provider client and record/replay baseline: done.
- Obj2 token budget and cost estimation: done.
- Obj3 V2 LLM-output safety gate pre-hardening: done.
- Obj4 S3 real LLM synthesis: done.
- Obj5 S4 real engineering analysis: done.
- Obj6 S5 real formula derivation and cycle-check hardening: done.
- Obj7 Claude Opus supervisor trial and correction executor: done.
- Obj8 golden-output eval minimum set and replay regression gate: done.
- Obj9 manual live validation and capture lane: done.
- Obj10 Phase-3 interface freeze and Phase-4 planning: done.

## Frozen Contracts To Preserve

Phase 3 freezes these additive LLM/replay/supervisor contracts:

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

The deprecated provider sampling parameter is not part of the frozen request
contract. Replay hashes bind prompt version, schema version, provider, model,
`max_tokens`, reasoning/verbosity settings where applicable, and request body.

Frozen `synthesis_mode` values:

- `deterministic`
- `llm`

Frozen `supervisor_action` values:

- `finalize`
- `gpt_correction`
- `correction_limit_fallback`

Supervisor clients support two frozen calling conventions:

- Legacy injected clients: `review(query, output, loop_count, reviewer_notes)`
  and optional `correct(query, output, review, loop_count, reviewer_notes)`.
- Replay/live LLM clients: `review(**kwargs)` and `correct(**kwargs)` with
  Phase-3 LLM request kwargs.

Changing schemas, chain order, structured result keys, replay fixture layout,
provider request shape, API shape, or ingestion output shape is a post-freeze
contract change and must start with a migration note in
`docs/phase_3_migrations.md`.

## Important Implementation Notes

- `config.load()` reads gitignored `.env.local` and `.env`, but only fills
  missing process environment variables. Tests set
  `VIBRATION_AGENT_DISABLE_DOTENV=1` for hermetic behavior.
- Live provider construction is forbidden under pytest.
- OpenAI and Anthropic SDK imports are lazy and happen only inside live calls.
- `RecordingClient` exposes replay-compatible `synthesize()`,
  `analyze_engineering()`, `derive_formula()`, `review()`, and `correct()`.
- Manual captures should write to `data\exports\manual_llm_fixtures` first, not
  directly to committed `tests\fixtures\llm`.
- Capture redaction removes API keys, authorization tokens, bearer tokens, long
  raw text, and common local absolute path forms.
- V2 is the faithfulness gate for LLM claims and S5 evidence derivation steps.
  Unsupported model output must be blocked before V4 rendering.
- S4/S5 deterministic fallback outputs clear inherited upstream cost metadata.
- Manual summary cost aggregation counts only model skills with non-null
  `token_cost`; V2/V4 pass-through metadata should not be double-counted.

## Manual Live Validation Results

Obj9 recorded successful manual live validation after local API keys were
configured:

- OpenAI engineering lane: S3 and S4 live paths completed with
  `openai:gpt-5.5`, `status="ok"`, and per-skill token/cost metadata.
- OpenAI derivation lane: S3 and S5 live paths completed with
  `openai:gpt-5.5`; S5 stayed evidence-scoped and declined unsupported
  quantitative formulas/numeric predictions when evidence was qualitative.
- Anthropic supervisor lane:
  `scripts\manual_e2e.py --live-supervisor --difficulty extreme --fixture-dir data\exports\manual_llm_fixtures`
  completed with `supervisor_status="approved"` and token/cost metadata from
  `anthropic:claude-opus-4-8`.

Live validation exposed and fixed:

- Provider sampling parameter rejection/deprecation.
- OpenAI Responses nested `output[].content[].text` parsing.
- Incomplete/truncated OpenAI payload handling.
- Anthropic review payloads missing local `task_id`.
- Anthropic review issues using `message` / `code` instead of `description`.
- Capture redaction gaps for local absolute paths.

## Last Verified Gates

Obj10 freeze verification recorded:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_llm_eval.py -q -p no:cacheprovider
```

Result: passed, 2 tests.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase3_eval_scorecard.json
```

Result: passed, 5/5 replay eval cases, all scorecard rates 1.0.

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --difficulty low
```

Result: passed with `status="ok"`, `supervisor_status="not_triggered"`, and no
token/cost metadata.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p3-freeze -p no:cacheprovider
```

Result: passed, 381 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

## Accepted Residual Risks

Accepted residual risks are consolidated in
`docs/phase_3_deferred_and_polish_audit.md`. Key points:

- LLM-backed S3/S4/S5 remain default-off.
- V2 significant-item checking is structural/string-based, not deep semantic
  entailment.
- S5 is not a symbolic proof engine.
- Supervisor approval is bounded model review, not formal proof.
- Captured live outputs require human inspection before promotion into replay
  fixtures.
- Provider aliases, prices, network behavior, and budget ceilings remain
  operational risks.
- CI remains replay/deterministic.

## Phase-4 Candidate Entry Points

Start Phase-4 planning from:

- `docs/phase_3_deferred_and_polish_audit.md`
- `docs/phase_3_interface_freeze.md`
- `docs/phase_3_migrations.md`

Candidate Phase-4 scope includes:

- S6 literature search.
- S7 model selection.
- S8 experiment advice.
- Web UI.
- Deployment/observability hardening.
- Stronger semantic entailment beyond V2 structural checks.
- Retrieval replacement or OpenAI embeddings, isolated from synthesis changes.
- Rendered DOCX pagination and richer image/formula anchoring.
- LaTeX/MathML generation and rendering.
- Symbolic proof or CAS-backed derivation checks.
- Broader golden eval sets.
- Operator-run full large-corpus baseline against the real corpus.

## Working Tree Notes At Handoff Creation

At the time this handoff was created, the worktree already showed:

- `D session_handoff_p3_2026_06_08.md` under `docs/`
- `?? docs/session_handoff_supervisor_review_pattern.md`

Those were pre-existing relative to this handoff creation. Do not assume they
were produced by the handoff task unless confirmed separately.

This handoff adds:

- `docs/session_handoff_p3_2026_06_12.md`

## Next Session Recommendations

1. Treat Phase 3 as frozen and do not change frozen contracts without a new
   migration note.
2. If starting Phase 4, first create a Phase-4 development-order/progress
   baseline instead of editing Phase-3 freeze docs ad hoc.
3. Keep live provider validation manual-only. Never wire live OpenAI/Anthropic
   into CI.
4. Do not edit `docs/issue_log_p3/` unless the user explicitly asks; issue logs
   are user-review artifacts.
5. If API keys are needed, rely on local `.env` / `.env.local` and never print
   or inspect key values.
