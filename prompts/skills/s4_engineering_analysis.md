# S4 Engineering Analysis

Runtime implementation: `src/vibration_agent/skills/s4_engineering_analysis.py`.

S4 is an optional engineering layer inserted after S3 and before V2.

## Contract

- Run only for `user_mode="engineering"` and sufficient cited S3 evidence.
- Use only claims and chunks already visible in S2/S3.
- Do not invent numeric values, thresholds, operating conditions, units, or
  maintenance conclusions.
- Add engineering framing such as implication, applicability, caveats, and next
  action.
- Always pass the result through V2 before V4 renders the final answer.

If S4 is not applicable or lacks evidence, skip and let S3 continue to V2.

## Phase-3 Obj5 LLM Contract

LLM-backed S4 is disabled by default. It may run only when `s4_llm_enabled=true`
or configuration enables it, and a replay/live `llm_client` is injected.

When active, return JSON only:

- `status`: `ok`, `insufficient`, `refusal`, or `refused`
- `answer`
- `engineering_meaning`
- `premises`
- `failure_modes`
- `next_action`
- `claims[]`
- optional `warnings`

Every engineering judgment must be represented in `claims[]`. Each claim must
include `text`, `chunk_id`, `doc_id`, `pages`, and `evidence_type`, and `answer`
must contain the visible `[chunk_id]` citation for that claim. Runtime degrades
to deterministic S4 on replay miss, timeout, budget denial, refusal, or schema
validation failure.
