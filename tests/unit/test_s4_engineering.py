import json
from pathlib import Path

from vibration_agent.config import load
from vibration_agent.llm.budget import BudgetDeniedError
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs, write_fixture
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill, EngineeringAnalysisSkill
from vibration_agent.skills.base import Skill


def _row(text: str = "Critical speed can amplify rotor vibration response.") -> dict:
    return {"chunk_id": "c1", "doc_id": "d1", "pages": [2], "text": text, "score": 1.0}


def _s2(row: dict | None = None) -> dict:
    row = row or _row()
    return {"status": "ok", "structured_result": {"retrieval_context": [row]}}


def _s3(claim_text: str = "Critical speed can amplify rotor vibration response.", *, language: str | None = None) -> dict:
    structured_result = {
        "answer": f"{claim_text} (evidence: c1)",
        "claims": [{"text": claim_text, "chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
        "synthesis_mode": "deterministic",
        "token_cost": 99,
        "cost": {"estimated_usd": 0.99, "source": "upstream"},
    }
    if language is not None:
        structured_result["language"] = language
    return {
        "status": "ok",
        "structured_result": structured_result,
        "citations": [{"chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
    }


def _payload(*, user_mode="engineering", s2: dict | None = None, s3: dict | None = None) -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query="How does critical speed affect rotor vibration?",
        user_mode=user_mode,
        context={"s2_result": s2 or _s2(), "s3_result": s3 or _s3()},
    )


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / name
    return json.loads(path.read_text(encoding="utf-8"))


class FakeS4LlmClient:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[dict] = []

    def analyze_engineering(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


def test_s4_engineering_analysis_uses_visible_cited_evidence_and_passes_v2():
    output = EngineeringAnalysisSkill().run(_payload())

    assert output.status == "ok"
    assert output.structured_result["mode"] == "engineering_analysis"
    assert output.structured_result["engineering_meaning"].startswith("Engineering implication")
    assert output.structured_result["claims"][0]["chunk_id"] == "c1"

    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="critical speed",
            context={"s2_result": _s2(), "s3_result": output.model_dump(mode="python")},
        )
    )

    assert checked.status == "ok"
    assert checked.structured_result["unsupported_claims"] == []


def test_s4_deterministic_framing_uses_threaded_chinese_language():
    claim = "临界转速附近转子响应会被放大。"
    output = EngineeringAnalysisSkill().run(
        _payload(s2=_s2(_row(claim)), s3=_s3(claim, language="zh"))
    )

    assert output.status == "ok"
    assert output.structured_result["language"] == "zh"
    assert output.structured_result["engineering_meaning"] == f"工程意义仅限于所引证据：{claim}"
    assert output.structured_result["premises"] == "仅适用于检索到的证据块：c1。"
    assert output.structured_result["failure_modes"] == "请勿超出所引工况、单位或数值范围进行外推。"
    assert output.structured_result["next_action"] == "在应用阈值、维护措施或模型假设前，请先核对所引证据块。"


def test_s4_deterministic_framing_infers_chinese_for_legacy_payload_without_language():
    claim = "阻尼比控制自由振动的衰减速度。"
    output = EngineeringAnalysisSkill().run(_payload(s2=_s2(_row(claim)), s3=_s3(claim)))

    assert output.status == "ok"
    assert output.structured_result["language"] == "zh"
    assert output.structured_result["engineering_meaning"].startswith("工程意义仅限于所引证据")


def test_s4_llm_replay_response_generates_rich_analysis_and_passes_v2(tmp_path):
    # WHY: Obj5 activates replayable S4 engineering analysis while keeping V2
    # as the single quality gate before V4 can render engineering sections.
    payload = _payload()
    payload.constraints["s4_llm_enabled"] = True
    response = _fixture("s4_visible_response.json")
    probe = FakeS4LlmClient(response)
    probe_output = EngineeringAnalysisSkill(llm_client=probe).run(payload)
    request = request_from_kwargs(task="s4_engineering_analysis", schema_version="s4.v1", kwargs=probe.calls[0])
    write_fixture(tmp_path, request, response)

    s4_output = EngineeringAnalysisSkill(llm_client=ReplayClient(tmp_path)).run(payload)
    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="critical speed",
            context={"s2_result": _s2(), "s3_result": s4_output.model_dump(mode="python")},
        )
    )

    assert probe_output.status == "ok"
    assert s4_output.status == "ok"
    assert s4_output.structured_result["synthesis_mode"] == "llm"
    assert s4_output.structured_result["engineering_meaning"].startswith("Critical speed")
    assert s4_output.structured_result["token_cost"] == 96
    assert checked.status == "ok"
    assert checked.structured_result["unsupported_claims"] == []


