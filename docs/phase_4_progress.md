# Phase 4 Progress

Updated: 2026-06-29

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
4. Qdrant reindex and retrieval replacement gate: complete
5. Deterministic V2 evidence support hardening: complete
6. S6 literature search prototype: complete
7. S7 model selection prototype: complete
8. S8 experiment advice prototype: complete
9. S6/S7/S8 routing activation gate: complete
10. Rendered DOCX pagination and rich asset anchoring: complete
11. LaTeX/MathML rendering contract: complete
12. Symbolic proof / CAS feasibility spike: complete
13. Backend interface freeze: complete
14. Web UI read-only operator surface: complete
15. Local-first observability essentials: complete
16. Remote/shared hardening decision: complete
17. Phase-4 final interface freeze: complete
18. Post-freeze R1-R3 local iteration closure: complete

Phase 4 is formally closed. No additional feature objectives should be added to
this ledger.

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

## Obj8 Notes

- Added `ExperimentAdviceSkill` as a default-off S8 advisory prototype in
  `src/vibration_agent/skills/s8_experiment_advice.py`.
- S8 produces structured measurement and validation advice only from visible S2
  evidence rows. Query wording alone does not trigger an experiment plan.
- Each plan separates `confirmed_facts`, `assumptions`,
  `required_measurements`, `sensor_layout`, `validation_steps`,
  `safety_limits`, and `evidence_refs`.
- S8 actively omits numeric query terms that are not visible in evidence and
  records them in `omitted_unsupported_thresholds` instead of inserting them
  into the plan text.
- Current calibrated advice focuses are:
  `runup_or_resonance_validation`, `bearing_fault_measurement_plan`, and
  `synchronous_unbalance_validation`.
- Post-review polish added Chinese evidence keywords for all three calibrated
  advice focuses so S8 coverage matches the bilingual corpus expectation before
  Obj9 routing activation.
- Added `agent_skills/s8_experiment_advice/SKILL.md` and
  `prompts/skills/s8_experiment_advice.md`.
- `ExperimentAdviceSkill` is exported lazily from `vibration_agent.skills` so
  importing active skills does not load deferred S8 modules.
- S8 remains outside `TutorOrchestrator` default routing and remains listed in
  `PHASE0_DEFERRED_SKILLS` until the routing activation gate.

## Obj8 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s8_experiment_advice.py tests\unit\test_tutor_orchestrator.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 38 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj8-final -p no:cacheprovider
```

Result: passed, 423 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s8_experiment_advice.py tests\unit\test_tutor_orchestrator.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 39 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj8-polish -p no:cacheprovider
```

Result: passed, 424 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj8 Residual Risk

- S8 uses narrow deterministic keyword rules. It is useful for explicit
  measurement-planning advice but is not a general experiment-design expert
  system.
- No live sensor, device, or data-acquisition integration exists in Obj8.
- S8 only omits unsupported numeric terms from query text. Future routed use
  must ensure `omitted_unsupported_thresholds` remains an audit field, not
  rendered as measurement advice.
- Obj9 must decide whether and how S8 advisory assumptions and safety limits can
  enter normal routing without expanding unsupported answer authority.

## Obj8 Next Obj Gate

- Cleared for Obj9 after focused and non-large regression verification. Obj9
  owns any S6/S7/S8 routing activation; without that gate, S8 remains
  explicit-call-only.

## Obj9 Notes

- Added a deterministic advisory routing gate for S6/S7/S8 in
  `src/vibration_agent/agent/routing.py`.
- Added default-off routing settings:
  `advisory_routing_enabled`, `advisory_intent_routing_enabled`, and
  `advisory_allowed_skills`.
- The default query chain remains unchanged. If `advisory_routing_enabled` is
  not set by config, context, or constraints, S6/S7/S8 are not selected even
  when the query contains literature/model/measurement intent.
