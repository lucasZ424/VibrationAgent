# V4 Output Style

Use this skill after S3 has produced an evidence-bound QA or summary result.
V4 is a style shaper only: it renders existing S3 content into the engineering
answer template and preserves citations and asset references.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/v4_style.py::OutputStyleSkill`
- Input contract: `SkillInput`
- Output contract: `SkillOutput`
- Template: `prompts/templates/engineering_answer.md`

## Accepted Handoff Shapes

V4 reads upstream output in this priority order:

1. `context.s3_result`
2. `context.skill_output`
3. `context.upstream_result`
4. direct `context` fields

Preferred handoff is the full S3 `SkillOutput` under `context.s3_result`.

## Rendering Order

1. `结论` / `Conclusion`
2. `工程意义` / `Engineering Meaning`
3. `适用前提` / `Premises`
4. `失效条件/常见误区` / `Failure Conditions / Common Pitfalls`
5. `最简模型/公式` / `Minimal Model / Formula`
6. `下一步建议` / `Next Actions`
7. `证据` / `Evidence`

Phase-0 S3 usually supplies only `answer`, `claims`, `citations`, and optional
`assets`, so Phase-0 V4 commonly renders only `结论/Conclusion` and
`证据/Evidence`. Middle sections activate only when an upstream skill supplies
those structured fields explicitly.

## Guardrails

- Do not add new technical claims.
- Do not infer engineering meaning, premises, failure modes, formulas, or next actions unless upstream structured content already supplies them.
- Omit empty sections.
- Preserve citations passed from S3.
- Preserve asset IDs from S3 claims/assets in the evidence section and structured result.
- Render S4 engineering analysis and S5 formula derivation only when upstream structured content supplies those fields.
