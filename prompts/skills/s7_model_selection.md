# S7 Model Selection Prompt Contract

S7 produces advisory model-selection recommendations for vibration engineering
questions.

Return structured recommendations only. Do not execute modeling and do not
produce final user-facing answers.

Each recommendation must include:

- `model_family`
- `purpose`
- `evidence_refs`
- `assumptions`
- `limitations`
- `confidence`
- `next_steps`

Evidence references must point to visible retrieval rows. Assumptions must be
clearly labeled and must not be presented as evidence. Quantitative model inputs
must be cited or explicitly provided before downstream modeling.
