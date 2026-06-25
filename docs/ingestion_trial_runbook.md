# Knowledge-base ingestion trial runbook

Date: 2026-06-23

## Purpose

Before full-corpus ingestion, run a small end-to-end trial that proves the local
pipeline can:

- parse/chunk a small document batch;
- write structured files under `data/ocr`, `data/chunks`, `data/exports`, and
  `data/extracted`;
- persist document/chunk rows into Postgres;
- persist non-empty vector points into Qdrant;
- answer from trial chunks without printing large JSON payloads to the terminal.

Do not start full ingestion until this trial is clear.

## Current Readiness

The latest plan-only scan found:

- 77 supported documents;
- 3461 pages total;
- 35 OCR PDFs / 1577 OCR pages;
- 41 native PDFs / 1883 native pages;
- 1 DOCX page.

This corpus is large enough for a useful initial knowledge base, but it is not
safe to ingest in one unbounded command. OCR must run in batches and never in
parallel on this machine.

## Files To Change

This runbook relies on one support script:

- `scripts/reset_runtime_stores.py`: dry-run by default; with `--execute`, it
  truncates regenerated Postgres ingestion tables and deletes the configured
  Qdrant collection so full ingestion starts from a consistent baseline.
- `scripts/persist_ingestion_exports.py`: persists existing `data/exports` and
  `data/chunks` artifacts into the configured Postgres/Qdrant stores. This is
  needed for long OCR books processed through the resumable file workflow.

Manually edit `.env` before running the trial. These values enable runtime store
persistence:

```env
POSTGRES_ENABLED=true
QDRANT_ENABLED=true
```

For a complete Qdrant vector trial, embeddings must also produce non-empty
vectors. The current default `EMBEDDING_ENABLED=false` will make Qdrant skip
vector upsert. Use one of these embedding configurations.

Preferred local sentence-transformer configuration:

```env
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_ENABLED=true
EMBEDDING_LOCAL_FILES_ONLY=false
EMBEDDING_FALLBACK_TO_TOKEN_FEATURES=true
EMBEDDING_BATCH_SIZE=16
QDRANT_COLLECTION=chunks
QDRANT_VECTOR_SIZE=384
```

If the model already exists at a local filesystem path, prefer the stricter
offline form:

```env
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=C:\path\to\all-MiniLM-L6-v2
EMBEDDING_ENABLED=true
EMBEDDING_LOCAL_FILES_ONLY=true
EMBEDDING_FALLBACK_TO_TOKEN_FEATURES=true
EMBEDDING_BATCH_SIZE=16
QDRANT_COLLECTION=chunks
QDRANT_VECTOR_SIZE=384
```

If embeddings are unavailable, the trial may still validate Postgres ingestion,
but it does not clear the vector-database path. In that case Qdrant will report
`status: skipped` and the full ingestion should not be treated as vector-ready.

`QDRANT_VECTOR_SIZE` must match the real embedding model dimension. The default
MiniLM model is 384-dimensional. If an existing Qdrant collection was created
with another dimension, delete/recreate that collection or use a new collection
name before the trial.

## Trial Rules

- Run one ingestion command at a time.
- Do not run `standard`, `manual`, `paper`, and `book` ingestion in parallel.
- Do not use `--keep-images` unless debugging OCR image quality.
- Do not run the full `data\raw` root with one `--source-type`; source type is a
  batch-level argument and must match the raw subdirectory.
- Use `--output` or PowerShell redirection for every command that emits
  diagnostics.
- Treat OCR errors, system sleep/restart, Qdrant skipped status, or Postgres
  write failure as not clear.
- For OCR-heavy categories, especially `standard` and `book`, use a staging
  directory plus the resumable OCR workflow first, then persist generated exports
  with `scripts/persist_ingestion_exports.py`. Do not rerun a long scanned PDF
  through non-resumable ingestion just to write database rows.
- The resumable OCR workflow uses PaddleOCR first and keeps Tesseract fallback
  enabled by default for empty or low-confidence pages. Use `--no-fallback`
  only for targeted troubleshooting.

## Clean Baseline Reset

The first trial proved the pipeline, but existing Postgres rows and Qdrant
points can diverge if they were written before the UUIDv5 Qdrant point-id fix.
Before steady full ingestion, reset regenerated runtime stores and confirm the
baseline is empty.

