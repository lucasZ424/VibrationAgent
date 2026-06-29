# Phase 5 Candidate Scope

Date: 2026-06-29

## Status

Phase 5 is not active. Phase 4 and its R1-R3 local iterations are formally
closed. This document is the durable home for candidates that must not be
treated as Phase-4 completion work.

The current product posture remains local-first and single-user. Before any
remote/shared expansion, the project should spend a local iteration cycle on
real operation, backend reliability, corpus quality, and taxonomy coverage.

## Recommended Pause Before Phase 5

Do not start remote/shared expansion immediately after Phase 4 unless the
deployment target has changed. The higher-value next work is local validation:

- run the local API/operator UI against real engineering questions;
- ingest and inspect a representative vibration corpus;
- expand taxonomy terms, symbols, units, aliases, and bilingual mappings from
  real misses;
- measure retrieval misses and citation failures against that corpus;
- improve local backend ergonomics and failure visibility only where real runs
  expose friction.

## Phase 5 Candidates

These candidates require a new objective and explicit acceptance criteria before
implementation:

- RAG answer reliability: a labeled real-question set spanning definition,
  mechanism, comparison, diagnosis, workflow, standards, and formulas;
- independent lexical and ANN retrieval with measured recall, rather than BM25
  limited to the ANN candidate set;
- evidence selection, adjacent-passage expansion, and reranking before S3;
- controlled API construction of GPT answer and Opus supervisor clients, with
  provider/model/usage/cost traces and budgets that permit the selected loop;
- answer-quality calibration against human usable/unusable labels, with V2
  faithfulness as a hard gate rather than an unweighted display field;

- multi-user identity and authorization;
- tenant/data isolation for documents, chunks, logs, cache, and model outputs;
- durable distributed rate limiting;
- remote/shared metrics, tracing, log shipping, and alerting;
- public ingress, TLS/reverse-proxy deployment, container or k8s hardening;
- remote secret storage, provider-key ownership, and key rotation;
- multi-user audit trails and administrative action logging;
- V2-compatible external-evidence contract for S6 literature records;
- rendering UI for DOCX anchors and formula metadata;
- multi-page DOCX block-to-rendered-page mapping;
- optional production symbolic checker if labeled eval demand justifies it;
- retrieval replacement or Qdrant reindex only after a real recall gap and a
  candidate satisfy the Obj2/Obj4 gate;
- model-backed V2 entailment only as a separate default-off, replay-first
  objective.

## Entry Gate

Remote/shared candidates require the Obj16 revisit gate:

- target deployment;
- identity and authorization model;
- tenant/data isolation boundary;
- secrets ownership;
- durable storage and rate-limit backend;
- logging/metrics retention and redaction policy;
- security test plan and rollback path.

Local iteration candidates require real-run evidence: replay failures,
retrieval misses, unsupported citation examples, taxonomy gaps, or operator
workflow friction captured from actual use.
