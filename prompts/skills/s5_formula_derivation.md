# S5 Formula Derivation

Runtime implementation: `src/vibration_agent/skills/s5_formula_derivation.py`.

S5 is an optional derivation layer inserted after S3 and before V2.
Obj15 S5 is deterministic scaffolding: it structures cited formulas into
premise/steps/conclusion, but it does not perform deep symbolic algebra or
generate new LaTeX/MathML.

Run only when `user_mode="derivation"` and cited evidence is available from S2.

Rules:
- Output premise -> steps -> conclusion.
- Every evidence step must cite a visible `chunk_id`.
- Axiomatic math steps may omit citations, but must be marked
  `source_type="axiomatic"`.
- Do not invent formulas, units, parameters, or measured values.
- If cited evidence is missing or the step graph is invalid, return
  `insufficient`.

V2 must check S5 output before V4 renders it.
