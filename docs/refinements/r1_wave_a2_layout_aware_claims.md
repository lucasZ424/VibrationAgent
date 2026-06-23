# R1 Wave A.2: layout-aware deterministic claims

Date: 2026-06-22

## Problem

Wave A repaired visual line wrapping but flattened blank-line block boundaries.
On layout-heavy manuals this joined cover labels, document numbers, taglines,
and body prose into one claim. Preserving every boundary without qualification
then reintroduced fragmented manual, paper, and standard sentences.

## Changes

- Ingestion adds optional `metadata.text_segments` spans to each chunk. A span
  records `page_no`, `start`, `end`, and `block_type`; offsets reference the
  existing chunk text and do not duplicate it.
- S3 consumes typed spans when present and excludes explicit `title` segments
  from deterministic claims.
- Native PDF layout uses the page's modal font size as a body baseline. The
  largest elevated short block becomes a true title; other elevated short
  blocks become `layout_role=label`, avoiding section explosion.
- Bracket-number bibliography blocks become `layout_role=bibliography`, and
  chunks whose section is `参考文献`/`References`/`Bibliography` are excluded
  from claim evidence.
- S3 uses the longest domain alias present in the query as a claim-focus gate
  when matching candidates exist. This prevents broad vibration vocabulary
  from filling an order-analysis answer with standard front matter.
- Existing chunks remain supported. Their blank-line boundaries are preserved,
  with cross-block joining allowed only when the preceding non-structural body
  text lacks terminal punctuation and is long enough to be a continuation, or
  when the next block is the observed short punctuated CJK continuation.
- Legacy cover labels are filtered with bounded patterns for short labels,
  revision document numbers, and bullet-separated taglines. Short CJK
  assertions containing an engineering predicate remain eligible.

No chain order, API route, provider behavior, database schema, citation model,
or top-level `MemoryChunk` field changed.

## Compatibility

- Existing chunks improve immediately through the bounded legacy fallback.
- Re-ingestion is optional for external legacy chunks. The active standard,
  manual, and paper corpus has been re-ingested and now uses typed spans.
- Consumers that ignore unknown metadata continue to work.

## Verification

- Focused chunking/S3 tests: 39 passed.
- Full non-large-corpus suite: 481 passed, 2 skipped, 1 deselected; one Qdrant
  compatibility-check warning.
- V2 calibration: pass rate 1.0, no false blocks or false allows.
- Retrieval evaluation: recall@5 = 1.0 and recall@10 = 1.0, no missing cases.
- LLM evaluation: all scorecard rates = 1.0.
- Real standard, manual, and paper questions return `ok` with no warnings.
- The Orbit answer contains four complete body claims and no cover title,
  selection label, revision number, tagline, or orphaned line fragment.
- The GB/T scope answer retains complete `准则` wording and the full speed list.
- Re-ingested corpus coverage: manual 39 chunks with title/label/body spans;
  paper 115 chunks including 71 bibliography spans; standard 31 chunks with no
  missing text-segment metadata.

## Residual disposition

- No open Wave A.2 correctness item remains on the active corpus.
- The legacy heuristic path is retained intentionally for externally supplied
  pre-A.2 chunks. It is covered by precision tests and is no longer used by the
  three active re-ingested documents, so removing it would reduce compatibility
  without simplifying the active path.
- The reported transient full-suite cascade exposed a test-infrastructure race:
  every pytest process cleared all children of the shared safe temp root during
  startup, including another process's active PID-scoped basetemp. Startup now
  only creates the root; session shutdown still removes only its own basetemp.
  An isolation regression test preserves another active session's marker.
- Post-fix full suite: 484 passed, 2 skipped; one existing Qdrant compatibility
  warning. No retry policy was added.

## Rollback

Remove font-based title/label and bibliography roles, remove
`metadata.text_segments` emission, restore S3 text-wide reflow and ungated claim
ranking, and remove the A.2 tests. Re-ingest the three active documents with the
previous code if exact old chunk boundaries are required.