Dry run first:

```powershell
.\.venv\Scripts\python.exe scripts\reset_runtime_stores.py --output data\run_logs\reset_runtime_stores_dry_run.json
```

Execute only when you are ready to discard existing ingestion rows and Qdrant
points:

```powershell
.\.venv\Scripts\python.exe scripts\reset_runtime_stores.py --execute --output data\run_logs\reset_runtime_stores_execute.json
```

Confirm Postgres ingestion tables are empty:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "select count(*) as documents from documents; select count(*) as chunks from chunks; select count(*) as sections from document_sections; select count(*) as figures_tables from figures_tables; select count(*) as citations from citations;" 2>&1 |
  Out-File -Encoding utf8 data\run_logs\reset_postgres_empty_check.txt
```

Confirm the Qdrant collection is absent or empty:

```powershell
try {
  Invoke-RestMethod -Method Post http://localhost:6333/collections/chunks/points/count -ContentType "application/json" -Body '{"exact":true}' |
    ConvertTo-Json -Depth 10
} catch {
  $_.Exception.Message
} |
  Out-File -Encoding utf8 data\run_logs\reset_qdrant_empty_check.txt
```

## Manual Trial Commands

Create the log directory:

```powershell
New-Item -ItemType Directory -Force data\run_logs | Out-Null
```

Record Docker service state:

```powershell
docker compose ps 2>&1 | Out-File -Encoding utf8 data\run_logs\trial_00_docker_ps.txt
```

Record Qdrant health:

```powershell
Invoke-WebRequest http://localhost:6333/healthz 2>&1 | Out-File -Encoding utf8 data\run_logs\trial_01_qdrant_health.txt
```

Record Postgres schema visibility:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "\dt" 2>&1 | Out-File -Encoding utf8 data\run_logs\trial_02_postgres_tables.txt
```

Record the active ingestion/storage settings without logging secret values:

```powershell
Get-Content .env |
  Select-String -Pattern "POSTGRES_ENABLED|QDRANT_ENABLED|QDRANT_COLLECTION|QDRANT_VECTOR_SIZE|EMBEDDING_PROVIDER|EMBEDDING_MODEL=|EMBEDDING_ENABLED|EMBEDDING_LOCAL_FILES_ONLY|EMBEDDING_BATCH_SIZE" |
  Out-File -Encoding utf8 data\run_logs\trial_03_env_storage_snapshot.txt
```

Record free disk space before parsing/OCR:

```powershell
[System.IO.DriveInfo]::GetDrives() |
  Where-Object { $_.Name -eq 'C:\' } |
  Select-Object Name,@{Name='FreeGB';Expression={[math]::Round($_.AvailableFreeSpace/1GB,2)}},@{Name='TotalGB';Expression={[math]::Round($_.TotalSize/1GB,2)}} |
  ConvertTo-Json |
  Out-File -Encoding utf8 data\run_logs\trial_03b_disk_free_before.json
```

Generate a full plan-only scan. This does not parse/OCR/chunk documents:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest data\raw --plan-only --output data\run_logs\trial_04_plan_all_raw.json
```

Summarize the plan by processing strategy and raw category:

```powershell
@'
import json, pathlib, collections
d = json.load(open("data/run_logs/trial_04_plan_all_raw.json", encoding="utf-8"))
docs = d.get("documents", [])
by_strategy = collections.Counter(x.get("processing_strategy") for x in docs)
by_category = {}
for x in docs:
    parts = pathlib.PureWindowsPath(x.get("source_path", "")).parts
    cat = parts[parts.index("raw") + 1] if "raw" in parts and parts.index("raw") + 1 < len(parts) else "unknown"
    item = by_category.setdefault(cat, {"docs": 0, "pages": 0, "ocr_docs": 0, "ocr_pages": 0})
    pages = x.get("page_count") or 0
    item["docs"] += 1
    item["pages"] += pages
    if x.get("processing_strategy") == "ocr_pdf":
        item["ocr_docs"] += 1
        item["ocr_pages"] += pages
