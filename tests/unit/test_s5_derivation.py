from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill, FormulaDerivationSkill
from vibration_agent.skills.base import Skill
from vibration_agent.skills.s5_formula_derivation import _validate_derivation_steps


def _formula_asset() -> dict:
    return {"asset_id": "f1", "object_type": "formula", "text_preview": "F = k x"}


def _row(text: str = "The cited formula is F = k x for linear stiffness.") -> dict:
    return {"chunk_id": "c1", "doc_id": "d1", "pages": [4], "text": text, "assets": [_formula_asset()]}


def _s2(row: dict | None = None) -> dict:
    row = row or _row()
    return {"status": "ok", "structured_result": {"retrieval_context": [row]}}


def _s3(claim_text: str = "The cited formula is F = k x for linear stiffness.") -> dict:
    return {
        "status": "ok",
        "structured_result": {
            "answer": f"{claim_text} (evidence: c1)",
            "claims": [
                {
                    "text": claim_text,
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "pages": [4],
                    "assets": [_formula_asset()],
                }
            ],
            "synthesis_mode": "deterministic",
        },
        "citations": [{"chunk_id": "c1", "doc_id": "d1", "pages": [4]}],
    }


def _payload(*, user_mode="derivation", s2: dict | None = None, s3: dict | None = None) -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query="Derive the stiffness relation.",
        user_mode=user_mode,
        context={"s2_result": s2 or _s2(), "s3_result": s3 or _s3()},
    )


def test_s5_formula_derivation_builds_evidence_and_axiomatic_step_chain():
    output = FormulaDerivationSkill().run(_payload())

    assert output.status == "ok"
    assert output.structured_result["mode"] == "formula_derivation"
    assert output.structured_result["derivation_steps"][0]["source_type"] == "evidence"
    assert output.structured_result["derivation_steps"][1]["source_type"] == "axiomatic"
    assert output.structured_result["assets"][0]["asset_id"] == "f1"
    assert "F = k x" in output.structured_result["minimal_model"]

    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="derive stiffness",
            context={"s2_result": _s2(), "s3_result": output.model_dump(mode="python")},
            user_mode="derivation",
        )
    )

    assert checked.status == "ok"
    assert checked.structured_result["unsupported_claims"] == []
    assert checked.structured_result["citation_check"]["derivation_step_count"] == 2


def test_s5_formula_derivation_skips_without_visible_evidence():
    s3 = _s3()
    s3["structured_result"]["claims"][0]["chunk_id"] = "missing"

    output = FormulaDerivationSkill().run(_payload(s3=s3))

    assert output.status == "insufficient"
    assert output.structured_result["skip_reason"] == "insufficient_evidence"


def test_s5_formula_derivation_skips_when_user_mode_is_not_derivation():
    output = FormulaDerivationSkill().run(_payload(user_mode="engineering"))

    assert output.status == "insufficient"
    assert output.structured_result["skip_reason"] == "user_mode"


def test_s5_derivation_step_validator_reports_missing_step_dependency():
    warnings = _validate_derivation_steps(
        [
            {"id": "step_1", "source_type": "evidence", "text": "F = k x", "chunk_id": "c1", "depends_on": []},
            {"id": "step_2", "source_type": "axiomatic", "text": "rearrange", "depends_on": ["step_missing"]},
        ]
    )

    assert "depends on missing step step_missing" in warnings[0]


def test_s5_derivation_step_validator_reports_circular_self_dependency():
    warnings = _validate_derivation_steps(
        [
            {"id": "step_1", "source_type": "evidence", "text": "F = k x", "chunk_id": "c1", "depends_on": ["step_1"]},
        ]
    )

    assert "depends on itself" in warnings[0]
    assert any("dependency cycle" in warning for warning in warnings)


def test_s5_derivation_step_validator_reports_multi_node_cycle():
    warnings = _validate_derivation_steps(
        [
            {"id": "step_1", "source_type": "evidence", "text": "F = k x", "chunk_id": "c1", "depends_on": ["step_2"]},
            {"id": "step_2", "source_type": "axiomatic", "text": "rearrange", "depends_on": ["step_1"]},
        ]
    )

    assert any("step_1 participates in a dependency cycle" in warning for warning in warnings)
    assert any("step_2 participates in a dependency cycle" in warning for warning in warnings)


def test_v2_accepts_axiomatic_s5_step_without_treating_it_as_fake_citation():
    s5_like = SkillOutput(
        status="ok",
        summary="S5 ok",
        structured_result={
            "answer": "Premise: F = k x. step_2 is algebraic rearrangement.",
            "claims": [{"text": "The cited formula is F = k x for linear stiffness.", "chunk_id": "c1", "doc_id": "d1"}],
            "derivation_steps": [
                {"id": "step_1", "source_type": "evidence", "text": "F = k x", "chunk_id": "c1"},
                {"id": "step_2", "source_type": "axiomatic", "text": "divide both sides by k", "depends_on": ["step_1"]},
            ],
        },
        citations=[Citation(chunk_id="c1", doc_id="d1", pages=[4])],
    )

    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="derive stiffness",
            context={"s2_result": _s2(), "s3_result": s5_like.model_dump(mode="python")},
            user_mode="derivation",
        )
    )

    assert checked.status == "ok"
    assert checked.structured_result["unsupported_claims"] == []


class StaticSkill(Skill):
    name = "static"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


def test_tutor_orchestrator_inserts_s5_before_v2_for_derivation_mode():
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
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[4])],
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3)

    output = orchestrator.handle_query(
        "derive stiffness",
        constraints={"scope": "in_scope"},
        user_mode="derivation",
        task_id="t1",
    )

    assert output.status == "ok"
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "s5_formula_derivation",
        "v2_citation_check",
        "v4_style",
    ]
    assert "s5" in output.structured_result["skill_results"]
    assert "Minimal Model / Formula" in output.structured_result["answer"]


def test_tutor_orchestrator_keeps_s4_s5_mutually_exclusive_when_both_forced():
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
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[4])],
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3)

    output = orchestrator.handle_query(
        "derive stiffness",
        constraints={"scope": "in_scope", "s4_enabled": True, "s5_enabled": True},
        user_mode="derivation",
        task_id="t1",
    )

    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "s5_formula_derivation",
        "v2_citation_check",
        "v4_style",
    ]
    assert "s5" in output.structured_result["skill_results"]
    assert "s4" not in output.structured_result["skill_results"]
    assert any("S5 formula derivation takes precedence" in warning for warning in output.warnings)
