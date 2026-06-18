"""Local-first observability helpers with deterministic redaction."""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[redacted]"
LOCAL_PATH_REDACTED = "[local-path]"
LONG_TEXT_REDACTED = "[redacted-long-text]"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_KEY_VALUE_RE = re.compile(
    r"\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*[^,\s;]+",
    re.IGNORECASE,
)
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\s\r\n]*")
_POSIX_PATH_RE = re.compile(r"(?<!\w)/(?:Users|home|tmp|var|private|mnt|Challenge)(?:/[^\s,;]+)+")


def _is_sensitive_key(key: str | None) -> bool:
    if not key:
        return False
    normalized = key.casefold().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _redact_path_prefixes(text: str, path_prefixes: Sequence[Any] | None) -> str:
    redacted = text
    for raw_prefix in path_prefixes or ():
        prefix = str(raw_prefix).strip().rstrip("\\/")
        if len(prefix) < 3:
            continue
        pattern = re.compile(re.escape(prefix) + r"(?:[\\/][^\s,;]+)*", re.IGNORECASE)
        redacted = pattern.sub(LOCAL_PATH_REDACTED, redacted)
    return redacted


def redact_text(text: str, *, max_length: int = 240, path_prefixes: Sequence[Any] | None = None) -> str:
    """Redact secrets, bearer tokens, local absolute paths, and long raw text."""
    redacted = _BEARER_RE.sub("Bearer " + REDACTED, text)
    redacted = _KEY_VALUE_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", redacted)
    redacted = _redact_path_prefixes(redacted, path_prefixes)
    redacted = _WINDOWS_PATH_RE.sub(LOCAL_PATH_REDACTED, redacted)
    redacted = _POSIX_PATH_RE.sub(LOCAL_PATH_REDACTED, redacted)
    if len(redacted) > max_length:
        return LONG_TEXT_REDACTED
    return redacted


def redact_value(
    value: Any,
    *,
    key: str | None = None,
    max_string_length: int = 240,
    path_prefixes: Sequence[Any] | None = None,
) -> Any:
    """Return a JSON-safe value with local observability redaction applied."""
    if _is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value, max_length=max_string_length, path_prefixes=path_prefixes)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_value(
                item_value,
                key=str(item_key),
                max_string_length=max_string_length,
                path_prefixes=path_prefixes,
            )
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact_value(item, max_string_length=max_string_length, path_prefixes=path_prefixes) for item in value]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return redact_text(str(value), max_length=max_string_length, path_prefixes=path_prefixes)


def structured_event(event: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "schema_version": "p4.local_observability.v1",
        "event": event,
    }
    payload.update(redact_value(fields))
    return payload


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    logger.log(
        level,
        json.dumps(structured_event(event, **fields), ensure_ascii=True, sort_keys=True, default=str),
    )


__all__ = [
    "LOCAL_PATH_REDACTED",
    "LONG_TEXT_REDACTED",
    "REDACTED",
    "log_event",
    "redact_text",
    "redact_value",
    "structured_event",
]
