"""PostgreSQL row mapping and dry-run write preparation.

The relational schema is owned by ``db/postgres/migrations/001_init.sql``. This
module intentionally contains no DDL; it only maps structured ingestion exports
to rows shaped for the Appendix-B tables.

Rows may include an ``_meta`` helper key with logical ids from the file export.
``_meta`` is not a SQL column; runtime writers must resolve those logical ids to
database BIGINT primary keys before insertion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .mappings import normalize_chunk_type

POSTGRES_TABLES: tuple[str, ...] = (
    "documents",
    "document_sections",
    "chunks",
    "figures_tables",
    "terms",
    "symbols",
    "units",
    "citations",
    "qa_logs",
)

POSTGRES_COLUMNS: dict[str, tuple[str, ...]] = {
    "documents": (
        "title",
        "type",
        "source",
        "language",
        "year",
        "authors",
        "file_path",
        "hash",
        "ocr_status",
        "parse_status",
        "version",
        "external_id",
    ),
    "document_sections": ("doc_id", "parent_id", "heading", "level", "page_start", "page_end"),
    "chunks": (
        "doc_id",
        "section_id",
        "page_start",
        "page_end",
        "chunk_type",
        "text",
        "normalized_text",
        "token_count",
        "citation_anchor",
        "external_id",
        "pages",
        "source_type",
        "topic",
    ),
    "figures_tables": ("doc_id", "page_no", "kind", "caption", "image_path", "related_chunk_ids"),
    "terms": ("canonical_term", "zh_name", "en_name", "aliases", "notes", "topic"),
    "symbols": ("canonical_symbol", "latex", "meaning", "unit", "notes", "avoid_confusion_with"),
    "units": ("quantity", "canonical_units", "aliases", "warning_notes"),
    "citations": ("answer_id", "chunk_id", "evidence_type", "confidence"),
    "qa_logs": (
        "query",
        "intent",
        "chosen_skills",
        "retrieved_chunks",
        "final_verdict",
        # Phase-2 Obj7 runtime columns (db/postgres/migrations/002_qa_logs_runtime.sql).
        "status",
        "citations",
        "latency_ms",
        "token_cost",
        # Phase-2 Obj13 supervisor observability.
        "supervisor_invocations",
    ),
}

POSTGRES_HELPER_KEYS: tuple[str, ...] = ("_meta",)


@dataclass(frozen=True)
class PostgresWritePlan:
    """Rows prepared for PostgreSQL insertion, keyed by table name."""

    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {table: [] for table in POSTGRES_TABLES})

    def counts(self) -> dict[str, int]:
        return {table: len(self.rows.get(table, [])) for table in POSTGRES_TABLES}

    def sql_rows(self) -> dict[str, list[dict[str, Any]]]:
        """Return rows stripped to columns that exist in ``001_init.sql``.

        Unknown non-helper keys raise instead of being silently dropped; this
        catches typo-d column names before a runtime writer reaches the DB.
        """
        sql_shaped: dict[str, list[dict[str, Any]]] = {}
        helper_keys = set(POSTGRES_HELPER_KEYS)
        for table, rows in self.rows.items():
            if table not in POSTGRES_COLUMNS:
                raise ValueError(f"Unknown Postgres table in write plan: {table}")
            allowed = set(POSTGRES_COLUMNS[table])
            table_rows: list[dict[str, Any]] = []
            for row in rows:
                unknown = sorted(set(row) - allowed - helper_keys)
                if unknown:
                    raise ValueError(f"Unknown Postgres column(s) for {table}: {unknown}")
                table_rows.append({key: value for key, value in row.items() if key in allowed})
            sql_shaped[table] = table_rows
        return sql_shaped

    def dry_run(self, *, preview: int = 3) -> dict[str, Any]:
        return {
            "status": "dry_run",
            "target": "postgres",
            "counts": self.counts(),
            "preview": {table: rows[:preview] for table, rows in self.rows.items() if rows},
            "sql_preview": {table: rows[:preview] for table, rows in self.sql_rows().items() if rows},
            "sql_columns": POSTGRES_COLUMNS,
            "ddl_source": "db/postgres/migrations/*.sql",
        }


def _empty_rows() -> dict[str, list[dict[str, Any]]]:
    return {table: [] for table in POSTGRES_TABLES}


def document_row(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Map a manifest to ``documents`` columns.

    ``created_at`` is intentionally omitted and left to the database default.
    """
    input_info = manifest.get("input", {})
    counts = manifest.get("counts", {})
    return {
        "external_id": manifest.get("doc_id"),
        "title": manifest.get("title") or input_info.get("filename") or manifest.get("doc_id"),
        "type": manifest.get("source_type", "book"),
        "source": input_info.get("source_path"),
        "language": input_info.get("language"),
        "year": None,
        "authors": [],
        "file_path": input_info.get("source_path"),
        "hash": input_info.get("sha256"),
        "ocr_status": "done" if counts.get("processed_pages", 0) else "pending",
        "parse_status": manifest.get("status", "ok"),
        "version": manifest.get("schema_version"),
    }


