# Phase 2 Progress

Updated: 2026-06-03

## Execution Model

Phase 2 proceeds one Obj at a time. Each Obj must define its verification, preserve Phase-1 fallback behavior for external dependencies, and pass review before the next Obj starts.

## Objective Status

1. Phase-2 boundary: done
2. Bilingual fixture and multi-page/cross-chunk regression samples: done
3. Bibliography metadata + section parent-child linking: done
4. DOCX ingestion capability: done (pending review)
5. Real embedding generation layer: done (pending review)
6. Qdrant write/read chain: done (pending review)
7. Postgres qa_logs persistence: done (pending review)

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

## Obj4 Notes

- Added `src/vibration_agent/ingestion/docx_parser.py`, backed by `python-docx`.
- `classify_document()` now accepts `.docx`, assigns `kind="docx"` and
  `processing_strategy="docx"`, detects language from paragraph/table text, and
  still skips Office lock files such as `~$name.docx`.
- `parse_document_pages()` now supports DOCX through the same `OcrPage` rows as
  PDF parsing. DOCX is represented as one logical page because DOCX has no stable
  parser-level pagination without rendering.
- DOCX paragraphs/headings become `PageBlock` rows; tables become `table`
  `DocumentAsset`s; embedded images become `figure` `DocumentAsset`s when
  present.
- Empty or corrupt DOCX files return structured `insufficient` page-parse
  results instead of bubbling a traceback through S1/CLI/API.
- Added fixed zh DOCX fixture: `tests/fixtures/raw/small_vibration_zh.docx`.
- Added `python-docx` as a runtime dependency.

## Obj4 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_docx_parser.py tests\unit\test_classify.py tests\unit\test_ingestion_classify.py tests\unit\test_page_parsing.py tests\integration\test_phase0_fixture_chain.py -q -p no:cacheprovider`
- Result: 23 passed.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 189 passed, 7 deselected.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\integration -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 7 passed.

## Obj4 Residual Risk

- DOCX pagination is logical, not rendered. All DOCX chunks currently cite page
  1; real rendered pagination is deferred unless later storage/API requirements
  need physical page numbers.
- DOCX image extraction is relationship-based. It records embedded image assets,
  but does not map images back to exact paragraph positions or page coordinates.
- Visual layout was not rendered/inspected for the fixture; text/table/image
  extraction is verified structurally by tests.

## Obj4 Next Obj Gate

- Pending review of Obj4 before starting Obj5.

## Obj4 Issue Follow-Up Notes

- Fixed Obj4 `#1`: added `scripts/generate_obj4_docx_fixtures.py`, which writes the zh DOCX source and parser-derived DOCX page/chunk baselines without touching the Obj2 PDF fixture pack. Added DOCX real-parse drift guards against `tests/fixtures/ocr/sample_zh_docx_pages.jsonl` and `tests/fixtures/chunks/sample_zh_docx_chunks.jsonl`.
- Fixed Obj4 `#2`: DOCX page count now matches the documented one-logical-page model. Real Word page breaks still classify as one logical page.
- Fixed Obj4 `#3`: table text is retrievable through `chunk.text` while table assets remain attached. This keeps tables searchable without dropping structured asset references.
- Fixed Obj4 `#4`: DOCX classification now catches only `DocxParseError`; unexpected parser bugs fail loud instead of becoming soft warnings.
- Improved Obj4 `#5` and `#6`: DOCX classification now opens the DOCX once via `inspect_docx()` and avoids duplicate text normalization.
- Obj4 `#7` remains disclosed as residual risk: embedded images are relationship-ordered and pinned to logical page 1.
- Obj4 `#8` remains part of the deferred EOL policy / hygiene thread.

## Obj4 Issue Follow-Up Verification

- Verified command: `.\.venv\Scripts\python.exe scripts\generate_obj4_docx_fixtures.py`
- Result: regenerated zh DOCX source/page/chunk baselines.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_docx_parser.py tests\unit\test_classify.py tests\unit\test_ingestion_classify.py tests\unit\test_page_parsing.py tests\unit\test_regression_fixtures.py tests\integration\test_phase0_fixture_chain.py -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 43 passed.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 194 passed, 7 deselected.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\integration -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 7 passed.

## Obj5 Notes

- Added `src/vibration_agent/retrieval/embeddings.py` with `embed_texts()`,
  batching, in-call text dedupe, a text-hash keyed in-memory cache, SHA-256
  text hashes, and `EmbeddingRecord` provenance.
- Added `configs/embeddings.yaml` and `EmbeddingSettings`.
- Added optional `pyproject.toml` extra `embeddings` for installing
  `sentence-transformers` without making it a mandatory runtime dependency.
