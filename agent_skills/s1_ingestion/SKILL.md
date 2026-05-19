# S1 Ingestion

Use this skill when the user asks to ingest, OCR, parse, chunk, or prepare a
source document for the vibration knowledge base.

## Runtime Implementation

- Python skill: `src/vibration_agent/skills/s1_ingestion.py`
- Pipeline: `src/vibration_agent/ingestion/pipeline.py`
- Contract: `SkillInput` -> `SkillOutput`

## Required Inputs

Provide one of these values in `SkillInput.constraints` or `SkillInput.context`:

- `input_path`
- `source_path`
- `raw_path`
- `path`
- `raw_dir`

Optional constraints:

- `recursive`: default `true`
- `max_pages`: optional integer page cap
- `write_output`: default `true`
- `keep_images`: default `false`
- `source_type`: default `book`

## Behavior

The skill classifies input documents, chooses native PDF parsing or OCR PDF
routing, emits structured pages, assets, chunks, api_context, and manifest files,
and returns a compact summary with output paths.

Do not interpret document content. Do not generate Markdown as an ingestion
artifact. Do not guess missing OCR text. Low-confidence or empty pages must be
reported as review warnings.

## Outputs

Return a `SkillOutput` with:

- `status`: `ok`, `insufficient`, or `fail`
- `structured_result.document_count`
- `structured_result.chunk_count`
- `structured_result.documents[].doc_id`
- `structured_result.documents[].outputs`
- warnings for review pages or failures
