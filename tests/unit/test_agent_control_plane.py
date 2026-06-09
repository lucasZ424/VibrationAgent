from pathlib import Path

import pytest

from vibration_agent.agent import (
    AgentSkillRegistry,
    Difficulty,
    ModelRegistry,
    ReviewIssue,
    ReviewReport,
    RoutingPolicy,
    SupervisorAction,
    clear_default_model_registry_cache,
    clear_default_routing_policy_cache,
    default_model_registry,
    default_routing_policy,
    next_supervisor_action,
    route_task,
)
from vibration_agent.config import LlmSettings, RoutingSettings, load
from vibration_agent.skills.s1_ingestion import IngestionSkill


def test_agent_skill_registry_loads_project_owned_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    assert "s1_ingestion" in registry.list_ids()
    skill = registry.get("s1_ingestion")
    assert skill.path == (Path.cwd() / "agent_skills/s1_ingestion/SKILL.md").resolve()
    assert skill.path.is_absolute()
    assert "ingest" in skill.body.lower()
    assert skill.references
    assert all(path.is_absolute() for path in skill.references)
    assert skill.scripts
    assert all(path.is_absolute() for path in skill.scripts)
    assert registry.as_prompt_catalog()[0]["skill_id"] == "s1_ingestion"
    assert IngestionSkill.__name__ == "IngestionSkill"


def test_agent_skill_registry_default_root_is_workspace_absolute():
    registry = AgentSkillRegistry.load()

    assert registry.root == (Path.cwd() / "agent_skills").resolve()
    assert registry.get("s1_ingestion").path.is_absolute()


def test_default_routing_keeps_low_medium_high_on_gpt():
    for difficulty in (Difficulty.LOW, Difficulty.MEDIUM, Difficulty.HIGH):
        decision = route_task(constraints={"difficulty": difficulty.value})

        assert decision.difficulty == difficulty
        assert decision.owner == "gpt"
        assert decision.use_opus_supervisor is False


def test_settings_can_route_high_to_opus_when_stakeholder_config_changes():
    settings = load(Path.cwd())
    custom_settings = settings.model_copy(
        update={
            "routing": settings.routing.model_copy(
                update={"opus_difficulties": ["high", "extreme"]}
            )
        }
    )

    decision = route_task(constraints={"difficulty": "high"}, settings=custom_settings)

    assert decision.difficulty == Difficulty.HIGH
    assert decision.owner == "opus_supervised_loop"
    assert decision.use_opus_supervisor is True


def test_routing_policy_can_be_built_from_settings():
    settings = load(Path.cwd()).model_copy(
        update={
            "routing": RoutingSettings(
                default_owner="gpt",
                opus_difficulties=["high", "extreme"],
                repeated_failure_threshold=3,
                explicit_extreme_markers=["critical"],
            )
        }
    )

    policy = RoutingPolicy.from_settings(settings)

    assert policy.gpt_owner == "gpt"
    assert policy.opus_difficulties == (Difficulty.HIGH, Difficulty.EXTREME)
    assert policy.repeated_failure_threshold == 3
    assert policy.explicit_extreme_markers == ("critical",)

def test_default_routing_policy_cache_returns_isolated_copy():
    clear_default_routing_policy_cache()

    first = default_routing_policy()
    second = default_routing_policy()
    first.gpt_owner = "mutated"

    assert second.gpt_owner == "gpt"
    assert default_routing_policy().gpt_owner == "gpt"


def test_extreme_routing_uses_opus_supervisor():
    decision = route_task(constraints={"difficulty": "extreme"})

    assert decision.difficulty == Difficulty.EXTREME
    assert decision.owner == "opus_supervised_loop"
    assert decision.use_opus_supervisor is True


