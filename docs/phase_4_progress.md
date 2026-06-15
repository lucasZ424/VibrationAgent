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

0. Phase-4 execution baseline: complete
1. Broader replay eval, V2 calibration, and large-corpus baseline: complete
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

- Phase-4 development order was reviewed by the user before Obj1 started.

## Obj0 Residual Risk

- This baseline is documentation-only. It does not implement any Phase-4
  runtime capability.
- Numeric thresholds are still to be filled by Obj1 artifacts, not guessed in
  Obj0.

## Obj0 Next Obj Gate

- Cleared by user review; Obj1 started afterward.

## Obj1 Notes

- Added two replay eval cases under `tests/fixtures/llm/`:
  `eval_fabricated_unit.json` and `eval_unstructured_answer.json`.
- Added `scripts/v2_calibration_eval.py`, a replay-only runner that executes
  the real deterministic V2 citation checker against labeled cases.
- Added `tests/fixtures/eval/v2_calibration/cases.json` with 11 calibration
  cases: 5 supported truth-label positives and 6 unsupported truth-label
  negatives. Three cases intentionally record known current-V2 gaps so Obj5 has
  measurable headroom.
- Added `tests/fixtures/retrieval/targets.json` with Obj2-ready recall target
  labels and required `top_k` values.
- Added focused tests in `tests/eval/test_phase4_obj1_eval_assets.py`.
- Obj1 review polish fixed the Chinese retrieval target chunk/doc id, added
  exact fixture chunk resolution coverage, converted V2 calibration to
  baseline-relative assertions, and tightened replay eval case-count coverage.
- Kept `scripts/bench_large_corpus.py` as the explicit operator-run baseline
  path. No large-corpus run was performed in this objective.
- No live provider, external network service, retrieval replacement, V2 rule
  change, schema change, API change, or chain-order change was introduced.

## Obj1 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_llm_eval.py tests\eval\test_phase4_obj1_eval_assets.py -q -p no:cacheprovider
```

Result after Obj1 review polish: passed, 5 tests.

```powershell
.\.venv\Scripts\python.exe scripts\v2_calibration_eval.py
```

Result after Obj1 review polish: passed with 11/11 baseline cases. Truth-label
confusion records supported recall 0.8, unsupported block rate 0.6666666667,
false allow 2, and false block 1.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase4_obj1_eval_scorecard.json
```

Result: passed and wrote the replay eval scorecard.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj1-polish -p no:cacheprovider
```

Result after Obj1 review polish: passed, 384 tests; 2 skipped; 1 deselected; 1
qdrant compatibility warning.

## Obj1 Residual Risk

- V2 calibration is a baseline set, not a new hardening implementation. It now
  exposes current deterministic V2 gaps for Obj5, but Obj5 still owns rule
  improvements and threshold decisions.
- Retrieval targets are labels for Obj2. Obj1 does not compute recall or decide
  whether retrieval replacement is justified.
- Large-corpus baseline remains operator-run only; this objective did not run
  against the user's real corpus.

## Obj1 Next Obj Gate

- Cleared for Obj2 after user review of Obj1 artifacts.
