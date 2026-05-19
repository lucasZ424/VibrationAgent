# S1 - Document ingestion & parsing

S1 converts supported source documents into structured Phase-0 exports. It does
not interpret document content and must not guess missing OCR text.

Input is a `SkillInput`. Provide the source through `constraints.input_path` or
`context.input_path`; `source_path`, `raw_path`, `path`, and `raw_dir` are accepted
aliases. Optional constraints:

- `recursive`: scan directories recursively; default `true`
- `max_pages`: page limit for validation or partial ingestion
- `write_output`: write structured files; default `true`
- `keep_images`: keep rendered OCR page images; default `false`
- `source_type`: one of the Phase-0 source types; default `book`

Output is a `SkillOutput` whose `structured_result.documents[]` contains `doc_id`,
`processed_pages`, `chunk_count`, `needs_review_pages`, quality summary, and paths
to `pages.jsonl`, `chunks.jsonl`, `api_context.json`, and `manifest.json`.

Do not generate Markdown as an ingestion artifact. Flag low-confidence or empty
pages through warnings and `needs_review_pages` instead of filling gaps.
