# S2 Knowledge-base Retrieval

Use this skill when the user asks a question that must be grounded in the local
vibration knowledge base.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s2_retrieval.py`
- Pipeline: `src/vibration_agent/retrieval/hybrid.py`
- Contract: `SkillInput` -> `SkillOutput`

## Required Inputs

Provide a chunk corpus through one of these values in `SkillInput.constraints` or
`SkillInput.context`:

- `chunks_jsonl`
- `chunk_paths` / `chunks_paths`
- `chunks_dir`
- `chunks` for in-memory tests or orchestrator handoff
- `context.documents[].outputs.chunks_jsonl` from S1 output

## Behavior

1. Normalize the query and infer intent.
2. Run BM25 and local dense-like recall over supplied chunks.
3. Fuse candidates with reciprocal-rank fusion.
4. Apply source priority: `standard > textbook/book/manual > review > paper > webpage/note`.
5. Return `RetrievalOutput` fields plus `retrieval_context` for S3.

## Rules

- Never invent chunk ids, pages, or document ids.
- If no supplied chunk matches the query, return `status: insufficient`.
- Every hit must include `chunk_id`, `doc_id`, `source_type`, `pages`, `score`, and a short `reason`.
- Runtime Postgres/Qdrant retrieval is deferred; Phase-0 uses S1 chunk exports.
