# S3 QA Summary

Canonical skill package: `agent_skills/s3_qa_summary/SKILL.md`.

This prompt-side file is kept as a legacy alias for older prompt loaders. The
runtime implementation is `src/vibration_agent/skills/s3_qa_summary.py`.

## Phase-3 Obj4 LLM Synthesis Contract

LLM-backed S3 is disabled by default and may only run when explicitly enabled by
configuration or request constraints. Enabling the flag alone does not create a
live provider client; the runtime must inject an `llm_client`, otherwise S3 logs
a warning and falls back to deterministic synthesis. When active:

- Use only retrieved S2 evidence.
- Do not answer if evidence is missing or insufficient.
- Return JSON only, with `status`, `answer`, `claims[]`, and optional
  `warnings`.
- Every claim must include `text`, `chunk_id`, `doc_id`, `pages`, and
  `evidence_type`.
- Every claim must include a visible `[chunk_id]` citation in `answer`, and the
  chunk id must come from supplied S2 evidence.
- On model failure, timeout, quota, or malformed output, runtime falls back to
  deterministic S3 and records a warning.
- Runtime still sends LLM output through V2. Claims that cite invisible chunks or
  fabricate significant numbers, units, or symbols are stripped by V2 before V4.
- Replay requests bind `s3_qa_summary.v1`, `s3.v1`, model,
  `max_tokens`, reasoning effort, text verbosity, and request body into the
  fixture hash.
