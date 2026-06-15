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
2. Retrieval recall audit and dataset: complete
3. Optional embedding provider upgrade: complete
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

## Obj2 Notes

- Added `scripts/retrieval_eval.py`, an offline retrieval recall audit runner
  that consumes `tests/fixtures/retrieval/targets.json` and the fixture chunk
  corpus under `tests/fixtures/chunks/*.jsonl`.
- Added `tests/eval/test_retrieval_eval.py` to verify the report shape,
  `top_k_recall@5`, `top_k_recall@10`, expected-miss accounting, and per-case
  diagnostics.
- The runner uses the real `vibration_agent.retrieval.hybrid.search()` path.
  It does not call S3/S4/S5/V2/V4, live providers, Qdrant, or external network
  services.
- The report separates evidence-bearing recall cases from expected-miss cases.
  Expected-miss cases are excluded from recall denominators.
- The default fixture audit currently has 3 evidence cases and 1 expected-miss
  case. Evidence cases reached `top_k_recall@5 = 1.0` and
  `top_k_recall@10 = 1.0`.
- The expected-miss case returns weak non-target hits and is therefore reported
  in `unexpected_expected_miss_hits`, not as a recall failure.
- Obj2 review polish added an explicit Obj4 replacement gate to the report:
  replacement is justified only if baseline `top_k_recall@10 < 0.80` or
  `missing_evidence_cases >= 1`, and a candidate must fix at least one miss
  without lowering recall on other evidence targets.
- The current fixture baseline has `top_k_recall@10 = 1.0` and 0 missing
  evidence cases, so replacement is not justified yet.
- Obj2 review polish also added a synthetic retrieval-miss test to prove
  `missing_evidence_cases` is populated when an expected chunk exists but is
  not retrieved.
- No retrieval replacement, embedding provider change, runtime schema change,
  API change, or chain-order change was introduced.

## Obj2 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_retrieval_eval.py tests\eval\test_phase4_obj1_eval_assets.py tests\eval\test_llm_eval.py -q -p no:cacheprovider
```

Result after Obj2 review polish: passed, 8 tests.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj2_retrieval_eval.json
```

Result after Obj2 review polish: passed. Report wrote 4 cases, 3 evidence
cases, 1 expected-miss case, `top_k_recall@5 = 1.0`,
`top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj2 -p no:cacheprovider
```

Result after Obj2 review polish: passed, 387 tests; 2 skipped; 1 deselected; 1
qdrant compatibility warning.

## Obj2 Residual Risk

- The default audit set is intentionally small and fixture-based. It proves the
  evaluation path and catches regressions on labeled fixture targets, but it is
  not a large-corpus recall benchmark.
- The expected-miss target currently returns weak non-target hits. That is a
  precision/threshold diagnostic for later retrieval work, not evidence that
  the expected chunk is missing.
- Obj2 explicitly does not justify replacement on the current fixture baseline.
  Obj3/Obj4 still need a candidate that satisfies the written replacement gate
  before changing defaults.

## Obj2 Next Obj Gate

- Cleared for Obj3 after user review of Obj2 artifacts.

## Obj3 Notes

- Added an explicit optional OpenAI embedding provider path in
  `src/vibration_agent/retrieval/embeddings.py`.
- Default embedding behavior remains deterministic:
  `configs/embeddings.yaml` still uses `provider: sentence_transformers`,
  `local_files_only: true`, and token-feature fallback.
- OpenAI embeddings are used only when `EMBEDDING_PROVIDER=openai` or the YAML
  provider is explicitly changed to `openai`.
- Real OpenAI embedding client construction is lazy and forbidden under pytest;
  without an injected client during tests, it falls back to token-feature
  retrieval with a warning.
- Added embedding config fields: `api_key_env` and `timeout`, with environment
  overrides `EMBEDDING_API_KEY_ENV` and `EMBEDDING_TIMEOUT`.
- Added environment overrides for existing embedding fields:
  `EMBEDDING_MODEL_VERSION`, `EMBEDDING_ENABLED`,
  `EMBEDDING_LOCAL_FILES_ONLY`, and
  `EMBEDDING_FALLBACK_TO_TOKEN_FEATURES`.
