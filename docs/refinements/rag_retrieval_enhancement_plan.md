# RAG Retrieval Enhancement — development plan

Date: 2026-06-26
Status: PHASE-5 INPUT (partially implemented; not an acceptance baseline)
Owner: (you) — this draft is a skeleton to complete; OPEN DECISIONS are marked [D#].
Scope: S2 retrieval and the S2->S3 evidence hand-off, on the now-complete
  full-corpus knowledge base (Postgres + Qdrant populated).

2026-06-29 closure note: Phase 4 is closed. C1 query-time Qdrant ANN and the D7
multilingual 384-dimensional model decision were implemented during R3, with
4436/4436 point parity. The required labeled real-question baseline was not
completed, BM25 currently runs only over ANN candidates on the runtime path,
the default API does not construct live GPT/Opus clients, and the answer-quality
heuristic is uncalibrated. Those gaps require an explicitly activated successor
phase; this document no longer authorizes Phase-4 work.

This plan covers an additive retrieval-enhancement layer that improves which
evidence reaches S3, measured against the current baseline on a real
engineering-question set. It is a RUNTIME retrieval enhancement, not a test net.

--------------------------------------------------------------------------------
## 0. Sequencing and governance (non-negotiable, from past phases)
--------------------------------------------------------------------------------

This is post-Phase-4-freeze local iteration. It MUST follow the established
discipline (same as R1/R2 and the Obj2/Obj4 retrieval gate):

1. Default-off: the enhancement ships disabled; the frozen deterministic chain
   (S2->S3->V2->V4) stays the default until the enhancement provably wins.
2. Migration-first: any schema/structured-result/chain change is recorded in
   `docs/phase_4_migrations.md` before callers change.
3. Replay-first: if the enhancement uses any LLM (query rewrite / rerank), it is
   replay/capture-gated; CI never constructs a live provider.
4. Evidence-gated promotion: it becomes default only if it beats the baseline on
   the retrieval recall audit AND the real-question set, via the Obj2/Obj4
   replacement gate (replace only when recall improves and no regression).
5. V2 stays the faithfulness gate: the enhancement must not reduce citation
   faithfulness.

REQUIRED ORDER: §1 real-question baseline FIRST (the "问题实测"), THEN build the
enhancement targeting the measured misses. Do not build it before the baseline gap
is quantified.

--------------------------------------------------------------------------------
## 1. Phase 0 — real-question baseline (prerequisite, do before any enhancement code)
--------------------------------------------------------------------------------

Goal: quantify what the current baseline retrieval+synthesis can and cannot answer
on the real corpus, so the enhancement targets real misses (not guesses).

- Build a labeled real-question set `tests/fixtures/rag_qa/questions.json`:
  - cover the four genres (manual / standard / paper / book) and bilingual zh/en;
  - per question record: expected evidence doc(s)/page(s), expected key facts, and
    an answer-completeness rubric (conclusion present, engineering meaning, units/
    numbers, citation traceable).
- Build a deterministic runner `scripts/rag_qa_eval.py` that, per question, records:
  retrieved chunks, whether expected evidence is in top-k, the final answer, V2
  status, and a completeness score against the rubric.
- Run it on the baseline (current S2->...->V4). Output a scorecard:
  recall@k, answer-completeness rate, V2 faithfulness rate, miss categories.
- Categorize misses, e.g.:
  - retrieval miss (right chunk not in top-k);
  - ranking miss (right chunk retrieved but out-ranked by noise);
  - cross-doc miss (answer needs evidence from multiple chunks/docs);
  - synthesis miss (evidence present but answer incomplete — that is S3, not
    retrieval);
  - terminology miss (zh/en or synonym gap — extends the Wave-B alias work).
[D1] Which miss categories dominate decides which components below are worth
     building. Fill this from the Phase-0 scorecard.

Verification: scorecard committed; baseline numbers are the bar to beat.

--------------------------------------------------------------------------------
## 2. Design goals
--------------------------------------------------------------------------------

1. Raise real-question answer-completeness and top-k recall over the baseline.
2. Keep local-first and deterministic-by-default; any LLM use is opt-in/replayable.
3. Add no new always-on dependency; reuse the populated Qdrant + existing embeddings.
4. Preserve V2 citation faithfulness and PG:Qdrant parity.
5. Bounded latency: a per-query budget; deterministic fallback to baseline on
   timeout/failure.
6. Every change additive + migration-recorded; promotion only via the replacement
   gate.

--------------------------------------------------------------------------------
## 3. Candidate components (a menu — you choose the scope) [D2]
--------------------------------------------------------------------------------

Listed cheapest/most-deterministic first. Recommend starting with C1+C2 (no LLM),
adding C3/C4 only if Phase-0 misses justify them.

### C1. Activate dense vector retrieval via Qdrant (core, deterministic)
The corpus is now embedded in Qdrant (UUIDv5 points, points==embeddable_chunks).
Make S2 query Qdrant for semantic neighbors and fuse with the existing BM25/token
lane. Likely the single biggest lever for "retrieval miss" / "terminology miss".
- additive: a dense lane in `retrieval/hybrid.py`; default-off behind a setting;
  falls back to current token-feature lane when Qdrant/embeddings unavailable.
- [D3] fusion method: weighted score, Reciprocal Rank Fusion (RRF), or normalized
  linear. RRF is a robust default.

### C2. Re-ranking of the fused top-N (deterministic or model)
Re-order the top-N candidates by a stronger relevance signal before handing the
top-k to S3.
- deterministic option: feature re-rank (lexical+dense agreement, title/section
  match, source_priority, query-term coverage) — no new dependency;
- [D4] model option (default-off, replay-first): a local cross-encoder reranker.
  Only if deterministic re-rank is insufficient on the Phase-0 set.

### C3. Query enhancement (LLM, default-off, replay-first) [D5]
For hard questions where the query and the corpus phrase the same concept
differently. Options: query rewrite/normalization, multi-query expansion, or HyDE
(LLM hypothetical answer embedded and used as a dense query). Strict budget +
replay capture; deterministic fallback = the existing query_normalize expansion.

### C4. Evidence selection / passage compression for S3
Choose and order the best evidence subset for S3 (reduce noise, fit token budget,
prefer outcome/definition passages per intent — extends the R2 scope-claim and
critical-speed work). Deterministic.

### C5. (deferred) multi-hop / iterative retrieval
For cross-doc questions. Defer unless Phase-0 shows a real cross-doc miss class.

--------------------------------------------------------------------------------
## 4. Where the enhancement plugs in (contract-preserving)
--------------------------------------------------------------------------------

- It lives inside / immediately after S2 retrieval, before S3. It must keep the
  frozen `SkillOutput` envelope and the `retrieval_context` shape; any new fields
  are additive (e.g. `retrieval_enhancement.enabled`,
  `retrieval_enhancement.rerank_scores`, `retrieval_enhancement.lanes`,
  `retrieval_enhancement.fallback_used`).
- It must not change S3/S4/V2/V4 contracts or the final-answer authority (still
  V2/V4-bound).
- Toggle via existing settings (e.g. `settings.retrieval.enhanced_retrieval_enabled`),
  default false; per-component sub-toggles for C1..C4.

--------------------------------------------------------------------------------
## 5. Promotion gate (when the enhancement becomes default)
--------------------------------------------------------------------------------

It is promoted from default-off to default-on only when, on the same fixtures:
- retrieval recall@10 >= baseline AND fixes >= 1 real miss with no new miss
  (the Obj2/Obj4 replacement-gate rule, reused);
- real-question answer-completeness strictly improves;
- V2 faithfulness rate does not drop;
- latency within the per-query budget;
- determinism: deterministic components reproducible across two runs; LLM
  components replay-stable.
Until then it runs only when explicitly enabled (operator/manual), and the
deterministic baseline remains the shipped default.

--------------------------------------------------------------------------------
## 6. Development steps (each with verification)
--------------------------------------------------------------------------------

Step 0  Governance: migration + freeze note (additive fields, default-off).
Step 1  Phase-0 baseline harness + real-question fixture + scorecard (§1).
Step 2  C1 dense lane + fusion; eval vs baseline on recall; default-off.
Step 3  C2 deterministic re-rank; eval; keep only if it improves the scorecard.
Step 4  (cond. on [D1]) C3 query enhancement, replay-first; eval; budget-bound.
Step 5  C4 evidence selection for S3; eval; V2 faithfulness unchanged.
Step 6  Promotion-gate run: compare enhancement-on vs baseline on all fixtures;
        decide default per §5; record decision.
Each step: focused unit tests + the rag_qa_eval scorecard attached to the change;
full suite green; PG:Qdrant parity unchanged.

--------------------------------------------------------------------------------
## 7. Acceptance rules
--------------------------------------------------------------------------------

- Default chain unchanged while the enhancement is off (byte-identical retrieval
  when disabled).
- Enhancement-on beats baseline on recall@k AND real-question completeness; no V2
  drop.
- Deterministic components reproducible; LLM components replay-stable; no live
  provider in CI.
- Latency within budget; on timeout/failure it falls back to baseline visibly
  (warning + `retrieval_enhancement.fallback_used=true`).
- Migration + freeze note recorded; additive fields only.
- A real miss fixed becomes a permanent labeled question (regression net) — the
  project's standing discipline.

--------------------------------------------------------------------------------
## 8. Eval assets
--------------------------------------------------------------------------------

- extend `tests/fixtures/retrieval/targets.json` with relevant targets;
- new `tests/fixtures/rag_qa/questions.json` (real-question golden set + rubric);
- `scripts/rag_qa_eval.py` (deterministic scorecard runner);
- reuse `scripts/retrieval_eval.py` recall audit and the Obj2/Obj4 gate;
- V2 calibration unchanged (faithfulness guard).

--------------------------------------------------------------------------------
## 9. Open decisions to complete (for you)
--------------------------------------------------------------------------------

[D1] Dominant miss categories from the Phase-0 scorecard -> drives component scope.
[D2] Component scope: minimal (C1+C2 only) vs full (C1-C4)?
[D3] Fusion method for C1 (RRF recommended).
[D4] Re-rank: deterministic-only, or add a local cross-encoder?
[D5] Any LLM in the enhancement (C3)? If yes: which provider lane, budget, replay
     policy.
[D6] Default-on promotion thresholds (recall delta, completeness delta, latency).
[D7] Embedding model/dimension for the dense lane (matches the ingested Qdrant
     vector size; must not require re-embedding the corpus).

--------------------------------------------------------------------------------
## 10. Review gate
--------------------------------------------------------------------------------

No implementation beyond the Phase-0 baseline harness proceeds until this plan is
completed (D1-D7 decided) and reviewed. Phase 0 (the real-question baseline) may
start immediately — it is measurement only, no contract change.
