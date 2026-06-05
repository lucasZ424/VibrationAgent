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
