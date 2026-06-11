"""Replay and capture helpers for Phase-3 LLM calls."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field


_WINDOWS_ABS_PATH_RE = re.compile(r"(?i)\b[A-Z]:[\\/][^\s\r\n\"'<>|?*]+")
_WINDOWS_FULL_ABS_PATH_RE = re.compile(r"(?i)^[A-Z]:[\\/].+")
_UNC_ABS_PATH_RE = re.compile(r"\\\\[^\\/\s]+[\\/][^\s\r\n\"'<>|?*]+")
_UNC_FULL_ABS_PATH_RE = re.compile(r"^\\\\[^\\/]+[\\/].+")
_POSIX_ABS_PATH_RE = re.compile(r"(?<![\w:])/(?:Users|home|tmp|var|mnt|opt|private|Volumes)/[^\s\r\n\"']+")
_POSIX_FULL_ABS_PATH_RE = re.compile(r"^/(?:Users|home|tmp|var|mnt|opt|private|Volumes)/.+")


class ReplayMissError(RuntimeError):
    """Raised when a replay fixture is missing for a request hash."""


class RecordingDisabledError(RuntimeError):
    """Raised when capture is attempted outside the manual recording lane."""


class LlmRequest(BaseModel):
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    request_body: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int = Field(default=1024, ge=1)
    reasoning_effort: str | None = None
    text_verbosity: str | None = None

    @property
    def request_hash(self) -> str:
        return stable_request_hash(self)


class LlmFixture(BaseModel):
    metadata: dict[str, Any]
    response: dict[str, Any]


def _normalized_request_payload(request: LlmRequest) -> dict[str, Any]:
    return {
        "prompt_version": request.prompt_version,
        "schema_version": request.schema_version,
        "provider": request.provider,
        "model": request.model,
        "max_tokens": request.max_tokens,
        "reasoning_effort": request.reasoning_effort,
        "text_verbosity": request.text_verbosity,
        "request_body": request.request_body,
    }


def stable_request_hash(request: LlmRequest) -> str:
    payload = json.dumps(_normalized_request_payload(request), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fixture_metadata(request: LlmRequest) -> dict[str, Any]:
    metadata = _normalized_request_payload(request)
    metadata["request_hash"] = request.request_hash
    return metadata


def fixture_path(replay_dir: str | Path, request_hash: str) -> Path:
    return Path(replay_dir) / f"{request_hash}.json"


class ReplayClient:
    """Return captured LLM responses by stable request hash."""

    def __init__(self, replay_dir: str | Path) -> None:
        self.replay_dir = Path(replay_dir)

    def complete(self, request: LlmRequest) -> dict[str, Any]:
        path = fixture_path(self.replay_dir, request.request_hash)
        if not path.exists():
            raise ReplayMissError(f"No replay fixture for request hash {request.request_hash}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        fixture = LlmFixture.model_validate(raw)
        stored_hash = fixture.metadata.get("request_hash")
        if stored_hash != request.request_hash:
            raise ReplayMissError(
                f"Replay fixture hash mismatch for {path.name}: expected {request.request_hash}, found {stored_hash}"
            )
        return fixture.response

    def synthesize(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s3_qa_summary", schema_version="s3.v1", kwargs=kwargs))

    def analyze_engineering(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s4_engineering_analysis", schema_version="s4.v1", kwargs=kwargs))

    def derive_formula(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s5_formula_derivation", schema_version="s5.v1", kwargs=kwargs))

    def review(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(
            request_from_kwargs(task="supervisor_review", schema_version="supervisor.v1", kwargs=kwargs)
        )

    def correct(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(
            request_from_kwargs(task="supervisor_correction", schema_version="correction.v1", kwargs=kwargs)
        )


class RecordingClient:
    """Manual-only wrapper that records redacted replay fixtures."""

    def __init__(
        self,
        *,
        client: Any,
        fixture_dir: str | Path,
        capture_enabled: bool,
        manual_lane: bool,
    ) -> None:
        if not capture_enabled or not manual_lane:
            raise RecordingDisabledError("RecordingClient requires capture_enabled=true and manual_lane=true.")
        self.client = client
        self.fixture_dir = Path(fixture_dir)

    def complete(self, request: LlmRequest) -> dict[str, Any]:
        response = self.client.complete(request)
        write_fixture(self.fixture_dir, request, response)
        return response

    def synthesize(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s3_qa_summary", schema_version="s3.v1", kwargs=kwargs))

    def analyze_engineering(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s4_engineering_analysis", schema_version="s4.v1", kwargs=kwargs))

    def derive_formula(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(request_from_kwargs(task="s5_formula_derivation", schema_version="s5.v1", kwargs=kwargs))

    def review(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(
            request_from_kwargs(task="supervisor_review", schema_version="supervisor.v1", kwargs=kwargs)
        )

    def correct(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(
            request_from_kwargs(task="supervisor_correction", schema_version="correction.v1", kwargs=kwargs)
        )


def write_fixture(fixture_dir: str | Path, request: LlmRequest, response: Mapping[str, Any]) -> Path:
    path = fixture_path(fixture_dir, request.request_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    fixture = LlmFixture(
        metadata=_redact(fixture_metadata(request)),
        response=_redact(dict(response)),
    )
    path.write_text(
        json.dumps(fixture.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def request_from_kwargs(*, task: str, schema_version: str, kwargs: Mapping[str, Any]) -> LlmRequest:
    provider, model = _split_model_ref(str(kwargs.get("model") or "unknown:unknown"))
    return LlmRequest(
        provider=provider,
        model=model,
        prompt_version=str(kwargs.get("prompt_version") or f"{task}.v1"),
        schema_version=str(kwargs.get("schema_version") or schema_version),
        request_body={key: value for key, value in kwargs.items() if key != "model"},
        max_tokens=int(kwargs.get("max_tokens") or 1024),
        reasoning_effort=kwargs.get("reasoning_effort"),
        text_verbosity=kwargs.get("text_verbosity"),
    )


def _request_from_kwargs(*, task: str, schema_version: str, kwargs: Mapping[str, Any]) -> LlmRequest:
    return request_from_kwargs(task=task, schema_version=schema_version, kwargs=kwargs)


def _split_model_ref(value: str) -> tuple[str, str]:
    if ":" not in value:
        return "unknown", value
    provider, model = value.split(":", 1)
    return provider, model


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if _is_secret_key(lowered):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        if len(value) > 4000:
            return f"{value[:4000]}...[TRUNCATED]"
        if "Bearer " in value:
            return "Bearer [REDACTED]"
        return _scrub_local_paths(value)
    return value


def _is_secret_key(lowered: str) -> bool:
    if lowered in {"token", "access_token", "refresh_token", "auth_token", "bearer_token"}:
        return True
    return any(marker in lowered for marker in ("api_key", "authorization", "secret", "password"))


def _scrub_local_paths(value: str) -> str:
    stripped = value.strip()
    if (
        _WINDOWS_FULL_ABS_PATH_RE.match(stripped)
        or _UNC_FULL_ABS_PATH_RE.match(stripped)
        or _POSIX_FULL_ABS_PATH_RE.match(stripped)
    ):
        return value.replace(stripped, "[REDACTED_PATH]")
    scrubbed = _WINDOWS_ABS_PATH_RE.sub("[REDACTED_PATH]", value)
    scrubbed = _UNC_ABS_PATH_RE.sub("[REDACTED_PATH]", scrubbed)
    return _POSIX_ABS_PATH_RE.sub("[REDACTED_PATH]", scrubbed)


__all__ = [
    "LlmFixture",
    "LlmRequest",
    "RecordingClient",
    "RecordingDisabledError",
    "ReplayClient",
    "ReplayMissError",
    "fixture_metadata",
    "request_from_kwargs",
    "stable_request_hash",
    "write_fixture",
]
