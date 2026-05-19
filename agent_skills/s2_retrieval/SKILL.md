# S2 Retrieval

Use this skill when the user asks a vibration-domain question that must be
answered from the local knowledge base rather than model memory.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s2_retrieval.py::RetrievalSkill`
- Hybrid pipeline: `src/vibration_agent/retrieval/hybrid.py`
- Input contract: `SkillInput`
- Output contract: `SkillOutput` containing `RetrievalOutput` fields and `retrieval_context`

## Required Inputs

Provide one of these corpus inputs in `SkillInput.constraints` or `SkillInput.context`:

- `chunks_jsonl`
- `chunk_paths` / `chunks_paths`
- `chunks_dir`
- `chunks` for in-memory orchestrator handoff
- S1 handoff: `context.documents[].outputs.chunks_jsonl`

## Behavior

Normalize the query, run BM25 plus the Phase-0 local dense-like fallback, fuse
with RRF, apply source-priority tie boost, and return citation-safe hits.

## Guardrails

- Never invent `chunk_id`, `doc_id`, or pages.
- Return `insufficient` when recall is weak or no corpus is supplied.
- Use returned `retrieval_context` as the evidence package for S3.
- Treat local dense-like recall as temporary; real Qdrant embedding retrieval is deferred.

