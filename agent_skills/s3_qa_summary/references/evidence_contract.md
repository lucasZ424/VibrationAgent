# S3 Evidence Contract

S3 consumes normalized text evidence from S2 retrieval. Each usable evidence row
must include:

- `chunk_id`
- `doc_id`
- `text`
- `pages` when available
- `source_type` when available

S3 emits:

- `structured_result.answer`
- `structured_result.claims[]`
- `citations[]` using `Citation`

Claim-level citation checking is deferred to V2/V3. In Phase-0, each extracted
claim is directly bound to the chunk it was extracted from and labeled
`documented`.