- `dense.py` now attempts embedding-vector retrieval first and falls back to the
  deterministic token-feature lane when the model is disabled, unavailable, or
  not configured as a local file.
- The default config keeps `local_files_only: true`; this prevents fast tests and
  local runs from accidentally downloading models. A real local model path can be
  configured through `EMBEDDING_MODEL` / `configs/embeddings.yaml`.
- A default cold start with no local embedding model configured falls back
  silently to the Phase-1 token-feature lane. Explicit disablement or real model
  load/encode failures still surface embedding warnings.
- Obj5 still embeds the query and supplied corpus in the request path when a real
  local model is configured. This is a bridge state before Obj6 moves dense
  retrieval to Qdrant write/read.
- `hybrid.search()` propagates actionable embedding fallback warnings through
  `RetrievalOutput.warnings` while preserving Phase-1 retrieval hit/citation
  shapes.

## Obj5 Verification

- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_embeddings.py tests\unit\test_s2_retrieval_skill.py tests\unit\test_schemas.py tests\unit\test_regression_fixtures.py -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 43 passed.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration" --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 200 passed, 7 deselected.
- Verified command: `.\.venv\Scripts\python.exe -m pytest tests\integration -q --basetemp=<repo-data-tmp> -p no:cacheprovider`
- Result: 7 passed.

## Obj5 Residual Risk

- No real sentence-transformers model is bundled with the repo. The real-model
  path is covered with fake-model tests; runtime uses deterministic fallback
  until a local model path is configured.
- The Obj5 in-memory cache is process-local only. Obj6 is expected to move
  persistent vector storage and search into Qdrant.

## Obj5 Next Obj Gate

- Pending review of Obj5 before starting Obj6.

## Obj6 Notes

- Added `src/vibration_agent/storage/qdrant_client.py`, a thin adapter around
  the optional `qdrant-client` package. Importing storage code does not require
  the dependency; runtime client creation does.
- Extended `src/vibration_agent/storage/qdrant.py` from dry-run point planning
  to collection initialization, chunk vector upsert, and vector search result
  mapping.
- Qdrant payloads now carry chunk text/api context/assets so dense hits can still
  feed retrieval context when BM25 does not already provide the same chunk.
- Added `DatabaseSettings.qdrant_enabled`, `qdrant_collection`,
  `qdrant_vector_size`, and `qdrant_timeout`. Qdrant remains off by default and
  can be enabled explicitly with `QDRANT_ENABLED=true`.
- `dense.py` attempts Qdrant search only when Qdrant is explicitly enabled and a
  real query embedding is available. Any Qdrant dependency, connection, or query
  failure records a warning and falls back to the deterministic token-feature
  lane.
- Added optional `pyproject.toml` extra `qdrant` for installing
  `qdrant-client`.
- Fixed Obj6 review `#3`: Qdrant default vector size now matches the default
  MiniLM embedding dimension (384), and dry-run plans report the actual vector
  dimension when vectors are supplied.
- Fixed Obj6 review `#4`: runtime Qdrant clients are cached by
  `url/api_key/timeout` to avoid reconnecting on every query.
- Fixed Obj6 review `#6` and `#7`: Qdrant results are filtered to the
  caller-supplied corpus, and empty Qdrant results fall back directly to
  token-feature search instead of re-embedding the full local corpus.
- Obj6 does not auto-populate Qdrant from ingestion. The write helpers are
  available, but corpus population is deferred to Obj8's cold-start / large
  corpus objective. Until vectors are upserted and a local embedding model is
  configured, `qdrant_enabled=true` is an opt-in read path that may fall back.

## Obj6 Verification

- Reviewer verification from `docs/issue_log_p2/issues_obj6.txt`: fast suite
  `208 passed, 8 deselected`; live Qdrant roundtrip `1 skipped` with no local
  Qdrant instance; Qdrant failure fallback unit passed.
- Follow-up verification command: `.\.venv\Scripts\python.exe -m pytest tests\unit\test_qdrant.py tests\unit\test_embeddings.py tests\integration\test_qdrant_roundtrip.py -q -p no:cacheprovider -p no:tmpdir`
- Result: 18 passed, 1 skipped.
- Attempted command including `tests\unit\test_s2_retrieval_skill.py` was blocked
  by environment temp-dir permissions (`tmp_path` cannot scan
  `C:\Users\zhoul\AppData\Local\Temp\pytest-of-zhoul`), not by an Obj6 assertion.

## Obj6 Residual Risk

- Qdrant remains explicit opt-in. The default Phase-1-compatible path still uses
  local chunk JSONL plus BM25/token-feature fallback.
- Live Qdrant roundtrip coverage is skippable when `qdrant-client` or a local
  Qdrant instance is unavailable.
