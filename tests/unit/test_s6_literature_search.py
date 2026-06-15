from __future__ import annotations

import sys
from pathlib import Path

import pytest

from vibration_agent.agent import AgentSkillRegistry
from vibration_agent.schemas import PHASE0_DEFERRED_SKILLS, SkillInput


FIXTURES = Path("tests/fixtures/literature")


@pytest.fixture(autouse=True)
def _unload_s6_module_after_test():
    yield
    sys.modules.pop("vibration_agent.skills.s6_literature_search", None)


def _skill():
    from vibration_agent.skills import LiteratureSearchSkill

    return LiteratureSearchSkill()


def _payload(**constraints) -> SkillInput:
    return SkillInput(
        task_id="s6-test",
        user_query="rotor critical speed damping",
        constraints=constraints,
        user_mode="research",
    )


def test_s6_is_default_off_without_replay_fixture_or_manual_gate():
    output = _skill().run(_payload())

    assert output.status == "insufficient"
    assert output.structured_result["source_mode"] == "disabled"
    assert output.structured_result["routing"]["default_chain"] is False
    assert "s6_literature_search" in PHASE0_DEFERRED_SKILLS


def test_agent_skill_registry_loads_s6_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("s6_literature_search")

    assert skill.path.name == "SKILL.md"
    assert "LiteratureSearchSkill" in skill.body


def test_s6_returns_structured_candidates_from_semantic_scholar_replay_fixture():
    output = _skill().run(
        _payload(literature_fixture=str(FIXTURES / "semantic_scholar_replay.json"), max_candidates=1)
    )

    candidate = output.structured_result["candidates"][0]
    assert output.status == "ok"
    assert output.structured_result["schema_version"] == "s6.literature_search.v1"
    assert output.structured_result["source_mode"] == "replay"
    assert candidate["title"] == "Damping Effects on Rotor Critical Speed Passage"
    assert candidate["authors"] == ["A. Engineer", "B. Researcher"]
    assert candidate["year"] == 2022
    assert candidate["doi"] == "10.1234/rotor.2022.001"
    assert candidate["retrieval_source"] == "semantic_scholar"
    assert candidate["evidence_anchors"][0]["anchor_id"].endswith("#abstract")
    assert output.structured_result["routing"]["default_chain"] is False


def test_s6_returns_structured_candidates_from_arxiv_replay_fixture():
    output = _skill().run(
        _payload(literature_fixture=str(FIXTURES / "arxiv_replay.json"), literature_source="arxiv")
    )

    candidate = output.structured_result["candidates"][0]
    assert output.status == "ok"
    assert candidate["arxiv_id"] == "2401.01234"
    assert candidate["retrieval_source"] == "arxiv"


def test_s6_manual_live_gate_falls_back_without_injected_client():
    output = _skill().run(_payload(s6_enabled=True, s6_live_enabled=True))

    assert output.status == "insufficient"
    assert output.structured_result["source_mode"] == "fallback"
    assert "no manual live client" in output.warnings[0]


def test_s6_manual_live_uses_injected_client_and_redacts_response():
    class Client:
        def search_semantic_scholar(self, **kwargs):
            return {
                "candidates": [
                    {
                        "paper_id": "live-1",
                        "title": "Live Replay",
                        "authors": ["A"],
                        "year": 2026,
                        "venue": "Manual",
                        "url": "https://example.org/live",
                        "abstract": "api_key=SECRET123456789 C:\\Users\\local\\paper.txt " + ("x" * 1300),
                    }
                ]
            }

    from vibration_agent.skills import LiteratureSearchSkill

    output = LiteratureSearchSkill(live_client=Client()).run(
        _payload(s6_enabled=True, s6_live_enabled=True, literature_source="semantic_scholar")
    )

    abstract = output.structured_result["candidates"][0]["abstract"]
    assert output.status == "ok"
    assert output.structured_result["source_mode"] == "manual_live"
    assert "SECRET123456789" not in abstract
    assert "[REDACTED_LOCAL_PATH]" in abstract
    assert abstract.endswith("...[TRUNCATED]")


def test_s6_redaction_covers_bearer_tokens_local_paths_and_long_text():
    from vibration_agent.skills.s6_literature_search import redact_capture

    raw = {
        "headers": {"Authorization": "Bearer abcdefghijklmnop"},
        "path": "/home/me/private/capture.json",
        "text": "y" * 1300,
    }

    redacted = redact_capture(raw)

    assert "abcdefghijklmnop" not in redacted["headers"]["Authorization"]
    assert redacted["path"] == "[REDACTED_LOCAL_PATH]"
    assert redacted["text"].endswith("...[TRUNCATED]")
