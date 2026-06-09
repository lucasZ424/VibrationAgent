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
from vibration_agent.llm.anthropic_client import AnthropicClient  # noqa: E402
from vibration_agent.llm.budget import BudgetGuard  # noqa: E402
from vibration_agent.llm.replay import RecordingClient, request_from_kwargs  # noqa: E402


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    return data


def _manual_checks(settings: Any) -> None:
    if not settings.llm.live_enabled:
        raise RuntimeError("Set LLM_LIVE_ENABLED=true or configs/llm.yaml live_enabled: true for manual capture.")
    if not settings.llm.capture_enabled:
        raise RuntimeError("Set LLM_CAPTURE_ENABLED=true or configs/llm.yaml capture_enabled: true for manual capture.")
    api_key_env = settings.llm.anthropic.api_key_env
    if not os.getenv(api_key_env):
        raise RuntimeError(f"Set {api_key_env} in the environment before running Anthropic capture.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture one manual Anthropic supervisor replay fixture.")
    parser.add_argument("task", choices=["supervisor_review", "supervisor_correction"])
    parser.add_argument("--request-json", type=Path, required=True, help="JSON kwargs for the selected task.")
    parser.add_argument("--fixture-dir", type=Path, default=ROOT / "tests" / "fixtures" / "llm")
    args = parser.parse_args(argv)

    settings = load(ROOT)
    _manual_checks(settings)
    kwargs = _load_json(args.request_json)
    kwargs.setdefault("model", f"{settings.llm.anthropic.provider}:{settings.llm.anthropic.model}")

    schema_version = "supervisor.v1" if args.task == "supervisor_review" else "correction.v1"
    request = request_from_kwargs(task=args.task, schema_version=schema_version, kwargs=kwargs)
    budget = BudgetGuard(
        per_task_tokens=settings.llm.token_budget_per_task,
        per_session_tokens=settings.llm.token_budget_per_session,
        usd_budget_per_task=settings.llm.usd_budget_per_task,
    )
    live = AnthropicClient(settings.llm.anthropic, allow_live=True, budget_guard=budget)
    recorder = RecordingClient(
        client=live,
        fixture_dir=args.fixture_dir,
        capture_enabled=settings.llm.capture_enabled,
        manual_lane=True,
    )
    response = recorder.complete(request)
    print(json.dumps({"request_hash": request.request_hash, "response_keys": sorted(response)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