def _section_key(chunk: Mapping[str, Any]) -> str | None:
    metadata = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), Mapping) else {}
    value = metadata.get("section_key")
    return str(value) if value else None


def section_rows(chunks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str | None, str], dict[str, Any]] = {}
    for chunk in chunks:
        metadata = chunk.get("metadata", {}) if isinstance(chunk.get("metadata"), Mapping) else {}
        key = _section_key(chunk)
        if not key or key == "front_matter":
            continue
        logical_doc_id = str(chunk.get("doc_id")) if chunk.get("doc_id") else None
        row = by_key.setdefault(
            (logical_doc_id, key),
            {
                "doc_id": None,
                "parent_id": None,
                "heading": metadata.get("section_title"),
                "level": metadata.get("section_level") or None,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "_meta": {"section_key": key},
            },
        )
        if chunk.get("page_start") is not None:
            row["page_start"] = min(row["page_start"], chunk["page_start"]) if row.get("page_start") else chunk["page_start"]
        if chunk.get("page_end") is not None:
            row["page_end"] = max(row["page_end"], chunk["page_end"]) if row.get("page_end") else chunk["page_end"]
    return list(by_key.values())


def chunk_row(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "external_id": chunk.get("chunk_id"),
        "doc_id": None,
        "section_id": None,
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "chunk_type": normalize_chunk_type(chunk.get("chunk_type", "body")),
        "text": chunk.get("text", ""),
        "normalized_text": chunk.get("text", ""),
        "token_count": chunk.get("token_estimate"),
        "citation_anchor": chunk.get("citation_anchor"),
        "pages": chunk.get("pages", []),
        "source_type": chunk.get("source_type"),
        "topic": chunk.get("topic"),
        "_meta": {
            "chunk_id": chunk.get("chunk_id"),
            "logical_doc_id": chunk.get("doc_id"),
            "pages": chunk.get("pages", []),
            "topic": chunk.get("topic"),
            "source_type": chunk.get("source_type"),
            "section_key": _section_key(chunk),
        },
    }


def figure_table_rows(chunks: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str]] = set()
    for chunk in chunks:
        for asset in chunk.get("assets", []) or []:
            if not isinstance(asset, Mapping):
                continue
            object_type = asset.get("object_type")
            if object_type not in {"figure", "table"}:
                continue
            asset_id = str(asset.get("asset_id"))
            logical_doc_id = str(asset.get("doc_id") or chunk.get("doc_id")) if asset.get("doc_id") or chunk.get("doc_id") else None
            seen_key = (logical_doc_id, asset_id)
            if seen_key in seen:
                continue
            seen.add(seen_key)
            rows.append(
                {
                    "doc_id": None,
                    "page_no": asset.get("page_no"),
                    "kind": object_type,
                    "caption": asset.get("text") or None,
                    "image_path": asset.get("asset_path"),
                    "related_chunk_ids": [],
                    "_meta": {
                        "asset_id": asset_id,
                        "logical_doc_id": logical_doc_id,
                        "related_chunk_refs": [chunk.get("chunk_id")],
                        "bbox": asset.get("bbox"),
                    },
                }
            )
    return rows


