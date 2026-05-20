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

## Phase-0 Answering Model

Phase-0 S3 produces cited sentence selections from retrieved chunks. It is not yet an LLM synthesis layer. Clean synthesized prose is deferred until the API client / model integration objective activates.

## Guardrails

- Never answer without retrieved evidence.
- Never fill retrieval gaps with model-world knowledge.
- Every returned claim must be tied to a documented chunk citation.
- Match the dominant source language.
- Keep S4 engineering analysis and S5 formula derivation deferred.

