"""S6 literature search prototype.

S6 is a default-off, replay-first literature search skill. It never performs a
network call on its own; manual live use requires an injected client and an
explicit live gate.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vibration_agent.config import Settings, load
from vibration_agent.schemas import SkillInput, SkillOutput

from .base import Skill

_SCHEMA_VERSION = "s6.literature_search.v1"
_DEFAULT_MAX_CANDIDATES = 5
_LONG_TEXT_LIMIT = 1200
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|x-api-key)(\s*[:=]\s*)([A-Za-z0-9_\-]{8,})"),
    re.compile(r"(?i)(authorization|bearer)(\s*[:=]?\s*)(Bearer\s+)?([A-Za-z0-9._\-]{8,})"),
)
_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_POSIX_PATH_RE = re.compile(r"(?<![\w.])/(?:Users|home|var|tmp|mnt)/[^\s\"']+")


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _first_present(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _replay_fixture(payload: SkillInput) -> Any:
    return _first_present(
        payload.constraints,
        payload.context,
        keys=("literature_fixture", "s6_fixture", "replay_fixture", "literature_replay"),
    )


def _skill_enabled(payload: SkillInput) -> bool:
    if _replay_fixture(payload) is not None:
        return True
    value = _first_present(
        payload.constraints,
        payload.context,
        keys=("s6_enabled", "literature_search_enabled", "use_s6"),
    )
    return _as_bool(value, default=False)


def _live_enabled(payload: SkillInput) -> bool:
    value = _first_present(
        payload.constraints,
        payload.context,
        keys=("s6_live_enabled", "literature_live_enabled", "live_external_search"),
    )
    return _as_bool(value, default=False)


def _source(payload: SkillInput) -> str:
    value = _first_present(payload.constraints, payload.context, keys=("literature_source", "s6_source", "source"))
    source = str(value or "semantic_scholar").strip().lower()
    aliases = {
        "semantic": "semantic_scholar",
        "semantic-scholar": "semantic_scholar",
        "semantic_scholar_graph": "semantic_scholar",
        "arxiv": "arxiv",
    }
    return aliases.get(source, source)


def _max_candidates(payload: SkillInput) -> int:
    value = _first_present(payload.constraints, payload.context, keys=("max_candidates", "top_k"))
    if value in (None, ""):
        return _DEFAULT_MAX_CANDIDATES
    return max(1, int(value))


def _load_replay_fixture(value: Any, settings: Settings) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    path = Path(str(value))
    if not path.is_absolute():
        path = settings.paths.workspace / path
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("S6 replay fixture must contain one JSON object.")
    return data


def _candidate_id(item: Mapping[str, Any], index: int) -> str:
    for key in ("paper_id", "paperId", "arxiv_id", "doi", "url"):
        value = item.get(key)
        if value not in (None, ""):
            normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value)).strip("_")
            if normalized:
                return f"lit_{normalized}"
    return f"lit_{index}"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _candidate(item: Mapping[str, Any], *, source: str, index: int) -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    abstract = str(item.get("abstract") or item.get("snippet") or "").strip()
    snippet = str(item.get("snippet") or abstract[:300]).strip()
    candidate_id = _candidate_id(item, index)
    return {
        "candidate_id": candidate_id,
        "title": title,
        "authors": _string_list(item.get("authors")),
        "year": item.get("year"),
        "venue": item.get("venue") or item.get("source") or "",
        "source": item.get("source") or source,
        "doi": item.get("doi") or "",
        "arxiv_id": item.get("arxiv_id") or item.get("arxivId") or "",
        "url": item.get("url") or "",
        "abstract": abstract,
        "snippet": snippet,
        "retrieval_source": source,
        "evidence_anchors": [
            {
                "anchor_id": f"{candidate_id}#abstract",
                "kind": "abstract",
                "text": snippet or title,
                "url": item.get("url") or "",
            }
        ],
    }


def _candidates(data: Mapping[str, Any], *, source: str, limit: int) -> list[dict[str, Any]]:
    raw = data.get("candidates")
    if raw is None:
        raw = data.get("papers")
    if not isinstance(raw, list):
        return []
    return [
        _candidate(item, source=str(item.get("retrieval_source") or source), index=index)
        for index, item in enumerate(raw[:limit], start=1)
        if isinstance(item, Mapping)
    ]


def _call_live_client(client: Any, *, query: str, source: str, limit: int) -> Mapping[str, Any]:
    if source == "semantic_scholar" and hasattr(client, "search_semantic_scholar"):
        response = client.search_semantic_scholar(query=query, limit=limit)
    elif source == "arxiv" and hasattr(client, "search_arxiv"):
        response = client.search_arxiv(query=query, limit=limit)
    elif callable(client):
        response = client(query=query, source=source, limit=limit)
    else:
        raise TypeError("S6 live client must be callable or expose a source-specific search method.")
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        dumped = response.model_dump(mode="python")
        if isinstance(dumped, Mapping):
            return dumped
    raise ValueError("S6 live client response must be a mapping.")


def redact_capture(value: Any) -> Any:
    """Redact API keys, bearer tokens, local paths, and long raw text."""
    if isinstance(value, Mapping):
        return {str(key): redact_capture(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_capture(item) for item in value]
    if not isinstance(value, str):
        return value
    text = value
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + match.group(2) + "[REDACTED]", text)
    text = _WINDOWS_PATH_RE.sub("[REDACTED_LOCAL_PATH]", text)
    text = _POSIX_PATH_RE.sub("[REDACTED_LOCAL_PATH]", text)
    if len(text) > _LONG_TEXT_LIMIT:
        text = text[:_LONG_TEXT_LIMIT] + "...[TRUNCATED]"
    return text


class LiteratureSearchSkill(Skill):
    name = "s6_literature_search"

    def __init__(self, *, settings: Settings | None = None, live_client: Any | None = None) -> None:
        self._settings = settings
        self._live_client = live_client

    def run(self, payload: SkillInput) -> SkillOutput:
        settings = self._settings or load()
        source = _source(payload)
        limit = _max_candidates(payload)
        if source not in {"semantic_scholar", "arxiv"}:
            return SkillOutput(
                status="insufficient",
                summary=f"S6 skipped: unsupported literature source '{source}'.",
                structured_result={
                    "schema_version": _SCHEMA_VERSION,
                    "task_id": payload.task_id,
                    "query": payload.user_query,
                    "source_mode": "fallback",
                    "retrieval_source": source,
                    "candidates": [],
                    "routing": {"default_chain": False, "requires_activation_gate": True},
                },
                warnings=["S6 supports Semantic Scholar Graph API and arXiv API only."],
                handoff_recommendation="Use literature_source='semantic_scholar' or 'arxiv'.",
            )

        if not _skill_enabled(payload):
            return SkillOutput(
                status="insufficient",
                summary="S6 skipped: literature search is default-off.",
                structured_result={
                    "schema_version": _SCHEMA_VERSION,
                    "task_id": payload.task_id,
                    "query": payload.user_query,
                    "source_mode": "disabled",
                    "retrieval_source": source,
                    "candidates": [],
                    "routing": {"default_chain": False, "requires_activation_gate": True},
                },
                handoff_recommendation="Pass a replay fixture or set s6_enabled=true for explicit S6 use.",
            )

        warnings: list[str] = []
        fixture = _replay_fixture(payload)
        if fixture is not None:
            try:
                data = _load_replay_fixture(fixture, settings)
            except Exception as exc:
                return SkillOutput(
                    status="fail",
                    summary="S6 replay fixture failed to load.",
                    structured_result={"schema_version": _SCHEMA_VERSION, "task_id": payload.task_id, "candidates": []},
                    warnings=[f"S6 replay fixture unavailable: {type(exc).__name__}: {exc}"],
                    handoff_recommendation="Fix or replace the S6 replay fixture.",
                )
            candidates = _candidates(data, source=str(data.get("retrieval_source") or source), limit=limit)
            mode = "replay"
        elif _live_enabled(payload):
            if self._live_client is None:
                candidates = []
                mode = "fallback"
                warnings.append("S6 live search requested but no manual live client was injected.")
            else:
                try:
                    data = _call_live_client(self._live_client, query=payload.user_query, source=source, limit=limit)
                    candidates = _candidates(redact_capture(data), source=source, limit=limit)
                    mode = "manual_live"
                except Exception as exc:  # noqa: BLE001 - live search must cleanly degrade
                    candidates = []
                    mode = "fallback"
                    warnings.append(f"S6 live search unavailable: {type(exc).__name__}: {exc}")
        else:
            candidates = []
            mode = "fallback"
            warnings.append("S6 literature search requires a replay fixture or explicit manual live gate.")

        status = "ok" if candidates else "insufficient"
        return SkillOutput(
            status=status,
            summary=f"S6 literature search {status}: {len(candidates)} candidate(s).",
            structured_result={
                "schema_version": _SCHEMA_VERSION,
                "task_id": payload.task_id,
                "query": payload.user_query,
                "source_mode": mode,
                "retrieval_source": source,
                "candidates": candidates,
                "redaction_policy": {
                    "api_keys": True,
                    "bearer_tokens": True,
                    "local_paths": True,
                    "long_raw_text": True,
                },
                "routing": {"default_chain": False, "requires_activation_gate": True},
            },
            warnings=warnings,
            handoff_recommendation="Use S6 candidates as cited research context only after V2/V4-bound synthesis.",
        )


__all__ = ["LiteratureSearchSkill", "redact_capture"]
