from __future__ import annotations

from vibration_agent.config import load
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills import QASummarySkill
from vibration_agent.skills.base import Skill


def _evidence(chunk_id: str = "c1", text: str = "Critical speed amplifies rotor response.") -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc1",
        "pages": [1],
        "source_type": "book",
        "topic": "rotor dynamics",
        "score": 1.0,
        "confidence": 0.9,
        "language": "en",
        "text": text,
        "assets": [],
        "metadata": {},
    }


class FakeLlmClient:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[dict] = []

    def synthesize(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


class StaticRetrievalSkill(Skill):
    name = "s2_retrieval"

    def run(self, payload: SkillInput) -> SkillOutput:
        return SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_evidence()]},
            citations=[],
        )


def _payload(*, evidence: list[dict] | None = None, enabled: bool = True) -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query="What happens near critical speed?",
        context={"retrieval_context": evidence or []},
        constraints={"s3_llm_enabled": enabled},
    )


def test_s3_llm_synthesis_ok_requires_visible_chunk_citations():
    client = FakeLlmClient(
        {
            "answer": "Rotor response is amplified near critical speed [c1].",
            "claims": [{"text": "Rotor response is amplified near critical speed.", "chunk_id": "c1"}],
            "token_usage": {"total_tokens": 42},
        }
    )

    payload = _payload(evidence=[_evidence()])
    payload.constraints["difficulty"] = "extreme"

    output = QASummarySkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "llm"
    assert output.structured_result["token_cost"] == 42
    assert output.structured_result["claims"][0]["chunk_id"] == "c1"
    assert output.citations[0].chunk_id == "c1"
    assert client.calls[0]["model"].startswith("openai:")
    assert "Every claim must include" in client.calls[0]["prompt"]


def test_default_config_keeps_s3_llm_disabled(monkeypatch):
    monkeypatch.delenv("S3_LLM_ENABLED", raising=False)

    assert load().llm.s3_enabled is False


def test_default_tutor_orchestrator_keeps_s3_deterministic(monkeypatch):
    monkeypatch.delenv("S3_LLM_ENABLED", raising=False)

    output = TutorOrchestrator(retrieval_skill=StaticRetrievalSkill()).handle_query(
        "What happens near critical speed?",
        constraints={"scope": "in_scope"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["skill_results"]["s3"]["synthesis_mode"] == "deterministic"


def test_s3_llm_disabled_uses_deterministic_path_without_calling_client():
    client = FakeLlmClient({"answer": "Should not run [c1].", "claims": []})

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()], enabled=False))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert client.calls == []


def test_s3_llm_enabled_without_evidence_does_not_call_model():
    client = FakeLlmClient({"answer": "Should not run [c1].", "claims": []})

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[]))

    assert output.status == "insufficient"
    assert client.calls == []


def test_s3_llm_insufficient_response_falls_back_to_deterministic_s3():
    client = FakeLlmClient({"status": "insufficient", "warnings": ["model declined"]})

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("S3 LLM returned insufficient" in warning for warning in output.warnings)


def test_s3_llm_malformed_uncited_output_falls_back_with_warning():
    client = FakeLlmClient(
        {
            "answer": "Rotor response is amplified near critical speed.",
            "claims": [{"text": "Rotor response is amplified near critical speed.", "chunk_id": "c1"}],
        }
    )

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("missing visible citation" in warning for warning in output.warnings)


def test_s3_llm_timeout_falls_back_to_deterministic_s3():
    client = FakeLlmClient(exc=TimeoutError("model timed out"))

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("TimeoutError" in warning for warning in output.warnings)


def test_s3_llm_quota_failure_falls_back_to_deterministic_s3():
    client = FakeLlmClient(exc=RuntimeError("quota exceeded"))

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("quota exceeded" in warning for warning in output.warnings)
