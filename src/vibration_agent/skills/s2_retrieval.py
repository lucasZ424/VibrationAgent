"""S2 knowledge-base retrieval skill.

This wraps the Phase-0 hybrid retrieval pipeline in the shared SkillInput /
SkillOutput contract. It retrieves only from supplied S1 chunk exports and never
invents chunk ids when recall is weak.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from vibration_agent.config import Settings
from vibration_agent.knowledge.evidence import snippet_text
from vibration_agent.retrieval.hybrid import default_retrieval_settings, search as hybrid_search
from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

RetrievalRunner = Callable[..., dict[str, Any]]

_CHUNK_PATH_KEYS = ("chunks_jsonl", "chunk_path", "chunks_path")
_CHUNK_PATHS_KEYS = ("chunk_paths", "chunks_paths")
_CHUNKS_DIR_KEYS = ("chunks_dir", "chunk_dir")


def _first_present(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _as_path_list(value: Any) -> list[Path]:
    if value in (None, ""):
        return []
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, list | tuple):
        return [Path(item) for item in value if item not in (None, "")]
    return []


def _paths_from_s1_context(payload: SkillInput) -> list[Path]:
    paths: list[Path] = []
    documents = payload.context.get("documents") or payload.context.get("s1_documents")
    if not isinstance(documents, list):
        s1_result = payload.context.get("s1_result")
        if isinstance(s1_result, Mapping):
            documents = s1_result.get("documents")
    if not isinstance(documents, list):
        return paths
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        outputs = document.get("outputs") if isinstance(document.get("outputs"), Mapping) else {}
        chunks_jsonl = outputs.get("chunks_jsonl") if isinstance(outputs, Mapping) else None
        if chunks_jsonl:
            paths.append(Path(str(chunks_jsonl)))
    return paths


def _resolve_path(path: Path, settings: Settings) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (settings.paths.workspace / expanded).resolve()


def _collect_chunk_paths(payload: SkillInput, settings: Settings) -> list[Path]:
    raw_paths: list[Path] = []
    raw_paths.extend(_as_path_list(_first_present(payload.constraints, payload.context, keys=_CHUNK_PATH_KEYS)))
    raw_paths.extend(_as_path_list(_first_present(payload.constraints, payload.context, keys=_CHUNK_PATHS_KEYS)))
    raw_paths.extend(_paths_from_s1_context(payload))
    return [_resolve_path(path, settings) for path in raw_paths]


def _collect_chunks_dir(payload: SkillInput, settings: Settings) -> Path | None:
    value = _first_present(payload.constraints, payload.context, keys=_CHUNKS_DIR_KEYS)
    if value in (None, ""):
        return None
    return _resolve_path(Path(str(value)), settings)


def _top_k(payload: SkillInput, settings: Settings) -> int:
    value = payload.constraints.get("top_k")
    if value in (None, ""):
        value = payload.context.get("top_k")
    if value in (None, ""):
        return settings.retrieval.final_top_k
    return int(value)


def _runtime_store_enabled(settings: Settings) -> bool:
    return bool(settings.database.qdrant_enabled)


def _citations_from_hits(hits: list[dict[str, Any]], context_rows: list[dict[str, Any]] | None = None) -> list[Citation]:
    """Create citations with result-relative confidence, not raw RRF score.

    Raw hybrid scores are ranking scores that usually cluster around 0.02-0.05;
    citation confidence is normalized against the strongest returned hit so later
    quality checks do not mistake low-magnitude RRF scores for weak evidence.
    """
    max_score = max((float(hit.get("score") or 0.0) for hit in hits), default=0.0)
    context_by_chunk = {
        str(row["chunk_id"]): row
        for row in context_rows or []
        if isinstance(row, dict) and row.get("chunk_id")
    }
    citations: list[Citation] = []
    for hit in hits:
        if not hit.get("chunk_id") or not hit.get("doc_id"):
            continue
        context = context_by_chunk.get(str(hit["chunk_id"]), {})
        raw_score = float(hit.get("score") or 0.0)
        confidence = raw_score / max_score if max_score > 0 else 0.0
        citations.append(
            Citation(
                chunk_id=str(hit["chunk_id"]),
                doc_id=str(hit["doc_id"]),
                pages=list(hit.get("pages") or []),
                evidence_type="documented",
                confidence=max(0.0, min(confidence, 1.0)),
                source_filename=str(context["source_filename"]) if context.get("source_filename") else None,
                source_title=str(context["source_title"]) if context.get("source_title") else None,
                snippet=snippet_text(context.get("text")),
            )
        )
    return citations


class RetrievalSkill(Skill):
    name = "s2_retrieval"

    def __init__(self, *, settings: Settings | None = None, runner: RetrievalRunner | None = None) -> None:
        self.settings = settings or default_retrieval_settings()
        self._runner = runner or hybrid_search

    def run(self, payload: SkillInput) -> SkillOutput:
        chunk_paths = _collect_chunk_paths(payload, self.settings)
        chunks_dir = _collect_chunks_dir(payload, self.settings)
        chunks = payload.context.get("chunks") if isinstance(payload.context.get("chunks"), list) else None

        missing_paths = [str(path) for path in chunk_paths if not path.exists()]
        if missing_paths:
            return SkillOutput(
                status="insufficient",
                summary="S2 retrieval requires existing chunks_jsonl paths.",
                structured_result={"task_id": payload.task_id, "missing_paths": missing_paths},
                warnings=[f"Missing chunks_jsonl path: {path}" for path in missing_paths],
                handoff_recommendation="Run S1 ingestion first or pass constraints.chunks_jsonl.",
            )
        if chunks_dir is not None and not chunks_dir.exists():
            return SkillOutput(
                status="insufficient",
                summary=f"S2 chunks_dir does not exist: {chunks_dir}",
                structured_result={"task_id": payload.task_id, "chunks_dir": str(chunks_dir)},
                warnings=[f"Missing chunks_dir: {chunks_dir}"],
                handoff_recommendation="Run S1 ingestion first or pass a valid chunks_dir.",
            )
        if not chunk_paths and chunks_dir is None and chunks is None and not _runtime_store_enabled(self.settings):
            return SkillOutput(
                status="insufficient",
                summary="S2 retrieval requires chunk_paths, chunks_dir, or in-memory chunks.",
                structured_result={"task_id": payload.task_id},
                warnings=["No chunk corpus supplied for S2 retrieval."],
                handoff_recommendation="Pass constraints.chunks_jsonl from S1 output.",
            )

        try:
            result = self._runner(
                payload.user_query,
                top_k=_top_k(payload, self.settings),
                chunks=chunks,
                chunk_paths=chunk_paths,
                chunks_dir=chunks_dir,
                settings=self.settings,
            )
        except Exception as exc:
            return SkillOutput(
                status="fail",
                summary=f"S2 retrieval failed: {type(exc).__name__}: {exc}",
                structured_result={"task_id": payload.task_id, "chunk_paths": [str(path) for path in chunk_paths]},
                warnings=[f"{type(exc).__name__}: {exc}"],
                handoff_recommendation="Validate chunk JSONL files and rerun S2.",
            )

        hits = result.get("hits", []) if isinstance(result.get("hits"), list) else []
        retrieval_context = result.get("retrieval_context", []) if isinstance(result.get("retrieval_context"), list) else []
        evidence_context = result.get("evidence_context", []) if isinstance(result.get("evidence_context"), list) else retrieval_context
        status = result.get("status") if result.get("status") in {"ok", "insufficient", "fail"} else "insufficient"
        return SkillOutput(
            status=status,
            summary=f"S2 retrieval {status}: {len(hits)} hit(s).",
            structured_result={
                "task_id": payload.task_id,
                "retrieval_output": {
                    key: result.get(key)
                    for key in ("normalized_query", "intent", "hits", "status", "warnings")
                },
                "retrieval_context": retrieval_context,
                "evidence_context": evidence_context,
                "evidence_selection": result.get("evidence_selection"),
                "detected_terms": result.get("detected_terms", []),
                "detected_symbols": result.get("detected_symbols", []),
                "retrieval_source": result.get("retrieval_source"),
                "chunk_paths": [str(path) for path in chunk_paths],
                "chunks_dir": str(chunks_dir) if chunks_dir is not None else None,
            },
            citations=_citations_from_hits(
                [
                    {
                        "chunk_id": row.get("chunk_id"),
                        "doc_id": row.get("doc_id"),
                        "pages": row.get("pages") or [],
                        "score": row.get("score") or 0.0,
                    }
                    for row in evidence_context
                ],
                evidence_context,
            ),
            warnings=list(result.get("warnings", [])),
            handoff_recommendation="Pass retrieval_context to S3." if status == "ok" else "Run S1 ingestion or broaden the query.",
        )
