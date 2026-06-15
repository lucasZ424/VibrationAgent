# Phase 4 Progress

Updated: 2026-06-15

## Execution Model

Phase 4 proceeds one objective at a time. It starts from the frozen Phase-3
interface and must preserve deterministic/replay CI. Live provider calls and
large-corpus runs remain local/operator-only unless a future objective changes
that boundary through an explicit migration.

Every objective must record:

1. Implementation notes.
2. Verification commands and results.
3. Review issues and fixes in `docs/issue_log_p4/issues_objN.txt`.
4. Residual risks.
5. Whether the next objective gate is cleared.

Issue logs are user-review artifacts. Implementation agents should not generate
or edit them unless explicitly asked.

## Objective Status

0. Phase-4 execution baseline: pending
1. Broader replay eval, V2 calibration, and large-corpus baseline: pending
2. Retrieval recall audit and dataset: pending
3. Optional embedding provider upgrade: pending
4. Qdrant reindex and retrieval replacement gate: pending
5. Deterministic V2 evidence support hardening: pending
6. S6 literature search prototype: pending
7. S7 model selection prototype: pending
8. S8 experiment advice prototype: pending
9. S6/S7/S8 routing activation gate: pending
10. Rendered DOCX pagination and rich asset anchoring: pending
11. LaTeX/MathML rendering contract: pending
12. Symbolic proof / CAS feasibility spike: pending
13. Backend interface freeze: pending
14. Web UI read-only operator surface: pending
15. Local-first observability essentials: pending
16. Remote/shared hardening decision: pending
17. Phase-4 final interface freeze: pending

## Obj0 Notes

- `docs/phase_4_development_order.md` is the proposed Phase-4 development
  order.
- `docs/phase_4_progress.md` is the Phase-4 progress ledger.
- `docs/phase_4_migrations.md` is the Phase-4 contract/migration ledger.
- `docs/issue_log_p4/` is the local ignored Phase-4 review issue directory.
- Phase 4 starts from the frozen Phase-3 contracts in
  `docs/phase_3_interface_freeze.md`.
- 2026-06-15 plan review was incorporated before Obj1 code starts:
  deterministic V2 hardening was chosen for Obj5, Obj1 now owns calibration
  labels and retrieval targets, S6/S7/S8 routing activation is explicit,
  external/manual dependencies are named, backend freeze is split from final
  freeze, and deployment hardening is split into local-first essentials vs
  remote/shared decision.

## Obj0 Verification

- Pending.

## Obj0 Residual Risk

- This baseline is documentation-only. It does not implement any Phase-4
  runtime capability.
- Numeric thresholds are still to be filled by Obj1 artifacts, not guessed in
  Obj0.

## Obj0 Next Obj Gate

- Pending user review of the Phase-4 development order.
