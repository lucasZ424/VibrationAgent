# R1 Wave C: direct UTF-8 CLI output

Date: 2026-06-22

## Problem

Windows PowerShell 5.1 decodes native-process stdout with the console code page
before `Out-File -Encoding utf8` writes it again. Python emitted valid UTF-8, but
the intermediate decode produced mojibake in run logs. OCR pages and chunks were
not affected because Python wrote those files directly.

## Change

`ingest`, `parse-pages`, and `ask` accept `--output PATH`. When supplied, the CLI
creates the parent directory and writes JSON directly from Python with UTF-8.
Nothing is printed to stdout.

The CLI also best-effort reconfigures default stdout to UTF-8 at process start
so redirected JSON does not crash on Windows code pages such as GBK. Use
`--output` for durable run logs because it bypasses shell pipeline decoding
entirely.

Example:

```powershell
.\.venv\Scripts\python.exe -m apps.cli.main ingest `
  "data\raw\standard\example.pdf" `
  --source-type standard `
  --output "data\run_logs\ingest_standard.json"
```

Do not pipe native JSON through `Out-File` on Windows PowerShell 5.1 when exact
Unicode preservation matters; prefer `--output`.

## Verification

- CLI unit tests cover strict UTF-8 Chinese, `∆`, and `•`, plus stdout
  reconfiguration before default JSON printing.
- Real standard query output: valid strict UTF-8, zero replacement characters,
  zero detected mojibake markers, status `ok`.
- Full non-large-corpus suite: 482 passed, 2 skipped, 1 deselected; one Qdrant
  compatibility warning.

## Rollback

Remove stdout reconfiguration, remove the three `--output` arguments, restore
stdout-only `_print_json`, and remove the UTF-8 output tests. Stored OCR/chunk
data requires no migration.
