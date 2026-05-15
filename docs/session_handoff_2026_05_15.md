# Session handoff — 2026-05-15

Working directory is now `C:\Challenge\Viberation\Agent` (was the parent dir `C:\Challenge\Viberation`). This note summarizes the review session that ended on 2026-05-15 so the next session can pick up without re-reading the entire tree.

## What was reviewed

Phase-1 progress against `docs/phase_1_development_order.md`. User stated dev is complete through **objective 5 (page-level OCR & parsing layer)**, i.e. files 1–12 in the recommended implementation order.

## Per-objective verdict

| Obj | Topic | Verdict | Notes |
| --- | --- | --- | --- |
| 1 | Phase-1 boundaries locked | ✅ done | `schemas.py:38–53` (`PHASE0_ACTIVE_SKILLS` etc.) + README table + phase_1 doc consistent |
| 2 | Data & interface contracts | ✅ substantial | `OcrPage`, `PageBlock`, `MemoryChunk`, `ApiContextPack`, `IngestionManifest` all present |
| 3 | Project config & run entry points | ⚠️ skeleton | `config.py` ignores YAML; `pyproject.toml` deps empty; apps are stubs |
| 4 | Document input layer | ✅ functional | sha256 doc_id, sampled density profile, kind/strategy decision, warnings |
| 5 | Page-level OCR & parsing | ✅ core works | PyMuPDF parser + Paddle/Tesseract engines + router all implemented against shared schema |

## Known gaps (priority order)

### Must fix before objective 6
1. **`DocumentInput` (`schemas.py:82`) and `DocumentClassification` dataclass (`ingestion/classify.py:36`) duplicate the same concept** with different framework (Pydantic vs stdlib) and different fields. Promote classify's into Pydantic in schemas; delete dataclass.
2. **`config.py` does not load any of `configs/*.yaml`** despite its docstring. `paddle_engine.py:156` hardcodes `0.60`, `router.py:39` defaults to `0.6`, `ingestion.yaml:13` declares `0.6` — three independent copies. Add `Settings.load()` that merges env + the three YAMLs.
3. **`scripts/ocr_raw_books_with_paddle.py` duplicates `ingestion/ocr/paddle_engine.py`** — `normalize_ocr_text`, `repair_mojibake`, `render_pdf_page`, `make_ocr`, `result_to_page` exist in both. Script is the one that produced the working 613-chunk Bently export. Refactor script to import from package before they drift further.
4. **`pyproject.toml` runtime deps are empty** (`dependencies = []`) while code imports fitz/paddleocr/pytesseract/PIL/pydantic. `pip install -e .` produces a non-functional install.

### Should fix
5. `profile_pdf_text` (`ingestion/classify.py:117`) always samples pages 0..7 — biased against Chinese textbooks with scanned covers. Spread sample across the document.
6. DOCX excluded from `SUPPORTED_TEXT_SUFFIXES` despite design §0 marking it URGENT. `扭振/` and `bently/` corpora contain `.docx`.
7. No language detection (SQL `documents.language` + design §7 expect it).
8. `Citation.pages` / `RetrievalHit.pages` are `list[int] | str | None` — pick one structured form.
9. `RetrievalHit.reason` required `str` should default to `""`.
10. `tesseract_engine.py:11` imports `render_pdf_page` from `paddle_engine` — extract to `ingestion/render.py`.
11. Script and package disagree on `os.environ` cache config style (`[]=` vs `setdefault`).
12. No tests for any objective-4/5 module — only `tests/unit/test_schemas.py` exists.

### Defer (note only)
- `_block_text` (`pymupdf_parser.py:19`) silently skips PyMuPDF image blocks — fine for Phase-0 text path; figure-asset gap surfaces at Obj 7.
- `_merge_fallback` (`ocr/router.py:25`) picks the longer of two OCR strings — loses info on dual-language pages.
- `text_density` unit (chars per kpt²) undocumented in `ingestion.yaml`.
- `~$lockfile.docx` filtering needed once DOCX is added.

## Recommended next-action queue

1. Promote `DocumentClassification` to Pydantic in `schemas.py`; delete dataclass. **~1 hr**
2. `Settings.load()` merging env + 3 YAMLs; route OCR thresholds through it. **~2 hr**
3. Move `render_pdf_page` to `ingestion/render.py`. **~15 min**
4. Spread PDF-classification sample pages across document. **~15 min**
5. Add `vib-agent scan <path>` CLI subcommand calling `classify.scan_inputs`. **~20 min**
6. One unit test per implemented module (classify / parser / router). **~2 hr**
7. Refactor `scripts/ocr_raw_books_with_paddle.py` to import from package. **~2 hr**
8. Fill in `pyproject.toml` runtime deps. **~15 min**

Then cleanly positioned for objective 6 (版面对象识别).

## Validation step after pipeline.py is wired (Obj 7+)

Re-run the Bently book through the new pipeline and diff the chunks against the existing `data/exports/book/donalde_bently_charlest_hatch_2014_af23924d/` export to catch any schema drift between script and package.

## Path notes

- Sibling corpus folders (`bently/`, `orbit60/`, `standard/`, `扭振/`, `阶比算法/`) live at `..\` relative to the new working dir — not inside `Agent/`. The original design DOCX is at `..\vibration_agent_design.docx`; mirror is `docs/vibration_agent_design.md`.
- Bently book input is at `data/raw/book/旋转机械诊断技术 [...].pdf`; pre-OCR'd export is at `data/exports/book/donalde_bently_charlest_hatch_2014_af23924d/`.
