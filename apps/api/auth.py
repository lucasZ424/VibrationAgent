"""API authentication helpers."""
from __future__ import annotations

from fastapi import Request

from vibration_agent.config import ApiSettings


def request_api_key(request: Request) -> str | None:
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key
    authorization = request.headers.get("authorization", "")
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix) :].strip()
    return None


def is_authorized(request: Request, api: ApiSettings) -> bool:
    if not api.auth_enabled:
        return True
    if not api.api_key:
        return False
    return request_api_key(request) == api.api_key