- Explicit activation path: set `advisory_routing_enabled=true` and provide
  `advisory_skills` / `routed_skills` / `activate_skills` using aliases such as
  `s6`, `s7`, `s8`, `literature`, `model_selection`, or `experiment_advice`.
- Intent activation path: only available when both
  `advisory_routing_enabled=true` and `advisory_intent_routing_enabled=true`.
  Deterministic query/user-mode terms may then select S6/S7/S8, optionally
  restricted by `advisory_allowed_skills`.
- `TutorOrchestrator` runs the advisory lane after V4 and before optional V3.
  The advisory lane appends structured handoff output under
  `structured_result["advisory_routing"]` and `skill_results["s6"|"s7"|"s8"]`;
  it does not rewrite or render the final V4 answer.
- Advisory outputs use `rendering="structured_handoff_only"` and
  `v2_v4_policy="do_not_render_as_final_answer"` so Obj9 does not expand answer
  authority without a later rendering/faithfulness design.
- Post-review polish reuses one settings object for model routing and advisory
  routing inside each `_run_chain` call, avoiding an extra Obj9 config load on
  the default path.
- Post-review polish added coverage for `difficulty=extreme` with advisory
  routing enabled, proving advisory handoff runs before V3 reviewer and does not
  change the V4 answer.

## Obj9 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_routing.py tests\unit\test_tutor_orchestrator.py tests\unit\test_s6_literature_search.py tests\unit\test_s7_model_selection.py tests\unit\test_s8_experiment_advice.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 63 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj9-final -p no:cacheprovider
```

Result: passed, 434 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_routing.py tests\unit\test_tutor_orchestrator.py tests\unit\test_s6_literature_search.py tests\unit\test_s7_model_selection.py tests\unit\test_s8_experiment_advice.py tests\unit\test_agent_control_plane.py -q -p no:cacheprovider
```

Result: passed, 64 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj9-polish -p no:cacheprovider
```

Result: passed, 435 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj9 Residual Risk

- S6 external literature remains structured handoff context only. External
  literature still needs ingestion or a V2-compatible external-evidence contract
  before it can support final answer claims.
- S7/S8 advisory assumptions, limitations, and safety text are not rendered as
  final answer claims by Obj9. A future rendering objective must decide how to
  present them without bypassing V2/V4 faithfulness.
- Intent routing uses deliberately narrow deterministic terms. Broader
  automatic routing should wait for replay eval coverage.

## Obj9 Next Obj Gate

- Cleared for Obj10 after focused and full non-large regression, provided
  review does not find routing-policy gaps. Obj10 can assume S6/S7/S8 have a
  controlled explicit advisory lane but are not automatically rendered into
  final answers.

## Obj10 Notes

- Added optional `OcrPage.metadata` for page-level parser metadata. The field
  defaults to an empty object and keeps existing page/chunk contracts backward
  compatible.
- Added `src/vibration_agent/ingestion/assets.py` with a shared
  `asset_anchor_metadata(...)` helper and anchor schema version
  `p4.rich_asset_anchor.v1`.
- Extended `parse_docx(...)` with `pagination_mode="logical|rendered"`.
  Logical mode remains the default and preserves Phase-3 DOCX page behavior.
- Added optional rendered DOCX pagination support through headless LibreOffice
  (`soffice`) DOCX-to-PDF conversion. CI does not require LibreOffice; the
  rendered lane is explicit and testable through injected/mocked page-count
  paths.
- Missing `soffice`, failed rendered-PDF inspection, and missing block-to-page
  layout mapping all fall back to the existing logical page while recording
  `metadata["docx_pagination"]` warnings/reasons.
- DOCX table and image assets now receive rich optional anchor metadata
  recording source, page anchor type, block id or DOCX relationship id, and
  rendered page number when safely known.
- Post-review polish redacts local paths from rendered DOCX fallback warnings
  before they are stored in `OcrPage.metadata["warnings"]`.
- Anchor metadata semantics: `anchor.page_no` remains the parser's logical page
  anchor; `anchor.rendered_page_no` is present only when a rendered backend can
  locate the asset on a rendered page without guessing.

## Obj10 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_docx_parser.py tests\unit\test_asset_model.py tests\unit\test_chunking_strategy.py tests\unit\test_classify.py -q -p no:cacheprovider
```

