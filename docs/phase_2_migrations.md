# Phase 2 Migrations

Updated: 2026-05-28

## Purpose

This file is the canonical migration log for Phase-2 schema and contract changes. It exists because Phase 1 froze public contracts in `src/vibration_agent/schemas.py`; Phase 2 may extend those contracts, but every change must be traceable.

## Canonical Schema-Change Checklist

For any Phase-2 Obj that changes a frozen schema, API response shape, structured export, or downstream caller contract:

1. Update `src/vibration_agent/schemas.py` first.
2. Add a migration note in this file.
3. Update fixtures and tests that encode the affected shape.
4. Update downstream callers after the contract and tests are in place.
5. Record verification and residual risk in `docs/phase_2_progress.md`.

Default policy: add fields as optional unless the Obj explicitly approves a breaking migration. Deprecated fields are not removed until a freeze document records the removal window.

## Migration Log

No Phase-2 schema migrations have been applied yet.
