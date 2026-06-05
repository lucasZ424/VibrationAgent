# S5 Formula Derivation

Use this skill when a vibration-agent answer needs a formula derivation after
S3 retrieval-grounded synthesis.

Runtime:
- Python skill: `src/vibration_agent/skills/s5_formula_derivation.py`
- Prompt note: `prompts/skills/s5_formula_derivation.md`

Activation:
- Run only for `user_mode="derivation"`.
- Require S2-visible cited evidence from S3.
- Skip with `insufficient` when evidence is missing or derivation steps are
  structurally invalid.

Output contract:
- `premises`
- `derivation_steps`
- `minimal_model`
- `conclusion`
- `claims`
- `assets`

Each derivation step must be either:
- `source_type="evidence"` with a visible `chunk_id`
- `source_type="axiomatic"` without a required citation

S5 must pass its output to V2 before V4 renders the final answer.

Obj15 note: the runtime is deterministic scaffolding. It threads formula asset
references and renders available formula text, but deep symbolic algebra and
LaTeX/MathML generation are future model-backed capabilities.
