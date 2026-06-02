# Phase 2 Progress

Updated: 2026-05-28

## Execution Model

Phase 2 proceeds one Obj at a time. Each Obj must define its verification, preserve Phase-1 fallback behavior for external dependencies, and pass review before the next Obj starts.

## Objective Status

1. Phase-2 boundary: done
2. Bilingual fixture and multi-page/cross-chunk regression samples: done

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