- Added OpenAI to the `embeddings` optional dependency extra in
  `pyproject.toml` so explicit OpenAI embedding users can install the needed
  SDK through the embedding feature set.
- No Qdrant reindex, retrieval replacement, API change, chain-order change, or
  live provider validation was performed.

## Obj3 Review Polish

- Resolved the Obj3 default-off review issue by changing embedding defaults to
  `enabled: false` in code and YAML. Explicit `EMBEDDING_ENABLED=true` still
  enables a real provider path.
- Disabled embeddings now fall back to token-feature retrieval without adding a
  warning, preserving warning-free default QA behavior.
- Added a pytest guard before real `sentence_transformers` model loading, so CI
  cannot accidentally trigger a heavy model load or network-backed model
  resolution through embedding config drift.
- Added OpenAI embedding parser coverage for object-response and `model_dump`
  response shapes.

## Obj3 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_embeddings.py tests\unit\test_config_env_file.py tests\unit\test_s2_retrieval_skill.py tests\eval\test_retrieval_eval.py -q -p no:cacheprovider
```

Result: passed, 33 tests.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_embeddings.py tests\unit\test_config_env_file.py tests\unit\test_s2_retrieval_skill.py tests\eval\test_retrieval_eval.py -q -p no:cacheprovider
```

Result: passed, 38 tests.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj3_retrieval_eval.json
```

Result: passed. Default fixture baseline remains `top_k_recall@5 = 1.0`,
`top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj3_review_polish_retrieval_eval.json
```

Result: passed. Default fixture baseline remains `top_k_recall@5 = 1.0`,
`top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj3 -p no:cacheprovider
```

Result: passed, 390 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj3-review-polish -p no:cacheprovider
```

Result: passed, 395 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

## Obj3 Residual Risk

- OpenAI embedding live behavior was not validated in this objective. The
  implementation is covered with an injected fake client and pytest fallback
  guard only.
- Embedding dimension changes are not applied to Qdrant in Obj3. Obj4 still
  owns dimension migration, reindex, and replacement decisions.
- Provider aliases, pricing, latency, and API behavior remain operational risks
  for manual/live use.

## Obj3 Next Obj Gate

- Cleared for Obj4 after user review of Obj3 artifacts. Obj4 must still use the
  written replacement gate from Obj2 before changing retrieval defaults.

## Obj4 Notes

- Added retrieval lane attribution to `retrieval_context`: each context row now
  exposes `retrieval_lanes`, `retrieval_contribution`, `lane_scores`, and
  `source_priority`.
- Extended `scripts/retrieval_eval.py` diagnostics with
  `top_hit_contributions`, so Obj4 reports can distinguish BM25/token, dense,
  and hybrid contribution without evaluating synthesis.
- Added `scripts/qdrant_reindex_gate.py`, an offline Obj4 gate runner that
  evaluates the Obj2 replacement gate before allowing any Qdrant reindex
  attempt.
- Current Obj4 decision is explicit non-replacement: baseline recall remains
  above the Obj2 threshold and no missing evidence cases exist, so no Qdrant
  reindex or default retrieval replacement was performed.
- Qdrant remains opt-in through existing settings; unavailable Qdrant still
  falls back through the existing dense/token path.

## Obj4 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s2_retrieval_skill.py tests\unit\test_qdrant.py tests\integration\test_qdrant_roundtrip.py tests\eval\test_retrieval_eval.py tests\eval\test_qdrant_reindex_gate.py -q -p no:cacheprovider
```

Result: passed, 29 tests; 1 skipped when live Qdrant is unavailable.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj4_retrieval_eval.json
```

Result: passed. Default fixture baseline remains `top_k_recall@5 = 1.0`,
`top_k_recall@10 = 1.0`, and
`replacement_justified_by_baseline = false`. Diagnostics now include
`top_hit_contributions`.

```powershell
.\.venv\Scripts\python.exe scripts\qdrant_reindex_gate.py --output data\exports\ci\phase4_obj4_qdrant_reindex_gate.json
```