Result: passed, 28 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj10 -p no:cacheprovider
```

Result: passed, 438 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_docx_parser.py tests\unit\test_asset_model.py tests\unit\test_chunking_strategy.py tests\unit\test_classify.py -q -p no:cacheprovider
```

Result: passed, 29 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj10-polish -p no:cacheprovider
```

Result: passed, 439 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj10 Residual Risk

- Multi-page rendered DOCX block-to-page mapping is not implemented in Obj10.
  The rendered page count is recorded, but text/assets stay on the logical
  fallback page until a layout map is available.
- LibreOffice rendering is explicit and optional. CI and default ingestion do
  not require `soffice`.
- Rich asset anchors are metadata-only; downstream UI/rendering still decides
  how to display or navigate them.

## Obj10 Next Obj Gate

- Cleared for Obj11 after non-large regression, provided review does not require
  real LibreOffice integration on the CI path. Obj11 may assume DOCX assets carry
  optional rich anchor metadata and rendered DOCX pagination has a safe fallback.

## Obj11 Notes

- Added `FormulaRender` as the stable formula rendering representation with
  schema version `p4.formula_render.v1`.
- Added shared formula-rendering helpers for S5/V4. They build render metadata
  from formula assets or upstream `formula_renders` and keep `plain_text` as the
  mandatory fallback for CLI/API clients.
- S5 now emits additive `structured_result["formula_renders"]` for formula
  derivations. Existing `answer`, `minimal_model`, `assets`, and citations stay
  plain-text compatible.
- V4 now preserves/normalizes additive `formula_renders` while keeping final
  `structured_result["answer"]` as the existing markdown/plain-text engineering
  template.
- Invalid LaTeX/MathML markup is fail-loud but non-fatal: the render record is
  marked `invalid_markup`, invalid markup fields are omitted, `plain_text`
  remains available, and warnings are surfaced.
- Review polish extended LaTeX checks for common malformed-but-brace-balanced
  markup: `\frac` must have two braced arguments, and `\begin{...}` /
  `\end{...}` environments must match.
- Obj11 does not add symbolic proof, CAS, a frontend renderer, live provider
  calls, or a chain-order change.

## Obj11 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py tests\unit\test_v4_style_skill.py -q -p no:cacheprovider
```

Result: passed, 30 tests.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py tests\unit\test_v4_style_skill.py -q -p no:cacheprovider
```

Result: passed, 30 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py tests\unit\test_v4_style_skill.py tests\unit\test_tutor_orchestrator.py -q -p no:cacheprovider
```

Result: passed, 49 tests.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_s5_derivation.py tests\unit\test_v4_style_skill.py tests\unit\test_tutor_orchestrator.py -q -p no:cacheprovider
```

Result: passed, 49 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj11 -p no:cacheprovider
```

Result: passed, 444 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

