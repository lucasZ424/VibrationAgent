# Phase 5 Backend / Eval Interface Freeze

Date: 2026-07-07
Status: FROZEN AFTER OBJ9

This document freezes the local RAG reliability backend and evaluation contract
after Phase-5 Obj8. Obj10 may add the final Phase-5 interface freeze, but it must
not silently change the backend authority, retrieval, scoring, provider, or
evaluation baseline recorded here.

## Product Boundary

The frozen product remains local-first and single-user:

- trusted local corpus files;
- localhost API/CLI/operator access;
- private local Postgres and Qdrant stores;
- no shared, remote, public, SaaS, or multi-user deployment surface.

Remote/shared/public/multi-user capability is indefinitely deferred. It is not a
hidden backend-freeze candidate and cannot be activated by a review note,
operator convenience need, or Obj10 documentation cleanup.

## Frozen Default Answer Path

The supported default answer path is:

```text
S2 retrieval -> S3 deterministic synthesis -> optional S4/S5 -> V2 hard gate -> V4
```

The optional V3/supervisor and model-backed lanes remain explicit opt-in lanes.
The default API/CLI path must not construct live LLM clients, require API keys,
or use network providers to answer ordinary queries.

`S3_LLM_ENABLED=false` is the supported production default. Enabling LLM S3,
Opus supervision, or combined-chain replay requires an explicit flag/constraint,
replay or live-provider setup, and a separate gate result. Obj6A/Obj6B validated
those lanes, but did not promote them into the default answer path.

## Frozen Corpus And Stores

The frozen corpus/runtime baseline is the Obj7C/Obj8 4,436-chunk local corpus:

- file, Postgres, and Qdrant counts: 4,436 chunks;
- source distribution: book 939 / manual 928 / paper 1,780 / standard 789;
- source filename/title coverage: 1.000;
- mojibake audit count: 0;
- Qdrant collection: `chunks`;
- embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`;
- embedding dimension: 384;
- distance/collection contract: unchanged from Obj3 multilingual ANN reindex.

Generic internal `document_*` ids are accepted as chunk/doc identifiers only
because citation display resolves to real source metadata. Renaming those ids is
a future fixture/corpus migration, not part of this freeze.

After any out-of-process corpus reindex, Qdrant rebuild, or
`taxonomy/corpus_standards.yaml` catalog rebuild, the API process must be
restarted before retrieval results are trusted:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py --restart
```

The reindex command clears caches in its own process. A separately running API
cannot receive that in-process cache clear without restart.

## Frozen Retrieval Contract

The default retrieval mode is hybrid with independent lanes:

- BM25 lexical lane over the runtime Qdrant payload corpus;
- dense ANN lane over Qdrant vectors;
- RRF fusion;
- `bm25_top_k=50`, `dense_top_k=50`, `final_top_k=10`;
- reranker disabled;
- evidence selection disabled by default.

The runtime lexical payload cache is an Obj8 local-process cache capped at four
entries. It is a supported implementation detail only under the restart contract
above; it is not a persistent shared index.

Taxonomy and retrieval aliases are versioned local files. Broad aliases accepted
for Obj7 are in-sample miss repairs, not held-out generalization evidence.

## Frozen Evaluation Baseline

`tests/fixtures/rag_qa/post_r3_baseline.json` is the standing Phase-5
backend/eval regression net from Obj9 onward. The file name is historical; the
contents now represent the post-Obj8 backend-freeze baseline.

The committed baseline uses the 14-case Obj1 real-question fixture and remains
in-sample. Obj7 aliases were derived from Obj1 misses and measured on the same
fixture. The scorecard is therefore a regression net for fixed misses, not a
claim of held-out engineering generalization.

Frozen scorecard:

- recall@5: 0.643;
- recall@10: 0.821;
- completeness: 0.720;
- sentence completeness: 0.867;
- V2 faithfulness: 1.000;
- citation alignment: 1.000;
- live providers constructed: false.

