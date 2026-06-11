from __future__ import annotations

import pytest

from vibration_agent.config import load

import scripts.llm_capture as llm_capture
import scripts.manual_e2e as manual_e2e
from vibration_agent.schemas import SkillOutput


def test_llm_capture_maps_phase3_tasks_to_manual_providers():
    # WHY: Obj9 permits live calls only through explicit manual commands. The
    # task name must deterministically select the intended provider lane.
    assert llm_capture._task_provider("s3_qa_summary") == "openai"
    assert llm_capture._task_provider("s4_engineering_analysis") == "openai"
    assert llm_capture._task_provider("s5_formula_derivation") == "openai"
    assert llm_capture._task_provider("supervisor_review") == "anthropic"
    assert llm_capture._schema_version("supervisor_correction") == "correction.v1"


def test_llm_capture_requires_live_capture_and_provider_key(monkeypatch):
    # WHY: Missing manual gates or keys must fail before constructing a live
    # provider client or attempting a network call.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VIBRATION_AGENT_DISABLE_DOTENV", "1")
    monkeypatch.setenv("LLM_LIVE_ENABLED", "true")
    monkeypatch.setenv("LLM_CAPTURE_ENABLED", "true")
    settings = load()

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm_capture._manual_checks(settings, provider_name="openai")


def test_manual_e2e_default_path_does_not_require_api_key(monkeypatch, capsys):
    # WHY: The manual probe must remain runnable as a deterministic smoke check;
    # live validation is opt-in only.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("LLM_CAPTURE_ENABLED", raising=False)
    monkeypatch.setenv("VIBRATION_AGENT_DISABLE_DOTENV", "1")

    exit_code = manual_e2e.main(["--difficulty", "low"])
    captured = capsys.readouterr()

    assert exit_code in {0, 2}
    assert '"status"' in captured.out
    assert "OPENAI_API_KEY" not in captured.out


def test_manual_e2e_live_openai_requires_manual_gates(monkeypatch):
    # WHY: A live flag without explicit config should stop immediately, rather
    # than silently falling back and pretending the live lane was validated.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("LLM_CAPTURE_ENABLED", raising=False)
    monkeypatch.setenv("VIBRATION_AGENT_DISABLE_DOTENV", "1")

    with pytest.raises(RuntimeError, match="LLM_LIVE_ENABLED"):
        manual_e2e.main(["--live-openai"])


def test_manual_summary_counts_only_model_skill_costs():
    # WHY: V2 may pass through S4's token/cost metadata. Manual validation
    # should not double-count that as another live model call.
    output = SkillOutput(
        status="ok",
        structured_result={
            "scope": "in_scope",
            "chain": [],
            "skill_results": {
                "s3": {
                    "token_cost": 10,
                    "cost": {"estimated_usd": 0.1, "source": "local_estimate"},
                },
                "s4": {
                    "token_cost": 20,
                    "cost": {"estimated_usd": 0.2, "source": "local_estimate"},
                },
                "s5": {
                    "token_cost": None,
                    "cost": {"estimated_usd": 0.3, "source": "stale_upstream_cost"},
                },
                "v2": {
                    "token_cost": 20,
                    "cost": {"estimated_usd": 0.2, "source": "local_estimate"},
                },
            },
        },
    )

    summary = manual_e2e._summary(output)

    assert summary["token_cost"] == 30
    assert summary["cost"]["estimated_usd"] == pytest.approx(0.3)
    assert summary["skill_token_costs"] == {"s3": 10, "s4": 20}
    assert set(summary["skill_costs"]) == {"s3", "s4"}