Post-review polish command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj11-polish -p no:cacheprovider
```

Result: passed, 444 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj11 Residual Risk

- LaTeX validation is intentionally lightweight and deterministic. It catches
  malformed brace structure plus narrow `\frac` and environment-pair errors, but
  `status: renderable` is still not a full TeX-render success guarantee.
- MathML validation checks XML parseability and `<math>` root shape only. Real
  client rendering remains a UI responsibility.
- Formula metadata currently comes from explicit formula assets or upstream
  formula-render records; Obj11 does not infer formulas from arbitrary prose.

## Obj11 Next Obj Gate

- Cleared for Obj12 after focused and non-large regression verification. Obj12
  remains a feasibility spike and must not add a mandatory CAS dependency
  without a separate production objective.

## Obj12 Notes

- Added `docs/phase_4_symbolic_proof_spike.md`.
- Decision: do not add a mandatory CAS or symbolic proof dependency in Phase 4.
- Recommended future production shape, if needed, is a narrow optional
  default-off algebra checker for S5, not a replacement for S5, V2, or Obj11
  rendering validation.
- The spike separates three contracts:
  - V2 evidence support checks visible-evidence faithfulness.
  - Obj11 formula rendering checks markup representation and plain-text
    fallback.
  - Symbolic checking would only verify algebraic equivalence under declared
    assumptions.
- Candidate approaches were evaluated:
  - keep current S5 with no CAS as the Phase-4 default;
  - consider future optional SymPy narrow algebra checking only after eval
    labels exist;
  - avoid model-backed proof review as a CAS substitute;
  - reject external CAS services for the local-first backend freeze baseline.
- The document defines supported future formula classes, unsupported cases,
  dependency costs, fallback behavior, and the eval gate required before any
  production symbolic checker.
- Review polish added the domain-fit rationale, current S5 replay-fixture step
  count, SymPy inconclusive/version-risk note, timeout/complexity requirement,
  and event-driven revisit triggers.
- No code, dependency, schema, chain-order, provider, replay, retrieval, or
  citation contract changed in Obj12.

## Obj12 Verification

```powershell
git diff --check
```

Result: no whitespace errors.

```powershell
rg -i "\b(sympy|antlr|wolfram|symbolic_check)\b|\bCAS\b" pyproject.toml src tests
```

Result: no matches, so no mandatory CAS/symbolic dependency or runtime path was
added.

Post-review polish command:

```powershell
git diff --check
```

Result: no whitespace errors.

Post-review polish command:

```powershell
rg -i "\b(sympy|antlr|wolfram|symbolic_check)\b|\bCAS\b" pyproject.toml src tests
```

Result: no matches, so no mandatory CAS/symbolic dependency or runtime path was
added.

Post-review polish command:

```powershell
$files = Get-ChildItem tests\fixtures\llm -Filter 's5*.json'; foreach ($file in $files) { $json = Get-Content $file.FullName -Raw | ConvertFrom-Json; $steps = @($json.derivation_steps); $axiomatic = @($steps | Where-Object { $_.source_type -eq 'axiomatic' }); $evidence = @($steps | Where-Object { $_.source_type -eq 'evidence' }); Write-Output ("{0}: steps={1}; evidence={2}; axiomatic={3}" -f $file.Name, $steps.Count, $evidence.Count, $axiomatic.Count) }
```

Result: `s5_visible_multistep_response.json` has 3 steps / 2 axiomatic;
`s5_fabricated_step_number_response.json` has 2 steps / 1 axiomatic;
`s5_cycle_response.json` has 2 steps / 1 axiomatic.

## Obj12 Residual Risk

- The spike recommends a future optional checker but does not implement it.
- The future eval gate is specified, not populated with fixture cases.
- S5 remains structurally validated and evidence-bound, but not a formal
  symbolic proof engine.
- Current S5 fixture counts are small and not a large-corpus measurement. They
  support the defer decision only as local grounding, not as a statistical
  corpus claim.

## Obj12 Next Obj Gate

- Cleared for Obj13 backend interface freeze. Obj13 should freeze the Obj1-Obj12
  backend contracts and record that symbolic proof/CAS remains deferred unless a
  separate production objective adds an optional checker behind an eval gate.

## Obj13 Notes

- Added `docs/phase_4_backend_interface_freeze.md`.
- Added `docs/phase_4_deferred_and_polish_audit.md`.
- Updated `README.md` and `docs/architecture.md` so backend consumers and later
  UI/observability work point to the Phase-4 backend freeze rather than only the
  planning document.
- Froze Obj1-Obj12 backend contracts, including:
  - eval fixtures and runners;
  - retrieval recall and Qdrant replacement gates;
  - optional/default-off embedding provider boundary;
  - deterministic V2 evidence-support hardening boundary;
  - S6/S7/S8 advisory skill and routing status;
  - rendered DOCX pagination and rich asset anchor metadata;
  - Obj11 `FormulaRender` contract;
  - Obj12 CAS/symbolic-proof defer decision.
- Recorded that the default final-answer path remains V2/V4-bound.
- Recorded that S6/S7/S8 are default-off advisory handoff skills and do not
  render into final answers.
- Recorded that formula rendering metadata is not symbolic proof metadata and
  CAS remains deferred unless a future optional checker objective satisfies the
  documented eval gate.
- Review polish added an explicit Phase-3 freeze inheritance pointer to
  `docs/phase_4_backend_interface_freeze.md`, clarifying that Phase 4 is
  additive over `docs/phase_3_interface_freeze.md`.
- No runtime schema, dependency, code path, provider path, replay fixture,
  retrieval behavior, chain order, citation contract, or API response shape
  changed.

## Obj13 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\eval\test_llm_eval.py tests\eval\test_retrieval_eval.py tests\unit\test_tutor_orchestrator.py tests\unit\test_v2_citation_check.py tests\unit\test_v4_style_skill.py tests\unit\test_s5_derivation.py -q -p no:cacheprovider
```