print(json.dumps({
    "documents": len(docs),
    "pages": sum((x.get("page_count") or 0) for x in docs),
    "by_strategy": dict(by_strategy),
    "by_category": by_category,
}, ensure_ascii=False, indent=2))
'@ | .\.venv\Scripts\python.exe - |
  Out-File -Encoding utf8 data\run_logs\trial_04b_plan_summary.json
```

Extract the largest OCR book path from the plan. Later commands read this path
from the log file, so the command line does not need to contain non-ASCII file
names:

```powershell
@'
import json, pathlib
d = json.load(open("data/run_logs/trial_04_plan_all_raw.json", encoding="utf-8"))
docs = []
for x in d.get('documents',[]):
    parts = pathlib.PureWindowsPath(x.get("source_path", "")).parts
    cat = parts[parts.index("raw") + 1] if "raw" in parts and parts.index("raw") + 1 < len(parts) else ""
    if x.get("processing_strategy") == "ocr_pdf" and cat == "book":
        docs.append(x)
docs = sorted(docs, key=lambda x: (x.get("page_count") or 0), reverse=True)
open("data/run_logs/trial_04c_largest_ocr_book_path.txt", "w", encoding="utf-8").write((docs[0]["source_path"] if docs else "") + "\n")
print(json.dumps({"book_ocr": len(docs)}, ensure_ascii=False, indent=2))
'@ | .\.venv\Scripts\python.exe - |
  Out-File -Encoding utf8 data\run_logs\trial_04c_largest_ocr_book_summary.json
```

Extract standard native/OCR path lists from the plan. Standard is the largest
OCR load in the current corpus, so it must be batched from these lists instead
of ingested as one directory command:

```powershell
@'
import json, pathlib
d = json.load(open("data/run_logs/trial_04_plan_all_raw.json", encoding="utf-8"))
standard_native = []
standard_ocr = []
for item in d.get("documents", []):
    parts = pathlib.PureWindowsPath(item.get("source_path", "")).parts
    cat = parts[parts.index("raw") + 1] if "raw" in parts and parts.index("raw") + 1 < len(parts) else ""
    if cat != "standard":
        continue
    if item.get("processing_strategy") == "ocr_pdf":
        standard_ocr.append(item.get("source_path", ""))
    else:
        standard_native.append(item.get("source_path", ""))
open("data/run_logs/standard_native_paths.txt", "w", encoding="utf-8-sig").write("\n".join(standard_native) + "\n")
open("data/run_logs/standard_ocr_paths.txt", "w", encoding="utf-8-sig").write("\n".join(standard_ocr) + "\n")
print(json.dumps({"standard_native": len(standard_native), "standard_ocr": len(standard_ocr)}, ensure_ascii=False, indent=2))
'@ | .\.venv\Scripts\python.exe - |
  Out-File -Encoding utf8 data\run_logs\trial_04d_standard_path_summary.json
```

Run a small native-PDF ingestion trial. This avoids OCR and should clear first:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest "data\raw\manual\ORBIT 60 SERIES System Modules User Guide - 142M9080.pdf" --source-type manual --max-pages 5 --output data\run_logs\trial_05_ingest_manual_native.json
```

Summarize the native trial result:

```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/run_logs/trial_05_ingest_manual_native.json',encoding='utf-8')); print(json.dumps({'status':d.get('status'),'document_count':d.get('document_count'),'storage':d.get('storage'),'warnings':d.get('warnings')},ensure_ascii=False,indent=2))" |
  Out-File -Encoding utf8 data\run_logs\trial_06_manual_native_summary.json
```

Validate Postgres row counts after the native trial:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "select count(*) as documents from documents; select count(*) as chunks from chunks; select count(*) as embeddable_chunks from chunks where btrim(coalesce(normalized_text,text,'')) <> ''; select type, count(*) from documents group by type order by type; select d.id,d.type,d.title,d.parse_status,count(c.id) as chunks from documents d left join chunks c on c.doc_id=d.id group by d.id,d.type,d.title,d.parse_status order by d.id desc limit 8;" 2>&1 |
  Out-File -Encoding utf8 data\run_logs\trial_07_postgres_counts_after_native.txt
