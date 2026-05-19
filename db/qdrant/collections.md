# Qdrant collections

## `chunks`
- **vector**: dense embedding of `chunks.normalized_text`
- **size**: 1024 (placeholder; depends on embedding model, e.g. `bge-m3`)
- **distance**: `Cosine`
- **payload**:
  - `chunk_id` (logical chunk id; maps to Postgres `_meta.chunk_id` until DB ids exist)
  - `doc_id` (logical document id; maps to Postgres document hash/source)
  - `source_type` (`standard|textbook|review|paper|webpage|book|manual|note`)
  - `page_start`, `page_end`, `pages`
  - `chunk_type` (`text|formula|caption|code|table`, normalized to the shared storage vocabulary)
  - `topic` / `section_key`
  - `citation_anchor`, `token_estimate`, `needs_review_pages`
  - `embedding_model`, `embedding_version`

## `figures`  *(phase-2)*
- Vision embeddings for figure/table captions + rendered thumbnails.
