# Phase 5 Obj6 — Controlled LLM synthesis lane: kickoff plan

Draft: 2026-07-02 (supervisor-drafted; proposal, not yet folded into the ledger)
Reflects the Obj5 handoff. Operationalizes `docs/phase_5_development_order.md` §6.

## Why now — the Obj5 handoff

Obj5 proved the deterministic completeness lever is **exhausted** against the gate
(full analysis: `docs/issue_log_p5/issues_obj5.txt`, ROOT-CAUSE + FOLLOW-UP):

- Corrected-off deterministic floor (selector default-off, S3 leak fixed, on the
  14-case Obj1 fixture): **completeness 0.708 · V2 faithfulness 1.000 · sentence
  completeness 0.890 · citation_alignment 1.0 · recall@10 0.607**.
- A cap bump lifts completeness but always dips readability below the 0.890 floor
  (strict gate) → rejected. A fixed-cap claim reranker cannot help the hard cases:
  for `diagnosis_zh` / `comparison_en` (both recall@10 = 1.0) the discriminating
  facts (phase / 2X / axial / misalignment) are **not in the candidate claims at
  all**, because `_ranked_claims` ranks by query-token overlap and those facts are
  the *answer*, not the *question*. Surfacing them generically already regressed
  cases; per-intent rules overfit the fixture.
- Conclusion: the remaining completeness gain is a **semantic synthesis** problem →
  Obj6, exactly where the dev-order sequences it. `answer_quality` gating (Obj2),
  the V2 hard gate, retrieval lanes (Obj3/4), and the Obj5 evidence contract stay
  as-is; Obj6 changes only how S3 composes an answer from already-visible evidence.

## What already exists (this is activation, not greenfield)

Phase-3/4 built the scaffolds, all default-off / replay-only:

- `src/vibration_agent/llm/{openai_client,anthropic_client,budget,replay,_guards}.py`
- `src/vibration_agent/skills/s3_qa_summary.py` — `_llm_enabled(...)` (reads
  `s3_llm_enabled` / `llm_enabled` / `use_llm_s3`), `S3LlmResponse` schema,
  `_llm_claims`, `_validate_llm_answer`, `synthesis_mode: "llm" | "deterministic"`.
- `src/vibration_agent/agent/supervisor.py` (Opus review/correction loop).
- `scripts/{llm_capture,manual_e2e}.py`; replay fixtures in `tests/fixtures/llm/`.

Obj6 wires these into the completeness path, captures the hard-case replays, and
calibrates against the Obj5 floor — it does not build new clients.

## Scope (dev-order §6, sequential sub-gates)

- **Obj6A — GPT S3 synthesis.** Activate the OpenAI S3 synthesis client behind the
  existing default-off `s3_llm_enabled` flag. Fixed prompt/schema version; evidence
  **allowlist = the Obj5 `evidence_context` / S2 handoff only** (never the raw
  corpus — this is the Obj5 leak fix, now a hard contract); budget cap;
  provider/model/prompt/schema/request-hash/token-usage/cost trace; replay capture.
- **Obj6B — Opus review/correction.** Independent reject→correct→approve loop; fix
  the malformed correction-schema fallback so a correction must carry `answer` or
  `structured_result` and never ValidationError-falls-back. Not started until 6A
  passes.
- Combined-chain quality is **not** claimed until 6A and 6B each pass in isolation
  (so a supervisor gain is never mis-attributed to synthesis, and vice-versa).

## Hard constraints (inherited — non-negotiable)

1. **CI never constructs a live provider**; fast suite has no network and lazy-imports
   every SDK. Live paths default-off; replay-first.
2. **Replay-first**: GPT and Opus each get replay fixtures; a replay miss fails loud
   and degrades to deterministic extraction with a visible warning.
3. **V2 faithfulness is the hard gate.** Every model claim passes V2; an unsupported
   claim is blocked. Deterministic extraction is the fallback, not a bypass.
4. **Schema-strict**: structured output only; never splice half-parsed text.
5. **Budget-gated**: missing key / live-disabled / budget-deny / timeout / refusal /
   schema-parse-failure / replay-miss all degrade deterministically and visibly.
6. **Evidence contract**: synthesis consumes only `evidence_context` (Obj5) — the
   full-corpus handoff leak must stay closed.
7. **Migration-first** for the synthesis contract (prompt/schema version, evidence
   allowlist, budget, default-off flag) before any default change.

## Success criteria — the Obj6 gate (14-case Obj1 fixture, replay)

Promote the lane only if ALL hold on a paired synthesis-off vs synthesis-on run:

