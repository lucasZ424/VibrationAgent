-- Phase-2 Obj7: runtime qa_logs persistence columns.
-- Additive and idempotent: extends qa_logs from 001_init.sql so Tutor-Orchestrator
-- can persist one row per handle_query with status, citations, timing, and token cost.
-- Re-running this file is safe (ADD COLUMN IF NOT EXISTS).

ALTER TABLE qa_logs ADD COLUMN IF NOT EXISTS status      TEXT;        -- ok | insufficient | fail
ALTER TABLE qa_logs ADD COLUMN IF NOT EXISTS citations   JSONB;       -- locatable refs only: [{chunk_id, doc_id, pages, evidence_type, confidence}]
ALTER TABLE qa_logs ADD COLUMN IF NOT EXISTS latency_ms  INTEGER;     -- wall-clock duration of handle_query
ALTER TABLE qa_logs ADD COLUMN IF NOT EXISTS token_cost  INTEGER;     -- LLM token cost; NULL until LLM lanes activate (Obj9)
