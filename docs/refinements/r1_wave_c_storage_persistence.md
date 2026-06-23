# R1 storage persistence: ingest runtime stores

Date: 2026-06-23

## Problem

During the R1 local-iteration work, Docker services were enabled and `ingest`
still stopped at file exports: Postgres/Qdrant write helpers existed, but the
normal CLI/API ingestion path did not persist document exports into runtime
stores. This is recorded as a storage objective, separate from Wave C's CLI
UTF-8 issue.

## Change

- `chunk_documents()` now attaches a `storage` summary after structured export.
- `POSTGRES_ENABLED=true` writes each manifest/chunk batch into Postgres.
  Re-ingesting the same document hash refreshes sections/chunks instead of
  failing on the `documents.hash` unique constraint.
- `QDRANT_ENABLED=true` embeds chunk text and upserts only chunks with non-empty
  vectors. If embeddings are disabled or unavailable and only empty fallback
  vectors are produced, the result reports `qdrant.status = "skipped"` with an
  explicit warning.
- API ingestion results now expose the same `storage` summary as CLI JSON.
- Qdrant point ids changed from SHA1 hex strings to stable UUIDv5 ids because
  the live Qdrant HTTP API rejects arbitrary hex strings as point ids.
- The Postgres live integration fallback now matches the local compose default:
  `postgresql://vib:vib@localhost:5432/vibration`.

## Verification

- Focused storage/Qdrant unit tests: 13 passed.
- CLI/API regression subset: 26 passed.
- Live Docker integrations: 3 passed, including a new smoke that persists one
  ingestion result to Postgres and Qdrant, then reads both back.
- Full pytest suite: 491 passed.

## Operational Note

Qdrant being healthy is not sufficient for vector indexing. A usable embedding
configuration must produce non-empty vectors; otherwise ingest still succeeds
for file/Postgres outputs, but Qdrant indexing is explicitly skipped.
