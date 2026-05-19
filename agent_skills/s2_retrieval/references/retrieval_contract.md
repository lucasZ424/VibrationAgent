# S2 Retrieval Contract

S2 consumes chunk rows produced by S1 structured export. The preferred file input
is `chunks.jsonl`, not `pages.jsonl` or `api_context.json`.

Each accepted chunk row must include at minimum:

- `chunk_id`
- `doc_id`
- `source_type`
- `pages` or `page_start` / `page_end`
- `text`

Returned hits follow `RetrievalOutput.hits[]`:

- `chunk_id`
- `doc_id`
- `source_type`
- `pages`
- `score`
- `reason`

Citation confidence is normalized relative to the strongest returned hit. Raw RRF
scores are ranking scores, not evidence confidence scores.
