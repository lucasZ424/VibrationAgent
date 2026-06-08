from __future__ import annotations

import sys

import pytest

from vibration_agent.config import load
from vibration_agent.llm.budget import (
    BudgetDeniedError,
    BudgetGuard,
    attach_cost_metadata,
    estimate_cost,
    usage_from_response,
)
from vibration_agent.llm.openai_client import OpenAIClient
from vibration_agent.llm.replay import LlmRequest
from vibration_agent.schemas import LlmTokenUsage
from vibration_agent.storage import qa_logs
from vibration_agent.schemas import SkillOutput


def _request(*, max_tokens: int = 100) -> LlmRequest:
    return LlmRequest(
        provider="openai",
        model="gpt-5.5",
        prompt_version="s3.v1",
        schema_version="s3.schema.v1",
        request_body={"task_id": "t1", "prompt": "Explain damping ratio."},
        max_tokens=max_tokens,
    )


def test_budget_guard_denies_before_over_budget_call():
    guard = BudgetGuard(per_task_tokens=50, per_session_tokens=100)

    with pytest.raises(BudgetDeniedError, match="per-task"):
        guard.reserve_request(_request(max_tokens=100), task_id="t1")

    assert guard.session_tokens_used == 0


def test_budget_guard_adjusts_reservation_to_actual_usage():
    guard = BudgetGuard(per_task_tokens=4000, per_session_tokens=30000)
    request = _request(max_tokens=100)

    decision = guard.reserve_request(request, task_id="t1")
    guard.record_usage(LlmTokenUsage(input_tokens=10, output_tokens=20, total_tokens=30), reservation_id=request.request_hash)

    assert decision.allowed is True
    assert guard.session_tokens_used == 30


def test_usage_parser_handles_provider_shapes():
    usage = usage_from_response(
        {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "input_token_details": {"cached_tokens": 20},
            }
        }
    )

    assert usage is not None
    assert usage.input_tokens == 100
    assert usage.output_tokens == 50
    assert usage.cached_input_tokens == 20
    assert usage.total_tokens == 150


def test_cost_estimate_uses_local_provider_rates():
    settings = load().llm.openai
    estimate = estimate_cost(
        provider_settings=settings,
        usage=LlmTokenUsage(input_tokens=1000, output_tokens=100, cached_input_tokens=100, total_tokens=1100),
    )

    assert estimate.provider == "openai"
    assert estimate.model == "gpt-5.5"
    assert estimate.total_tokens == 1100
    assert estimate.estimated_usd is not None
    assert estimate.estimated_usd > 0


def test_attach_cost_metadata_keeps_warning_when_usage_missing():
    response = attach_cost_metadata({"answer": "ok"}, provider_settings=load().llm.openai)

    assert response["warnings"] == ["Provider usage missing; token cost estimate unavailable."]
    assert "token_cost" not in response
    assert "cost" not in response


def test_attach_cost_metadata_sets_token_cost_and_cost():
    response = attach_cost_metadata(
        {"answer": "ok", "usage": {"input_tokens": 10, "output_tokens": 5}},
        provider_settings=load().llm.openai,
    )

    assert response["token_cost"] == 15
    assert response["cost"]["total_tokens"] == 15
    assert response["cost"]["estimated_usd"] is not None


def test_config_env_overrides_budget(monkeypatch):
    monkeypatch.setenv("LLM_TOKEN_BUDGET_PER_TASK", "123")
    monkeypatch.setenv("LLM_TOKEN_BUDGET_PER_SESSION", "456")
    monkeypatch.setenv("LLM_USD_BUDGET_PER_TASK", "0.01")

    settings = load().llm

    assert settings.token_budget_per_task == 123
    assert settings.token_budget_per_session == 456
    assert settings.usd_budget_per_task == 0.01


def test_qa_log_row_records_token_cost_when_supplied():
    row = qa_logs.build_qa_log_row(SkillOutput(status="ok"), query="q", token_cost=42)

    assert row["token_cost"] == 42


def test_openai_budget_denial_happens_before_sdk_import(monkeypatch):
    sys.modules.pop("openai", None)
    monkeypatch.setenv("VIBRATION_AGENT_ALLOW_LIVE_LLM_IN_TESTS", "1")
    settings = load().llm.openai
    guard = BudgetGuard(per_task_tokens=10, per_session_tokens=10)
    client = OpenAIClient(settings, allow_live=True, budget_guard=guard)

    with pytest.raises(BudgetDeniedError):
        client.complete(_request(max_tokens=100))

    assert "openai" not in sys.modules
