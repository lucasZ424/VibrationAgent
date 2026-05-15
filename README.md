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

## Development Start Points

1. `src/vibration_agent/schemas.py`: Pydantic contracts.
2. `src/vibration_agent/config.py`: runtime configuration.
3. `src/vibration_agent/skills/base.py`: skill interface.
4. `src/vibration_agent/ingestion/pipeline.py`: ingestion entry.