def test_explicit_stakeholder_marker_overrides_model_recommendation():
    decision = route_task(
        constraints={"route": "opus"},
        model_recommendation="low",
    )

    assert decision.difficulty == Difficulty.EXTREME
    assert decision.model_recommendation == Difficulty.LOW
    assert decision.use_opus_supervisor is True
    assert decision.reason == "explicit stakeholder extreme marker"
    assert decision.reasons == ["default medium", "explicit stakeholder extreme marker"]


def test_repeated_failure_escalates_to_extreme_after_threshold():
    policy = RoutingPolicy(repeated_failure_threshold=2)

    still_gpt = route_task(constraints={"issues_remain": True, "correction_attempts": 1}, policy=policy)
    escalated = route_task(constraints={"issues_remain": True, "correction_attempts": 2}, policy=policy)

    assert still_gpt.use_opus_supervisor is False
    assert escalated.difficulty == Difficulty.EXTREME
    assert escalated.use_opus_supervisor is True
    assert escalated.reasons == ["default medium", "repeated correction failure threshold reached"]


def test_model_registry_defaults_are_loaded_from_settings_and_gpt_first():
    registry = default_model_registry()

    assert registry.provider_for("interaction_main") == "openai"
    assert registry.provider_for("executor") == "openai"
    assert registry.provider_for("senior_planner") == "anthropic"
    assert registry.provider_for("senior_reviewer") == "anthropic"
    assert registry.provider_for("main_answer") == "openai"
    with pytest.raises(KeyError):
        registry.get("unknown")

def test_default_model_registry_cache_returns_isolated_copy():
    clear_default_model_registry_cache()

    first = default_model_registry()
    second = default_model_registry()
    first.roles["executor"].provider = "mutated"

    assert second.provider_for("executor") == "openai"
    assert default_model_registry().provider_for("executor") == "openai"


def test_model_registry_can_be_built_from_settings():
    settings = load(Path.cwd()).model_copy(
        update={
            "llm": LlmSettings(
                providers={
                    "executor": "openai:gpt-custom",
                    "senior_reviewer": "anthropic:opus-custom",
                }
            )
        }
    )

    registry = ModelRegistry.from_settings(settings)

    assert registry.get("executor").ref == "openai:gpt-custom"
    assert registry.get("senior_reviewer").ref == "anthropic:opus-custom"


def test_model_registry_rejects_invalid_model_reference():
    settings = load(Path.cwd()).model_copy(
        update={"llm": LlmSettings(providers={"executor": "missing_provider_separator"})}
    )

    with pytest.raises(ValueError, match="provider:model"):
        ModelRegistry.from_settings(settings)

def test_model_registry_warns_on_unknown_role(caplog):
    settings = load(Path.cwd()).model_copy(
        update={"llm": LlmSettings(providers={"typo_executor": "openai:gpt-custom"})}
    )

    registry = ModelRegistry.from_settings(settings)

    assert registry.get("typo_executor").purpose == ""
    assert "Unknown model role configured: typo_executor" in caplog.text


def test_supervisor_action_loop_limit():
    approved = ReviewReport(task_id="t1", approved=True)
    issue_report = ReviewReport(task_id="t1", issues=[ReviewIssue(description="schema mismatch")])

    assert next_supervisor_action(approved, loop_count=0) == SupervisorAction.FINALIZE
    assert next_supervisor_action(issue_report, loop_count=0) == SupervisorAction.GPT_CORRECTION
    assert next_supervisor_action(issue_report, loop_count=1) == SupervisorAction.GPT_CORRECTION
    assert next_supervisor_action(issue_report, loop_count=2) == SupervisorAction.CORRECTION_LIMIT_FALLBACK


def test_config_loads_gpt_first_routing_policy():
    settings = load(Path.cwd())

    assert settings.routing.default_owner == "gpt"
    assert settings.routing.opus_difficulties == ["extreme"]
    assert settings.routing.repeated_failure_threshold == 2
    assert settings.llm.providers["interaction_main"].startswith("openai:")
    assert settings.llm.providers["senior_reviewer"].startswith("anthropic:")