Result: passed. Gate report decision is `non_replacement`; `replacement.allowed`
is false; `reindex.allowed` is false; `reindex.executed` is false.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj4 -p no:cacheprovider
```

Result: passed, 396 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

## Obj4 Residual Risk

- No live Qdrant reindex was run because the Obj2 replacement gate did not
  justify retrieval replacement.
- No real embedding candidate was benchmarked against a recall gap in Obj4.
  Future reindex work must first satisfy the Obj2 gate and explicitly enable a
  provider/Qdrant path.

## Obj4 Next Obj Gate

- Cleared for Obj5 after user review of Obj4 artifacts. Obj5 remains scoped to
  deterministic V2 evidence-support hardening.

## Obj5 Notes

- Hardened deterministic V2 support checks without adding model-backed
  entailment or live provider calls.
- Added calibrated paraphrase support groups for vibration wording such as
  `zeta`/damping and runup/passage wording, so legitimate low-overlap
  engineering paraphrases can pass when multiple deterministic support groups
  align.
- Added deterministic conflict checks for:
  - direction reversal, such as evidence saying damping reduces resonance
    response while the claim says damping increases it;
  - numeric/unit values bound to a different quantity term, such as citing a
    visible `3000 rpm` shaft speed as a critical speed.
- Updated V2 calibration reporting from baseline-relative pass/fail to true
  label pass/fail: report schema is now `phase4.v2_calibration.report.v3`.
- Updated the Obj1 calibration fixture's `expected_current_supported` labels for
  the three pre-Obj5 known gaps so the current baseline reflects Obj5 behavior.
- No structured V2 result fields, API shape, chain order, or model provider path
  changed.

## Obj5 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\eval\test_phase4_obj1_eval_assets.py -q -p no:cacheprovider
```

Result: passed, 24 tests.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\eval\test_phase4_obj1_eval_assets.py -q -p no:cacheprovider
```

Result: passed, 26 tests.

```powershell
.\.venv\Scripts\python.exe scripts\v2_calibration_eval.py --output data\exports\ci\phase4_obj5_v2_calibration.json
```

Result: passed. Calibration report has `passed_count = 11`, `failed_count = 0`,
`false_allow = 0`, `false_block = 0`, `supported_precision = 1.0`,
`supported_recall = 1.0`, `unsupported_block_rate = 1.0`, and
`over_block_count = 0`.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe scripts\v2_calibration_eval.py --output data\exports\ci\phase4_obj5_review_polish_v2_calibration.json
```

Result: passed with the same scorecard: `false_allow = 0`, `false_block = 0`,
`supported_precision = 1.0`, `supported_recall = 1.0`,
`unsupported_block_rate = 1.0`, and `over_block_count = 0`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\unit\test_tutor_orchestrator.py tests\eval\test_phase4_obj1_eval_assets.py tests\eval\test_llm_eval.py -q -p no:cacheprovider
```

Result: passed, 40 tests.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_v2_citation_check.py tests\unit\test_tutor_orchestrator.py tests\eval\test_phase4_obj1_eval_assets.py tests\eval\test_llm_eval.py -q -p no:cacheprovider
```

Result: passed, 42 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj5 -p no:cacheprovider
```

Result: passed, 399 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj5-review-polish -p no:cacheprovider
```

Result: passed, 401 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

## Obj5 Residual Risk

- The hardening is still deterministic and table/rule based. It catches the
  Obj1 calibration gaps but is not a general semantic entailment checker.
- Synonym and quantity-term coverage is intentionally narrow to avoid hidden
  over-allowing. Future calibration cases should expand the tables only when
  labeled evidence supports the expansion.
- Post-review polish removed corrupted damping-symbol entries from the support
  table and replaced them with real damping vocabulary/symbols (`damping`,
  `damping ratio`, `zeta`, `ζ`, `阻尼`, `阻尼比`).
- The direction-conflict heuristic is now scoped to matching evidence clauses
  that share at least two non-direction anchors with the claim, reducing
  over-block risk when a chunk contains opposite directions for different
  quantities.

## Obj5 Next Obj Gate

- Cleared for Obj6 after user review of Obj5 artifacts. Obj6 must remain
  default-off, replay-first, and manual-live-only for external literature search.

## Obj6 Notes

- Added `LiteratureSearchSkill` as a default-off S6 prototype in
  `src/vibration_agent/skills/s6_literature_search.py`.