```

Validate Qdrant collection metadata:

```powershell
Invoke-RestMethod http://localhost:6333/collections/chunks |
  ConvertTo-Json -Depth 10 |
  Out-File -Encoding utf8 data\run_logs\trial_08_qdrant_collection_after_native.json
```

Validate exact Qdrant point count:

```powershell
Invoke-RestMethod -Method Post http://localhost:6333/collections/chunks/points/count -ContentType "application/json" -Body '{"exact":true}' |
  ConvertTo-Json -Depth 10 |
  Out-File -Encoding utf8 data\run_logs\trial_09_qdrant_count_after_native.json
```

Run one answer probe against the generated file-backed chunks:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ask "What are ORBIT 60 system modules used for?" --chunks-dir data\chunks --top-k 5 --scope in_scope --output data\run_logs\trial_10_answer_manual_native.json
```

If the native trial is clear, run a tiny OCR smoke test. This intentionally
limits the largest OCR-heavy book to two pages:

```powershell
$bookOcr = Get-Content -Encoding UTF8 -Raw data\run_logs\trial_04c_largest_ocr_book_path.txt
.\.venv\Scripts\python.exe -m apps.cli.main ingest $bookOcr.Trim() --source-type book --max-pages 2 --output data\run_logs\trial_11_ingest_book_ocr_2p.json
```

Summarize the OCR smoke result:

```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/run_logs/trial_11_ingest_book_ocr_2p.json',encoding='utf-8')); print(json.dumps({'status':d.get('status'),'document_count':d.get('document_count'),'storage':d.get('storage'),'warnings':d.get('warnings')},ensure_ascii=False,indent=2))" |
  Out-File -Encoding utf8 data\run_logs\trial_12_book_ocr_2p_summary.json
```

Validate Postgres row counts after the OCR smoke test:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "select count(*) as documents from documents; select count(*) as chunks from chunks; select count(*) as embeddable_chunks from chunks where btrim(coalesce(normalized_text,text,'')) <> ''; select type, count(*) from documents group by type order by type; select d.id,d.type,d.title,d.parse_status,count(c.id) as chunks from documents d left join chunks c on c.doc_id=d.id group by d.id,d.type,d.title,d.parse_status order by d.id desc limit 8;" 2>&1 |
  Out-File -Encoding utf8 data\run_logs\trial_13_postgres_counts_after_ocr.txt
```

Validate Qdrant point count after the OCR smoke test:

```powershell
Invoke-RestMethod -Method Post http://localhost:6333/collections/chunks/points/count -ContentType "application/json" -Body '{"exact":true}' |
  ConvertTo-Json -Depth 10 |
  Out-File -Encoding utf8 data\run_logs\trial_14_qdrant_count_after_ocr.json
