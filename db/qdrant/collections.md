# Qdrant collections

## `chunks`
- **vector**: dense embedding of `chunks.normalized_text`
- **size**: 1024 (placeholder — depends on embedding model, e.g. `bge-m3`)
- **distance**: `Cosine`
- **payload**:
  - `chunk_id` (int, postgres FK)
  - `doc_id` (int)
  - `source_type` (`standard|textbook|review|paper|webpage`)
  - `page_start`, `page_end` (int)
  - `chunk_type`
  - `topic` (optional, populated from taxonomy)

## `figures`  *(phase-2)*
- Vision embeddings for figure/table captions + rendered thumbnails.
