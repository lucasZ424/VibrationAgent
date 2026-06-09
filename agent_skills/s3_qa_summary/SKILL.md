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
Phase-3 Obj4 adds a replay/live-client synthesis path through the injected
`llm_client`. It remains disabled by default. The feature flag only enables the
branch; a runtime client must still be injected, and replay/live errors degrade
to deterministic S3.

LLM responses must be JSON with `status`, `answer`, `claims[]`, and optional
`warnings`. Each claim must include `text`, `chunk_id`, `doc_id`, `pages`, and
`evidence_type`. S3 preserves structured LLM claims and the orchestrator sends
them through V2 before V4, so invisible citations and fabricated significant
numbers/units/symbols are stripped before the final answer.

## Guardrails

- Never answer without retrieved evidence.
- Never fill retrieval gaps with model-world knowledge.
- Every returned claim must be tied to a documented chunk citation.
- LLM-backed claims must include visible `[chunk_id]` references in the answer.
- LLM-backed claims must use only visible S2 `chunk_id` values; V2 is the final
  enforcement layer.
- Match the dominant source language.
- Keep S4 engineering analysis and S5 formula derivation out of S3; they run as separate optional skills after S3.

