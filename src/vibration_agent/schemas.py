"""Shared Pydantic schemas for vibration_agent.

This module is the single source of truth for Phase-0 skill I/O and the
file-level objects produced by ingestion.

Phase-1 Interface Freeze (2026-05-26): these contracts are stable for Phase-0 consumers.
Any Phase-2 schema change must start here, update fixtures/tests, and be
recorded in docs/phase_1_interface_freeze.md before callers are changed.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

UserMode = Literal["engineering", "definition", "derivation", "research"]
SkillStatus = Literal["ok", "insufficient", "fail"]
EvidenceType = Literal["documented", "inferred", "heuristic"]
Intent = Literal[
    "definition",
    "comparison",
    "standard_lookup",
    "engineering",
    "summary",
    "unknown",
]
SourceType = Literal["standard", "textbook", "review", "paper", "webpage", "book", "manual", "note"]
AssetType = Literal["body", "title", "text", "formula", "figure", "table", "page_image", "unknown"]
AssetObjectType = Literal["body", "formula", "figure", "table", "page_image"]
ChunkType = Literal["body", "section_summary", "formula_context", "figure_context", "table_context"]
SupportedKind = Literal["pdf", "docx", "image", "text", "unsupported"]
ProcessingStrategy = Literal["native_pdf", "ocr_pdf", "docx", "image", "text", "unknown"]
DocumentLanguage = Literal["zh", "en", "mixed", "unknown"]
DeferredSkill = Literal[
    "s4_engineering_analysis",
    "s5_formula_derivation",
    "s6_literature_search",
    "s7_model_selection",
    "s8_experiment_advice",
    "v1_term_symbol_unit_normalizer",
    "v2_citation_check",
    "v3_reviewer",
]

PHASE0_ACTIVE_SKILLS: tuple[str, ...] = (
    "s1_ingestion",
    "s2_retrieval",
    "s3_qa_summary",
    "v4_style",
)
PHASE0_DEFERRED_SKILLS: tuple[str, ...] = (
    "s4_engineering_analysis",
    "s5_formula_derivation",
    "s6_literature_search",
    "s7_model_selection",
    "s8_experiment_advice",
    "v1_term_symbol_unit_normalizer",
    "v2_citation_check",
    "v3_reviewer",
)


class Citation(BaseModel):
    chunk_id: str
    doc_id: str
    pages: list[int] | None = None
    evidence_type: EvidenceType = "documented"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SkillInput(BaseModel):
    task_id: str
    user_query: str
    context: dict[str, Any] = Field(default_factory=dict)
    retrieval_results: list[dict[str, Any]] = Field(default_factory=list)
    user_mode: UserMode = "engineering"
    constraints: dict[str, Any] = Field(default_factory=dict)


class SkillOutput(BaseModel):
    status: SkillStatus
    summary: str = ""
    structured_result: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    handoff_recommendation: str | None = None


class DocumentClassification(BaseModel):
    doc_id: str
    source_path: str
    filename: str
    suffix: str
    kind: SupportedKind
    mime_type: str | None = None
    file_size: int = Field(ge=0)
    sha256: str
    page_count: int | None = Field(default=None, ge=0)
    processing_strategy: ProcessingStrategy = "unknown"
    language: DocumentLanguage = "unknown"
    text_density: float | None = None
    text_chars: int | None = Field(default=None, ge=0)
    image_size: tuple[int, int] | None = None
    warnings: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DocumentInput(BaseModel):
    doc_id: str
    source_path: str
    title: str | None = None
    source_type: SourceType = "book"
    mime_type: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    processing_strategy: ProcessingStrategy = "unknown"
    language: DocumentLanguage = "unknown"


class DocumentBibliography(BaseModel):
    """Bibliographic metadata extracted from PDF metadata and first-page text.

    Phase-2 Obj3 addition. Every field falls back to empty/None when nothing is
    found, so Phase-1 citation behavior is preserved when no bibliography exists.
    Maps to the future `documents` table (year/authors/publisher columns).
    """

    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    publisher: str | None = None

    def has_author_year(self) -> bool:
        return bool(self.authors) and self.year is not None


class EmbeddingRecord(BaseModel):
    """One text embedding plus provenance.

    Phase-2 Obj5 addition. Fields are standalone and optional where provenance
    may be unavailable during fallback; no Phase-1 retrieval schema changes.
    """

    text_hash: str
    vector: list[float] = Field(default_factory=list)
    dimension: int | None = Field(default=None, ge=0)
    model_name: str | None = None
    model_version: str | None = None
    provider: str = "unknown"
    warnings: list[str] = Field(default_factory=list)


class DocumentAsset(BaseModel):
    asset_id: str
    doc_id: str
    page_no: int = Field(ge=1)
    object_type: AssetObjectType
    asset_path: str | None = None
    bbox: list[float] | list[list[float]] | None = None
    text: str = ""
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

class PageBlock(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    block_id: str
    text: str = ""
    bbox: list[float] | list[list[float]] | None = None
    block_type: AssetType = "text"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    asset_id: str | None = None
    asset_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def validated_copy(self, **updates: Any) -> "PageBlock":
        """Return a copy with updates validated against PageBlock invariants."""
        return type(self).model_validate({**self.model_dump(mode="python"), **updates})

    @model_validator(mode="after")
    def asset_blocks_must_have_asset_id(self) -> "PageBlock":
        if self.block_type in {"formula", "figure", "table", "page_image"} and not self.asset_id:
            raise ValueError(f"{self.block_type} blocks must carry asset_id")
        return self


class OcrPage(BaseModel):
    doc_id: str
    page_no: int = Field(ge=1)
    primary_engine: str
    fallback_used: bool = False
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    layout_quality: Literal["ok", "low", "empty", "unknown"] = "unknown"
    raw_text: str = ""
    normalized_text: str = ""
    blocks: list[PageBlock] = Field(default_factory=list)
    assets: list[DocumentAsset] = Field(default_factory=list)
    needs_review: bool = False




class MemoryChunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str | None = None
    source_type: SourceType = "book"
    source_path: str | None = None
    chunk_index: int = Field(ge=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    pages: list[int] = Field(default_factory=list)
    chunk_type: ChunkType = "body"
    topic: str | None = None
    token_estimate: int = Field(ge=0)
    char_count: int = Field(ge=0)
    citation_anchor: str | None = None
    text: str
    assets: list[DocumentAsset] = Field(default_factory=list)
    ocr_confidence_min: float | None = Field(default=None, ge=0.0, le=1.0)
    ocr_confidence_avg: float | None = Field(default=None, ge=0.0, le=1.0)
    needs_review_pages: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    api_context: str | None = None


class RetrievalHit(BaseModel):
    chunk_id: str
    doc_id: str
    source_type: SourceType | str
    pages: list[int] | None = None
    score: float
    reason: str = ""


class RetrievalOutput(BaseModel):
    normalized_query: str
    intent: Intent
    hits: list[RetrievalHit] = Field(default_factory=list)
    status: SkillStatus = "ok"
    warnings: list[str] = Field(default_factory=list)


class ApiContextPack(BaseModel):
    schema_version: str = "0.1"
    type: Literal["api_context_pack"] = "api_context_pack"
    doc_id: str
    title: str | None = None
    usage_note: str = "Use chunk_id and pages when citing. Do not answer beyond supplied chunks."
    chunks: list[dict[str, Any]] = Field(default_factory=list)


class IngestionManifestInput(BaseModel):
    source_path: str
    filename: str | None = None
    kind: SupportedKind | str
    sha256: str | None = None
    language: DocumentLanguage = "unknown"
    doc_id_mode: str = "content"
    processing_strategy: ProcessingStrategy | str = "unknown"
    document_page_count: int | None = Field(default=None, ge=0)


class IngestionManifestCounts(BaseModel):
    page_count: int = Field(ge=0)
    processed_pages: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    needs_review_page_count: int = Field(ge=0)
    total_token_estimate: int = Field(ge=0)


class IngestionManifestQuality(BaseModel):
    page_ocr_confidence_min: float | None = Field(default=None, ge=0.0, le=1.0)
    page_ocr_confidence_avg: float | None = Field(default=None, ge=0.0, le=1.0)
    chunk_ocr_confidence_min: float | None = Field(default=None, ge=0.0, le=1.0)
    chunk_ocr_confidence_avg: float | None = Field(default=None, ge=0.0, le=1.0)


class IngestionManifest(BaseModel):
    schema_version: str = "0.1"
    type: Literal["document_ingestion_manifest"] = "document_ingestion_manifest"
    created_at: str | None = None
    status: SkillStatus = "ok"
    doc_id: str
    title: str | None = None
    source_type: SourceType = "book"
    input: IngestionManifestInput
    counts: IngestionManifestCounts
    quality: IngestionManifestQuality = Field(default_factory=IngestionManifestQuality)
    needs_review_pages: list[int] = Field(default_factory=list)
    outputs: dict[str, str | None] = Field(default_factory=dict)
    output_formats: dict[str, str] = Field(default_factory=dict)
    downstream_use: list[str] = Field(default_factory=list)
    markdown_outputs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApiHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app: str
    workspace: str
    default_user_mode: UserMode
    phase0_pipeline: list[str]


class ApiScopeResponse(BaseModel):
    active_skills: list[str] = Field(default_factory=lambda: list(PHASE0_ACTIVE_SKILLS))
    deferred_skills: list[str] = Field(default_factory=lambda: list(PHASE0_DEFERRED_SKILLS))
    phase0_pipeline: list[str]


class ApiErrorItem(BaseModel):
    loc: list[str]
    reason: str
    error_type: str | None = None


class ApiErrorResponse(BaseModel):
    status: Literal["fail"] = "fail"
    detail: list[ApiErrorItem]


class ApiIngestionRequest(BaseModel):
    path: str = Field(min_length=1)
    workspace: str | None = None
    source_type: SourceType = "book"
    max_pages: int | None = Field(default=None, ge=1)
    recursive: bool = True
    write_output: bool = True
    keep_images: bool = False
    plan_only: bool = False


class ApiIngestionResult(BaseModel):
    status: SkillStatus
    stage: str | None = None
    input_path: str | None = None
    document_count: int | None = Field(default=None, ge=0)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApiIngestionResponse(BaseModel):
    workspace: str
    status: SkillStatus
    result: ApiIngestionResult


class ApiQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    workspace: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    chunks_jsonl: list[str] = Field(default_factory=list)
    chunks_dir: str | None = None
    top_k: int | None = Field(default=None, ge=1)
    scope: Literal["in_scope", "out_of_scope"] | None = Field(
        default=None,
        validation_alias=AliasChoices("scope", "domain_scope"),
    )
    user_mode: UserMode = "engineering"
    task_id: str | None = None


class ApiQueryResponse(BaseModel):
    workspace: str
    status: SkillStatus
    task_id: str | None = None
    output: SkillOutput

class PhaseScope(BaseModel):
    active_skills: tuple[str, ...] = PHASE0_ACTIVE_SKILLS
    deferred_skills: tuple[str, ...] = PHASE0_DEFERRED_SKILLS
    default_user_mode: UserMode = "engineering"
    allowed_domains: tuple[str, ...] = (
        "vibration",
        "rotating_machinery",
        "signal_analysis",
        "standards_interpretation",
    )
