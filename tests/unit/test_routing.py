from pathlib import Path

from vibration_agent.agent import RoutingPolicy, route_advisory_skills
from vibration_agent.config import RoutingSettings, load


def test_advisory_routing_is_disabled_by_default_even_when_query_has_intent():
    decision = route_advisory_skills(
        "Find papers, choose a model, and plan a measurement test.",
        user_mode="research",
    )

    assert decision.enabled is False
    assert decision.selected_skills == ()
    assert decision.reason == "advisory routing disabled"


def test_advisory_routing_uses_explicit_skill_list_only_after_gate():
    decision = route_advisory_skills(
        "critical speed",
        constraints={"advisory_routing_enabled": True, "advisory_skills": ["s8", "s6"]},
    )

    assert decision.enabled is True
    assert decision.selected_skills == ("s6_literature_search", "s8_experiment_advice")
    assert decision.reason == "explicit advisory skill list"
    assert decision.rendering == "structured_handoff_only"
    assert decision.v2_v4_policy == "do_not_render_as_final_answer"


def test_advisory_routing_can_infer_skills_when_policy_allows_intent_routing():
    policy = RoutingPolicy(advisory_routing_enabled=True, advisory_intent_routing_enabled=True)

    decision = route_advisory_skills(
        "Find literature, select a model, and plan sensor measurements.",
        user_mode="engineering",
        policy=policy,
    )

    assert decision.selected_skills == (
        "s6_literature_search",
        "s7_model_selection",
        "s8_experiment_advice",
    )
    assert decision.reason == "deterministic intent routing"


def test_advisory_routing_respects_configured_allowed_skills_for_intent_path():
    policy = RoutingPolicy(
        advisory_routing_enabled=True,
        advisory_intent_routing_enabled=True,
        advisory_allowed_skills=("s7_model_selection",),
    )

    decision = route_advisory_skills(
        "Find literature, select a model, and plan sensor measurements.",
        user_mode="research",
        policy=policy,
    )

    assert decision.selected_skills == ("s7_model_selection",)
    assert "restricted by configured advisory_allowed_skills" in decision.reasons


def test_settings_keep_advisory_routing_off_by_default():
    settings = load(Path.cwd())

    assert settings.routing.advisory_routing_enabled is False
    assert settings.routing.advisory_intent_routing_enabled is False
    assert settings.routing.advisory_allowed_skills == []


def test_routing_policy_reads_advisory_settings():
    settings = load(Path.cwd()).model_copy(
        update={
            "routing": RoutingSettings(
                advisory_routing_enabled=True,
                advisory_intent_routing_enabled=True,
                advisory_allowed_skills=["s7", "s8"],
            )
        }
    )

    policy = RoutingPolicy.from_settings(settings)

    assert policy.advisory_routing_enabled is True
    assert policy.advisory_intent_routing_enabled is True
    assert policy.advisory_allowed_skills == ("s7_model_selection", "s8_experiment_advice")
