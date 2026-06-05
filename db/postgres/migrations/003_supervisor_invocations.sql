-- Phase-2 Obj13: qa_logs supervisor observability.
-- Additive and idempotent: records how many supervisor review attempts were
-- made for a Tutor-Orchestrator query. Non-supervised queries write 0/NULL.

ALTER TABLE qa_logs ADD COLUMN IF NOT EXISTS supervisor_invocations INTEGER;
