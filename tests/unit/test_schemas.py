"""Smoke test — keeps the I/O contract honest."""
from vibration_agent.schemas import Citation, SkillInput, SkillOutput


def test_skill_input_defaults():
    payload = SkillInput(task_id="t1", user_query="what is damping ratio?")
    assert payload.user_mode == "engineering"


def test_skill_output_roundtrip():
    out = SkillOutput(
        status="ok",
        summary="damping ratio ≈ 0.05",
        citations=[Citation(chunk_id="c1", doc_id="d1")],
    )
    assert out.model_dump()["citations"][0]["evidence_type"] == "documented"