The evaluator contract remains `phase5.rag_qa.report.v3`; evidence matching is
`exact_chunk_id OR same_doc_id_with_page_overlap`.

## Frozen Scoring And Gates

V2 faithfulness remains a hard gate. An answer with `faithfulness_status != ok`
cannot be treated as usable or pass-quality.

Obj9 froze `phase5.answer_quality.v2` as the production quality schema. A
post-freeze scoring amendment on 2026-07-07 supersedes it with
`phase5.answer_quality.v3`, adding deterministic prompt/answer language
adaptation as a subscore and gate signal. Mixed Chinese/English prompts are
judged by explicit language instructions first, otherwise by the prompt's
primary script; algorithm/formula/unit-heavy answers may be
`mixed_acceptable` when the main prose still follows the requested language.
The answer-language check ignores the evidence section.

The current runtime threshold is `0.75`, but it is provisional and backstopped
by the hard `completeness == 1.0`, no `language_status=mismatch`, and V2
requirements. The refreshed deterministic calibration artifact now ranks `0.90`
as the best observed candidate, but this is not a runtime threshold migration:
current labels still have one usable and thirteen unusable cases, and the Obj6
combined-chain calibration showed that LLM-style answers reduce threshold
discriminative power.

Future threshold changes require all of the following:

- human label re-review for newly pass-like answers;
- regenerated calibration report;
- migration entry;
- regression proving no false allow/false block regression under the complete
  gate rule.

## Frozen LLM / Supervisor Contract

Obj6A GPT synthesis and Obj6B Opus supervisor lanes are validated but dormant:

- default-off;
- replay-first;
- budgeted/live-provider explicit;
- deterministic fallback preserved;
- no default production promotion in Obj9.

The Obj6 combined-chain scorecard reached completeness 0.804 with V2 1.000 in
the promoted replay/live lane. That result is a lane validation result, not the
production default baseline. The Obj9 production default baseline remains the
deterministic post-Obj8 scorecard above.

## Backend Reliability Contract

Obj8 freezes the local reliability behavior:

- Qdrant bulk writes support explicit batching and bounded retry;
- successful in-process reindex clears runtime retrieval/taxonomy caches;
- Postgres `qa_logs` failures are fail-safe side effects with a short cooldown;
- `/health` exposes configured/reachable status per dependency;
- `/diagnostics` uses `phase5.obj8.local_diagnostics.v1` and reports retrieval
  mode/source, embedding model/dimension, store state, and lexical-cache stats;
- `scripts/start_operator.py` is the supported lifecycle entry for start, stop,
  restart, and local `--reload`.

These are local operator ergonomics. They do not create remote administration,
shared accounts, public ingress, or multi-user observability.

## Change Control

The following changes are backend/eval contract changes and require a successor
migration plus updated freeze/progress evidence:

- retrieval mode, lane independence, fusion method, top-k defaults, reranker
  default, or evidence-selection default;
- corpus count, chunk ids, source metadata contract, embedding model/dimension,
  Qdrant collection, or parity rules;
- V2 hard-gate semantics, answer-quality schema, threshold, or pass rendering;
- default LLM/supervisor enablement, provider request shape, replay hash
  semantics, or live-provider construction in default tests/API;
- Obj1 question fixture, standing baseline scorecard, evidence match rule, or
  committed calibration report.

Documentation, UI, or operator changes after Obj9 are compatible only if they
preserve this backend authority and make any remaining residual risk explicit.

## Accepted Residual Risks

- The standing 0.821 recall@10 scorecard is in-sample on the Obj1 fixture.
- The fixture has one labeled usable answer and thirteen unusable answers; the
  answer-quality threshold remains provisional.
- LLM/supervisor lanes are validated but not promoted to the default path.
- Out-of-process reindex requires API restart before retrieval can be trusted.
- The runtime lexical lane uses a bounded local process cache, not a persistent
  external lexical index.
- Generic internal ids remain until a future explicit id migration.
