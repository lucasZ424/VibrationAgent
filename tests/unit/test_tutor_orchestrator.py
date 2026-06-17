import json
import sys
from pathlib import Path

from vibration_agent.orchestrator import TutorOrchestrator, handle_query, is_in_scope
from vibration_agent.orchestrator.tutor import _token_cost
from vibration_agent.config import RoutingSettings, load
from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills import (
    CitationCheckSkill,
    EngineeringAnalysisSkill,
    FormulaDerivationSkill,
    OutputStyleSkill,
    QASummarySkill,
    RetrievalSkill,
    ReviewerSkill,
    TermSymbolUnitNormalizerSkill,
)
from vibration_agent.skills.base import Skill


def _chunk(chunk_id: str, text: str, *, pages: list[int] | None = None) -> dict:
    pages = pages or [1]
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc1",
        "title": "Rotor Dynamics",
        "source_type": "book",
        "chunk_index": 1,
        "page_start": pages[0],
        "page_end": pages[-1],
        "pages": pages,
        "chunk_type": "body",
        "topic": "rotor_dynamics",
        "token_estimate": 20,
        "char_count": len(text),
        "text": text,
        "api_context": f"[chunk_id={chunk_id}; doc_id=doc1; pages={pages[0]}-{pages[-1]}]\n{text}",
        "assets": [],
        "metadata": {},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


class RecordingSkill(Skill):
    name = "recording"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


def test_default_tutor_orchestrator_uses_only_phase1_active_query_skills():
    orchestrator = TutorOrchestrator()

    active_skills = [
        orchestrator.retrieval_skill,
        orchestrator.qa_summary_skill,
        orchestrator.engineering_analysis_skill,
        orchestrator.formula_derivation_skill,
        orchestrator.normalizer_skill,
        orchestrator.citation_check_skill,
        orchestrator.style_skill,
        orchestrator.reviewer_skill,
    ]
    active_names = {skill.name for skill in active_skills}
    deferred_prefixes = ("s6_", "s7_", "s8_")

    assert type(orchestrator.retrieval_skill) is RetrievalSkill
    assert type(orchestrator.qa_summary_skill) is QASummarySkill
    assert type(orchestrator.engineering_analysis_skill) is EngineeringAnalysisSkill
    assert type(orchestrator.formula_derivation_skill) is FormulaDerivationSkill
    assert type(orchestrator.normalizer_skill) is TermSymbolUnitNormalizerSkill
    assert type(orchestrator.citation_check_skill) is CitationCheckSkill
    assert type(orchestrator.style_skill) is OutputStyleSkill
    assert type(orchestrator.reviewer_skill) is ReviewerSkill
    assert active_names == {
        "s2_retrieval",
        "s3_qa_summary",
        "s4_engineering_analysis",
        "s5_formula_derivation",
        "v1_term_symbol_unit_normalizer",
        "v2_citation_check",
        "v3_reviewer",
        "v4_style",
    }
    assert all(not name.startswith(deferred_prefixes) for name in active_names)
    assert not any(
        module_name.startswith(f"vibration_agent.skills.{prefix}")
        for module_name in sys.modules
        for prefix in deferred_prefixes
    )


def test_scope_detection_accepts_vibration_terms_and_rejects_general_topics():
    assert is_in_scope("阻尼比如何影响转子振动？") is True
    assert is_in_scope("How does API 684 discuss critical speed?") is True
    assert is_in_scope("bearing fault diagnosis workflow") is True
    assert is_in_scope("帮我写一个市场营销口号") is False


def test_scope_detection_rejects_borderline_false_positives():
    assert is_in_scope("shaft of an elevator") is False
    assert is_in_scope("modal verbs in English") is False
    assert is_in_scope("autism spectrum support resources") is False
    assert is_in_scope("standard operating procedure for visas") is False
    assert is_in_scope("标准操作流程怎么写") is False


