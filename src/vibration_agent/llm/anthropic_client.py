"""Lazy Anthropic provider client for Phase-3 supervisor paths."""
from __future__ import annotations

import importlib
import json
import os
from typing import Any

from vibration_agent.agent.supervisor import ReviewReport
from vibration_agent.config import LlmProviderSettings

from ._guards import LiveProviderDisabledError, pytest_guard_active
from .budget import BudgetGuard, attach_cost_metadata, usage_from_response
from .replay import LlmRequest


class AnthropicClient:
    """Anthropic live client with supervisor review/correction seams."""

    def __init__(
        self,
        settings: LlmProviderSettings,
        *,
        allow_live: bool = False,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        if not allow_live:
            raise LiveProviderDisabledError("AnthropicClient requires allow_live=True for manual live use.")
        if pytest_guard_active():
            raise LiveProviderDisabledError("Live Anthropic clients are forbidden during pytest.")
        self.settings = settings
        self.budget_guard = budget_guard

    def complete(self, request: LlmRequest) -> dict[str, Any]:
        if self.budget_guard is not None:
            self.budget_guard.reserve_request(request, task_id=str(request.request_body.get("task_id") or "default"))
        api_key = os.getenv(self.settings.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing Anthropic API key env var: {self.settings.api_key_env}")

        anthropic = importlib.import_module("anthropic")
        client = anthropic.Anthropic(api_key=api_key, timeout=self.settings.timeout)
        message = client.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[{"role": "user", "content": request.request_body.get("prompt", "")}],
        )
        mapped = _message_to_mapping(message)
        if self.budget_guard is not None:
            parsed_usage = usage_from_response(mapped)
            if parsed_usage is not None:
                self.budget_guard.record_usage(
                    parsed_usage,
                    task_id=str(request.request_body.get("task_id") or "default"),
                    reservation_id=request.request_hash,
                )
        return attach_cost_metadata(mapped, provider_settings=self.settings)

    def review(self, **kwargs: Any) -> ReviewReport:
        response = self.complete(self._request(task="supervisor_review", schema_version="supervisor.v1", kwargs=kwargs))
        return ReviewReport.model_validate(response)

    def correct(self, **kwargs: Any) -> dict[str, Any]:
        return self.complete(self._request(task="supervisor_correction", schema_version="correction.v1", kwargs=kwargs))

    def _request(self, *, task: str, schema_version: str, kwargs: dict[str, Any]) -> LlmRequest:
        return LlmRequest(
            provider=self.settings.provider,
            model=_model_name(str(kwargs.get("model") or self.settings.model)),
            prompt_version=str(kwargs.get("prompt_version") or f"{task}.v1"),
            schema_version=str(kwargs.get("schema_version") or schema_version),
            request_body={key: value for key, value in kwargs.items() if key != "model"},
            temperature=float(kwargs.get("temperature") or self.settings.temperature),
            max_tokens=int(kwargs.get("max_tokens") or self.settings.max_tokens),
            reasoning_effort=kwargs.get("reasoning_effort") or self.settings.reasoning_effort,
            text_verbosity=kwargs.get("text_verbosity") or self.settings.text_verbosity,
        )


def _model_name(value: str) -> str:
    return value.split(":", 1)[1] if value.startswith("anthropic:") else value


def _message_to_mapping(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        data = message.model_dump(mode="python")
        if isinstance(data, dict):
            text = _content_text(data.get("content"))
            if text:
                parsed = _json_or_text(text)
                if isinstance(data.get("usage"), dict):
                    parsed.setdefault("usage", data["usage"])
                return parsed
            return data
    content = getattr(message, "content", None)
    text = _content_text(content)
    return _json_or_text(text) if text else {}


def _content_text(content: Any) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif hasattr(item, "text"):
                parts.append(str(item.text))
        return "\n".join(parts)
    return str(content) if isinstance(content, str) else ""


def _json_or_text(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"answer": text}
    return parsed if isinstance(parsed, dict) else {"answer": text}


__all__ = ["AnthropicClient"]
