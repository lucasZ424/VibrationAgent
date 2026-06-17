import json
from pathlib import Path

from vibration_agent.config import load
from vibration_agent.llm.budget import BudgetDeniedError
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs, write_fixture
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill, FormulaDerivationSkill
from vibration_agent.skills.base import Skill
from vibration_agent.skills.s5_formula_derivation import _validate_derivation_steps


def _formula_asset(**updates) -> dict:
    asset = {"asset_id": "f1", "object_type": "formula", "text_preview": "F = k x"}
    asset.update(updates)
    return asset


def _row(text: str = "The cited formula is F = k x for linear stiffness.", asset: dict | None = None) -> dict:
    return {"chunk_id": "c1", "doc_id": "d1", "pages": [4], "text": text, "assets": [asset or _formula_asset()]}


def _s2(row: dict | None = None) -> dict:
    row = row or _row()
    return {"status": "ok", "structured_result": {"retrieval_context": [row]}}


def _s3(claim_text: str = "The cited formula is F = k x for linear stiffness.", asset: dict | None = None) -> dict:
    asset = asset or _formula_asset()
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
                    "assets": [asset],
                }
            ],
            "synthesis_mode": "deterministic",
            "token_cost": 99,
            "cost": {"estimated_usd": 0.99, "source": "upstream"},
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


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / name
    return json.loads(path.read_text(encoding="utf-8"))


class FakeS5LlmClient:
    def __init__(self, response=None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[dict] = []

    def derive_formula(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


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


def test_s5_records_renderable_formula_contract_without_changing_citations():
    # WHY: Obj11 adds UI/API render metadata while the evidence-bound S5 answer
    # and citations stay plain-text compatible.
    asset = _formula_asset(latex=r"F = k x")
    output = FormulaDerivationSkill().run(_payload(s2=_s2(_row(asset=asset)), s3=_s3(asset=asset)))

    render = output.structured_result["formula_renders"][0]
    assert render["schema_version"] == "p4.formula_render.v1"
    assert render["formula_id"] == "f1"
    assert render["plain_text"] == "F = k x"
    assert render["latex"] == r"F = k x"
    assert render["status"] == "renderable"
    assert output.citations[0].chunk_id == "c1"
    assert "F = k x" in output.structured_result["answer"]


def test_s5_invalid_latex_markup_degrades_to_plain_text_formula_render():
    # WHY: broken formula markup must be loud for render clients but must not
    # remove the fallback derivation text.
    asset = _formula_asset(latex=r"\frac{F}{k")
    output = FormulaDerivationSkill().run(_payload(s2=_s2(_row(asset=asset)), s3=_s3(asset=asset)))

    render = output.structured_result["formula_renders"][0]
    assert render["status"] == "invalid_markup"
    assert render["latex"] is None
    assert render["plain_text"] == "F = k x"
    assert any("invalid LaTeX formula markup" in warning for warning in output.warnings)
    assert "F = k x" in output.structured_result["answer"]


def test_s5_llm_replay_multistep_derivation_passes_v2(tmp_path):
    # WHY: Obj6 activates replayable S5 formula derivation while V2 remains the
    # gate for evidence steps and axiomatic steps.
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = True
    response = _fixture("s5_visible_multistep_response.json")
    probe = FakeS5LlmClient(response)
    probe_output = FormulaDerivationSkill(llm_client=probe).run(payload)
    request = request_from_kwargs(task="s5_formula_derivation", schema_version="s5.v1", kwargs=probe.calls[0])
    write_fixture(tmp_path, request, response)

    s5_output = FormulaDerivationSkill(llm_client=ReplayClient(tmp_path)).run(payload)
    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="derive stiffness",
            context={"s2_result": _s2(), "s3_result": s5_output.model_dump(mode="python")},
            user_mode="derivation",
        )
    )

    assert probe_output.status == "ok"
    assert s5_output.status == "ok"
    assert s5_output.structured_result["synthesis_mode"] == "llm"
    assert s5_output.structured_result["token_cost"] == 112
    assert len(s5_output.structured_result["derivation_steps"]) == 3
    assert checked.status == "ok"
    assert checked.structured_result["unsupported_claims"] == []
    assert checked.structured_result["citation_check"]["derivation_step_count"] == 3


def test_s5_llm_two_node_cycle_is_rejected_and_falls_back():
    client = FakeS5LlmClient(_fixture("s5_cycle_response.json"))
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = True

    output = FormulaDerivationSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("dependency cycle" in warning for warning in output.warnings)


def test_s5_llm_unsupported_numeric_step_is_blocked_by_v2():
    client = FakeS5LlmClient(_fixture("s5_fabricated_step_number_response.json"))
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = True

    s5_output = FormulaDerivationSkill(llm_client=client).run(payload)
    checked = CitationCheckSkill().run(
        SkillInput(
            task_id="t1",
            user_query="derive stiffness",
            context={"s2_result": _s2(), "s3_result": s5_output.model_dump(mode="python")},
            user_mode="derivation",
        )
    )

    assert s5_output.structured_result["synthesis_mode"] == "llm"
    assert checked.status == "insufficient"
    assert checked.structured_result["answer"] == ""
    assert "999n" in checked.structured_result["unsupported_claims"][0]["reasons"][-1]
    assert checked.structured_result["s5_derivation"]["policy"] == "llm_evidence_and_axiomatic_steps"
    assert "minimal_model" not in checked.structured_result


def test_default_config_keeps_s5_llm_disabled(monkeypatch):
    monkeypatch.delenv("S5_LLM_ENABLED", raising=False)

    assert load().llm.s5_enabled is False


def test_s5_llm_disabled_uses_deterministic_path_without_calling_client():
    client = FakeS5LlmClient(_fixture("s5_visible_multistep_response.json"))
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = False

    output = FormulaDerivationSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert output.structured_result["token_cost"] is None
    assert output.structured_result["cost"] is None
    assert client.calls == []


def test_s5_llm_replay_miss_falls_back_to_deterministic_s5(tmp_path):
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = True

    output = FormulaDerivationSkill(llm_client=ReplayClient(tmp_path)).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("ReplayMissError" in warning for warning in output.warnings)


def test_s5_llm_insufficient_response_uses_clean_fallback_branch():
    client = FakeS5LlmClient({"status": "insufficient", "warnings": ["model needs more evidence"]})
    payload = _payload()
    payload.constraints["s5_llm_enabled"] = True

    output = FormulaDerivationSkill(llm_client=client).run(payload)

    assert output.status == "ok"
    assert output.structured_result["synthesis_mode"] == "deterministic"
    assert any("S5 LLM returned insufficient" in warning for warning in output.warnings)
    assert not any("ValidationError" in warning for warning in output.warnings)


def test_s5_llm_schema_failure_refusal_and_budget_deny_fall_back():
    for client in (
        FakeS5LlmClient({"answer": "F = k x [c1].", "premises": "F = k x [c1]."}),
        FakeS5LlmClient({"refusal": True, "answer": "", "claims": []}),
        FakeS5LlmClient(exc=BudgetDeniedError("per-task token budget exceeded")),
    ):
        payload = _payload()
        payload.constraints["s5_llm_enabled"] = True

        output = FormulaDerivationSkill(llm_client=client).run(payload)

        assert output.status == "ok"
        assert output.structured_result["synthesis_mode"] == "deterministic"


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
