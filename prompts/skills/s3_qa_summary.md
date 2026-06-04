# S3 QA Summary

Canonical skill package: `agent_skills/s3_qa_summary/SKILL.md`.

This prompt-side file is kept as a legacy alias for older prompt loaders. The
runtime implementation is `src/vibration_agent/skills/s3_qa_summary.py`.

## Phase-2 Obj9 LLM Synthesis Contract

LLM-backed S3 is disabled by default and may only run when explicitly enabled by
configuration or request constraints. Enabling the flag alone does not create a
live provider client; the runtime must inject an `llm_client`, otherwise S3 logs
a warning and falls back to deterministic synthesis. When active:

- Use only retrieved S2 evidence.
- Do not answer if evidence is missing or insufficient.
- Every claim must include a visible `[chunk_id]` citation from the supplied
  evidence.
- Return structured claims with `text` and `chunk_id`; unsupported or uncited
  claims must not be emitted.
- On model failure, timeout, quota, or malformed output, runtime falls back to
  deterministic S3 and records a warning.
