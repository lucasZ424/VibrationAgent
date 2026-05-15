-- Initial schema — tables specified in Appendix B of vibration_agent_design.docx.
-- Keep this file the single source of truth for the relational model.

CREATE EXTENSION IF NOT EXISTS vector;   -- optional: pgvector for on-DB experiments
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Documents ---------------------------------------------------------------
CREATE TABLE documents (
    id            BIGSERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    type          TEXT NOT NULL,                  -- textbook | standard | paper | review | datasheet | note
    source        TEXT,
    language      TEXT,
    year          INT,
    authors       TEXT[],
    file_path     TEXT NOT NULL,
    hash          TEXT UNIQUE,
    ocr_status    TEXT,                           -- none | pending | done | failed
    parse_status  TEXT,                           -- pending | done | failed
    version       TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- Hierarchical sections ---------------------------------------------------
CREATE TABLE document_sections (
    id         BIGSERIAL PRIMARY KEY,
    doc_id     BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    parent_id  BIGINT REFERENCES document_sections(id) ON DELETE CASCADE,
    heading    TEXT,
    level      INT,
    page_start INT,
    page_end   INT
);

-- Retrievable chunks ------------------------------------------------------
CREATE TABLE chunks (
    id               BIGSERIAL PRIMARY KEY,
    doc_id           BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    section_id       BIGINT REFERENCES document_sections(id) ON DELETE SET NULL,
    page_start       INT,
    page_end         INT,
    chunk_type       TEXT,                        -- text | formula | caption | code | table
    text             TEXT NOT NULL,
    normalized_text  TEXT,
    token_count      INT,
    citation_anchor  TEXT
);
CREATE INDEX chunks_text_trgm ON chunks USING gin (normalized_text gin_trgm_ops);

-- Figures / tables --------------------------------------------------------
CREATE TABLE figures_tables (
    id                 BIGSERIAL PRIMARY KEY,
    doc_id             BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    page_no            INT,
    kind               TEXT,                      -- figure | table
    caption            TEXT,
    image_path         TEXT,
    related_chunk_ids  BIGINT[]
);

-- Taxonomy ---------------------------------------------------------------
CREATE TABLE terms (
    id              BIGSERIAL PRIMARY KEY,
    canonical_term  TEXT UNIQUE NOT NULL,
    zh_name         TEXT,
    en_name         TEXT,
    aliases         TEXT[],
    notes           TEXT,
    topic           TEXT
);

CREATE TABLE symbols (
    id                    BIGSERIAL PRIMARY KEY,
    canonical_symbol      TEXT UNIQUE NOT NULL,
    latex                 TEXT,
    meaning               TEXT,
    unit                  TEXT,
    notes                 TEXT,
    avoid_confusion_with  TEXT[]
);

CREATE TABLE units (
    id               BIGSERIAL PRIMARY KEY,
    quantity         TEXT NOT NULL,
    canonical_units  TEXT NOT NULL,
    aliases          TEXT[],
    warning_notes    TEXT
);

-- Evidence / QA logs -----------------------------------------------------
CREATE TABLE citations (
    id             BIGSERIAL PRIMARY KEY,
    answer_id      TEXT NOT NULL,
    chunk_id       BIGINT REFERENCES chunks(id) ON DELETE CASCADE,
    evidence_type  TEXT,                         -- documented | inferred | heuristic
    confidence     REAL
);

CREATE TABLE qa_logs (
    id                 BIGSERIAL PRIMARY KEY,
    query              TEXT NOT NULL,
    intent             TEXT,
    chosen_skills      TEXT[],
    retrieved_chunks   BIGINT[],
    final_verdict      TEXT,
    created_at         TIMESTAMPTZ DEFAULT now()
);
