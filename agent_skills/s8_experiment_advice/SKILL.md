# S8 Experiment Advice

Use this skill only when explicitly requested for vibration measurement,
experimental validation, sensor-placement, or test-boundary advice. It is
default-off and is not part of the normal TutorOrchestrator query chain.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s8_experiment_advice.py::ExperimentAdviceSkill`
- Input contract: `SkillInput`
- Output contract: `SkillOutput`
- Prompt reference: `prompts/skills/s8_experiment_advice.md`

## Behavior

S8 produces evidence-bound experiment plans from visible S2 retrieval evidence.
It separates confirmed facts, assumptions, required measurements, sensor layout,
validation steps, and safety limits.

## Guardrails

- Never produce an experiment plan without visible evidence.
- Keep confirmed facts tied to evidence refs.
- Label assumptions separately from documented facts.
- Do not invent numeric thresholds, alarm limits, sampling rates, clearances, or
  acceptance criteria.
- Keep S8 out of ordinary routing until the Phase-4 routing activation gate.
