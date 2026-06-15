# S7 Model Selection

Use this skill only when explicitly requested for analysis-model or modeling-route
advice. It is default-off and is not part of the normal TutorOrchestrator query
chain.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s7_model_selection.py::ModelSelectionSkill`
- Input contract: `SkillInput`
- Output contract: `SkillOutput`
- Prompt reference: `prompts/skills/s7_model_selection.md`

## Behavior

S7 recommends model families from visible S2 evidence and explicit assumptions.
It does not run simulations, identify parameters, compute thresholds, or execute
a modeling pipeline.

## Guardrails

- Never recommend a model family without visible evidence or an explicit
  assumption.
- Every recommendation must separate documented evidence, assumptions, and
  limitations.
- Do not invent numeric inputs, thresholds, bearing geometry, damping ratios, or
  critical-speed values.
- Keep S7 out of ordinary routing until the Phase-4 routing activation gate.