- completeness **strictly > 0.708** (the corrected-off floor) — the objective.
- V2 faithfulness **stays 1.000** (any hallucinated claim drops it → fail).
- sentence_completeness **>= 0.890** (readability not below floor).
- citation_alignment_rate **== 1.0**.
- recall@10 **unchanged at 0.607** (synthesis must not touch retrieval).
- No existing baseline pass becomes a complete miss.
- Gains concentrated on the semantic hard cases (`diagnosis_zh/en`,
  `comparison_zh/en`) where facts are retrieved but not deterministically extracted.
- **Separate** GPT and Opus replay scorecards; combined chain claimed only after
  both pass. At least one **manual live** GPT run and one Opus run must be
  recorded as acceptance evidence (provider / model / status / usage / cost /
  residual risk under `run_logs/`); manual live never replaces replay regression.

Rollback: `s3_llm_enabled=false` (default) restores deterministic extraction; no
corpus or retrieval change.

## Approved decisions and entry gate (2026-07-03)

1. **Obj5 is closed within deterministic scope.** The selector remains default-off;
   its lack of strict gain is retained as a negative result. Semantic completeness
   gain moves to Obj6 without weakening the Obj5 gate.
2. **Corrected calibration comes first.** Regenerate the fixed-S3, selector-off Obj1
   baseline and re-validate Obj2 threshold 0.75 before changing Obj6 runtime code.
   Obj6A cannot start until 0.75 retains zero false allows and zero false blocks.
3. **Keep Obj6→Obj7 ordering.** Corpus noise can be inventoried, but OCR/mojibake
   cleanup and any reindex are deferred until Obj7 so the Obj6 comparison uses one
   immutable corpus.

## First implementation slice (proposed)

Obj6A-0 (local, no live): enable `synthesis_mode="llm"` in S3 behind `s3_llm_enabled`
with `evidence_context` as the strict allowlist; capture GPT replay fixtures for the
four semantic hard cases; unit-test the fallback matrix (no key / budget-deny /
timeout / refusal / schema-error / replay-miss → deterministic fallback, visible
warning); confirm the fast suite stays green with zero live construction. THEN one
operator replay scorecard (synthesis-off vs synthesis-on) against the 0.708 floor.
Pause for review before 6B.

## Current checkpoint

Obj6A is complete: prompt-v3 replay and the clean-environment canonical
non-large suite passed (619 passed, 1 deselected in 13.00s), and runtime remains
default-off. Obj6B local contract and replay verification is implemented:
reject->correct->approve replay passes through hash-addressed fixtures, malformed
ok corrections fall back visibly instead of approving, manual capture rejects
malformed correction fixtures before write, and supervisor residual risk is
preserved in final annotations and manual E2E summaries. Obj6B live correction
evidence is now complete: after explicit approval for Anthropic data transfer,
`run_logs/obj6b_live_correction_20260706_140930.json` passed with
`supervisor_status=approved`, two review invocations, one correction, residual
risk recorded, and token/cost trace. The schema prompt gap found in the first
live correction attempt (`status="revised"` in a review payload) is fixed and
covered by unit tests. Final local regression passed with
`run_logs/obj6b_final_nonlarge_20260706_141053.json` (625 passed).

The earlier user-only validation-running rule is lifted: the agent may run
needed validation directly, while keeping `run_logs/` for traceability. Obj6A
and Obj6B are complete in isolation, and the combined-chain replay/live gate has
now passed. Final evidence:

- Live combined gate:
  `run_logs/obj6_combined_live_gate_20260706_152132.json`, eligible true.
- Promoted replay gate:
  `run_logs/obj6_combined_replay_promoted_gate_20260706_152530.json`, eligible
  true.
- Combined scorecard: recall@10 0.607, completeness 0.804, V2 faithfulness
  1.000, sentence completeness 0.921, citation alignment 1.000.
- All four semantic hard cases were supervisor-approved and post-supervisor V2
  `ok`.
- Final non-large regression:
  `run_logs/obj6_combined_final_nonlarge_20260706_153100.log`, 631 passed,
  1 registered large-corpus deselection, exit code 0.

The combined-chain answer-quality retake does not authorize a threshold
migration. With the current human labels still at 1 usable / 13 unusable,
thresholds 0.75 and 0.85 both produce three false allows on the now-pass-like
hard cases; 0.95 blocks the only labeled usable case. Those hard-case labels
must be manually re-reviewed before changing the 0.75 provisional production
threshold.

Obj6 is complete. Obj7 may start next; corpus/taxonomy mutation remains
separate and must establish a new baseline before later comparisons.
