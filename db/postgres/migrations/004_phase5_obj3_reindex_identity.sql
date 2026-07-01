-- Phase-5 Obj3: stable identities and provenance for reproducible Qdrant reindex.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS documents_external_id_unique
    ON documents (external_id) WHERE external_id IS NOT NULL;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS external_id TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS pages INTEGER[];
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS source_type TEXT;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS topic TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS chunks_external_id_unique
    ON chunks (external_id) WHERE external_id IS NOT NULL;