Result: passed, 77 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj13 -p no:cacheprovider
```

Result: passed, 444 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase4_obj13_llm_eval.json
```

Result: passed. Report has 7 cases, 7 passed, 0 failed, pass rate 1.0, citation
faithfulness pass rate 1.0, and unsupported numeric block rate 1.0.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_obj13_retrieval_eval.json
```

Result: passed. Report has 4 cases, 3 evidence cases, 1 expected-miss case,
`top_k_recall@5 = 1.0`, `top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

Post-review polish command:

```powershell
git diff --check
```

Result: no whitespace errors; existing CRLF/LF warnings remain for `README.md`
and `docs/architecture.md`.

## Obj13 Residual Risk

- Obj13 is a documentation freeze. It does not implement UI, local
  observability, remote/shared hardening, retrieval replacement, external
  evidence contracts, or symbolic checking.
- The freeze records fixture-sized eval gates. Large-corpus and live-provider
  validation remain operator-run only.
- UI/observability work can still accidentally depend on internal fields unless
  it explicitly cites the freeze and records any API contract migration first.

## Obj13 Next Obj Gate

- Cleared for Obj14 read-only operator UI. Obj14 must treat the backend freeze
  as the source of truth for API/structured-result assumptions and record any
  UI-facing API contract change in `docs/phase_4_migrations.md` before callers
  are updated.

## Obj14 Notes

- Added a zero-build local operator UI under `apps/ui/`.
- Added FastAPI static routes:
  - `GET /operator`
  - `GET /operator/assets/{path}`
- The UI calls the existing `POST /query` contract and displays:
  - final answer text;
  - citations;
  - chain steps;
  - warnings;
  - supervisor status/action/invocation metadata;
  - token/cost metadata when present;
  - raw response JSON for inspection.
- The UI is read-only: no ingestion, delete, admin, remote/shared management,
  live-provider, or provider-key control was added.
- Optional API authentication remains the existing API token mechanism. The UI
  does not require live OpenAI/Anthropic keys.
- Updated `README.md` with the local `/operator` URL.
- Recorded the UI-facing API contract in `docs/phase_4_migrations.md` before
  treating it as an operator surface.
- Review polish documented and reconciled the bundled repository hygiene
  cleanup: tracked `.env.example` and `.claude/worktrees/serene-satoshi-01115b`
  were removed, `.claude/` is ignored, and README now states that `.env` is the
  only local dotenv source.
- No runtime schema, `/query` response shape, provider path, retrieval behavior,
  chain order, final-answer authority, or write/admin API contract changed.

## Obj14 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_api_main.py -q -p no:cacheprovider
```

Result: passed, 14 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj14 -p no:cacheprovider
```

