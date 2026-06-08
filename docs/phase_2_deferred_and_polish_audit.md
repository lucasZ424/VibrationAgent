# Phase-2 Deferred And Polish Audit

Updated: 2026-06-08

## Freeze Summary

Phase 2 completed the local personal knowledge-base runtime and Obj17/18
low-risk polish. No unresolved Phase-2 polish item blocks Obj19 freeze.

Items below are accepted residual risks or explicit Phase-3/operator scope. They
should not be treated as forgotten Phase-2 work.

## Completed Polish Before Freeze

- Obj17 O1: README now documents that PR blocking requires branch protection to
  mark the `fast regression` GitHub Actions check as required.
- Obj17 O2: README/progress now document that nightly failure notification uses
  GitHub Actions notification settings unless an explicit notify step is added.
- Obj17 O3: 5-minute fast timeout remains intentional; PR/push also runs the
  cheap Phase-2 contract E2E.
- Obj18 O4: `test_phase2_end_to_end.py` now states that S2/S3 are injected on
  purpose and real S1/S2/S3 fixture-chain coverage lives in existing fixture
  chain tests.
- Obj18 O5: PR/push CI now runs the cheap Phase-2 contract E2E explicitly even
  though the tests remain marked integration for suite partitioning.
- Obj18 O6: README, progress, and `scripts/manual_e2e.py` now state that the
  optional S3 LLM path is captured-response replay, not a live provider call.

## Accepted Runtime Limits

- V2 citation checking is deterministic and lexical. It blocks visible fake
  references and obvious mismatches, but it does not prove semantic entailment.
- S4 engineering analysis is deterministic evidence-bound framing, not a deep
  semantic engineering reasoner.
- S5 formula derivation is deterministic scaffolding. It validates evidence and
  `axiomatic` steps, but it does not perform symbolic proof or generate
  LaTeX/MathML.
- V3 is advisory. It records reviewer notes and can trigger supervisor fallback,
  but it does not block ordinary answers.
- The supervisor loop has an injectable client seam and fail-safe fallback. A
  live Opus client and real GPT correction executor are not shipped in Phase 2.
- Online S3 LLM validation remains manual/captured-response only until a
  provider client is explicitly wired.

## Accepted Dependency Limits

- Qdrant is opt-in and requires a local embedding model plus a live Qdrant
  instance for real vector search. The deterministic token-feature lane remains
  the default fallback.
- Postgres qa_logs persistence is opt-in. Disabled/offline mode skips
  persistence; write failures become warnings and do not change answer status.
- Live Qdrant/Postgres roundtrip tests skip when dependencies or instances are
  unavailable.
- Large-corpus real-book benchmarking is a manual/operator run. CI runs the
  fixture large-corpus smoke and one-page benchmark sample.
- Token cost remains `null` unless an LLM-backed S3 path returns usage data.

## Accepted API/Deployment Limits

- The API is still a local personal deployment surface by default. Auth, CORS,
  and rate limiting exist but are disabled unless configured.
- The rate limiter is in-memory and process-local.
- CORS middleware is configured at app import time from default settings.
- Dependency health checks are best-effort and only run when the corresponding
  dependency is enabled.
- Branch protection and guaranteed alert routing are repository/operator
  configuration, not YAML-only behavior.

## Accepted Fixture/Ingestion Limits

- DOCX pagination is logical, not rendered physical pagination.
- DOCX image assets are relationship-ordered and pinned to logical page 1.
- OCR quality for scanned PDFs remains outside the deterministic fixture suite.
- `citation_anchor` is a display string, not a stable identifier.

## Phase-3 Candidate Scope

- S6 literature search.
- S7 model selection.
- S8 experiment advice.
- Web UI.
- k8s/shared/remote deployment hardening.
- Multi-tenant authz and durable rate limiting.
- Full observability stack.
- Live OpenAI/Anthropic provider clients for S3 and supervisor flows.
- Real GPT correction executor inside the supervisor loop.
- Stronger semantic entailment checking beyond V2 lexical support.
- Rendered DOCX pagination and richer image/formula layout anchoring.
- LaTeX/MathML generation and symbolic derivation checks.
- Redis runtime cache access.
- Operator-run full large-corpus baseline against the user's real corpus.

## Environment Note

The local Windows sandbox repeatedly produced pytest temp-dir
`PermissionError` failures unrelated to assertions. Ordinary PowerShell runs can
use a clean, unique `--basetemp` or the repaired `%TEMP%\pytest-of-zhoul` ACL.
This is recorded as an environment issue, not Phase-2 product behavior.
