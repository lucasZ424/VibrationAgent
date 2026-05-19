"""S1 document ingestion skill.

This skill adapts the formal ingestion pipeline to the Phase-0 SkillInput /
SkillOutput contract. It does not interpret document content; it only produces
page, asset, chunk, api_context, and manifest exports for downstream retrieval.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from vibration_agent.config import Settings
from vibration_agent.ingestion.pipeline import chunk_documents

from ..schemas import SkillInput, SkillOutput, SkillStatus
from .base import Skill

IngestionRunner = Callable[..., dict[str, Any]]

_INPUT_PATH_KEYS = ("input_path", "source_path", "raw_path", "path", "raw_dir")


def _first_present(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _skill_status(value: Any, *, has_documents: bool) -> SkillStatus:
    if value in {"ok", "insufficient", "fail"}:
        return value
    return "ok" if has_documents else "insufficient"


def _resolve_input_path(payload: SkillInput) -> Path | None:
    value = _first_present(payload.constraints, payload.context, keys=_INPUT_PATH_KEYS)
    if value is not None:
        return Path(str(value)).expanduser()

    query = payload.user_query.strip().strip('"')
    if query and Path(query).expanduser().exists():
        return Path(query).expanduser()
    return None


def _document_summary(document: Mapping[str, Any]) -> dict[str, Any]:
    manifest = document.get("manifest", {}) if isinstance(document.get("manifest"), Mapping) else {}
    manifest_input = manifest.get("input", {}) if isinstance(manifest.get("input"), Mapping) else {}
    counts = manifest.get("counts", {}) if isinstance(manifest.get("counts"), Mapping) else {}
    quality = manifest.get("quality", {}) if isinstance(manifest.get("quality"), Mapping) else {}
    outputs = document.get("outputs") or manifest.get("outputs") or {}
    return {
        "doc_id": document.get("doc_id") or manifest.get("doc_id"),
        "status": document.get("status") or manifest.get("status"),
        "source_path": document.get("source_path") or manifest_input.get("source_path"),
        "processed_pages": document.get("processed_pages") or counts.get("processed_pages"),
        "chunk_count": document.get("chunk_count") or counts.get("chunk_count"),
        "needs_review_pages": manifest.get("needs_review_pages", []),
        "outputs": outputs,
        "quality": quality,
    }


def _collect_warnings(result: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = [str(item) for item in result.get("warnings", []) if item]
    for document in documents:
        for warning in document.get("warnings", []) or []:
            if warning:
                warnings.append(str(warning))
        manifest = document.get("manifest", {}) if isinstance(document.get("manifest"), Mapping) else {}
        for warning in manifest.get("warnings", []) or []:
            if warning:
                warnings.append(str(warning))
    return list(dict.fromkeys(warnings))


class IngestionSkill(Skill):
    name = "s1_ingestion"

    def __init__(self, *, settings: Settings | None = None, runner: IngestionRunner | None = None) -> None:
        self.settings = settings
        self._runner = runner or chunk_documents

    def run(self, payload: SkillInput) -> SkillOutput:
        input_path = _resolve_input_path(payload)
        if input_path is None:
            return SkillOutput(
                status="insufficient",
                summary="S1 ingestion requires an input_path/source_path in constraints or context.",
                warnings=["Missing input_path for S1 ingestion."],
                handoff_recommendation="Provide constraints.input_path pointing to a PDF file or input directory.",
            )

        if not input_path.exists():
            return SkillOutput(
                status="insufficient",
                summary=f"Input path does not exist: {input_path}",
                structured_result={"input_path": str(input_path)},
                warnings=[f"Input path does not exist: {input_path}"],
                handoff_recommendation="Check the path and rerun S1 ingestion.",
            )

        try:
            result = self._runner(
                input_path,
                recursive=_as_bool(payload.constraints.get("recursive"), default=True),
                max_pages=_as_optional_int(payload.constraints.get("max_pages")),
                write_output=_as_bool(payload.constraints.get("write_output"), default=True),
                keep_images=_as_bool(payload.constraints.get("keep_images"), default=False),
                source_type=str(payload.constraints.get("source_type") or payload.context.get("source_type") or "book"),
                settings=self.settings,
            )
        except Exception as exc:
            return SkillOutput(
                status="fail",
                summary=f"S1 ingestion failed: {type(exc).__name__}: {exc}",
                structured_result={"input_path": str(input_path)},
                warnings=[f"{type(exc).__name__}: {exc}"],
                handoff_recommendation="Inspect the source file and ingestion logs, then rerun S1.",
            )

        raw_documents = result.get("documents", []) if isinstance(result, Mapping) else []
        documents = [item for item in raw_documents if isinstance(item, Mapping)]
        document_summaries = [_document_summary(document) for document in documents]
        warnings = _collect_warnings(result, documents) if isinstance(result, Mapping) else []
        total_chunks = sum(int(item.get("chunk_count") or 0) for item in document_summaries)
        status = _skill_status(result.get("status") if isinstance(result, Mapping) else None, has_documents=bool(documents))
        if status == "ok" and total_chunks == 0:
            status = "insufficient"
            warnings.append("S1 ingestion produced no chunks.")

        return SkillOutput(
            status=status,
            summary=f"S1 ingestion {status}: {len(document_summaries)} document(s), {total_chunks} chunk(s).",
            structured_result={
                "stage": result.get("stage") if isinstance(result, Mapping) else None,
                "input_path": result.get("input_path", str(input_path)) if isinstance(result, Mapping) else str(input_path),
                "document_count": len(document_summaries),
                "chunk_count": total_chunks,
                "documents": document_summaries,
            },
            warnings=warnings,
            handoff_recommendation="Run S2 retrieval on chunks_jsonl/api_context_json outputs." if status == "ok" else None,
        )
