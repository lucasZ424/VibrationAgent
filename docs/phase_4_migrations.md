# Phase 4 Migrations

Updated: 2026-06-15

## Purpose

This file is the canonical migration log for Phase-4 schema, contract,
configuration, replay-fixture, retrieval, skill, API, and UI changes.

Phase 3 is frozen in `docs/phase_3_interface_freeze.md`. Phase 4 may supersede
Phase-3 contracts only through an explicit migration entry in this file.

## Canonical Change Checklist

For any Phase-4 objective that changes a frozen schema, API response shape,
structured result key, provider request shape, replay-fixture layout, retrieval
contract, prompt schema, chain order, UI/API contract, or downstream caller
contract:

1. Update `src/vibration_agent/schemas.py` first when a schema is affected.
2. Add a migration note in this file.
3. Update fixtures and tests that encode the affected shape.
4. Update downstream callers after the contract and tests are in place.
5. Record verification and residual risk in `docs/phase_4_progress.md`.
6. Record review findings in `docs/issue_log_p4/issues_objN.txt`.

Default policy: add fields as optional unless the objective explicitly approves
a breaking migration. Deprecated fields are not removed until a freeze document
or migration entry records the removal window.

## Replay / Provider / Retrieval Checklist

For any objective that changes replay, provider, retrieval, or live/manual
behavior:

1. Keep live paths default-off unless the objective explicitly changes that
   boundary.
2. Add or update replay fixtures before adding CI assertions.
3. Include prompt version, schema version, provider/model, retrieval provider,
   embedding model/dimension, max-token settings, request body, and request hash
   where those fields are part of the request.
4. Redact API keys, local absolute paths, long raw source text, and bearer tokens
   from captured fixtures and reports.
5. Add fallback tests for missing key, timeout, budget denial, schema parse
   failure, replay miss, unavailable retrieval provider, and unavailable storage
   dependency when applicable.
6. Confirm CI never constructs a live provider client or requires a live network
   service unless the test is explicitly skipped when unavailable.

## Migration Log

### Obj0 - Phase-4 execution baseline (2026-06-12)

Documentation-only baseline.

- Added `docs/phase_4_development_order.md` as the proposed Phase-4 objective
  order.
- Added `docs/phase_4_progress.md` as the Phase-4 progress ledger.
- Added `docs/phase_4_migrations.md` as the Phase-4 contract and migration
  ledger.
- Reserved `docs/issue_log_p4/` as the local ignored Phase-4 review issue
  directory.

No runtime schema, API, replay fixture, retrieval, provider request, UI, or
chain-order contract changed.

Rollback: remove the Phase-4 baseline docs. The ignored issue-log directory can
be cleaned locally if no review artifacts need to be kept.

### Obj0 review update - Phase-4 plan hardening (2026-06-15)

Documentation-only review update before Obj1 implementation.

- Chose deterministic V2 evidence-support hardening for Obj5. Model-backed
  entailment remains out of Obj5 and requires a separate default-off,
  replay-first objective if pursued later.
- Moved V2 calibration labels and retrieval recall targets into Obj1 so later
  Obj4/Obj5 gates can be numeric.
- Named optional/manual external dependencies:
  Semantic Scholar Graph API and arXiv API for S6 live literature search, and
  headless LibreOffice (`soffice`) for rendered DOCX pagination.
- Added an explicit S6/S7/S8 routing activation gate.
- Split backend interface freeze from final Phase-4 freeze.
- Split local-first observability essentials from remote/shared hardening
  decision, with remote/shared hardening defaulting to deferred unless product
  positioning changes.

No runtime schema, API, replay fixture, retrieval, provider request, UI, or
chain-order contract changed.

Rollback: revert the Phase-4 planning docs to the 2026-06-12 objective list.
