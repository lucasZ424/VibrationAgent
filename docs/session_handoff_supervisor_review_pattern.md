# Handoff — Supervisor Review Interaction Pattern

Captured: 2026-06-12
Source: the developer⇄reviewer interaction the user framed across the Phase-3
Obj1–Obj10 review session.

## What this file is

This is the interaction pattern between **the user (acting as developer/lead who
presents completed objective work)** and **the assistant (acting as a
senior-engineer supervisor who gates each objective)**.

It is NOT the in-product `SupervisorLoop` / Opus-supervisor agentic role inside
`vibration_agent`. It is the *review protocol* the user uses to drive the
assistant during development. A fresh session should read this to resume the same
cadence without re-deriving it.

The durable, phase-agnostic version of this policy lives in user memory as
`feedback-review-workflow`; this handoff is the session-grounded, copy-pasteable
form with concrete Phase-3 examples.

## Roles

- **Developer (user):** implements each objective out-of-band, then presents the
  working tree for review. The assistant does NOT watch the dev happen; it
  reviews the resulting tree.
- **Supervisor (assistant):** reviews one objective at a time, runs the full
  suite itself, writes a full report to disk, briefs the chat, and issues a gate.
  Objectives are sequential and gated — each must clear before the next starts.

## The two driver commands

The whole loop runs on two phrases the user issues:

1. **`evaluate objN dev`** — full review of objective N.
2. **`verify objN fixes`** — re-review after the developer applied fixes from the
   previous review round.

The user may attach a **specific lens** to a command. Honor it as a first-class
part of that review. Example from this session:
> "evaluate obj7 dev. the supervisor is on manual select mode, no api keys
> implemented. state the necessity of api keys by this stage of dev."
Here the assistant added a dedicated "API-key necessity at this stage" section to
the Obj7 review and grounded it in the ACs + Phase-3 default-off discipline.

## Procedure for `evaluate objN dev`

1. **Mark a chapter** for the objective evaluation (one chapter per objective).
2. **Read the spec / acceptance criteria** for objective N from the development
   order (`docs/phase_3_development_order.md` for Phase 3).
