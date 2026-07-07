# Phase 5 Scope

Date: 2026-07-07
Status: FROZEN / CLOSED AFTER OBJ10

## Phase Boundary

Phase 4 and its R1-R3 local iterations are formally closed. Phase 5 is a local,
single-user RAG answer-reliability phase. It closes measured gaps in retrieval,
evidence selection, synthesis, scoring, corpus quality, and local backend
operation; it does not add a new deployment or product surface.

The frozen Phase-4 chain remains the compatibility baseline:

```text
S2 -> S3 -> optional S4/S5 -> V2 -> V4 -> optional V3/supervisor
```

## Binding Product Discipline

Shared, remote, public, and multi-user deployment are deferred indefinitely.
They are not Phase-5 candidates, objectives, optional workstreams, or exit
gates. Phase 5 must not implement or reserve product scope for:

- multi-user identity, authorization, administration, or audit trails;
- tenant or shared-data isolation;
- public ingress, TLS/reverse-proxy, SaaS, or k8s deployment hardening;
- distributed rate limiting or remote observability infrastructure;
- remote secret ownership, storage, or rotation.

Only an explicit user-directed revision to `docs/vibration_agent_design.md` may
change this boundary. A normal objective, review finding, or deployment
convenience request cannot activate the deferred scope.

## In Scope

- a labeled real-question set covering definition, mechanism, comparison,
  diagnosis, workflow, standards, and formulas in Chinese and English;
- calibrated answer-quality evaluation with V2 faithfulness as a hard gate;
- independently measured lexical and ANN retrieval, bilingual expansion, and
  evidence-gated fusion;
- evidence selection, adjacent-passage expansion, and deterministic-first
  reranking before S3;
- controlled, default-off, replay-first GPT synthesis and Opus supervision with
  separate promotion gates and provider/model/usage/cost traces;
- corpus, filename, OCR, taxonomy, symbol, unit, and bilingual-alias quality;
- reproducible reindexing, PG:Qdrant parity, local dependency fast-fail, and
  operator diagnostics;
- backend/eval freeze followed by a final Phase-5 interface freeze.

## Deferred Local Capabilities

These remain outside the Phase-5 reliability critical path unless Obj1 evidence
shows they are required to close a labeled miss:

- V2-compatible external-evidence authority for S6 literature records;
- richer DOCX anchor/formula rendering UI;
- multi-page DOCX block-to-rendered-page mapping;
- a production symbolic checker;
- model-backed V2 entailment beyond the planned deterministic hard gate.

## Entry Gate

Phase 5 implementation may start only after Obj0 approves the canonical document
set and Obj1 owns the measurement baseline. Any later objective must trace to a
labeled miss or a measured local reliability failure.

## Exit Gate

Phase 5 is closed. The exit gate was:

- the real-question scorecard and human usability labels are committed;
- retrieval, answer completeness, and faithfulness meet the approved thresholds;
- live lanes remain opt-in, replayable, budgeted, and visibly degradable;
- reindexing is reproducible and PG:Qdrant parity is preserved;
- no remote/shared/multi-user scope entered the implementation;
- backend/eval and final interface freeze documents are complete.

Obj9 freezes the backend/eval subset in
`docs/phase_5_backend_interface_freeze.md`. Obj10 freezes the final Phase-5
interface in `docs/phase_5_interface_freeze.md`.

## Canonical Documents

- `docs/phase_5_scope.md`: binding scope and non-goals.
- `docs/phase_5_development_order.md`: objective order and acceptance rules.
- `docs/phase_5_progress.md`: per-objective execution ledger.
- `docs/phase_5_migrations.md`: contract and configuration migration ledger.
- `docs/phase_5_backend_interface_freeze.md`: Obj9 backend/eval freeze.
- `docs/phase_5_interface_freeze.md`: Obj10 final Phase-5 freeze.
- `docs/issue_log_p5/`: user-owned review findings.
