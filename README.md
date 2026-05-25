# Vibration Agent

`vibration_agent` is a personal, engineering-oriented vibration-learning and knowledge-base agent. It is designed for real industrial use cases such as rotating machinery, condition monitoring, signal analysis, and standards interpretation.

## Phase-0 Scope

Only four skills ship in the first milestone.

| ID | Skill | Status |
| --- | --- | --- |
| S1 | Document ingestion and parsing | active |
| S2 | Knowledge-base retrieval | active |
| S3 | Concept explanation, summary, and QA | active |
| V4 | Output-style shaping | active |
| S4-S8, V1-V3 | engineering analysis, formula derivation, literature search, model selection, experiment advice, term/symbol/unit normalization, citation check, reviewer | deferred |

## Phase-0 Development Rules

- Default answer mode is engineering.
- Phase-0 runtime chain is `S2 -> S3 -> V4`; S1 prepares the knowledge base.
- S4-S8 and V1-V3 are deferred. Keep their names reserved, but do not call or implement them in the Phase-0 path.
- `src/vibration_agent/schemas.py` is the single source of truth for I/O contracts.
- `src/vibration_agent/config.py` is the single source of truth for config loading.
- Markdown is not a required Agent intermediate format; structured JSON/JSONL and asset references are preferred.

## Architecture

```text
User
  -> Tutor-Orchestrator
       -> Task layer      src/vibration_agent/skills
       -> Quality layer   src/vibration_agent/quality + skills/v4_style.py
       -> Knowledge layer src/vibration_agent/knowledge + taxonomy
       -> Data layer      src/vibration_agent/storage + db + data
```

## Tech Stack

Python 3.11, FastAPI, PostgreSQL, Qdrant, Redis, PyMuPDF, PaddleOCR primary, Tesseract fallback, React/Next.js deferred.

## Top-Level Layout

```text
Agent/
  apps/       entry points: api, worker, cli, ui
  src/        importable Python package vibration_agent
  data/       raw, ocr, extracted, chunks, embeddings, exports
  db/         postgres migrations and qdrant collection specs
  configs/    YAML runtime config
  taxonomy/   glossary, symbols, units, engineering context
  prompts/    orchestrator, skill prompts, templates
  scripts/    operational scripts and migration references
  tests/      unit, integration, fixtures
  docs/       architecture and development notes
```

## Quickstart

```bash
pip install -e .
cp .env.example .env
python -m apps.cli.main scope
python -m apps.cli.main config
```

## Phase-0 CLI

Build structured ingestion exports for books under `data/raw/book`:

```bash
python -m apps.cli.main ingest data/raw/book --source-type book
```

Ask against an exported chunk file:

```bash
python -m apps.cli.main ask "阻尼比如何影响转子振动？" --chunks-jsonl data/chunks/book/<doc_id>/chunks.jsonl --top-k 4
```

CLI exit codes:

- `0`: ok
- `1`: fail
- `2`: insufficient, including out-of-scope or missing evidence


## Phase-0 API

The API is a localhost development entry point for Phase-0. It does not yet include CORS, auth, rate limiting, path sandboxing, or downstream dependency readiness checks.

Start the local FastAPI server:

```powershell
.\.venv\Scripts\uvicorn.exe apps.api.main:app --reload
```

Check runtime status:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Build ingestion exports through the API:

```powershell
$body = @{
  path = "data/raw/book"
  source_type = "book"
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -ContentType "application/json" -Body $body
```

Ask against exported chunks:

```powershell
$body = @{
  query = "阻尼比如何影响转子振动？"
  chunks_jsonl = @("data/chunks/book/<doc_id>/chunks.jsonl")
  top_k = 4
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/query -Method Post -ContentType "application/json" -Body $body
```

HTTP `2xx` means the API call itself was handled. Agent-level outcomes are still reported in the JSON body as `status: ok | insufficient | fail`.

Legacy compatibility:

- `scripts/ingest_folder.py` is deprecated as a primary interface. It remains as a thin wrapper around `python -m apps.cli.main` for older commands.
API keys should not be pasted into chat or committed. When model-backed API work
is activated, put provider keys in local environment variables or `.env.local`.


## Testing

Install test dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the regression suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Reusable small fixtures live under `tests/fixtures/`; they are intentionally independent of the full book corpus.

## Development Start Points

1. `src/vibration_agent/schemas.py`: Pydantic contracts.
2. `src/vibration_agent/config.py`: runtime configuration.
3. `src/vibration_agent/skills/base.py`: skill interface.
4. `src/vibration_agent/ingestion/pipeline.py`: ingestion entry.