3. **Isolate the objective delta.** HEAD advances one commit per cleared
   objective (commits read `p3 objN clear`), so after objective N-1 is committed,
   `git diff HEAD` is exactly objective N's delta. Always check `git log -1` +
   `git status --short` first — HEAD may lag, and prior cleared-but-uncommitted
   objectives can sit in the tree (review ONLY the current objective's files).
4. **Read every changed/new file.** For broad deltas, classify each change:
   - legitimate objective plumbing vs business-logic change to already-cleared code;
   - in-scope vs scope creep (and if a frozen/cleared surface like V2 is touched,
     scrutinize and confirm it is recorded in migrations).
5. **Run the FULL suite yourself — never trust the dev's subset run.** The exact
   command used all session:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=.pytest_tmp -p no:cacheprovider
   ```
   (`--basetemp=.pytest_tmp` avoids a Windows temp-dir ACL/WinError-5 issue;
   `large_corpus` is deselected; integration tests DO run under this selection.)
6. **Verify each acceptance criterion explicitly (AC-by-AC)**, citing the test
   that proves it. Then apply the **Phase-3 acceptance lenses** on top:
   default-off regression (byte-identical to deterministic when flags off),
   replay-not-live (no live client under pytest; replay miss fails loud),
   deterministic fallback (missing key / budget deny / timeout / refusal /
   schema-parse failure / replay miss all degrade with a warning), schema-strict
   fail-loud (structured output only; never splice half-parsed text),
   budget-gated, and V2 as the load-bearing faithfulness gate.
7. **Cross-check migrations** for any contract change (schemas-first → migration
   note → fixtures/tests → callers). A contract change not recorded is a finding.
8. **Write the FULL report** to `docs/issue_log_p3/issues_objN.txt` (this folder
   is gitignored — local review artifact). Structure:
   - Scope reviewed (file list)
   - Reviewer verification (full-suite pass count + delta from prior objective)
   - AC compliance (AC-by-AC: PASS/PARTIAL + evidence)
   - Positives
   - Issues, each `#k [Severity] title` + explanation + recommendation
   - Recommended fix order
   - Gate
9. **Brief the chat — general-info only.** Issue-log file link + full-suite pass
   count + the load-bearing findings + one-line gate verdict. Full detail stays in
   the file; do NOT dump severity tables or per-AC prose into chat.
10. **Decide the gate** (see Gate rule).

## Procedure for `verify objN fixes`

1. Mark a chapter ("ObjN fix verification").
2. Re-inspect the fix delta (diff the touched files; confirm what changed).
3. Re-run the FULL suite.
4. **Append** a `FIX VERIFICATION — round K` section to the SAME
   `issues_objN.txt` — a table: `# | finding | severity | status | evidence`,
   where status ∈ {RESOLVED, Accepted, Deferred, Open}. Note any new
   out-of-scope changes observed.
5. Brief chat (file link + pass count + per-finding resolution + gate).

## Gate rule (hard)

- A RED full suite = **NOT CLEARED**, period (Golden Rule 12: "tests pass" is
  false if any fail). Fix stale tests that break because a per-spec default
  changed — fix the test, not the feature — then re-run green.
- **AC sub-clauses and named deliverables matter even when the suite is green.**
  Example: Obj8's eval gate ran in CI via pytest (green), but the spec's
  `.github/workflows/test.yml` scorecard-artifact deliverable was not wired →
  gated as **CLEARED WITH REQUIRED FOLLOW-UP**, not silently cleared.
- Three gate outcomes were used this session:
  - **CLEARED** — all ACs met, suite green.
  - **CLEARED WITH REQUIRED FOLLOW-UP** — core intent met + green, but a named
    deliverable / AC sub-clause or a decision-needing inconsistency remains
    (e.g., Obj8 artifact; Obj9 live-validation doc reconciliation). Surfaced
    loudly so it is not dropped.
  - **NOT CLEARED** — blocking failure.

## Findings discipline

- Tag every finding with a severity: Critical / Significant / Medium / Low / Info.
- Prefix with `#1 #2 …` so the user can locate them quickly.
- Always give a concrete recommendation and a recommended fix order.
- Distinguish **blocking** vs **freeze-checklist** vs **informational**.
- **Accumulate cross-objective items** for the freeze. This session carried
  forward, e.g.: the Obj9 `temperature`/replay-hash removal superseding Obj1's
  "hash includes temperature"; V2's grown contract (Obj3 strict checks + Obj5
  positive-allowlist blanking + Obj6 derivation-step checks); the Obj7
  `correction_limit_fallback` rename; and the V2 over-blocking calibration
  deferred to eval — all re-checked at the Obj10 freeze review.

## Style contract (the user corrected this early — honor it)

- The user's correction this session: *"recall the evaluation policy… the current
  workflow is inconsistent."* The assistant had put the full report in chat.
- Rule: **full report → on-disk issue log; chat → general-info brief only**
  (file link + pass count + gate + the few findings that matter). Brevity in
  chat was demanded repeatedly.
- Reviewer writes its OWN independent findings; it does not just restate the
  dev's self-review notes. Documentation-only objectives (Obj0, Obj10) still get
  a full-suite run to confirm the tree is green at gate time.

## One-line mental model

> Developer presents → Supervisor reads spec, isolates the diff, runs the full
> suite itself, writes the full report to the issue log, briefs chat, and gates;
> `verify` re-runs and appends a fix round to the same log. Green suite + every
> AC (incl. named deliverables) ⇒ CLEARED; otherwise required-follow-up or
> NOT CLEARED.

## Related

- User memory `feedback-review-workflow` — the reusable, phase-agnostic policy.
- User memory `vibration-agent-project-overview` — project scope + phase status.
- Phase-3 freeze: `docs/phase_3_interface_freeze.md`,
  `docs/phase_3_deferred_and_polish_audit.md`.