def test_domain_scope_alias_can_force_scope_decision():
    assert is_in_scope("generic question", constraints={"domain_scope": "in_scope"}) is True
    assert is_in_scope("转子振动", constraints={"domain_scope": "out_of_scope"}) is False


def test_tutor_orchestrator_out_of_scope_returns_localized_insufficient_without_calling_skills():
    s2 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    s3 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    v4 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, style_skill=v4)

    output = orchestrator.handle_query("写一首销售文案", task_id="t1")

    assert output.status == "insufficient"
    assert output.summary.startswith("范围外")
    assert output.structured_result["language"] == "zh"
    assert output.structured_result["scope"] == "out_of_scope"
    assert output.structured_result["chain"] == []
    assert output.structured_result["skill_results"] == {}
    assert s2.calls == []
    assert s3.calls == []
    assert v4.calls == []


def test_tutor_orchestrator_runs_s2_s3_v2_v4_for_in_scope_query(tmp_path):
    chunks_path = _write_jsonl(
        tmp_path / "chunks.jsonl",
        [_chunk("c1", "阻尼比 zeta 控制自由振动衰减速度。阻尼越大，振动衰减越快。", pages=[3])],
    )
    orchestrator = TutorOrchestrator()

    output = orchestrator.handle_query(
        "阻尼比如何影响转子振动？",
        constraints={"chunks_jsonl": str(chunks_path), "top_k": 1},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["scope"] == "in_scope"
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "s4_engineering_analysis",
        "v2_citation_check",
        "v4_style",
    ]
    assert output.structured_result["chain"][0]["status"] == "ok"
    assert output.structured_result["chain"][1]["status"] == "ok"
    assert "## 结论" in output.structured_result["answer"]
    assert "## 证据" in output.structured_result["answer"]
    assert output.structured_result["v4"]["answer"] == output.structured_result["answer"]
    assert set(output.structured_result["skill_results"]) == {"s2", "s3", "s4", "v2", "v4"}
    assert output.citations[0].chunk_id == "c1"


def test_tutor_orchestrator_short_circuits_when_s2_has_no_evidence():
    orchestrator = TutorOrchestrator()

    output = orchestrator.handle_query(
        "临界转速下转子振动如何变化？",
        task_id="t1",
    )

    assert output.status == "insufficient"
    assert output.structured_result["scope"] == "in_scope"
    assert [step["skill"] for step in output.structured_result["chain"]] == ["s2_retrieval"]
    assert output.structured_result["chain"][0]["status"] == "insufficient"
    assert set(output.structured_result["skill_results"]) == {"s2"}
    assert output.citations == []


def test_tutor_orchestrator_short_circuits_when_s3_is_insufficient():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [{"chunk_id": "c1", "doc_id": "doc1", "text": ""}]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="insufficient", summary="S3 no usable evidence", warnings=["no evidence"]))
    v4 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, style_skill=v4)

    output = orchestrator.handle_query(
        "转子振动如何诊断？",
        constraints={"scope": "in_scope"},
        task_id="t1",
    )

    assert output.status == "insufficient"
    assert [step["skill"] for step in output.structured_result["chain"]] == ["s2_retrieval", "s3_qa_summary"]
    assert output.summary == "S3 no usable evidence"
    assert "no evidence" in output.warnings
    assert v4.calls == []


def test_tutor_orchestrator_short_circuits_and_preserves_fail_status_from_s2():
    s2 = RecordingSkill(SkillOutput(status="fail", summary="retrieval exploded", warnings=["boom"]))
    s3 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    v4 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, style_skill=v4)

    output = orchestrator.handle_query(
        "转子振动如何诊断？",
        constraints={"scope": "in_scope"},
        task_id="t1",
    )

    assert output.status == "fail"
    assert [step["skill"] for step in output.structured_result["chain"]] == ["s2_retrieval"]
    assert "boom" in output.warnings
    assert s3.calls == []
    assert v4.calls == []