Result: passed, 446 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

Post-review polish command:

```powershell
git ls-files .env .env.example .env.local .claude
```

Result: no tracked files returned.

Post-review polish command:

```powershell
rg "\.env\.example|\.env\.local|\.claude" README.md docs .gitignore
```

Result: README no longer points to `.env.example`; remaining matches are
historical migration/progress records, `.env.local` non-loading notes, and
ignore/progress rules.

## Obj14 Residual Risk

- The UI is intentionally static and minimal. It does not include a frontend
  build pipeline, persisted history, file upload, or management workflows.
- The UI depends on the existing `/query` response envelope. Future UI fields
  still require a Phase-4 migration before backend callers are changed.
- No browser automation screenshot was run yet; API smoke tests verify route
  availability and contract references. Manual visual verification remains
  operator-run by starting uvicorn and opening `/operator`.

## Obj14 Next Obj Gate

- Cleared for Obj15 local-first observability essentials after focused API
  verification and full non-large regression. Obj15 must preserve the local UI
  defaults and keep diagnostics redacted.

## Obj15 Notes

- Added `src/vibration_agent/observability.py` with deterministic redaction and
  JSON structured-log helpers.
- Redaction covers sensitive keys, API-key-like assignments, bearer tokens,
  local absolute paths, and long raw text.
- Added API request structured logging through middleware. Logs include method,
  path, status code, duration, and error type when applicable; they do not log
  headers, query text, request bodies, provider keys, or local paths.
- Converted the query observability log to the same structured event format for
  `supervisor_status`, `supervisor_invocations`, output status, and task id.
- Migrated `/health` to a local liveness/config probe. It no longer touches
  Postgres, Qdrant, external networks, or live model providers.
- Added read-only `GET /diagnostics`. By default it reports local config and
  dependency configured/disabled status without external probes. Operators can
  explicitly pass `probe_dependencies=true` to run the existing Postgres/Qdrant
  reachability checks.
- Added a Diagnostics panel to the local `/operator` UI. It reads `/health`,
  reusing the existing API token field when a query run supplies one.
- Reviewed `.github/workflows/test.yml`; no change was needed because CI does
  not require Postgres/Qdrant/live-provider health probes.
- No `/query` response shape, retrieval behavior, provider path, chain order,
  final-answer authority, write/admin API, or remote/shared hardening was added.

## Obj15 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_observability.py tests\unit\test_api_main.py tests\unit\test_api_hardening.py -q -p no:cacheprovider
```

Result: passed, 26 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj15 -p no:cacheprovider
```

Result: passed, 451 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj15 Review Follow-Up

- Fixed Obj15 `#1`: true low-impact brittleness. Observability redaction now
  accepts explicit local path prefixes and the API passes the configured
  workspace into workspace/diagnostics redaction. This covers custom POSIX
  workspaces such as `/opt/...` or `/srv/...` without broadening the fixed POSIX
  path regex enough to catch normal URL/API paths.

## Obj15 Review Follow-Up Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests\unit\test_observability.py tests\unit\test_api_main.py tests\unit\test_api_hardening.py -q -p no:cacheprovider
```

Result: passed, 28 tests.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-obj15-review-polish -p no:cacheprovider
```

Result: passed, 453 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

## Obj15 Residual Risk

- Observability is local/basic only. It does not add durable metrics storage,
  tracing, log rotation, dashboards, multi-user audit trails, or remote
  monitoring.
- `/diagnostics?probe_dependencies=true` can still touch configured Postgres or
  Qdrant by explicit operator request; the default `/health` and `/diagnostics`
  paths do not.
- Browser visual verification of the Diagnostics panel was not run in this
  objective; API/UI smoke tests verify route availability and asset references.

## Obj15 Next Obj Gate

- Cleared for Obj16 remote/shared hardening decision after focused
  observability/API tests. Obj16 should decide or defer remote/shared scope
  without changing the local-first default unless that product decision is
  explicit.

