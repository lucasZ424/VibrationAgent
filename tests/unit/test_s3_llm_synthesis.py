from __future__ import annotations

import json
from pathlib import Path

from vibration_agent.config import load
from vibration_agent.llm.budget import BudgetDeniedError
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs, write_fixture
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill, QASummarySkill
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


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / name
    return json.loads(path.read_text(encoding="utf-8"))


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
            "claims": [
                {
                    "text": "Rotor response is amplified near critical speed.",
                    "chunk_id": "c1",
                    "doc_id": "doc1",
                    "pages": [1],
                    "evidence_type": "documented",
                }
            ],
            "token_usage": {"total_tokens": 42},
            "cost": {"provider": "openai", "model": "gpt-5.5", "total_tokens": 42, "source": "local_estimate"},
        }
    )

    payload = _payload(evidence=[_evidence()])
    payload.constraints["difficulty"] = "extreme"

    output = QASummarySkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "llm"
    assert output.structured_result["token_cost"] == 42
    assert output.structured_result["cost"]["total_tokens"] == 42
    assert output.structured_result["claims"][0]["chunk_id"] == "c1"
    assert output.citations[0].chunk_id == "c1"
    assert client.calls[0]["model"].startswith("openai:")
    assert client.calls[0]["prompt_version"] == "s3_qa_summary.v3"
    assert client.calls[0]["schema_version"] == "s3.v1"
    assert client.calls[0]["reasoning_effort"] == "high"
    assert client.calls[0]["text_verbosity"] == "high"
    assert "Every claim must include" in client.calls[0]["prompt"]
    assert "support anchor" in client.calls[0]["prompt"]
    assert "never translate it" in client.calls[0]["prompt"]


def test_s3_llm_uses_query_language_when_evidence_is_cross_lingual():
    # WHY: an English user question must not ask the model for Chinese output
    # merely because retrieval returned more Chinese evidence; V2 then compares
    # translated claims against English evidence and correctly blocks them.
    client = FakeLlmClient({"status": "insufficient", "answer": "", "claims": []})

    QASummarySkill(llm_client=client).run(
        _payload(evidence=[_evidence(text="不平衡通常表现为一倍频振动。")])
    )

    assert client.calls[0]["language"] == "en"
    assert "language: en" in client.calls[0]["prompt"]


def test_s3_replay_response_with_visible_claim_passes_v2(tmp_path):
    # WHY: Obj4 turns S3 from an injected fake seam into replayable model
    # synthesis. A replay hit with visible citations must survive V2 unchanged.
    payload = _payload(evidence=[_evidence()])
    response = _fixture("s3_visible_response.json")
    probe = FakeLlmClient(response)
    probe_output = QASummarySkill(llm_client=probe).run(payload)
    request = request_from_kwargs(task="s3_qa_summary", schema_version="s3.v1", kwargs=probe.calls[0])
    write_fixture(tmp_path, request, response)

    s3_output = QASummarySkill(llm_client=ReplayClient(tmp_path)).run(payload)
    v2_output = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query=payload.user_query,
            context={
                "s2_result": {"status": "ok", "structured_result": {"retrieval_context": [_evidence()]}},
                "s3_result": s3_output.model_dump(mode="python"),
            },
        )
    )

    assert probe_output.status == "ok"
    assert s3_output.status == "ok"
    assert s3_output.structured_result["synthesis_mode"] == "llm"
    assert v2_output.status == "ok"
    assert v2_output.structured_result["unsupported_claims"] == []


def test_s3_replay_miss_falls_back_to_deterministic_s3(tmp_path):
    output = QASummarySkill(llm_client=ReplayClient(tmp_path)).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("ReplayMissError" in warning for warning in output.warnings)


def test_s3_llm_invisible_chunk_reaches_v2_and_strips_conclusion():
    client = FakeLlmClient(_fixture("s3_invisible_chunk_response.json"))

    s3_output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))
    v2_output = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="What happens near critical speed?",
            context={
                "s2_result": {"status": "ok", "structured_result": {"retrieval_context": [_evidence()]}},
                "s3_result": s3_output.model_dump(mode="python"),
            },
        )
    )

    assert s3_output.status == "ok"
    assert s3_output.structured_result["claims"][0]["chunk_id"] == "ghost"
    assert s3_output.citations == []
    assert v2_output.status == "insufficient"
    assert v2_output.structured_result["answer"] == ""
    assert "chunk not visible in retrieval" in v2_output.structured_result["unsupported_claims"][0]["reasons"]


def test_s3_llm_fabricated_number_is_blocked_in_default_chain():
    client = FakeLlmClient(_fixture("s3_fabricated_number_response.json"))
    orchestrator = TutorOrchestrator(
        retrieval_skill=StaticRetrievalSkill(),
        qa_summary_skill=QASummarySkill(llm_client=client),
    )

    output = orchestrator.handle_query(
        "What happens near critical speed?",
        constraints={"scope": "in_scope", "s3_llm_enabled": True, "s4_enabled": False},
        task_id="t1",
    )

    assert output.status == "insufficient"
    assert output.structured_result["skill_results"]["s3"]["synthesis_mode"] == "llm"
    assert output.structured_result["skill_results"]["v2"]["answer"] == ""
    assert "50hz" in output.structured_result["skill_results"]["v2"]["unsupported_claims"][0]["reasons"][-1]


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


def test_s3_enabled_tutor_uses_replay_before_live(tmp_path, monkeypatch):
    # WHY: enabling Obj6A in normal runtime must exercise reproducible replay
    # without constructing a provider or silently behaving as an unwired flag.
    monkeypatch.setenv("S3_LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_LIVE_ENABLED", "false")
    monkeypatch.setenv("LLM_REPLAY_DIR", str(tmp_path))

    output = TutorOrchestrator(
        retrieval_skill=StaticRetrievalSkill(),
    ).handle_query(
        "What happens near critical speed?",
        constraints={"scope": "in_scope", "s4_enabled": False},
        task_id="t1",
    )

    assert output.structured_result["skill_results"]["s3"]["synthesis_mode"] == "deterministic"
    assert any("ReplayMissError" in warning for warning in output.warnings)


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
            "claims": [
                {
                    "text": "Rotor response is amplified near critical speed.",
                    "chunk_id": "c1",
                    "doc_id": "doc1",
                    "pages": [1],
                    "evidence_type": "documented",
                }
            ],
        }
    )

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("missing visible citation" in warning for warning in output.warnings)


def test_s3_llm_schema_failure_falls_back_to_deterministic_s3():
    client = FakeLlmClient(
        {
            "answer": "Rotor response is amplified near critical speed [c1].",
            "claims": [{"text": "Rotor response is amplified near critical speed.", "chunk_id": "c1"}],
        }
    )

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("ValidationError" in warning for warning in output.warnings)


def test_s3_llm_refusal_flag_falls_back_to_deterministic_s3():
    client = FakeLlmClient({"refusal": True, "answer": "", "claims": []})

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("refused" in warning for warning in output.warnings)


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


def test_s3_llm_budget_deny_falls_back_to_deterministic_s3():
    client = FakeLlmClient(exc=BudgetDeniedError("per-task token budget exceeded"))

    output = QASummarySkill(llm_client=client).run(_payload(evidence=[_evidence()]))

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("BudgetDeniedError" in warning for warning in output.warnings)