```

Record free disk space after the trial:

```powershell
[System.IO.DriveInfo]::GetDrives() |
  Where-Object { $_.Name -eq 'C:\' } |
  Select-Object Name,@{Name='FreeGB';Expression={[math]::Round($_.AvailableFreeSpace/1GB,2)}},@{Name='TotalGB';Expression={[math]::Round($_.TotalSize/1GB,2)}} |
  ConvertTo-Json |
  Out-File -Encoding utf8 data\run_logs\trial_15_disk_free_after.json
```

## Acceptance Criteria

The trial is clear only if all required conditions below are true.

Infrastructure:

- `trial_00_docker_ps.txt` shows Postgres healthy and Qdrant running.
- `trial_01_qdrant_health.txt` contains HTTP 200 / health passed.
- `trial_02_postgres_tables.txt` lists the expected ingestion tables, including
  `documents`, `document_sections`, `chunks`, and `figures_tables`.
- `trial_03b_disk_free_before.json` shows enough free disk for the selected
  batch. Keep at least 50 GB free before full-corpus OCR.

Native ingestion:

- `trial_05_ingest_manual_native.json` has top-level `status: "ok"`.
- The native trial has no fatal warnings.
- `storage.postgres.status` is `ok`.
- `storage.postgres.documents` is at least 1.
- `storage.postgres.chunks` is greater than 0.
- `storage.qdrant.status` is `ok` for a vector-ready trial.
- `storage.qdrant.points` equals `storage.qdrant.embeddable_chunks` for the
  native trial. For text-only smoke batches this may also equal
  `storage.qdrant.chunks`, but full-corpus validation must use
  `embeddable_chunks`.
- `trial_10_answer_manual_native.json` has `status: "ok"` or a clear
  evidence-bound `insufficient`; it must not contain malformed JSON or terminal
  mojibake.

OCR smoke:

- `trial_11_ingest_book_ocr_2p.json` completes without machine sleep/restart.
- Top-level status is `ok`.
- The OCR trial writes Postgres rows successfully.
- Qdrant is `ok` with non-zero points if embeddings are enabled.
- Qdrant `points` equals `embeddable_chunks`, or any gap is explicitly explained
  by empty-text/non-embeddable chunks.
- Any OCR `needs_review` warnings are page-quality warnings, not pipeline
  crashes.

Vector readiness:

- Qdrant skipped status is not acceptable for full vector ingestion.
- Empty-vector fallback is not acceptable for full vector ingestion.
- `QDRANT_VECTOR_SIZE` matches the active embedding model dimension.
- Full-corpus Qdrant point count should match Postgres chunks with non-empty
  text, not total chunks. Figure/table-only or empty-text chunks may be valid
  Postgres chunks without Qdrant vectors.
- If `trial_08_qdrant_collection_after_native.json` or
  `trial_09_qdrant_count_after_native.json` is missing because no collection was
  created, the vector path is not clear.

Operational safety:

- No ingestion command was run in parallel.
- No command printed large JSON payloads to the terminal.
- All outputs needed for diagnosis are in `data\run_logs`.
- The operator can restart the UI/API with:

```powershell
.\.venv\Scripts\python.exe scripts\start_operator.py --restart
```

## Full Ingestion Gate

Only after the trial clears, proceed to full ingestion in this order:

1. Clean baseline reset.
2. `manual`
3. `standard` native PDFs one by one.
4. `standard` OCR PDFs through staging/resumable OCR.
5. `paper`
6. `book` through staging/resumable OCR for scanned books.

Run each non-book category as a separate command with the matching
`--source-type`, and write every result to `data\run_logs`.

Do not run full ingestion until Qdrant produces non-empty vector points in the
small trial, unless the explicit goal is Postgres-only ingestion.

After `reset_runtime_stores.py --execute`, rerun the short native + OCR smoke
trial on the clean baseline. Proceed to full ingestion only if the clean trial
shows Postgres embeddable chunks and Qdrant points aligned.

## Full Ingestion Commands

Manual batch:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest data\raw\manual --source-type manual --output data\run_logs\full_01_manual.json
```

Do not run `data\raw\standard` as one command. Standard is currently the
largest OCR load. Run native standard files one at a time from the path list:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest data\raw\standard --plan-only --output data\run_logs\full_02_standard_plan.json

@'
import json
d = json.load(open("data/run_logs/full_02_standard_plan.json", encoding="utf-8"))
native = []
ocr = []
for item in d.get("documents", []):
    target = ocr if item.get("processing_strategy") == "ocr_pdf" else native
    target.append(item.get("source_path", ""))
open("data/run_logs/standard_native_paths.txt", "w", encoding="utf-8-sig").write("\n".join(native) + "\n")
open("data/run_logs/standard_ocr_paths.txt", "w", encoding="utf-8-sig").write("\n".join(ocr) + "\n")
open("data/run_logs/full_02_standard_path_summary.json", "w", encoding="utf-8").write(
    json.dumps({"standard_native": len(native), "standard_ocr": len(ocr)}, ensure_ascii=False, indent=2) + "\n"
)
'@ | .\.venv\Scripts\python.exe -

$nativeList = (Resolve-Path -LiteralPath data\run_logs\standard_native_paths.txt).Path
$nativePaths = @([System.IO.File]::ReadAllLines($nativeList, [System.Text.Encoding]::UTF8) | Where-Object { $_.Trim() })
$missingNative = @($nativePaths | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingNative.Count -gt 0) {
  $missingNative | Out-File -Encoding utf8 data\run_logs\full_02_standard_native_missing_paths.txt
  throw "Standard native path validation failed. See full_02_standard_native_missing_paths.txt"
}

$i = 0
$nativePaths | ForEach-Object {
  $i += 1
  $path = $_.Trim()
  $out = "data\run_logs\full_02_standard_native_{0:D3}.json" -f $i
  .\.venv\Scripts\python.exe -m apps.cli.main ingest $path --source-type standard --output $out
  if ($LASTEXITCODE -ne 0) {
    throw "Standard native ingestion failed at item $i. See $out"
  }
}
```

Run scanned standard PDFs through the staged/resumable flow in the next section.

Paper batch:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest data\raw\paper --source-type paper --output data\run_logs\full_03_paper.json
```

Do not run `data\raw\book` as one unbounded command. Use the bounded/resumable
book flow below for scanned books.

## Resumable OCR Standard Flow

Standard is the current OCR bulk: the plan found 27 OCR standard PDFs / 754 OCR
pages. Process one standard PDF at a time through a staging directory. The
resumable workflow reuses existing `pages.jsonl` for the staged document, so
rerunning the same checkpoint does not restart from page 1.

```powershell
$ocrList = (Resolve-Path -LiteralPath data\run_logs\standard_ocr_paths.txt).Path
$ocrPaths = @([System.IO.File]::ReadAllLines($ocrList, [System.Text.Encoding]::UTF8) | Where-Object { $_.Trim() })
$missingOcr = @($ocrPaths | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingOcr.Count -gt 0) {
  $missingOcr | Out-File -Encoding utf8 data\run_logs\full_02_standard_ocr_missing_paths.txt
  throw "Standard OCR path validation failed. See full_02_standard_ocr_missing_paths.txt"
}

$i = 0
$ocrPaths | ForEach-Object {
  $i += 1
  $path = $_.Trim()
  $tag = "standard_ocr_{0:D3}" -f $i
  if (Test-Path data\raw\standard_staging) {
    Remove-Item -LiteralPath data\raw\standard_staging -Recurse -Force
  }
  New-Item -ItemType Directory -Force data\raw\standard_staging | Out-Null
  Copy-Item -LiteralPath $path -Destination data\raw\standard_staging -Force
  .\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\standard_staging --source-type standard --doc-id-mode content --max-pages 25 2>&1 | Out-File -Encoding utf8 "data\run_logs\$tag`_025.txt"
  if ($LASTEXITCODE -ne 0) { throw "Standard OCR ingestion failed at item $i, 25-page checkpoint." }
  .\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\standard_staging --source-type standard --doc-id-mode content --max-pages 50 2>&1 | Out-File -Encoding utf8 "data\run_logs\$tag`_050.txt"
  if ($LASTEXITCODE -ne 0) { throw "Standard OCR ingestion failed at item $i, 50-page checkpoint." }
  .\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\standard_staging --source-type standard --doc-id-mode content 2>&1 | Out-File -Encoding utf8 "data\run_logs\$tag`_full.txt"
  if ($LASTEXITCODE -ne 0) { throw "Standard OCR ingestion failed at item $i, full checkpoint." }
}
```

After the standard OCR files complete, persist all standard exports:

```powershell
.\.venv\Scripts\python.exe scripts\persist_ingestion_exports.py --source-type standard --output data\run_logs\full_02_standard_persist_exports.json
```

Validate standard Postgres/Qdrant counts:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "select count(*) as documents from documents; select count(*) as chunks from chunks; select count(*) as embeddable_chunks from chunks where btrim(coalesce(normalized_text,text,'')) <> ''; select type, count(*) from documents group by type order by type;" 2>&1 |
  Out-File -Encoding utf8 data\run_logs\full_02_standard_postgres_counts.txt
Invoke-RestMethod -Method Post http://localhost:6333/collections/chunks/points/count -ContentType "application/json" -Body '{"exact":true}' |
  ConvertTo-Json -Depth 10 |
  Out-File -Encoding utf8 data\run_logs\full_02_standard_qdrant_count.json
```

