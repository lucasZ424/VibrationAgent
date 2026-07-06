"""Manual Phase-3 LLM capture helper.

This script is intentionally outside CI. It constructs a live provider client
only when the operator explicitly enables the manual lane through config/env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import load  # noqa: E402
from vibration_agent.agent.supervisor import ReviewReport, SupervisorCorrectionResponse  # noqa: E402
from vibration_agent.llm.anthropic_client import AnthropicClient  # noqa: E402
from vibration_agent.llm.budget import BudgetGuard  # noqa: E402
from vibration_agent.llm.openai_client import OpenAIClient  # noqa: E402
from vibration_agent.llm.replay import request_from_kwargs, write_fixture  # noqa: E402
from vibration_agent.schemas import S3LlmResponse, S4LlmResponse, S5LlmResponse  # noqa: E402

_OPENAI_TASKS = {
    "s3_qa_summary": "s3.v1",
    "s4_engineering_analysis": "s4.v1",
    "s5_formula_derivation": "s5.v1",
}
_ANTHROPIC_TASKS = {
    "supervisor_review": "supervisor.v1",
    "supervisor_correction": "correction.v1",
}


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    return data


def _manual_checks(settings: Any, *, provider_name: str) -> None:
    if not settings.llm.live_enabled:
        raise RuntimeError("Set LLM_LIVE_ENABLED=true or configs/llm.yaml live_enabled: true for manual capture.")
    if not settings.llm.capture_enabled:
        raise RuntimeError("Set LLM_CAPTURE_ENABLED=true or configs/llm.yaml capture_enabled: true for manual capture.")
    provider = settings.llm.openai if provider_name == "openai" else settings.llm.anthropic
    if not os.getenv(provider.api_key_env):
        raise RuntimeError(f"Set {provider.api_key_env} in the environment before running {provider_name} capture.")


def _task_provider(task: str) -> str:
    if task in _OPENAI_TASKS:
        return "openai"
    if task in _ANTHROPIC_TASKS:
        return "anthropic"
    raise ValueError(f"Unsupported capture task: {task}")


def _schema_version(task: str) -> str:
    return {**_OPENAI_TASKS, **_ANTHROPIC_TASKS}[task]


def _default_model(settings: Any, provider_name: str) -> str:
    provider = settings.llm.openai if provider_name == "openai" else settings.llm.anthropic
    return f"{provider.provider}:{provider.model}"


def _live_client(settings: Any, *, provider_name: str, budget: BudgetGuard) -> Any:
    if provider_name == "openai":
        return OpenAIClient(settings.llm.openai, allow_live=True, budget_guard=budget)
    return AnthropicClient(settings.llm.anthropic, allow_live=True, budget_guard=budget)


def _validate_response(task: str, response: dict[str, Any]) -> None:
    if response.get("status") == "incomplete":
        details = response.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else "unknown"
        raise RuntimeError(f"{task} provider response incomplete: {reason}")
    schema = {
        "s3_qa_summary": S3LlmResponse,
        "s4_engineering_analysis": S4LlmResponse,
        "s5_formula_derivation": S5LlmResponse,
        "supervisor_review": ReviewReport,
        "supervisor_correction": SupervisorCorrectionResponse,
    }[task]
    schema.model_validate(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture one manual Phase-3 replay fixture.")
    parser.add_argument("task", choices=[*_OPENAI_TASKS.keys(), *_ANTHROPIC_TASKS.keys()])
    parser.add_argument("--request-json", type=Path, required=True, help="JSON kwargs for the selected task.")
    parser.add_argument("--fixture-dir", type=Path, default=ROOT / "tests" / "fixtures" / "llm")
    args = parser.parse_args(argv)

    settings = load(ROOT)
    provider_name = _task_provider(args.task)
    _manual_checks(settings, provider_name=provider_name)
    kwargs = _load_json(args.request_json)
    kwargs.setdefault("model", _default_model(settings, provider_name))

    request = request_from_kwargs(task=args.task, schema_version=_schema_version(args.task), kwargs=kwargs)
    budget = BudgetGuard(
        per_task_tokens=settings.llm.token_budget_per_task,
        per_session_tokens=settings.llm.token_budget_per_session,
        usd_budget_per_task=settings.llm.usd_budget_per_task,
    )
    live = _live_client(settings, provider_name=provider_name, budget=budget)
    response = live.complete(request)
    _validate_response(args.task, response)
    write_fixture(args.fixture_dir, request, response)
    print(
        json.dumps(
            {
                "provider": provider_name,
                "task": args.task,
                "request_hash": request.request_hash,
                "response_keys": sorted(response),
                "token_cost": response.get("token_cost"),
                "cost": response.get("cost"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