def test_default_handle_query_uses_default_orchestrator_for_out_of_scope_query():
    output = handle_query("请解释股票估值", task_id="t1")

    assert output.status == "insufficient"
    assert output.structured_result["scope"] == "out_of_scope"


def test_tutor_orchestrator_skips_v3_for_non_extreme_query():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={
                "answer": "## Conclusion\nCritical speed affects rotor response.",
                "sections": {"conclusion": "Critical speed affects rotor response."},
            },
        )
    )
    v3 = RecordingSkill(SkillOutput(status="insufficient", summary="should not run"))
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        reviewer_skill=v3,
    )

    output = orchestrator.handle_query("critical speed", constraints={"scope": "in_scope"}, task_id="t1")

    assert output.status == "ok"
    assert v3.calls == []
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
    ]
    assert "v3" not in output.structured_result["skill_results"]


def test_tutor_orchestrator_runs_v3_for_extreme_query_without_blocking_answer():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={
                "answer": "## Conclusion\nCritical speed always eliminates vibration risk.",
                "sections": {"conclusion": "Critical speed always eliminates vibration risk."},
            },
        )
    )
    v3 = RecordingSkill(
        SkillOutput(
            status="insufficient",
            summary="V3 flagged issue",
            structured_result={"reviewer_notes": [{"code": "overclaiming", "message": "absolute wording"}]},
        )
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        reviewer_skill=v3,
    )

    output = orchestrator.handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert len(v3.calls) == 1
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
        "v3_reviewer",
    ]
    assert output.structured_result["reviewer_notes"][0]["code"] == "overclaiming"
    assert "v3" in output.structured_result["skill_results"]


def test_tutor_orchestrator_v3_exception_warns_without_blocking_answer():
    class BrokenReviewer(Skill):
        name = "v3_reviewer"

        def run(self, payload: SkillInput) -> SkillOutput:
            raise RuntimeError("v3 boom")

    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={
                "answer": "## Conclusion\nCritical speed affects rotor response.",
                "sections": {"conclusion": "Critical speed affects rotor response."},
            },
        )
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        reviewer_skill=BrokenReviewer(),
    )

    output = orchestrator.handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["answer"] == "## Conclusion\nCritical speed affects rotor response."
    assert output.structured_result["reviewer_notes"] == []
    assert output.structured_result["chain"][-1]["skill"] == "v3_reviewer"
    assert any("V3 reviewer failed" in warning for warning in output.warnings)


def test_tutor_token_cost_reads_s3_skill_result_for_qa_logs():
    output = SkillOutput(
        status="ok",
        structured_result={"skill_results": {"s3": {"token_cost": 17}}},
    )

    assert _token_cost(output) == 17


def test_tutor_orchestrator_leaves_advisory_lane_absent_without_activation():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "## Conclusion\nCritical speed affects rotor response."},
        )
    )
    s7 = RecordingSkill(SkillOutput(status="ok", summary="should not run"))
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        model_selection_skill=s7,
    )

    output = orchestrator.handle_query(
        "select a model for critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False},
        task_id="t1",
    )

    assert output.status == "ok"
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
    ]
    assert "advisory_routing" not in output.structured_result
    assert "s7" not in output.structured_result["skill_results"]
    assert s7.calls == []


