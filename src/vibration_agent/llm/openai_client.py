"""Lazy OpenAI provider client for Phase-3 model paths."""
from __future__ import annotations

import importlib
import json
import os
from typing import Any

from vibration_agent.config import LlmProviderSettings

from ._guards import LiveProviderDisabledError, pytest_guard_active
from .budget import BudgetGuard, attach_cost_metadata, usage_from_response
from .replay import LlmRequest


class OpenAIClient:
    """OpenAI live client with structured-output seams for S3/S4/S5."""

    def __init__(
        self,
        settings: LlmProviderSettings,
        *,
        allow_live: bool = False,
        budget_guard: BudgetGuard | None = None,
    ) -> None:
        if not allow_live:
            raise LiveProviderDisabledError("OpenAIClient requires allow_live=True for manual live use.")
        if pytest_guard_active():
            raise LiveProviderDisabledError("Live OpenAI clients are forbidden during pytest.")
        self.settings = settings
        self.budget_guard = budget_guard

    def complete(self, request: LlmRequest) -> dict[str, Any]:
        if self.budget_guard is not None:
            self.budget_guard.reserve_request(request, task_id=str(request.request_body.get("task_id") or "default"))
        api_key = os.getenv(self.settings.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing OpenAI API key env var: {self.settings.api_key_env}")

        openai = importlib.import_module("openai")
        client = openai.OpenAI(api_key=api_key, timeout=self.settings.timeout)
        response = client.responses.create(**_responses_create_kwargs(request))
        mapped = _response_to_mapping(response)
        if self.budget_guard is not None:
            usage = mapped.get("usage") or mapped.get("token_usage")
            if isinstance(usage, dict):
                parsed_usage = usage_from_response(mapped)
                if parsed_usage is not None:
                    self.budget_guard.record_usage(
                        parsed_usage,
                        task_id=str(request.request_body.get("task_id") or "default"),
                        reservation_id=request.request_hash,
                    )
        return attach_cost_metadata(mapped, provider_settings=self.settings)

    def synthesize(self, **kwargs: Any) -> dict[str, Any]:
        request = self._request(task="s3_qa_summary", schema_version="s3.v1", kwargs=kwargs)
        return self.complete(request)

    def analyze_engineering(self, **kwargs: Any) -> dict[str, Any]:
        request = self._request(task="s4_engineering_analysis", schema_version="s4.v1", kwargs=kwargs)
        return self.complete(request)

    def derive_formula(self, **kwargs: Any) -> dict[str, Any]:
        request = self._request(task="s5_formula_derivation", schema_version="s5.v1", kwargs=kwargs)
        return self.complete(request)

    def _request(self, *, task: str, schema_version: str, kwargs: dict[str, Any]) -> LlmRequest:
        return LlmRequest(
            provider=self.settings.provider,
            model=_model_name(str(kwargs.get("model") or self.settings.model)),
            prompt_version=str(kwargs.get("prompt_version") or f"{task}.v1"),
            schema_version=str(kwargs.get("schema_version") or schema_version),
            request_body={key: value for key, value in kwargs.items() if key != "model"},
            max_tokens=int(kwargs.get("max_tokens") or self.settings.max_tokens),
            reasoning_effort=str(kwargs.get("reasoning_effort") or self.settings.reasoning_effort or ""),
            text_verbosity=str(kwargs.get("text_verbosity") or self.settings.text_verbosity or ""),
        )


def _model_name(value: str) -> str:
    return value.split(":", 1)[1] if value.startswith("openai:") else value


def _responses_create_kwargs(request: LlmRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": request.model,
        "input": request.request_body.get("prompt", ""),
        "max_output_tokens": request.max_tokens,
        "reasoning": {"effort": request.reasoning_effort} if request.reasoning_effort else None,
        "text": {"verbosity": request.text_verbosity} if request.text_verbosity else None,
    }
    return kwargs


def _response_to_mapping(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        data = response.model_dump(mode="python")
        if isinstance(data, dict):
            output_text = _output_text(data)
            if output_text.strip().startswith("{"):
                try:
                    parsed = json.loads(output_text)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, dict):
                        if isinstance(data.get("usage"), dict):
                            parsed.setdefault("usage", data["usage"])
                        return parsed
            return data
    text = getattr(response, "output_text", None)
    if isinstance(text, str):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"answer": text}
        return parsed if isinstance(parsed, dict) else {"answer": text}
    return {}


def _output_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str):
        return direct

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
    return "\n".join(parts)


__all__ = ["LiveProviderDisabledError", "OpenAIClient"]