## Resumable OCR Book Flow

The existing resumable flow is file-based. It reuses already parsed pages in
`data/ocr/book/<doc_id>/pages.jsonl` and regenerates chunks/manifests from those
pages. It does not directly write Postgres/Qdrant rows, so persist exports after
the OCR pass.

Use incremental `--max-pages` checkpoints for large scanned books. Stage one
PDF at a time so the directory-level OCR workflow cannot accidentally process
the entire `data\raw\book` folder:

```powershell
$bookOcr = Get-Content -Encoding UTF8 -Raw data\run_logs\trial_04c_largest_ocr_book_path.txt
New-Item -ItemType Directory -Force data\run_logs | Out-Null
New-Item -ItemType Directory -Force data\raw\book_staging | Out-Null
Copy-Item -LiteralPath $bookOcr.Trim() -Destination data\raw\book_staging -Force
.\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\book_staging --source-type book --doc-id-mode content --max-pages 50 2>&1 |
  Out-File -Encoding utf8 data\run_logs\book_ocr_050.txt
.\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\book_staging --source-type book --doc-id-mode content --max-pages 100 2>&1 |
  Out-File -Encoding utf8 data\run_logs\book_ocr_100.txt
.\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\book_staging --source-type book --doc-id-mode content --max-pages 200 2>&1 |
  Out-File -Encoding utf8 data\run_logs\book_ocr_200.txt
.\.venv\Scripts\python.exe scripts\ocr_raw_books_with_paddle.py --raw-dir data\raw\book_staging --source-type book --doc-id-mode content 2>&1 |
  Out-File -Encoding utf8 data\run_logs\book_ocr_full.txt
```