def citation_rows(answer_id: str, citations: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "answer_id": answer_id,
            "chunk_id": None,
            "evidence_type": item.get("evidence_type", "documented"),
            "confidence": item.get("confidence", 1.0),
            "_meta": {
                "logical_chunk_id": item.get("chunk_id"),
                "logical_doc_id": item.get("doc_id"),
                "pages": item.get("pages"),
            },
        }
        for item in citations
    ]


def qa_log_row(
    query: str,
    *,
    intent: str | None = None,
    chosen_skills: Iterable[str] | None = None,
    retrieved_chunks: Iterable[str] | None = None,
    final_verdict: str | None = None,
    status: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    latency_ms: int | None = None,
    token_cost: int | None = None,
    supervisor_invocations: int | None = None,
) -> dict[str, Any]:
    """Prepare a QA log row with logical retrieval refs in ``_meta``.

    ``retrieved_chunks`` is a BIGINT[] column, so the dry-run row leaves it empty
    until a runtime writer resolves logical chunk ids to database ids. The Obj7
    runtime columns (``status``/``citations``/``latency_ms``/``token_cost``) carry
    only locatable citation refs and metadata — never raw chunk text or secrets.
    """
    logical_refs = [str(item) for item in retrieved_chunks or []]
    return {
        "query": query,
        "intent": intent,
        "chosen_skills": list(chosen_skills or []),
        "retrieved_chunks": [],
        "final_verdict": final_verdict,
        "status": status,
        "citations": citations if citations is not None else [],
        "latency_ms": latency_ms,
        "token_cost": token_cost,
        "supervisor_invocations": supervisor_invocations,
        "_meta": {"logical_retrieved_chunk_ids": logical_refs},
    }


def term_rows(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "canonical_term": item.get("canonical_term") or item.get("term"),
            "zh_name": item.get("zh_name"),
            "en_name": item.get("en_name"),
            "aliases": item.get("aliases", []),
            "notes": item.get("notes"),
            "topic": item.get("topic"),
        }
        for item in items
    ]


def symbol_rows(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "canonical_symbol": item.get("canonical_symbol") or item.get("symbol"),
            "latex": item.get("latex"),
            "meaning": item.get("meaning"),
            "unit": item.get("unit"),
            "notes": item.get("notes"),
            "avoid_confusion_with": item.get("avoid_confusion_with", []),
        }
        for item in items
    ]


def unit_rows(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "quantity": item.get("quantity"),
            "canonical_units": item.get("canonical_units") or item.get("unit"),
            "aliases": item.get("aliases", []),
            "warning_notes": item.get("warning_notes") or item.get("notes"),
        }
        for item in items
    ]


def _validate_single_document_chunks(manifest: Mapping[str, Any], chunks: Iterable[Mapping[str, Any]]) -> None:
    manifest_doc_id = manifest.get("doc_id")
    if not manifest_doc_id:
        return
    mismatches = sorted({str(chunk.get("doc_id")) for chunk in chunks if chunk.get("doc_id") and chunk.get("doc_id") != manifest_doc_id})
    if mismatches:
        raise ValueError(f"prepare_ingestion_plan accepts one manifest document; got chunks for doc_id(s): {mismatches}")


def prepare_ingestion_plan(manifest: Mapping[str, Any], chunks: Iterable[Mapping[str, Any]]) -> PostgresWritePlan:
    chunk_list = list(chunks)
    _validate_single_document_chunks(manifest, chunk_list)
    rows = _empty_rows()
    rows["documents"] = [document_row(manifest)]
    rows["document_sections"] = section_rows(chunk_list)
    rows["chunks"] = [chunk_row(chunk) for chunk in chunk_list]
    rows["figures_tables"] = figure_table_rows(chunk_list)
    return PostgresWritePlan(rows=rows)


def dry_run_ingestion(manifest: Mapping[str, Any], chunks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    return prepare_ingestion_plan(manifest, chunks).dry_run()


def connect(url: str):
    """Open a runtime Postgres connection via the optional psycopg adapter."""
    from .postgres_client import connect as _connect

    return _connect(url)
