# Test Fixtures

These fixtures are intentionally small and independent of the full Bently book corpus.
They support fast regression tests for Phase-0 schemas and the S1 -> S2 -> S3 -> V4 chain.

## Files

- `raw/small_vibration_native.pdf`: one-page native-text PDF used for fast S1 ingestion tests.
- `ocr/sample_pages.jsonl`: page-level parse fixture matching `OcrPage`.
- `chunks/sample_chunks.jsonl`: chunk fixture matching `MemoryChunk`.
- `retrieval/sample_retrieval.json`: retrieval fixture matching `RetrievalOutput`.

## Regeneration Policy

The PDF was generated with PyMuPDF from a short rotor-vibration paragraph. If the chunker
format changes, regenerate the page/chunk fixtures from this PDF and update the golden
regression assertions in `tests/unit/test_regression_fixtures.py` in the same change.

Keep fixture paths portable: use forward slashes in JSON fields even on Windows.