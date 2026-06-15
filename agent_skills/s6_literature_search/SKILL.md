# S6 Literature Search

Use this skill only when explicitly requested for literature discovery,
paper lookup, or citation capture. It is default-off and is not part of the
normal TutorOrchestrator query chain.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s6_literature_search.py::LiteratureSearchSkill`
- Input contract: `SkillInput`
- Output contract: `SkillOutput`
- Prompt reference: `prompts/skills/s6_literature_search.md`

## Supported Sources

- Semantic Scholar Graph API (`semantic_scholar`) for the primary manual-live
  source.
- arXiv API (`arxiv`) for arXiv-only manual-live lookup.
- Replay fixtures under `tests/fixtures/literature/` for CI and deterministic
  regression.

## Guardrails

- Never call live external search unless an explicit manual live gate is present
  and a live client is injected by the operator.
- Keep replay fixtures as the CI source of truth.
- Redact API keys, bearer tokens, local paths, and long raw text before capture
  or promotion to fixtures.
- S6 candidates are research context only. They must not bypass S2/S3/S4/S5,
  V2 citation checks, V4 style shaping, or the later routing activation gate.