## Obj16 Notes

- Added `docs/phase_4_remote_shared_hardening_decision.md`.
- Decision: remote/shared hardening is deferred. Phase 4 remains a local-first,
  single-user product baseline.
- Recorded that multi-user authorization, tenant isolation, durable distributed
  rate limits, remote/shared metrics, k8s/public ingress, remote secrets
  management, and multi-user audit trails are not implemented in Phase 4.
- Defined the revisit gate required before remote/shared hardening can become
  implementation scope: deployment target, identity/authorization model,
  tenant/data isolation boundary, secrets ownership, durable backend choices,
  retention/redaction policy, security tests, and rollback path.
- Updated `README.md` and `docs/architecture.md` to point to the Obj16
  decision document.
- Reviewed runtime scope and made no code/config/API changes.

## Obj16 Verification

```powershell
git diff --check
```

Result: no whitespace errors; existing CRLF/LF warnings remain for `README.md`
and `docs/architecture.md`.

```powershell
rg -n "Phase 4 remains a local-first|remote/shared hardening is deferred|Remote/shared hardening decision: complete" docs README.md
```

Result: decision text is present in the Obj16 decision doc, progress ledger,
README, architecture, migration log, and deferred/polish audit.

## Obj16 Residual Risk

- No remote/shared hardening was implemented. This is intentional while the
  product remains local-first and single-user.
- If the product later moves to shared, remote, or public access, Obj16 is not
  sufficient as a security baseline; a new implementation objective must satisfy
  the documented revisit gate.

## Obj16 Next Obj Gate

- Cleared for Obj17 final Phase-4 interface freeze. Obj17 should freeze the
  Phase-4 final interface with Obj16 recorded as a deferred remote/shared
  decision, not as implemented security hardening.

## Obj16 Review Follow-Up

- Fixed Obj16 `#1`: true clarity issue. The Obj16 decision document now
  explicitly states that the optional local API token and in-process rate
  limiter are retained single-user local controls, while multi-user
  authorization and durable distributed rate limiting remain deferred.
- Fixed Obj16 `#2`: useful forward-looking polish. Added
  `docs/phase_5_candidate_scope.md` as the durable home for Phase-5 candidates,
  including remote/shared hardening candidates and the recommended pause for
  local backend, real-run, knowledge-base, and taxonomy iteration before any
  remote/multi-user expansion.

## Obj16 Review Follow-Up Verification

```powershell
rg -n "optional API token|in-process rate limiter|Phase 5 is not active|local iteration cycle" docs\phase_4_remote_shared_hardening_decision.md docs\phase_5_candidate_scope.md
```

Result: retained local controls and Phase-5 candidate/pause guidance are
documented in the expected files.

## Obj17 Notes

- Added `docs/phase_4_interface_freeze.md`.
- Froze Phase 4 as the local-first, single-user engineering-assistant baseline
  for real local iteration.
- The final freeze incorporates:
  - inherited Phase-3 freeze;
  - Obj13 backend interface freeze;
  - Obj14 read-only operator UI;
  - Obj15 local-first observability;
  - Obj16 remote/shared hardening defer decision;
  - `docs/phase_5_candidate_scope.md` as the durable future-candidate home.
- Updated README and architecture to point to the Phase-4 final freeze as the
  current baseline.
- Recorded that the next recommended work is not remote/shared expansion, but
  local real-run iteration: corpus ingestion, taxonomy expansion, retrieval and
  citation miss analysis, and backend ergonomics from actual operator use.
- No runtime schema, API response shape, provider path, retrieval behavior,
  chain order, final-answer authority, deployment default, or security model
  changed.

