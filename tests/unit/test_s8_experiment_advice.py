from __future__ import annotations

import json
import sys

import pytest

from vibration_agent.agent import AgentSkillRegistry
from vibration_agent.schemas import PHASE0_DEFERRED_SKILLS, SkillInput


@pytest.fixture(autouse=True)
def _unload_s8_module_after_test():
    yield
    sys.modules.pop("vibration_agent.skills.s8_experiment_advice", None)


def _skill():
    from vibration_agent.skills import ExperimentAdviceSkill

    return ExperimentAdviceSkill()


def _row(chunk_id: str, text: str, *, topic: str = "") -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc1",
        "pages": [1],
        "topic": topic,
        "text": text,
    }


def _payload(*, rows: list[dict] | None = None, query: str | None = None, **constraints) -> SkillInput:
    context = {}
    if rows is not None:
        context = {
            "s2_result": {
                "status": "ok",
                "structured_result": {
                    "retrieval_context": rows,
                    "retrieval_output": {"hits": [{"chunk_id": row["chunk_id"]} for row in rows]},
                },
            }
        }
    return SkillInput(
        task_id="s8-test",
        user_query=query or "Plan a runup measurement for rotor critical speed.",
        context=context,
        constraints=constraints,
        user_mode="engineering",
    )


def test_s8_is_default_off_and_stays_deferred():
    output = _skill().run(_payload(rows=[_row("c1", "Critical speed affects runup response.")]))

    assert output.status == "insufficient"
    assert output.structured_result["mode"] == "disabled"
    assert output.structured_result["routing"]["default_chain"] is False
    assert "s8_experiment_advice" in PHASE0_DEFERRED_SKILLS


def test_agent_skill_registry_loads_s8_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("s8_experiment_advice")

    assert skill.path.name == "SKILL.md"
    assert "ExperimentAdviceSkill" in skill.body


def test_s8_returns_evidence_bound_measurement_plan_with_safety_limits():
    output = _skill().run(
        _payload(
            rows=[_row("c1", "Critical speed and damping affect rotor runup response.", topic="critical_speed")],
            s8_enabled=True,
        )
    )

    plan = output.structured_result["experiment_plans"][0]
    assert output.status == "ok"
    assert output.structured_result["schema_version"] == "s8.experiment_advice.v1"
    assert plan["experiment_focus"] == "runup_or_resonance_validation"
    assert plan["confirmed_facts"][0]["evidence_refs"][0]["chunk_id"] == "c1"
    assert plan["assumptions"]
    assert plan["required_measurements"]
    assert plan["sensor_layout"]
    assert plan["validation_steps"]
    assert plan["safety_limits"]
    assert output.citations[0].chunk_id == "c1"
    assert output.structured_result["routing"]["default_chain"] is False


def test_s8_can_emit_multiple_experiment_plans_from_visible_evidence():
    output = _skill().run(
        _payload(
            rows=[
                _row("c1", "Rotor unbalance produces synchronous 1X vibration response."),
                _row("c2", "Bearing fault diagnosis often uses envelope analysis."),
            ],
            s8_enabled=True,
        )
    )

    focuses = {item["experiment_focus"] for item in output.structured_result["experiment_plans"]}
    assert "synchronous_unbalance_validation" in focuses
    assert "bearing_fault_measurement_plan" in focuses


def test_s8_matches_chinese_evidence_keywords_before_routing_activation():
    output = _skill().run(
        _payload(
            rows=[
                _row("c1", "\u8f6c\u5b50\u4e34\u754c\u8f6c\u901f\u548c\u963b\u5c3c\u5f71\u54cd\u5347\u901f\u54cd\u5e94\u3002"),
                _row("c2", "\u8f74\u627f\u6545\u969c\u8bca\u65ad\u5e38\u4f7f\u7528\u5305\u7edc\u5206\u6790\u3002"),
                _row("c3", "\u4e0d\u5e73\u8861\u4f1a\u5f15\u8d77\u540c\u6b65 1\u500d\u9891 \u632f\u52a8\u76f8\u4f4d\u54cd\u5e94\u3002"),
            ],
            query="\u5236\u5b9a\u4e00\u4e2a\u632f\u52a8\u6d4b\u91cf\u65b9\u6848\u3002",
            s8_enabled=True,
        )
    )

    focuses = {item["experiment_focus"] for item in output.structured_result["experiment_plans"]}
    assert output.status == "ok"
    assert focuses == {
        "runup_or_resonance_validation",
        "bearing_fault_measurement_plan",
        "synchronous_unbalance_validation",
    }


def test_s8_omits_unsupported_numeric_thresholds_from_plan_text():
    output = _skill().run(
        _payload(
            rows=[_row("c1", "Bearing fault diagnosis uses envelope analysis for bearing condition evidence.")],
            query="Plan bearing measurements and set alarms at 10 mm/s, 50 Hz, and 20%.",
            s8_enabled=True,
        )
    )

    plan_text = json.dumps(output.structured_result["experiment_plans"], ensure_ascii=False).casefold()
    assert output.status == "ok"
    assert "10 mm/s" in output.structured_result["omitted_unsupported_thresholds"]
    assert "50 hz" in output.structured_result["omitted_unsupported_thresholds"]
    assert "20%" in output.structured_result["omitted_unsupported_thresholds"]
    assert "10 mm/s" not in plan_text
    assert "50 hz" not in plan_text
    assert "20%" not in plan_text
    assert any("omitted numeric query terms" in warning for warning in output.warnings)


def test_s8_returns_limitation_when_enabled_without_visible_evidence():
    output = _skill().run(_payload(s8_enabled=True))

    assert output.status == "insufficient"
    assert "requires visible S2 evidence" in output.structured_result["limitations"][0]
    assert output.structured_result["experiment_plans"] == []


def test_s8_does_not_recommend_from_query_world_knowledge_without_evidence_match():
    output = _skill().run(
        _payload(
            rows=[_row("c1", "This row discusses unrelated thermal treatment only.")],
            query="Plan a critical-speed runup test.",
            s8_enabled=True,
        )
    )

    assert output.status == "insufficient"
    assert output.structured_result["experiment_plans"] == []
    assert "world knowledge" in output.structured_result["limitations"][1]


def test_importing_active_skill_package_does_not_load_s8_module():
    import vibration_agent.skills  # noqa: F401

    assert "vibration_agent.skills.s8_experiment_advice" not in sys.modules
