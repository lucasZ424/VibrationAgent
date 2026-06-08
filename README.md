# Vibration Agent

`vibration_agent` is a personal, engineering-oriented vibration-learning and knowledge-base agent. It is designed for real industrial use cases such as rotating machinery, condition monitoring, signal analysis, and standards interpretation.

## Product Positioning

This product is designed for local, personal deployment by one engineering user. The default operating model is trusted local files, localhost API/CLI access, and a private knowledge base; it is not a multi-user SaaS or public web service.

Development should prioritize corpus quality, retrieval reliability, citation traceability, Chinese/English engineering usability, and local reproducibility before production API hardening. Shared, remote, or public deployment changes the security model and must be treated as explicit hardening work.

## Phase-2 Runtime Scope

Phase 2 is the current local personal knowledge-base runtime. Phase 1 remains
documented as the compatibility baseline in `docs/phase_1_interface_freeze.md`;
the Phase-2 freeze is recorded in `docs/phase_2_interface_freeze.md`.

Current active and available skills:

| ID | Skill | Status |
| --- | --- | --- |
| S1 | Document ingestion and parsing | active |
| S2 | Knowledge-base retrieval | active |
| S3 | Concept explanation, summary, and QA | active |
| S4 | Evidence-bound engineering analysis | optional active |
| S5 | Evidence-bound formula derivation | optional active |
| V1 | Term/symbol/unit normalization | optional active |
| V2 | Citation and visible-evidence check | active |
| V3 | Advisory reviewer for extreme tasks | optional active |
| V4 | Output-style shaping | active |
| S6-S8 | literature search, model selection, experiment advice | deferred |

## Phase-2 Runtime Rules

- Default answer mode is engineering.
- Phase-2 query chain is `S2 -> S3 -> optional S4/S5 -> V2 -> V4`, with V3
  advisory review only for extreme tasks.
- V1 is active but not a chain step; it normalizes in-memory input/output when
  configured.
- S1 prepares the knowledge base and is invoked explicitly through ingestion
  entry points.
- S6-S8 remain deferred and must not be called by the Phase-2 runtime.
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


## Phase-2 API

The API is a localhost development entry point. Defaults preserve the trusted
local workflow: auth, CORS, and rate limiting are disabled unless explicitly
enabled in `configs/api.yaml` or environment variables. HTTP ingestion now
validates that requested paths stay inside the configured workspace before any
other API gate runs. `/health` reports `ok`, `degraded`, or `fail` plus optional
Postgres/Qdrant dependency details when those dependencies are enabled.

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

For API ingestion, `path` must resolve inside the request workspace. Copy or
place external files under the workspace before posting them to `/ingest`.

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

The same fast command is the PR/push CI gate:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration"
```

CI also runs the cheap Phase-2 contract E2E on PR/push:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_phase2_end_to_end.py -q -m "not large_corpus"
```

To actually block PR merges, configure the `fast regression` GitHub Actions
check as a required status check in branch protection. Scheduled nightly
failures rely on GitHub Actions notification settings unless an explicit
notification step is added.

Run the full regression suite, including Phase-0 end-to-end checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not large_corpus"
```

This is the Makefile equivalent:

```powershell
make test-full
```

Run only the Phase-2 contract E2E:

```powershell
make test-contract
```

Run the Obj8 large-corpus smoke test explicitly; it is excluded from the fast
suite by marker:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_large_corpus.py -q -m large_corpus
```

The nightly CI path runs `python -m pytest tests -q`, which includes the
large-corpus smoke, then runs a one-page benchmark sample and uploads
`data/exports/ci/` as a workflow artifact instead of committing benchmark
output.

Run a real cold-start baseline against a larger local corpus:

```powershell
.\.venv\Scripts\python.exe scripts\bench_large_corpus.py data\raw\book --output data\exports\large_corpus_baseline.json
```

Run the manual Phase-2 E2E probe outside CI:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py
```

To manually replay the S3 LLM contract without adding an online dependency to
CI, pass a captured JSON response. This is captured-response replay, not a live
provider call:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --s3-llm-response-json data\exports\manual_s3_response.json
```

Phase-3 model-backed work keeps the same rule: CI is replay-only and must not
make live OpenAI or Anthropic calls. Live provider calls are allowed only through
explicit local manual/capture commands after the relevant Phase-3 objective adds
provider clients, replay fixtures, budget guards, and live-call guards. Provider
keys must stay in local environment variables or `.env.local`, never in chat,
fixtures, logs, or commits.

When validating the Obj6 Qdrant cold-start population path, enable a local
embedding model plus Qdrant and add `--require-qdrant-population`; the command
then exits non-zero if the benchmark falls back before Qdrant upsert succeeds.

Reusable small fixtures live under `tests/fixtures/`; they are intentionally independent of the full book corpus. Phase-2 end-to-end tests use these fixtures to validate CLI/API/legacy ingestion paths and the Phase-2 contract chain. Phase-2 deferred/polish decisions are tracked in `docs/phase_2_deferred_and_polish_audit.md`.


## Phase-1 Interface Freeze

Phase 1 is frozen as the Phase-0 implementation. The stable runtime chain is `S1 ingestion -> S2 retrieval -> S3 evidence-bound QA/summary -> V4 style`. Interface freeze details are recorded in `docs/phase_1_interface_freeze.md`; deferred/polish decisions are recorded in `docs/phase_1_deferred_and_polish_audit.md`.

## Phase-2 Freeze

Phase 2 has been frozen as the local personal knowledge-base Agent runtime.
The approved development order is recorded in
`docs/phase_2_development_order.md`; the frozen Phase-2 interface is recorded in
`docs/phase_2_interface_freeze.md`.

In short, Phase 2 makes the local knowledge-base path usable: stronger fixtures and document ingestion, real retrieval/storage, citation-guarded model synthesis, selected quality and engineering skills, targeted API hardening, CI, and a Phase-2 interface freeze. It still excludes later-phase product surfaces such as literature search, model selection, experiment advice, Web UI, k8s, multi-tenant operation, and a full observability stack.

Post-freeze changes to schemas, chain order, structured result keys, API shapes,
or ingestion output shapes must follow `docs/phase_2_interface_freeze.md` and
`docs/phase_2_migrations.md`.

## Phase-3 Planning

Phase 3 is planned as the first usable engineering-assistant intelligence
upgrade on top of the Phase-2 freeze. The approved development order is recorded
in `docs/phase_3_development_order.md`; progress and contract changes are
tracked in `docs/phase_3_progress.md` and `docs/phase_3_migrations.md`.

Phase 3 keeps deterministic Phase-2 behavior as the default. OpenAI S3/S4/S5 and
Claude supervisor paths are default-off, budget-governed, replayable, and
manual-live-only until their dedicated objectives clear review.

## Development Start Points

1. `src/vibration_agent/schemas.py`: Pydantic contracts.
2. `src/vibration_agent/config.py`: runtime configuration.
3. `src/vibration_agent/skills/base.py`: skill interface.
4. `src/vibration_agent/ingestion/pipeline.py`: ingestion entry.