- Qdrant writes are not wired into ingestion yet. Obj8 must either populate
  Qdrant during cold start or explicitly keep Qdrant as a manual vector store.
- Qdrant requires a real local embedding model for query vectors. The default
  offline config still falls back before any Qdrant query.
- Qdrant payload currently denormalizes text/api context/assets to keep dense
  hits self-contained before Postgres rehydration lands; re-upsert is required
  after chunk regeneration.

## Obj6 Next Obj Gate

- Pending verification of Obj6 before starting Obj7.

## Obj7 Notes

- Added `db/postgres/migrations/002_qa_logs_runtime.sql` extending `qa_logs`
  with `status`, `citations` (JSONB), `latency_ms`, `token_cost` via
  `ADD COLUMN IF NOT EXISTS`.
- Added `storage/postgres_client.py` (optional psycopg adapter: `connect`,
  `apply_migrations`, `insert_row`, `fetch_rows`) and `storage/qa_logs.py`
  (redacted row builder + fail-safe `record_qa_log`).
- `apply_migrations` is replayable: a `schema_migrations` ledger records applied
  files so a second run applies nothing. The column registry in
  `storage/postgres.py` and its alignment guard now span 001 + 002.
- `TutorOrchestrator.handle_query` times the S2->S3->V4 chain and persists one
  `qa_logs` row as an optional side effect. Offline/disabled -> silent skip; a
  write failure appends a warning and never changes the return status.
- Added `DatabaseSettings.postgres_enabled` (default false) and the optional
  `postgres` pyproject extra (`psycopg[binary]`).
- Redaction: qa_logs stores only locatable citation refs and short summaries —
  never raw chunk text, document originals, or secrets; query/summary are capped.

## Obj7 Verification

- Verified command: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest tests -q --basetemp=.pytest_tmp`
- Result: 230 passed, 2 skipped (the Qdrant and Postgres roundtrips skip with no
  live instance). Split: 223 passed (not integration) + 7 passed integration.
- Obj7-specific: `tests/unit/test_qa_logs.py` 11 passed;
  `tests/integration/test_postgres_roundtrip.py` skipped (no live Postgres).

## Obj7 Residual Risk

- The live Postgres roundtrip (idempotent migrations + qa_logs read-back) is
  skip-only here; it needs a real Postgres + psycopg. The write path, redaction,
  and fail-safe degradation are covered by fakes/monkeypatch unit tests.
- `record_qa_log` opens a fresh connection per query (no pooling); acceptable for
  a local-personal write rate, revisit if qa_logs volume grows.
- `token_cost` is always NULL until LLM-S3 / token accounting lands (Obj9).
- 001_init.sql's `CREATE EXTENSION`/`CREATE TABLE` require privileges; the
  roundtrip test skips (not fails) if migrations cannot be applied.

## Obj7 Next Obj Gate

- Pending review of Obj7 before starting Obj8.

## Obj7 Review Follow-Up

Applied after the `issues_obj7.txt` review:
- #1/#2 (migration operational model): documented that `POSTGRES_ENABLED=true`
  requires migrations through 002, and hardened `apply_migrations` to backfill
  `001_init.sql` into the ledger when the base schema pre-exists (so "replayable"
  holds for a legacy 001-only DB, not only an empty DB).
- #3 (silent logging failure): `_persist_qa_log` now surfaces an unexpected
  failure as a "qa_logs persistence skipped (unexpected failure)" warning instead
  of swallowing it; the primary status is still untouched.
- #4 (per-query delay): added `DatabaseSettings.postgres_timeout` (default 2.0s,
  `POSTGRES_TIMEOUT`) threaded into the connect, so a bad host no longer pays the
  5s psycopg default per query.
- #5 (secrets): added a conservative best-effort secret mask on query/summary
  (`sk-…`/`Bearer …`/`api_key=…`/GitHub/AWS shapes) and documented it as
  best-effort, not a guarantee.
- #6 (SQL identifiers): `insert_row`/`fetch_rows` now validate table/column and
  `order_by` identifiers (values remain parameterized).
- #7 (dry-run drift): `PostgresWritePlan.dry_run` ddl_source now points at
  `db/postgres/migrations/*.sql`.
- #8 (exports): left `storage/__init__.py` unchanged by decision — runtime and
  tests import `storage.qa_logs` / `storage.postgres_client` directly.
- Judgment calls J1–J4 were affirmed by review; no change required.

Residual (accepted): live Postgres roundtrip is skip-only without an instance;
per-query connection (no pool) is acceptable at local-personal volume and now
timeout-bounded; `token_cost` stays NULL until Obj9; the secret mask is
best-effort.
