# Phase 2 Progress

Updated: 2026-06-02

## Execution Model

Phase 2 proceeds one Obj at a time. Each Obj must define its verification, preserve Phase-1 fallback behavior for external dependencies, and pass review before the next Obj starts.

## Objective Status

1. Phase-2 boundary: done
2. Bilingual fixture and multi-page/cross-chunk regression samples: done
3. Bibliography metadata + section parent-child linking: done (pending review)

## Obj1 Notes

- `docs/phase_2_development_order.md` is the approved Phase-2 development order.
- `README.md`, `docs/architecture.md`, and `docs/phase_1_interface_freeze.md` now point to the approved Phase-2 boundary.
- Phase 2 remains one continuous phase executed by Obj-level gates; it is not split into Phase-2A/2B/2C.
- Phase-1 frozen contracts and runtime chain remain unchanged until a specific Phase-2 Obj performs a documented migration.

## Obj1 Verification

- Verified command: `git diff --check` passed with LF/CRLF warnings only.
- Code tests: not run; Obj1 is documentation-only.

## Obj1 Residual Risk

- Phase-2 boundary enforcement is mostly document/process based. Existing Tutor-Orchestrator tests cover the default Phase-1 query chain, but later feature-flagged Phase-2 activation will need additional guards.
- Repo-wide EOL policy is not settled; this is tracked as hygiene and does not block Obj2.

## Obj1 Next Obj Gate

- Cleared to start Obj2 after review of this Obj1 follow-up.

## Obj2 Notes

- Added a two-page native-text Chinese PDF fixture at `tests/fixtures/raw/small_vibration_zh.pdf`.
- Added matching Chinese page, chunk, and retrieval fixtures:
  - `tests/fixtures/ocr/sample_zh_pages.jsonl`
  - `tests/fixtures/chunks/sample_zh_chunks.jsonl`
  - `tests/fixtures/retrieval/sample_zh_retrieval.json`
- The Chinese chunk fixture spans pages 1-2 and asserts `metadata.page_boundary_crossed == true`.
- Added a fixture regeneration helper: `scripts/generate_obj2_fixtures.py`.
- Added Chinese S1 -> S2 -> S3 -> V4 integration coverage and Chinese CLI ok / insufficient / out-of-scope coverage.

## Obj2 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_regression_fixtures.py tests\integration\test_phase0_fixture_chain.py tests\integration\test_obj19_end_to_end.py -q -p no:cacheprovider`
- Result: 18 passed.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 153 passed, 6 deselected.

## Obj2 Residual Risk

- Chinese retrieval remains Phase-1 deterministic token/ngram retrieval; gap tests choose low-overlap queries to avoid testing retrieval quality tuning before the real embedding objective.
- The new Chinese integration uses native-text PDF parsing, not OCR. PaddleOCR quality remains outside Obj2.

## Obj2 Next Obj Gate

- Cleared to start Obj3 after review.

## Obj2 Follow-Up Notes

- Fixed Obj2 `#1` and `#2`: `scripts/generate_obj2_fixtures.py` now writes the Chinese PDF, parses it through the real native PyMuPDF parser, and emits parser-derived zh page/chunk/retrieval fixtures.
- Added a zh pipeline drift guard in `tests/unit/test_regression_fixtures.py`, mirroring the English PDF-vs-fixture regression.
- Fixed Obj2 `#3`: zh ok-path integration now relies on automatic in-scope detection instead of forcing `scope=in_scope`.
- Fixed Obj1 `#10`: `docs/architecture.md` now cross-references the binding fallback and feature-flag risk principles in `docs/phase_2_development_order.md`.
- Deferred Obj1 `#3` until Obj9, when Phase-2 default-chain and feature-flag guards need to tighten around LLM S3 / V2 activation.
- Deferred Obj1 `#8` EOL policy.

## Obj2 Follow-Up Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_regression_fixtures.py tests\integration\test_phase0_fixture_chain.py tests\integration\test_obj19_end_to_end.py -q -p no:cacheprovider`
- Result: 19 passed.

## Obj3 Notes

