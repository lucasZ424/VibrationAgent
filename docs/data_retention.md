# Data Retention and Cleanup

The `data/` tree is local runtime state. It is ignored by git and should be
managed as disposable working data except for source documents that you still
need for provenance or re-ingestion.

## Keep by Default

- `data/raw/`: original corpus files. Keep unless the document is intentionally
  removed from the knowledge base.
- `data/chunks/`: current file-backed retrieval corpus. Keep while S2 retrieval
  still uses `--chunks-dir` or `chunks_jsonl`.
- `data/extracted/`: extracted visual assets when you need figure/table/image
  evidence to remain locatable. Postgres and Qdrant currently store `asset_path`
  references, not image bytes.
- `data/cache/`: downloaded OCR/model cache. This is regenerable, but deleting
  it may force a re-download or slow OCR startup.

## Regenerable

- `data/ocr/`: page-level OCR/native parse exports.
- `data/extracted/`: extracted figures, tables, and rendered assets. Regenerate
  by re-ingesting from `data/raw`, but do not delete it if current answers or
  downstream UI need to open referenced images.
- `data/exports/`: manifests, API context files, eval outputs, and pytest
  temporary roots.
- `data/embeddings/`: embedding exports if written locally.
- `data/run_logs/` and `data/answer_logs/`: diagnostic logs and manual snapshots.
- `data/tmp/`: temporary working files.

## Cleanup Commands

Preview diagnostic cleanup:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile diagnostics
```

Delete logs, temp files, and pytest cache:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile diagnostics --execute
```

Preview regenerable ingestion artifacts without deleting `data/raw` or
`data/chunks`:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile regenerable
```

Delete regenerable ingestion artifacts:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile regenerable --execute
```

This removes `data/extracted`. Existing database rows and Qdrant payloads will
still contain their old `asset_path` values, but those paths will be dead until
you re-ingest or rebuild the asset files.

Only clean `data/chunks` when you are prepared to re-ingest or when retrieval no
longer depends on file-backed chunks:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile deep --execute
```

Add `--include-cache` only when you accept re-downloading OCR/model files.
