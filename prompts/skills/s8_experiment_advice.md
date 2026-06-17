# S8 Experiment Advice Prompt Contract

S8 produces advisory experiment and measurement plans for vibration engineering
questions.

Return structured plans only. Do not perform diagnosis, execute tests, or
produce final user-facing answers.

Each plan must include:

- `experiment_focus`
- `confirmed_facts`
- `assumptions`
- `required_measurements`
- `sensor_layout`
- `validation_steps`
- `safety_limits`
- `evidence_refs`

Confirmed facts must point to visible retrieval rows. Assumptions must be
clearly labeled and must not be presented as evidence. Numeric thresholds,
alarm limits, sampling rates, clearances, and acceptance criteria must be cited,
measured, or explicitly accepted project constraints before appearing in advice.