## Obj17 Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus" --basetemp=data\exports\pytest-p4-final-freeze -p no:cacheprovider
```

Result: passed, 453 tests; skipped 2; deselected 1; one Qdrant compatibility
warning.

```powershell
.\.venv\Scripts\python.exe scripts\llm_eval.py --output data\exports\ci\phase4_final_llm_eval.json
```

Result: passed with 7 cases, 7 passed, 0 failed, pass rate 1.0, citation
faithfulness pass rate 1.0, and unsupported numeric block rate 1.0.

```powershell
.\.venv\Scripts\python.exe scripts\retrieval_eval.py --output data\exports\ci\phase4_final_retrieval_eval.json
```

Result: passed with 4 cases, 3 evidence cases, 1 expected-miss case,
`top_k_recall@5 = 1.0`, `top_k_recall@10 = 1.0`, no missing evidence cases, and
`replacement_justified_by_baseline = false`.

```powershell
git diff --check
```

Result: no whitespace errors; existing CRLF/LF warnings remain for `README.md`
and `docs/architecture.md`.

## Obj17 Residual Risk

- Phase 4 is a local engineering-assistant baseline, not a remote/shared
  production security baseline.
- The eval/retrieval gates are fixture-sized regression nets. Real engineering
  reliability now depends on local corpus ingestion, real operator questions,
  taxonomy expansion, and miss-driven backend iteration.
- S6/S7/S8, external evidence, symbolic checking, rendered-page mapping,
  retrieval replacement, and model-backed V2 entailment remain future
  candidates rather than frozen default behavior.

## Obj17 Next Phase Gate

- Phase 4 is frozen.
- Phase 5 is not active.
- The project should enter local iteration before any remote/shared expansion:
  build the real knowledge base, enrich taxonomy, run operator/API trials, and
  use retrieval/citation failures to prioritize backend improvements.

## Obj17 Review Follow-Up

- Fixed Obj17 `#1`: true stale-doc issue. Updated
  `docs/phase_4_deferred_and_polish_audit.md` so its Freeze Summary states that
  Phase 4 is fully frozen through Obj17 and points to the final interface
  freeze, instead of saying the backend is merely ready for Obj13.
- Fixed Obj17 `#2`: useful API-surface clarity polish. Added an explicit API
  delta line to `docs/phase_4_interface_freeze.md`: relative to the Obj13
  backend freeze, Obj14 added `/operator` and `/operator/assets/{path}`, Obj15
  added `/diagnostics` and migrated `/health` to offline semantics, and
  `/query`, `/ingest`, `/scope`, chain order, retrieval, provider, and
  final-answer contracts did not change.
- Reviewed Obj17 `#3`: process hygiene only. Obj16 decision docs and Obj17
  freeze docs should be committed together or with Obj16 first, so freeze
  references are not dangling in history.

## Obj17 Review Follow-Up Verification

```powershell
rg -n "Phase 4 is fully frozen|Relative to the Obj13 backend freeze|Obj14 added the additive" docs\phase_4_deferred_and_polish_audit.md docs\phase_4_interface_freeze.md
```

Result: updated freeze summary and API-surface delta are present.

## Post-Freeze R3 Closure

Date: 2026-06-29

- Closed the R1-R3 local iteration ledger. Phase 4 accepts no further feature
  objectives.
- Added runtime Qdrant ANN retrieval over the re-embedded 4436-point
  multilingual corpus, source-aware citations, answer-first operator rendering,
  and diagnostic answer-quality telemetry.
- Reclassified `answer_quality` as an uncalibrated heuristic after an adversarial
  keyword-repetition non-answer scored 1.0. It is not an acceptance gate.
- Confirmed the default API orchestrator does not construct live GPT/Opus
  clients; production answer generation and supervisor reliability move to the
  successor phase.
- Aligned configured LLM limits to GPT max output 8192, Opus max output 4096,
  60000 tokens per task, and 180000 per session. Live Opus no longer fails the
  local budget reservation; malformed correction output remains a known gap.

Verification: 541 tests passed with 1 deselected; replay LLM eval 7/7; offline
retrieval fixture recall@5 and recall@10 both 1.0 with embeddings explicitly
disabled for the deterministic gate.