- New deterministic bibliography extractor `src/vibration_agent/ingestion/bibliography.py` (regex/keyword heuristics, no model calls). Pulls year/authors/publisher from PyMuPDF `doc.metadata` and first-page text; every field falls back to empty/None.
- New `src/vibration_agent/ingestion/section_hierarchy.py` computes each section's ancestor chain (stack-based on heading level), decoupled from chunking (operates on plain `(section_key, level)` tuples).
- `MemoryChunk.metadata` gains two optional keys (no Pydantic model change — `metadata` is free-form): `bibliography` (`{year, authors, publisher}`, defaulting to `{null, [], null}`) and `section_parent_keys` (`list[str]`, `[]` for front-matter / top-level).
- `schemas.py` adds a standalone `DocumentBibliography` model (maps to the future `documents` table). Migration recorded in `docs/phase_2_migrations.md`.
- `citation_anchor` now renders `"Author (Year), p. N"` (multi-author -> `"First et al. (Year)"`) only when the document has BOTH author and year; otherwise the Phase-1 `"Title, p. N"` form is byte-unchanged.
- `pipeline.chunk_document_pages` extracts bibliography once per document (reusing the already-parsed first-page text so OCR'd docs still get inference) and threads it through `chunk_pages`.
- Fixed a year-regex gap found via testing: the trailing `\b` never fired before a CJK character, so the dominant Chinese year form `"2019年"` was missed. Replaced with a `(?!\d)` lookahead, which preserves all ASCII behaviour (still rejects 5-digit runs and alphanumeric codes).
- Regenerated both chunk fixtures from the committed page fixtures (not by re-parsing the PDFs), so only the two new metadata keys changed; CJK title/text/anchor verified byte-identical to the prior committed version.

## Obj3 Verification

- Verified command: `PYTHONPATH=src .\.venv\Scripts\python.exe -m pytest tests -q --basetemp=.pytest_tmp`
- Result: 180 passed (174 non-integration + 6 integration; 20 new Obj3 tests).
- New tests: `tests/unit/test_bibliography.py` (11), `tests/unit/test_section_hierarchy.py` (5), `tests/unit/test_chunking_strategy.py` (+3: author/year anchor, title fallback, section_parent_keys wiring), `tests/unit/test_regression_fixtures.py` (+1 fixture-PDF bibliography guard, +EN/zh drift assertions on the two new keys).

## Obj3 Residual Risk

- Author splitting over-splits a `"Lastname, First"` metadata convention into two names (the separator set includes `,`). Accepted: most engineering PDFs store comma-separated full names. Documented in `bibliography.py`.
- `citation_anchor` uses `"First et al."` for any multi-author document; there is no two-author `"A and B"` form. Deliberate simplification.
- Year inference from text still requires a word boundary *before* the digits, so a year immediately preceded by a CJK glyph (e.g. `"公元2019年"`) is missed; line-start / whitespace-preceded `"2019年"` works. PDF metadata `creationDate` remains the more reliable year source.
- Bibliography is best-effort and deterministic; documents with no recoverable metadata or markers yield empty defaults, which is the intended Phase-1-preserving behaviour, not a failure.

## Obj3 Open Question For Review

- `citation_anchor`'s Author(Year) form gates on `has_author_year()` — it requires BOTH author and year, falling back to the title form if either is missing. This avoids a half-populated anchor like `"Author (), p. N"` or `"(2020), p. N"`, but it means a document with a known author but no year still cites by title. Flagging this gating choice for review.

## Obj3 Next Obj Gate

- Pending review of Obj3 before starting Obj4.

## Obj3 Follow-Up Notes

- Fixed Obj3 `#2`: added a pipeline-level regression that creates a real metadata-bearing PDF and verifies bibliography flows through `chunk_document_pages()` into chunk metadata and `citation_anchor`.
- Improved Obj3 `#3`: author parsing now preserves `Lastname, First` while still splitting comma-separated full names; year inference accepts CJK-prefixed years such as `公元2019年`; English publisher inference handles explicit `Publisher:` labels and avoids ordinary prose containing lowercase `press`.
- Carried Obj3 `#4` forward in `docs/issue_log_p2/issues_obj3.txt`: `citation_anchor` is a conditional display string and should not be used as a stable identifier.
- Improved Obj3 `#5`: chunk metadata now exposes `section_hierarchy_source` and `section_hierarchy_warnings` so heading-level parent links remain diagnosable instead of looking like semantic certainty.

## Obj3 Follow-Up Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_bibliography.py tests\unit\test_section_hierarchy.py tests\unit\test_chunking_strategy.py tests\unit\test_regression_fixtures.py -q -p no:cacheprovider`
- Result: 46 passed.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 181 passed, 6 deselected.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\integration -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 6 passed.
