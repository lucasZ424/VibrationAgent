"""qa_logs persistence: one optional, fail-safe row per Tutor-Orchestrator query.

Phase-2 Obj7. Writing is an optional side effect of ``handle_query``:
- when Postgres is disabled/offline the write is silently skipped and the primary
  answer is unaffected;
- a write failure returns a warning string (never raises), so the orchestrator's
  return status never changes;
- only locatable citation refs and short summaries are persisted — never raw
  chunk text, document originals, or secrets.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from vibration_agent.config import Settings, load

from .postgres import qa_log_row

# Defensive caps so a pathological query/summary never becomes long stored text.
_MAX_QUERY_CHARS = 2000
_MAX_SUMMARY_CHARS = 2000

# Best-effort secret masking for the free-text fields (query/summary). This is a
# conservative net for common credential shapes, not a guarantee — it covers the
# secret forms AC4 names ("API key") without over-redacting ordinary prose.
_SECRET_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[REDACTED]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{10,}"), "Bearer [REDACTED]"),
    (
        re.compile(r"(?i)\b(api[_-]?key|apikey|access[_-]?token|secret|password)(\s*[:=]\s*)(\S+)"),
        r"\1\2[REDACTED]",
    ),
)


def _redact_secrets(text: str | None) -> str | None:
    if not text:
        return text
    for pattern, replacement in _SECRET_RULES:
        text = pattern.sub(replacement, text)
    return text


def _truncate(text: str | None, limit: int) -> str | None:
    if not text:
        return text
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _attr(item: Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)


def _citation_refs(citations: Sequence[Any] | None) -> list[dict[str, Any]]:
    """Locatable references only — chunk/doc ids, pages, evidence type. No text."""
    refs: list[dict[str, Any]] = []
    for citation in citations or []:
        refs.append(
            {
                "chunk_id": _attr(citation, "chunk_id"),
                "doc_id": _attr(citation, "doc_id"),
                "pages": _attr(citation, "pages"),
                "evidence_type": _attr(citation, "evidence_type"),
                "confidence": _attr(citation, "confidence"),
            }
        )
    return refs


def _intent(output: Any) -> str | None:
    structured = getattr(output, "structured_result", {}) or {}
    skill_results = structured.get("skill_results", {}) if isinstance(structured, Mapping) else {}
    s2 = skill_results.get("s2", {}) if isinstance(skill_results, Mapping) else {}
    intent = s2.get("intent") if isinstance(s2, Mapping) else None
    return str(intent) if intent else None


def _chosen_skills(output: Any) -> list[str]:
    structured = getattr(output, "structured_result", {}) or {}
    chain = structured.get("chain", []) if isinstance(structured, Mapping) else []
    return [str(step.get("skill")) for step in chain if isinstance(step, Mapping) and step.get("skill")]


def _supervisor_invocations(output: Any) -> int | None:
    structured = getattr(output, "structured_result", {}) or {}
    if not isinstance(structured, Mapping):
        return None
    value = structured.get("supervisor_invocations")
    if value in (None, ""):
        return None
    return int(value)


def build_qa_log_row(
    output: Any,
    *,
    query: str,
    latency_ms: int | None = None,
    token_cost: int | None = None,
) -> dict[str, Any]:
    """Build the redacted, SQL-ready qa_logs row from a handle_query result."""
    citations = getattr(output, "citations", []) or []
    row = qa_log_row(
        _truncate(_redact_secrets(query), _MAX_QUERY_CHARS) or "",
        intent=_intent(output),
        chosen_skills=_chosen_skills(output),
        retrieved_chunks=[_attr(c, "chunk_id") for c in citations],
        final_verdict=_truncate(_redact_secrets(getattr(output, "summary", None)), _MAX_SUMMARY_CHARS),
        status=getattr(output, "status", None),
        citations=_citation_refs(citations),
        latency_ms=latency_ms,
        token_cost=token_cost,
        supervisor_invocations=_supervisor_invocations(output),
    )
    row.pop("_meta", None)  # _meta is a planning helper, not a SQL column
    # Empty SQL arrays are written as NULL: an untyped empty list is ambiguous to
    # the driver, and NULL vs empty array is not meaningful for these log columns.
    for array_column in ("chosen_skills", "retrieved_chunks"):
        if not row.get(array_column):
            row[array_column] = None
    return row


def record_qa_log(
    output: Any,
    *,
    query: str,
    latency_ms: int | None = None,
    token_cost: int | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Persist one qa_logs row as a fail-safe side effect.

    Returns ``None`` when skipped or successful, or a warning string when a write
    was attempted (Postgres enabled) but failed. Never raises.
    """
    database = (settings or load()).database
    if not getattr(database, "postgres_enabled", False):
        return None  # offline / disabled: silent skip, primary chain unaffected

    try:
        from . import postgres_client

        row = build_qa_log_row(output, query=query, latency_ms=latency_ms, token_cost=token_cost)
        connection = postgres_client.connect(
            database.postgres_url,
            connect_timeout=getattr(database, "postgres_timeout", 5.0),
        )
        try:
            postgres_client.insert_row(connection, "qa_logs", row, jsonb_columns=("citations",))
        finally:
            connection.close()
        return None
    except Exception as exc:  # noqa: BLE001 - side effect must never break the answer
        return f"qa_logs persistence skipped (write failed): {type(exc).__name__}: {exc}"