- S6 replay fixtures are the CI/default path. Manual live search is allowed only
  when an explicit live gate is set and an operator injects a live client.
- Named manual live sources are Semantic Scholar Graph API
  (`semantic_scholar`) and arXiv API (`arxiv`).
- Added replay fixtures under `tests/fixtures/literature/` for Semantic Scholar
  and arXiv-shaped candidates.
- S6 output schema is `s6.literature_search.v1`; replay fixture schema is
  `phase4.s6_literature_fixture.v1`.
- Added capture redaction for API keys, bearer tokens, local paths, and long raw
  text before captured data is promoted.
- Added `agent_skills/s6_literature_search/SKILL.md` and
  `prompts/skills/s6_literature_search.md`.
- `LiteratureSearchSkill` is exported lazily from `vibration_agent.skills` so
  importing the active skill package does not load deferred S6 modules.
- S6 remains outside `TutorOrchestrator` default routing. It stays listed in
  `PHASE0_DEFERRED_SKILLS` until the separate routing activation gate.
- S6 candidates are research context only; they are not final answers and must
  still pass through later V2/V4-bound synthesis if used.

## Obj6 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s6_literature_search.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 23 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s6_literature_search.py tests\unit\test_tutor_orchestrator.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 37 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj7 -p no:cacheprovider
```

Result: passed, 415 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj6 -p no:cacheprovider
```

Result: passed, 408 tests; 2 skipped; 1 deselected; 1 qdrant compatibility
warning.

## Obj6 Residual Risk

- No real Semantic Scholar or arXiv request was run. Live use still requires an
  explicit manual operator command and injected client.
- S6 is not automatically routed from normal user queries; routing activation is
  still owned by Obj9.
- Candidate quality depends on replay/live source quality. Obj6 only captures
  structured literature candidates and does not synthesize claims into answers.
- There is no dedicated S6 capture script yet. `redact_capture()` is covered and
  exported for manual use; a small capture command should be added before
  routinely promoting live captures.
- S6 `evidence_anchors` refer to external literature records, not internal
  `chunk_id` evidence. Obj9 must decide whether routed S6 use requires
  ingestion into the local corpus or a V2-compatible external-evidence contract.

## Obj6 Next Obj Gate

- Cleared for Obj7 after user review of Obj6 artifacts. Obj7 must remain
  default-off and cannot enter ordinary routing before the routing activation
  gate.

## Obj7 Notes

- Added `ModelSelectionSkill` as a default-off S7 advisory prototype in
  `src/vibration_agent/skills/s7_model_selection.py`.
- S7 recommends model families only from visible S2 evidence and explicit
  deterministic assumptions. It does not execute modeling, estimate parameters,
  or invent numeric thresholds.
- Model recommendations require visible evidence refs; query wording alone does
  not trigger a recommendation.
- Each recommendation separates `evidence_refs`, `assumptions`, `limitations`,
  `confidence`, and `next_steps`.
- Current calibrated model families are:
  `critical_speed_runup_response`,
  `rotor_unbalance_synchronous_response`, and
  `bearing_fault_envelope_analysis`.
- Added `agent_skills/s7_model_selection/SKILL.md` and
  `prompts/skills/s7_model_selection.md`.
- `ModelSelectionSkill` is exported lazily from `vibration_agent.skills` so
  importing active skills does not load deferred S7 modules.
- S7 remains outside `TutorOrchestrator` default routing and remains listed in
  `PHASE0_DEFERRED_SKILLS` until the routing activation gate.

## Obj7 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s7_model_selection.py tests\unit\test_tutor_orchestrator.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 37 tests.

## Obj7 Residual Risk

- S7 uses narrow deterministic keyword rules. It is useful for explicit advisory
  routing but is not a general model-selection expert system.
- No live provider or model-backed reasoning path exists in Obj7.
- S7 outputs are advisory context only. Future routed use must still preserve
  V2/V4-bound synthesis or return explicit handoff/limitation.
- Obj9 must decide how advisory assumptions/limitations pass through routing
  while still V2-gating factual claims.

## Obj7 Next Obj Gate

- Cleared for Obj8 after user review of Obj7 artifacts. Obj8 must remain
  default-off and out of ordinary routing until Obj9 activation.
