# Vibration Agent

`vibration_agent` is a personal, engineering-oriented vibration-learning and knowledge-base agent. It is designed for real industrial use cases such as rotating machinery, condition monitoring, signal analysis, and standards interpretation.

## Product Positioning

This product is designed for local, personal deployment by one engineering user. The default operating model is trusted local files, localhost API/CLI access, and a private knowledge base; it is not a multi-user SaaS or public web service.

Development should prioritize corpus quality, retrieval reliability, citation traceability, Chinese/English engineering usability, and local reproducibility before production API hardening. Shared, remote, or public deployment changes the security model and must be treated as explicit hardening work.

## Phase-0 Scope

This is the frozen Phase-1 runtime state. Active development is Phase 2; see the Phase-2 Development Plan below.

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

Run only fast tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration"
```

Run the full regression suite, including Phase-0 end-to-end checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus"
```

Run the Obj8 large-corpus smoke test explicitly; it is excluded from the fast
suite by marker:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_large_corpus.py -q -m large_corpus
```

Run a real cold-start baseline against a larger local corpus:

```powershell
.\.venv\Scripts\python.exe scripts\bench_large_corpus.py data\raw\book --output data\exports\large_corpus_baseline.json
```

When validating the Obj6 Qdrant cold-start population path, enable a local
embedding model plus Qdrant and add `--require-qdrant-population`; the command
then exits non-zero if the benchmark falls back before Qdrant upsert succeeds.

Reusable small fixtures live under `tests/fixtures/`; they are intentionally independent of the full book corpus. Obj19 end-to-end tests use the same fixture to validate CLI, API, and legacy ingestion paths. Phase-1 deferred/polish decisions are tracked in `docs/phase_1_deferred_and_polish_audit.md`.


## Phase-1 Interface Freeze

Phase 1 is frozen as the Phase-0 implementation. The stable runtime chain is `S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style`. Interface freeze details are recorded in `docs/phase_1_interface_freeze.md`; deferred/polish decisions are recorded in `docs/phase_1_deferred_and_polish_audit.md`.

## Phase-2 Development Plan

Phase 2 is now the active development plan for turning the frozen Phase-1 skeleton into a locally usable personal knowledge-base Agent. The approved development order is recorded in `docs/phase_2_development_order.md`.

In short, Phase 2 makes the local knowledge-base path usable: stronger fixtures and document ingestion, real retrieval/storage, citation-guarded model synthesis, selected quality and engineering skills, targeted API hardening, CI, and a Phase-2 interface freeze. It still excludes later-phase product surfaces such as literature search, model selection, experiment advice, Web UI, k8s, multi-tenant operation, and a full observability stack.

Work proceeds one Obj at a time, with review before the next Obj starts. Phase-1 frozen contracts remain valid until a documented Phase-2 migration updates them through `docs/phase_2_migrations.md`.

## Development Start Points

1. `src/vibration_agent/schemas.py`: Pydantic contracts.
2. `src/vibration_agent/config.py`: runtime configuration.
3. `src/vibration_agent/skills/base.py`: skill interface.
4. `src/vibration_agent/ingestion/pipeline.py`: ingestion entry.
