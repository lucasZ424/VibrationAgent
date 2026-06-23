# R1 Wave B: retrieval and standard-scope synthesis

Date: 2026-06-22

## Scope

- Added deterministic aliases for steam turbines, torsional vibration, order analysis, and shaft trains.
- Kept the steam-turbine alias precise by excluding bare English `turbine`, so gas-turbine queries are not expanded to `汽轮机`.
- Classified queries containing both a standard identifier and a scope cue as `standard_lookup` before generic definition intent.
- For standard-scope questions, S3 selects explicit applicability claims when available instead of higher-overlap mechanism text.
- Recognized both Chinese applicability wording and English `This document/standard specifies...` scope clauses.
- Corrected structural-line detection so `GB/T...` prose is not discarded as an uppercase label.
- Excluded normative-reference and terminology boilerplate ending in `适用于本文件` from scope answers.
- Prevented V2 from treating numeric paper bibliography markers such as `[29]` and `[29-31]` as Agent chunk citations.
- Added labeled retrieval fixtures for the standard-scope and order-analysis introduction misses.

No chain order, API schema, provider routing, database schema, or source-type weighting changed.

## Verification

- Focused Wave B residual tests: 73 passed.
- Full non-large-corpus suite: 470 passed, 2 skipped, 1 deselected; one Qdrant compatibility-check warning.
- V2 calibration: 12 cases, 0 failed, no false blocks or false allows.
- Retrieval evaluation: 6 cases, recall@5 = 1.0, recall@10 = 1.0, no missing evidence cases.
- LLM evaluation: 7/7; citation faithfulness and unsupported numeric blocking = 1.0.
- Real Q1: `standard_lookup`; scope chunk is top-1; final S3 output contains only the two applicability statements from page 5.
- Real Q3: four of the top five chunks are from the paper, including its introduction evidence.

## Residual work

- No open Wave B correctness blocker remains.
- Wave A.2 is complete: new chunks expose typed offset spans and legacy chunks use a bounded compatibility fallback.
- Wave C remains open: make CLI JSON output safe on Windows non-UTF-8 consoles and add file output if retained by the design.
- Alias groups remain in the deterministic in-code fallback. A taxonomy file should be introduced only when corpus growth demonstrates a maintenance need.
- Q3 retains one standard chunk in top-5. The labeled requirement is met (four paper chunks including the introduction); source-type affinity remains deferred because the current corpus does not justify a global genre prior.

## Rollback

Revert the R1 Wave B changes in `query_normalize.py` and the standard-scope candidate filter in `s3_qa_summary.py`; remove the associated unit tests. No data migration or re-ingestion is required.
Also restore numeric bracket parsing in V2 and remove the Wave B retrieval and calibration fixtures.