def test_s4_llm_fabricated_threshold_is_blocked_and_stripped_before_v4():
    client = FakeS4LlmClient(_fixture("s4_fabricated_threshold_response.json"))
    s2 = StaticSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_row()], "retrieval_output": {"hits": [{"chunk_id": "c1"}]}},
        )
    )
    s3 = StaticSkill(
        SkillOutput(
            status="ok",
            summary="S3 ok",
            structured_result={**_s3()["structured_result"], "synthesis_mode": "llm"},
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[2])],
        )
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        engineering_analysis_skill=EngineeringAnalysisSkill(llm_client=client),
    )

    output = orchestrator.handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_llm_enabled": True},
        task_id="t1",
    )

    assert output.status == "insufficient"
    assert output.structured_result["skill_results"]["s4"]["synthesis_mode"] == "llm"
    assert "engineering_meaning" not in output.structured_result["skill_results"]["v2"]
    assert "999kn" in output.structured_result["skill_results"]["v2"]["unsupported_claims"][0]["reasons"][-1]
    assert "999 kN" not in output.structured_result["answer"]


def test_default_config_keeps_s4_llm_disabled(monkeypatch):
    monkeypatch.delenv("S4_LLM_ENABLED", raising=False)

    assert load().llm.s4_enabled is False


def test_s4_llm_disabled_uses_deterministic_path_without_calling_client():
    client = FakeS4LlmClient(_fixture("s4_visible_response.json"))
    payload = _payload()
    payload.constraints["s4_llm_enabled"] = False

    output = EngineeringAnalysisSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert output.structured_result["token_cost"] is None
    assert output.structured_result["cost"] is None
    assert client.calls == []


def test_s4_llm_replay_miss_falls_back_to_deterministic_s4(tmp_path):
    payload = _payload()
    payload.constraints["s4_llm_enabled"] = True

    output = EngineeringAnalysisSkill(llm_client=ReplayClient(tmp_path)).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("ReplayMissError" in warning for warning in output.warnings)


def test_s4_llm_insufficient_response_uses_clean_fallback_branch():
    client = FakeS4LlmClient({"status": "insufficient", "warnings": ["model needs more evidence"]})
    payload = _payload()
    payload.constraints["s4_llm_enabled"] = True

    output = EngineeringAnalysisSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("S4 LLM returned insufficient" in warning for warning in output.warnings)
    assert not any("ValidationError" in warning for warning in output.warnings)


def test_s4_llm_schema_failure_falls_back_to_deterministic_s4():
    client = FakeS4LlmClient(
        {
            "answer": "Critical speed can amplify rotor response [c1].",
            "engineering_meaning": "Critical speed can amplify rotor response [c1].",
            "premises": "Use only cited evidence [c1].",
        }
    )
    payload = _payload()
    payload.constraints["s4_llm_enabled"] = True

    output = EngineeringAnalysisSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("missing required engineering fields" in warning for warning in output.warnings)


def test_s4_llm_refusal_and_budget_deny_fall_back_to_deterministic_s4():
    for client in (
        FakeS4LlmClient({"refusal": True, "answer": "", "claims": []}),
        FakeS4LlmClient(exc=BudgetDeniedError("per-task token budget exceeded")),
    ):
        payload = _payload()
        payload.constraints["s4_llm_enabled"] = True

        output = EngineeringAnalysisSkill(llm_client=client).run(payload)

        assert output.status == "ok"
        assert output.structured_result["synthesis_mode"] == "deterministic"