def test_tutor_orchestrator_routes_explicit_advisory_skills_as_structured_handoff():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "## Conclusion\nCritical speed affects rotor response."},
        )
    )
    s6 = RecordingSkill(SkillOutput(status="ok", summary="S6 ok", structured_result={"candidates": [{"title": "A"}]}))
    s7 = RecordingSkill(
        SkillOutput(status="ok", summary="S7 ok", structured_result={"recommendations": [{"model_family": "m"}]})
    )
    s8 = RecordingSkill(
        SkillOutput(status="ok", summary="S8 ok", structured_result={"experiment_plans": [{"experiment_focus": "e"}]})
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        literature_search_skill=s6,
        model_selection_skill=s7,
        experiment_advice_skill=s8,
    )

    output = orchestrator.handle_query(
        "find literature, select a model, and plan measurements",
        constraints={
            "scope": "in_scope",
            "s4_enabled": False,
            "advisory_routing_enabled": True,
            "advisory_skills": ["s6", "s7", "s8"],
        },
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["answer"] == "## Conclusion\nCritical speed affects rotor response."
    assert [step["skill"] for step in output.structured_result["chain"]][-3:] == [
        "s6_literature_search",
        "s7_model_selection",
        "s8_experiment_advice",
    ]
    advisory = output.structured_result["advisory_routing"]
    assert advisory["selected_skills"] == ["s6_literature_search", "s7_model_selection", "s8_experiment_advice"]
    assert advisory["rendering"] == "structured_handoff_only"
    assert advisory["v2_v4_policy"] == "do_not_render_as_final_answer"
    assert set(advisory["outputs"]) == {"s6", "s7", "s8"}
    assert set(output.structured_result["skill_results"]) >= {"s6", "s7", "s8"}
    assert s6.calls[0].constraints["s6_enabled"] is True
    assert s7.calls[0].constraints["s7_enabled"] is True
    assert s8.calls[0].constraints["s8_enabled"] is True
    assert "s2_result" in s7.calls[0].context


def test_tutor_orchestrator_records_enabled_gate_without_selected_advisory_skill():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "## Conclusion\nCritical speed affects rotor response."},
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, citation_check_skill=v2, style_skill=v4)

    output = orchestrator.handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False, "advisory_routing_enabled": True},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["advisory_routing"]["selected_skills"] == []
    assert output.structured_result["advisory_routing"]["reason"] == "advisory routing gate enabled without explicit skills"
    assert [step["skill"] for step in output.structured_result["chain"]][-1] == "v4_style"


def test_tutor_orchestrator_routes_intent_when_policy_allows_it():
    settings = load(Path.cwd()).model_copy(
        update={
            "routing": RoutingSettings(
                advisory_routing_enabled=True,
                advisory_intent_routing_enabled=True,
                advisory_allowed_skills=["s7"],
            )
        }
    )
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "## Conclusion\nCritical speed affects rotor response."},
        )
    )
    s7 = RecordingSkill(
        SkillOutput(status="ok", summary="S7 ok", structured_result={"recommendations": [{"model_family": "m"}]})
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        model_selection_skill=s7,
        settings=settings,
    )

    output = orchestrator.handle_query(
        "Which model should I use for critical speed?",
        constraints={"scope": "in_scope", "s4_enabled": False},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["advisory_routing"]["reason"] == "restricted by configured advisory_allowed_skills"
    assert output.structured_result["advisory_routing"]["selected_skills"] == ["s7_model_selection"]
    assert len(s7.calls) == 1


def test_tutor_orchestrator_runs_advisory_lane_before_extreme_reviewer():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [_chunk("c1", "Critical speed affects rotor response.")]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "## Conclusion\nCritical speed affects rotor response."},
        )
    )
    s7 = RecordingSkill(
        SkillOutput(status="ok", summary="S7 ok", structured_result={"recommendations": [{"model_family": "m"}]})
    )
    v3 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V3 ok",
            structured_result={"reviewer_notes": []},
        )
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        model_selection_skill=s7,
        reviewer_skill=v3,
    )

    output = orchestrator.handle_query(
        "Which model should I use for critical speed?",
        constraints={
            "scope": "in_scope",
            "s4_enabled": False,
            "difficulty": "extreme",
            "advisory_routing_enabled": True,
            "advisory_skills": ["s7"],
        },
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["answer"] == "## Conclusion\nCritical speed affects rotor response."
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
        "s7_model_selection",
        "v3_reviewer",
    ]
    assert output.structured_result["advisory_routing"]["selected_skills"] == ["s7_model_selection"]
    assert len(s7.calls) == 1
    assert len(v3.calls) == 1
