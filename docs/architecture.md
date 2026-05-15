# Architecture Notes

This project implements `vibration_agent`, a personal engineering-oriented vibration-learning and knowledge-base agent. The design source is `vibration_agent_design.docx`; this file records the decisions that are already binding for code layout and Phase-0 development.

## Layer To Code Map

| Layer | Code Location |
| --- | --- |
| Interaction | `src/vibration_agent/orchestrator/` and `apps/*` |
| Task skills | `src/vibration_agent/skills/` |
| Quality control | `src/vibration_agent/quality/` and `src/vibration_agent/skills/v4_style.py` |
| Knowledge | `src/vibration_agent/knowledge/` and `taxonomy/` |
| Data | `src/vibration_agent/storage/`, `db/`, and `data/` |

## Src Layout

The importable package lives under `src/vibration_agent`. Runtime entry points under `apps/*` stay thin and delegate to the library. This keeps package imports stable and prevents app runners from becoming hidden business logic.

## OCR Ownership

OCR belongs under `src/vibration_agent/ingestion/ocr/` because OCR is only one branch of document ingestion. It should not become an independent top-level feature. The ingestion pipeline owns routing between native PDF parsing, PaddleOCR, and Tesseract fallback.

## Phase-0 Scope

Phase-0 is limited to four active skills:

- `s1_ingestion`: document ingestion and parsing
- `s2_retrieval`: knowledge-base retrieval
- `s3_qa_summary`: concept explanation, summary, and QA
- `v4_style`: output-style shaping

Reserved but inactive skills are:

- `s4_engineering_analysis`
- `s5_formula_derivation`
- `s6_literature_search`
- `s7_model_selection`
- `s8_experiment_advice`
- `v1_term_symbol_unit_normalizer`
- `v2_citation_check`
- `v3_reviewer`

Deferred skills may appear in registries or scope declarations, but they must not be implemented inside S3 or called by the Phase-0 orchestrator.

## Development Order Rule

Targets 1-3 establish the control plane for later work:

1. Scope and boundary are documented before new capability work.
2. `src/vibration_agent/schemas.py` is the single source of truth for skill I/O, ingestion objects, retrieval hits, and file export contracts.
3. `src/vibration_agent/config.py` is the single entry point for runtime settings. Business modules should not read `configs/*.yaml` or environment variables directly.

Emergency scripts under `scripts/` can be used as migration references, but stable behavior should move into `src/vibration_agent/` modules.