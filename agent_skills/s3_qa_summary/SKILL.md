# S3 QA Summary

Use this skill after S2 retrieval when the user asks for a concept explanation,
section summary, whole-document summary, or evidence-grounded QA answer.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s3_qa_summary.py::QASummarySkill`
- Evidence helpers: `src/vibration_agent/knowledge/evidence.py`
- Input contract: `SkillInput`
- Output contract: `SkillOutput`

## Supported Modes

- `qa`
- `section_summary`
- `whole_doc_summary`

Mode can be supplied through `constraints.mode` / `context.mode`; otherwise S3
infers it from the user query and defaults to `qa`.

## Required Evidence

S3 requires retrieved text evidence from S2. Preferred input is
`context.retrieval_context`. It also accepts `retrieval_results`, `context.evidence`,
`context.chunks`, or `context.s2_result.structured_result.retrieval_context`.

## Answering Model

The default S3 path produces cited sentence selections from retrieved chunks.
Phase-2 Obj9 adds an explicitly feature-flagged LLM synthesis path. It is not
the default until V2 citation checking or an equivalent citation interception
layer is active in the main chain. The feature flag only enables the branch; a
runtime `llm_client` must still be injected by a future provider integration.

## Guardrails

- Never answer without retrieved evidence.
- Never fill retrieval gaps with model-world knowledge.
- Every returned claim must be tied to a documented chunk citation.
- LLM-backed claims must include visible `[chunk_id]` references in the answer.
- Match the dominant source language.
- Keep S4 engineering analysis and S5 formula derivation out of S3; they run as separate optional skills after S3.