def test_v2_unsupported_block_strips_unknown_free_text_fields():
    bad_s4 = SkillOutput(
        status="ok",
        summary="bad S4",
        structured_result={
            "answer": "Bearing load is 999 kN [c1].",
            "claims": [{"text": "Bearing load is 999 kN.", "chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
            "synthesis_mode": "llm",
            "engineering_meaning": "Bearing load is 999 kN [c1].",
            "future_s5_narrative": "A future unsupported derivation says 999 kN [c1].",
            "sections": {"future_s5_narrative": "A future unsupported derivation says 999 kN [c1]."},
        },
        citations=[Citation(chunk_id="c1", doc_id="d1", pages=[2])],
    )

    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="critical speed",
            context={"s2_result": _s2(), "s3_result": bad_s4.model_dump(mode="python")},
        )
    )

    assert checked.status == "insufficient"
    assert checked.structured_result["answer"] == ""
    assert "engineering_meaning" not in checked.structured_result
    assert "future_s5_narrative" not in checked.structured_result
    assert "sections" not in checked.structured_result


def test_s4_engineering_analysis_skips_when_evidence_is_insufficient():
    s3 = _s3()
    s3["structured_result"]["claims"] = []

    output = EngineeringAnalysisSkill().run(_payload(s3=s3))

    assert output.status == "insufficient"
    assert output.structured_result["skip_reason"] == "insufficient_evidence"


def test_s4_engineering_analysis_skips_when_user_mode_is_not_engineering():
    output = EngineeringAnalysisSkill().run(_payload(user_mode="definition"))

    assert output.status == "insufficient"
    assert output.structured_result["skip_reason"] == "user_mode"


def test_v2_blocks_unsupported_numeric_claim_from_s4_like_output():
    bad_s4 = SkillOutput(
        status="ok",
        summary="bad S4",
        structured_result={
            "answer": "Bearing load is 999 kN (evidence: c1).",
            "claims": [{"text": "Bearing load is 999 kN.", "chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
            "synthesis_mode": "deterministic",
        },
        citations=[Citation(chunk_id="c1", doc_id="d1", pages=[2])],
    )

    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="critical speed",
            context={"s2_result": _s2(), "s3_result": bad_s4.model_dump(mode="python")},
        )
    )

    assert checked.status == "insufficient"
    assert "claim text does not lexically match cited evidence" in checked.structured_result["unsupported_claims"][0]["reasons"]


class StaticSkill(Skill):
    name = "static"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


def test_tutor_orchestrator_inserts_s4_before_v2_for_engineering_mode():
    s2 = StaticSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_row()], "retrieval_output": {"hits": [{"chunk_id": "c1"}]}},
        )
    )
    s3 = StaticSkill(
        SkillOutput(
            status="ok",
            summary="S3 ok",
            structured_result=_s3()["structured_result"],
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[2])],
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3)

    output = orchestrator.handle_query("critical speed", constraints={"scope": "in_scope"}, task_id="t1")

    assert output.status == "ok"
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "s4_engineering_analysis",
        "v2_citation_check",
        "v4_style",
    ]
    assert "s4" in output.structured_result["skill_results"]
    assert "Engineering Meaning" in output.structured_result["answer"]


def test_tutor_orchestrator_skips_s4_for_non_engineering_mode():
    s2 = StaticSkill(SkillOutput(status="ok", summary="S2 ok", structured_result={"retrieval_context": [_row()]}))
    s3 = StaticSkill(
        SkillOutput(
            status="ok",
            summary="S3 ok",
            structured_result=_s3()["structured_result"],
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[2])],
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3)

    output = orchestrator.handle_query(
        "critical speed",
        constraints={"scope": "in_scope"},
        user_mode="definition",
        task_id="t1",
    )

    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
    ]
    assert "s4" not in output.structured_result["skill_results"]
