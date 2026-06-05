from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill, EngineeringAnalysisSkill
from vibration_agent.skills.base import Skill


def _row(text: str = "Critical speed can amplify rotor vibration response.") -> dict:
    return {"chunk_id": "c1", "doc_id": "d1", "pages": [2], "text": text, "score": 1.0}


def _s2(row: dict | None = None) -> dict:
    row = row or _row()
    return {"status": "ok", "structured_result": {"retrieval_context": [row]}}


def _s3(claim_text: str = "Critical speed can amplify rotor vibration response.") -> dict:
    return {
        "status": "ok",
        "structured_result": {
            "answer": f"{claim_text} (evidence: c1)",
            "claims": [{"text": claim_text, "chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
            "synthesis_mode": "deterministic",
        },
        "citations": [{"chunk_id": "c1", "doc_id": "d1", "pages": [2]}],
    }


def _payload(*, user_mode="engineering", s2: dict | None = None, s3: dict | None = None) -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query="How does critical speed affect rotor vibration?",
        user_mode=user_mode,
        context={"s2_result": s2 or _s2(), "s3_result": s3 or _s3()},
    )


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
