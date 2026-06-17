# Vibration Agent

`vibration_agent` is a personal, engineering-oriented vibration-learning and knowledge-base agent. It is designed for real industrial use cases such as rotating machinery, condition monitoring, signal analysis, and standards interpretation.

## Product Positioning

This product is designed for local, personal deployment by one engineering user. The default operating model is trusted local files, localhost API/CLI access, and a private knowledge base; it is not a multi-user SaaS or public web service.

Development should prioritize corpus quality, retrieval reliability, citation traceability, Chinese/English engineering usability, and local reproducibility before production API hardening. Shared, remote, or public deployment changes the security model and must be treated as explicit hardening work.

## Phase-3 Runtime Scope

Phase 3 is the current frozen local personal knowledge-base runtime with
default-off model-backed engineering-assistant lanes. Phase 1 and Phase 2 remain
documented compatibility baselines in `docs/phase_1_interface_freeze.md` and
`docs/phase_2_interface_freeze.md`; the Phase-3 freeze is recorded in
`docs/phase_3_interface_freeze.md`.

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

## Phase-3 Runtime Rules

- Default answer mode is engineering.
- Default query chain is `S2 -> S3 -> optional S4/S5 -> V2 -> V4`, with V3
  advisory review only for extreme tasks and optional supervisor annotation for
  extreme/reviewer-flagged answers.
- V1 is active but not a chain step; it normalizes in-memory input/output when
  configured.
- S1 prepares the knowledge base and is invoked explicitly through ingestion
  entry points.
- S3/S4/S5 LLM branches and the Anthropic supervisor lane are default-off,
  budget-governed, replayable, and manual-live-only.
- S6-S8 remain deferred and must not be called by the Phase-3 runtime.
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
is activated, put provider keys in local environment variables or a local
`.env` file. `config.load()` reads `.env` from the workspace, only fills
missing process environment variables, and never overrides values already set in
PowerShell. `.env.example` is a historical sanitized config snapshot, not the
active runtime source.


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
explicit local manual/capture commands with live/capture gates enabled. Provider
keys must stay in local environment variables or `.env`, never in chat,
fixtures, logs, or commits.

Run the Phase-3 manual E2E probe without live provider calls:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --difficulty low
```

For repeated manual live validation, create ignored local `.env` content
like this:

```dotenv
LLM_LIVE_ENABLED=true
LLM_CAPTURE_ENABLED=true
OPENAI_API_KEY=<local key>
ANTHROPIC_API_KEY=<local key>
```

Run a manual OpenAI S3/S4/S5 live capture:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --live-openai --user-mode engineering --fixture-dir data\exports\manual_llm_fixtures
```

Run a manual Anthropic supervisor live capture:

```powershell
.\.venv\Scripts\python.exe scripts\manual_e2e.py --live-supervisor --difficulty extreme --fixture-dir data\exports\manual_llm_fixtures
```

Capture a single provider request from prepared JSON kwargs:

```powershell
.\.venv\Scripts\python.exe scripts\llm_capture.py s3_qa_summary --request-json data\exports\manual_s3_request.json --fixture-dir data\exports\manual_llm_fixtures
```

Manual live fixtures should be inspected, redacted by the capture helper, and
promoted to `tests\fixtures\llm\` only when they are intentionally becoming
replay regression fixtures.

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

## Phase-3 Freeze

Phase 3 is frozen as the first usable engineering-assistant intelligence upgrade
on top of the Phase-2 freeze. The approved development order is recorded in
`docs/phase_3_development_order.md`; the frozen Phase-3 interface is recorded in
`docs/phase_3_interface_freeze.md`; accepted residual risks and Phase-4
candidates are recorded in `docs/phase_3_deferred_and_polish_audit.md`.
Progress and contract changes are tracked in `docs/phase_3_progress.md` and
`docs/phase_3_migrations.md`.

Phase 3 keeps deterministic Phase-2 behavior as the default. OpenAI S3/S4/S5 and
Claude supervisor paths are default-off, budget-governed, replayable, and
manual-live-only. Obj9 recorded successful manual live validation for the OpenAI
S3/S4/S5 lanes and the Anthropic supervisor lane.

Post-freeze changes to schemas, chain order, structured result keys, replay
fixture layout, provider request shapes, API shapes, or ingestion output shapes
must follow `docs/phase_3_interface_freeze.md` and
`docs/phase_3_migrations.md`.

## Phase-4 Backend Freeze

Phase 4 is the first post-freeze expansion cycle. The approved development
order is recorded in `docs/phase_4_development_order.md`; progress and contract
changes are tracked in `docs/phase_4_progress.md` and
`docs/phase_4_migrations.md`.

As of Obj13, the Phase-4 backend is frozen before UI and observability work.
The backend freeze is recorded in `docs/phase_4_backend_interface_freeze.md`;
accepted residual risks and deferred items are recorded in
`docs/phase_4_deferred_and_polish_audit.md`.

The frozen backend keeps final answers on the V2/V4-bound path. S6/S7/S8 are
default-off advisory handoff skills, not final-answer renderers. Formula
rendering metadata is structured fallback information for clients, not symbolic
proof. CAS/symbolic proof remains deferred unless a future optional checker
objective satisfies the documented eval gate.

## Development Start Points

1. `src/vibration_agent/schemas.py`: Pydantic contracts.
2. `src/vibration_agent/config.py`: runtime configuration.
3. `src/vibration_agent/skills/base.py`: skill interface.
4. `src/vibration_agent/ingestion/pipeline.py`: ingestion entry.
