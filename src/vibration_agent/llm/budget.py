"""Token budget and local cost estimation for Phase-3 LLM calls."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, Field

from vibration_agent.config import LlmProviderSettings, LlmSettings
from vibration_agent.schemas import LlmCostEstimate, LlmTokenUsage

from .replay import LlmRequest


class BudgetDeniedError(RuntimeError):
    """Raised before a provider call when the local budget would be exceeded."""


class BudgetDecision(BaseModel):
    allowed: bool
    requested_tokens: int = Field(default=0, ge=0)
    remaining_task_tokens: int = Field(default=0, ge=0)
    remaining_session_tokens: int = Field(default=0, ge=0)
    estimated_usd: float | None = None
    reason: str = ""


@dataclass
class _Reservation:
    task_id: str
    tokens: int


class BudgetGuard:
    """In-memory per-session guard for local LLM token/cost budgets."""

    def __init__(
        self,
        *,
        per_task_tokens: int = 4000,
        per_session_tokens: int = 30000,
        usd_budget_per_task: float | None = None,
    ) -> None:
        self.per_task_tokens = per_task_tokens
        self.per_session_tokens = per_session_tokens
        self.usd_budget_per_task = usd_budget_per_task
        self._session_tokens = 0
        self._task_tokens: dict[str, int] = {}
        self._reservations: dict[str, _Reservation] = {}

    @classmethod
    def from_settings(cls, settings: LlmSettings) -> "BudgetGuard":
        return cls(
            per_task_tokens=settings.token_budget_per_task,
            per_session_tokens=settings.token_budget_per_session,
            usd_budget_per_task=settings.usd_budget_per_task,
        )

    def reserve(
        self,
        *,
        task_id: str,
        requested_tokens: int,
        estimated_usd: float | None = None,
        reservation_id: str | None = None,
    ) -> BudgetDecision:
        task_used = self._task_tokens.get(task_id, 0)
        remaining_task = max(self.per_task_tokens - task_used, 0)
        remaining_session = max(self.per_session_tokens - self._session_tokens, 0)
        if requested_tokens > remaining_task:
            return BudgetDecision(
                allowed=False,
                requested_tokens=requested_tokens,
                remaining_task_tokens=remaining_task,
                remaining_session_tokens=remaining_session,
                estimated_usd=estimated_usd,
                reason="per-task token budget exceeded",
            )
        if requested_tokens > remaining_session:
            return BudgetDecision(
                allowed=False,
                requested_tokens=requested_tokens,
                remaining_task_tokens=remaining_task,
                remaining_session_tokens=remaining_session,
                estimated_usd=estimated_usd,
                reason="per-session token budget exceeded",
            )
        if self.usd_budget_per_task is not None and estimated_usd is not None:
            if estimated_usd > self.usd_budget_per_task:
                return BudgetDecision(
                    allowed=False,
                    requested_tokens=requested_tokens,
                    remaining_task_tokens=remaining_task,
                    remaining_session_tokens=remaining_session,
                    estimated_usd=estimated_usd,
                    reason="per-task USD budget exceeded",
                )

        self._task_tokens[task_id] = task_used + requested_tokens
        self._session_tokens += requested_tokens
        if reservation_id:
            self._reservations[reservation_id] = _Reservation(task_id=task_id, tokens=requested_tokens)
        return BudgetDecision(
            allowed=True,
            requested_tokens=requested_tokens,
            remaining_task_tokens=max(remaining_task - requested_tokens, 0),
            remaining_session_tokens=max(remaining_session - requested_tokens, 0),
            estimated_usd=estimated_usd,
            reason="reserved",
        )

    def reserve_request(
        self,
        request: LlmRequest,
        *,
        task_id: str = "default",
        estimate: LlmCostEstimate | None = None,
    ) -> BudgetDecision:
        prompt_tokens = estimate_prompt_tokens(request.request_body)
        requested = prompt_tokens + request.max_tokens
        decision = self.reserve(
            task_id=task_id,
            requested_tokens=requested,
            estimated_usd=estimate.estimated_usd if estimate else None,
            reservation_id=request.request_hash,
        )
        if not decision.allowed:
            raise BudgetDeniedError(decision.reason)
        return decision

    def record_usage(self, usage: LlmTokenUsage, *, task_id: str = "default", reservation_id: str | None = None) -> None:
        actual = usage.total_tokens
        if reservation_id and reservation_id in self._reservations:
            reservation = self._reservations.pop(reservation_id)
            delta = actual - reservation.tokens
            self._task_tokens[reservation.task_id] = max(self._task_tokens.get(reservation.task_id, 0) + delta, 0)
            self._session_tokens = max(self._session_tokens + delta, 0)
            return
        self._task_tokens[task_id] = self._task_tokens.get(task_id, 0) + actual
        self._session_tokens += actual

    @property
    def session_tokens_used(self) -> int:
        return self._session_tokens


def estimate_prompt_tokens(value: Any) -> int:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return max(1, len(text) // 4) if text else 0


def usage_from_response(response: Mapping[str, Any]) -> LlmTokenUsage | None:
    raw = response.get("usage") or response.get("token_usage")
    if not isinstance(raw, Mapping):
        return None
    input_tokens = _int_first(raw, "input_tokens", "prompt_tokens", "input")
    output_tokens = _int_first(raw, "output_tokens", "completion_tokens", "output")
    cached_input_tokens = _cached_tokens(raw)
    total_tokens = _int_first(raw, "total_tokens", "total")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    return LlmTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        total_tokens=total_tokens,
    )


def estimate_cost(
    *,
    provider_settings: LlmProviderSettings,
    usage: LlmTokenUsage,
) -> LlmCostEstimate:
    notes: list[str] = []
    estimated_usd: float | None = None
    input_rate = provider_settings.input_usd_per_million_tokens
    output_rate = provider_settings.output_usd_per_million_tokens
    cached_rate = provider_settings.cached_input_usd_per_million_tokens
    if input_rate is None or output_rate is None:
        notes.append("Provider rates missing; estimated_usd is null.")
    else:
        billable_input = max(usage.input_tokens - usage.cached_input_tokens, 0)
        cached_cost = 0.0
        if usage.cached_input_tokens:
            if cached_rate is None:
                notes.append("Cached input tokens used standard input rate because cached rate is missing.")
                cached_rate = input_rate
            cached_cost = usage.cached_input_tokens * cached_rate / 1_000_000
        estimated_usd = (billable_input * input_rate + usage.output_tokens * output_rate) / 1_000_000
        estimated_usd += cached_cost
    return LlmCostEstimate(
        provider=provider_settings.provider,
        model=provider_settings.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        total_tokens=usage.total_tokens,
        estimated_usd=estimated_usd,
        notes=notes,
    )


def attach_cost_metadata(response: dict[str, Any], *, provider_settings: LlmProviderSettings) -> dict[str, Any]:
    usage = usage_from_response(response)
    if usage is None:
        response.setdefault("warnings", []).append("Provider usage missing; token cost estimate unavailable.")
        return response
    estimate = estimate_cost(provider_settings=provider_settings, usage=usage)
    response["token_cost"] = usage.total_tokens
    response["cost"] = estimate.model_dump(mode="json")
    return response


def _int_first(mapping: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return int(value)
    return 0


def _cached_tokens(mapping: Mapping[str, Any]) -> int:
    direct = _int_first(mapping, "cached_input_tokens", "cached_tokens", "cache_read_input_tokens")
    if direct:
        return direct
    details = mapping.get("input_token_details") or mapping.get("prompt_tokens_details")
    if isinstance(details, Mapping):
        return _int_first(details, "cached_tokens", "cache_read_input_tokens")
    return 0


__all__ = [
    "BudgetDecision",
    "BudgetDeniedError",
    "BudgetGuard",
    "attach_cost_metadata",
    "estimate_cost",
    "estimate_prompt_tokens",
    "usage_from_response",
]
