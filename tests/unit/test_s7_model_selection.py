from __future__ import annotations

import sys

import pytest

from vibration_agent.agent import AgentSkillRegistry
from vibration_agent.schemas import PHASE0_DEFERRED_SKILLS, SkillInput


@pytest.fixture(autouse=True)
def _unload_s7_module_after_test():
    yield
    sys.modules.pop("vibration_agent.skills.s7_model_selection", None)


def _skill():
    from vibration_agent.skills import ModelSelectionSkill

    return ModelSelectionSkill()


def _row(chunk_id: str, text: str, *, topic: str = "") -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc1",
        "pages": [1],
        "topic": topic,
        "text": text,
    }


def _payload(*, rows: list[dict] | None = None, **constraints) -> SkillInput:
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
        task_id="s7-test",
        user_query="Which analysis model should I use for rotor critical speed?",
        context=context,
        constraints=constraints,
        user_mode="engineering",
    )


def test_s7_is_default_off_and_stays_deferred():
    output = _skill().run(_payload(rows=[_row("c1", "Critical speed and damping affect runup response.")]))

    assert output.status == "insufficient"
    assert output.structured_result["mode"] == "disabled"
    assert output.structured_result["routing"]["default_chain"] is False
    assert "s7_model_selection" in PHASE0_DEFERRED_SKILLS


def test_agent_skill_registry_loads_s7_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("s7_model_selection")

    assert skill.path.name == "SKILL.md"
    assert "ModelSelectionSkill" in skill.body


def test_s7_recommends_model_family_from_visible_evidence():
    output = _skill().run(
        _payload(
            rows=[_row("c1", "Critical speed and damping affect rotor runup response.", topic="critical_speed")],
            s7_enabled=True,
        )
    )

    recommendation = output.structured_result["recommendations"][0]
    assert output.status == "ok"
    assert output.structured_result["schema_version"] == "s7.model_selection.v1"
    assert recommendation["model_family"] == "critical_speed_runup_response"
    assert recommendation["evidence_refs"][0]["chunk_id"] == "c1"
    assert recommendation["assumptions"]
    assert recommendation["limitations"]
    assert output.citations[0].chunk_id == "c1"
    assert output.structured_result["routing"]["default_chain"] is False


def test_s7_can_recommend_multiple_model_families_from_visible_evidence():
    output = _skill().run(
        _payload(
            rows=[
                _row("c1", "Rotor unbalance produces synchronous 1X vibration response."),
                _row("c2", "Bearing fault diagnosis often uses envelope analysis."),
            ],
            s7_enabled=True,
        )
    )

    families = {item["model_family"] for item in output.structured_result["recommendations"]}
    assert "rotor_unbalance_synchronous_response" in families
    assert "bearing_fault_envelope_analysis" in families


def test_s7_returns_limitation_when_enabled_without_visible_evidence():
    output = _skill().run(_payload(s7_enabled=True))

    assert output.status == "insufficient"
    assert "requires visible S2 evidence" in output.structured_result["limitations"][0]
    assert output.structured_result["recommendations"] == []


def test_s7_does_not_recommend_from_query_world_knowledge_without_evidence_match():
    output = _skill().run(
        _payload(rows=[_row("c1", "This row discusses unrelated thermal treatment only.")], s7_enabled=True)
    )

    assert output.status == "insufficient"
    assert output.structured_result["recommendations"] == []
    assert "world knowledge" in output.structured_result["limitations"][1]


def test_importing_active_skill_package_does_not_load_s7_module():
    import vibration_agent.skills  # noqa: F401

    assert "vibration_agent.skills.s7_model_selection" not in sys.modules
