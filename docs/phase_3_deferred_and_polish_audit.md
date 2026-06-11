# Phase-3 Deferred And Polish Audit

Updated: 2026-06-11

## Freeze Summary

Phase 3 completed the default-off model-backed S3/S4/S5 lanes, V2 LLM-output
hardening, Claude supervisor trial/correction loop, replay eval gate, and
manual live validation lane. No unresolved Phase-3 polish item blocks the Obj10
freeze.

Items below are accepted residual risks or explicit Phase-4/operator scope.
They should not be treated as forgotten Phase-3 work.

## Completed Polish Before Freeze

- Removed the legacy provider sampling parameter after OpenAI and Anthropic live
  lanes rejected or deprecated it.
- Fixed OpenAI Responses parsing for nested `output[].content[].text` payloads.
- Preserved incomplete/truncated provider payloads fail-loud instead of parsing
  partial JSON as valid model output.
- Normalized live Anthropic supervisor review responses that omit local
  `task_id` or use `message` / `code` fields for review issues.
- Hardened capture redaction for API keys, bearer tokens, long raw text, and
  local absolute paths.
- Ensured S4/S5 deterministic fallback outputs do not inherit upstream S3 cost
  metadata.
- Hardened manual summary cost aggregation so V2/V4 pass-through metadata is
  not counted as separate live spend.
- Reconciled Obj9 documentation so live validation is recorded as completed.

## Accepted Runtime Limits

- LLM-backed S3/S4/S5 remain default-off. The deterministic Phase-2 path is the
  frozen default behavior.
- V2 significant-item checking is structural and string-based. It blocks
  unsupported visible numbers, units, and common engineering symbols, but it is
  not deep semantic entailment.
- Citation faithfulness remains a V2-supported structural metric. It does not
  prove full engineering truth.
- S5 validates derivation-step structure and cited evidence support, but it is
  not a symbolic proof engine.
- Supervisor approval is a model-generated review signal bounded by schema
  validation, budget guards, correction limits, and deterministic fallback. It
  is not a formal proof of correctness.
- Captured live outputs require human inspection before promotion into
  committed replay fixtures.

## Accepted Dependency And Budget Limits

- OpenAI and Anthropic SDKs are lazy-imported and optional for package installs
  through the `llm` extra. `requirements_min.txt` includes them because that
  file is the project's initial urgent runtime dependency set, not the minimal
  packaging dependency list.
- Provider model aliases and prices can change. The frozen defaults are config
  values and may be overridden by YAML or environment variables.
- Local cost estimates are operational estimates only, not billing facts.
- Manual live probes can hit token or USD budget ceilings. Operators should set
  local `.env` budgets high enough for the intended validation run.
- Network failures remain live-only operational risks. CI remains replay-only.

## Accepted Capture Limits

- Redaction scrubs common local absolute path forms, secrets, bearer tokens, and
  long strings. Human review remains required before any captured fixture is
  promoted to `tests/fixtures/llm/`.
- Replay fixtures store redacted metadata and the original request hash. The
  hash validates fixture identity but is not recomputed from redacted metadata.
- Manual captures are written to `data\exports\manual_llm_fixtures` by default
  to avoid direct pollution of committed replay fixtures.

## Phase-4 Candidate Scope

- S6 literature search.
- S7 model selection.
- S8 experiment advice.
- Web UI.
- k8s/shared/remote deployment hardening.
- Multi-tenant authz and durable rate limiting.
- Full observability stack.
- Stronger semantic entailment beyond V2 structural checks.
- OpenAI embeddings or another retrieval replacement, isolated from synthesis
  changes so quality regressions remain attributable.
- Rendered DOCX pagination and richer image/formula layout anchoring.
- LaTeX/MathML generation and rendering.
- Symbolic proof or CAS-backed derivation checks.
- Broader golden eval sets and domain-calibrated unit/symbol support checks.
- Operator-run full large-corpus baseline against the user's real corpus.

## Freeze Follow-Up Notes

- Any Phase-4 work that changes provider request metadata, replay hash inputs,
  structured result keys, or chain order must be recorded as a post-freeze
  migration before callers are updated.
- Live validation commands stay manual-only. CI and nightly gates must remain
  replay/deterministic unless a future phase explicitly changes that boundary.

