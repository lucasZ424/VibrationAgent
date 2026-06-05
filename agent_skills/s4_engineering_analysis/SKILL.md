# S4 Engineering Analysis

Use this skill when a vibration-agent answer needs engineering framing after S3
has produced cited evidence-bound claims.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s4_engineering_analysis.py`
- Contract: `SkillInput` -> `SkillOutput`
- Chain position: after S3, before V2

## Required Inputs

Provide:

- `SkillInput.user_mode = "engineering"`
- `context.s2_result` with visible retrieval context
- `context.s3_result` with cited claims

## Behavior

S4 adds engineering implication, applicability/premises, caveats, and next
action from the existing cited claims. It must not create new numeric values,
thresholds, units, operating conditions, or maintenance conclusions.

If the mode is not engineering or cited evidence is missing, S4 returns
`insufficient` so the orchestrator can skip it and continue with S3.

## Outputs

Return a `SkillOutput` with:

- `status`: `ok` only when cited S3 claims are visible to S2
- `structured_result.engineering_meaning`
- `structured_result.premises`
- `structured_result.failure_modes`
- `structured_result.next_action`
- `structured_result.claims` copied from evidence-bound upstream claims