The script processes all PDFs in the selected directory. Keep only the intended
PDF in `data\raw\book_staging` for each OCR batch.

After the resumable OCR flow completes, persist the generated exports:

```powershell
.\.venv\Scripts\python.exe scripts\persist_ingestion_exports.py --source-type book --output data\run_logs\book_persist_exports.json
```

Validate Postgres/Qdrant after persisting:

```powershell
docker compose exec -T postgres psql -U vib -d vibration -c "select count(*) as documents from documents; select count(*) as chunks from chunks; select count(*) as embeddable_chunks from chunks where btrim(coalesce(normalized_text,text,'')) <> ''; select type, count(*) from documents group by type order by type; select d.id,d.type,d.title,d.parse_status,count(c.id) as chunks from documents d left join chunks c on c.doc_id=d.id group by d.id,d.type,d.title,d.parse_status order by d.id desc limit 8;" 2>&1 |
  Out-File -Encoding utf8 data\run_logs\book_postgres_counts.txt
Invoke-RestMethod -Method Post http://localhost:6333/collections/chunks/points/count -ContentType "application/json" -Body '{"exact":true}' |
  ConvertTo-Json -Depth 10 |
  Out-File -Encoding utf8 data\run_logs\book_qdrant_count.json
```

## Runtime Expectations

OCR throughput varies by page complexity and CPU load. Treat OCR as hours-scale
work for 1577 pages, not as a hang, as long as the log shows page progress. A
single PaddleOCR process can still saturate CPU. For unattended long runs, you
may cap common math runtimes before starting the process:

```powershell
$env:OMP_NUM_THREADS="4"
$env:MKL_NUM_THREADS="4"
```

Record these caps in the run log if used:

```powershell
"OMP_NUM_THREADS=$env:OMP_NUM_THREADS; MKL_NUM_THREADS=$env:MKL_NUM_THREADS" |
  Out-File -Encoding utf8 data\run_logs\ocr_thread_caps.txt
```

## Failure And Recovery

If a batch fails:

1. Stop. Do not launch another ingestion command in parallel.
2. Preserve the failed command's run log.
3. Check disk space and Docker health again.
4. For resumable book OCR, rerun the same command or the next higher
   `--max-pages`; existing pages are reused by default.
5. For normal ingest, re-running the same document hash refreshes existing
   Postgres rows instead of duplicating them.
6. If the local artifacts are polluted, preview cleanup first:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile regenerable |
  Out-File -Encoding utf8 data\run_logs\cleanup_preview_after_failed_batch.json
```

Run destructive cleanup only when you are ready to regenerate artifacts:

```powershell
.\.venv\Scripts\python.exe scripts\data_cleanup.py --profile regenerable --execute |
  Out-File -Encoding utf8 data\run_logs\cleanup_execute_after_failed_batch.json
```

This cleanup removes regenerable outputs such as `data/ocr`, `data/extracted`,
and `data/exports`, but keeps `data/raw` and `data/chunks` unless a deeper
profile is explicitly selected.
