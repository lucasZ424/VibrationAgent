import json
import sys
from pathlib import Path

from vibration_agent.orchestrator import TutorOrchestrator, handle_query, is_in_scope
from vibration_agent.orchestrator.tutor import (
    _answer_quality,
    _complete_sentence_ratio,
    _evidence_relevance,
    _intent_completeness,
    _merge_warnings,
    _query_coverage,
    _token_cost,
)
from vibration_agent.config import RoutingSettings, load
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
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


def test_merge_warnings_deduplicates_repeated_upstream_warning():
    warning = "S3 dropped 5 retrieval row(s) without usable chunk text."
    outputs = [SkillOutput(status="ok", warnings=[warning]) for _ in range(3)]

    assert _merge_warnings(*outputs) == [warning]


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
    assert is_in_scope("旋转机械到达临界转速后会发生什么？") is True
    assert is_in_scope("阻尼比如何影响转子振动？") is True
    assert is_in_scope("How does API 684 discuss critical speed?") is True
    assert is_in_scope("bearing fault diagnosis workflow") is True
    assert is_in_scope("GB/T 33199.1 的适用机组范围和规定的方法是什么？") is True
    assert is_in_scope("What units and methods are covered by GB/T 33199.1?") is True
    assert is_in_scope("GB/T 11348.4 的轴振动测量范围是什么？") is True
    assert is_in_scope("DL/T 5565 的适用范围是什么？") is True
    assert is_in_scope("What does ISO 10816 cover?") is True
    assert is_in_scope("帮我写一个市场营销口号") is False


def test_scope_detection_rejects_borderline_false_positives():
    assert is_in_scope("shaft of an elevator") is False
    assert is_in_scope("modal verbs in English") is False
    assert is_in_scope("autism spectrum support resources") is False
    assert is_in_scope("standard operating procedure for visas") is False
    assert is_in_scope("标准操作流程怎么写") is False
    assert is_in_scope("GB/T 19001 quality management requirements") is False


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


def test_tutor_orchestrator_exposes_answer_quality_score():
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={
                "retrieval_output": {"hits": [{"chunk_id": "c1", "doc_id": "doc1", "score": 0.2}]},
                "retrieval_context": [_chunk("c1", "Critical speed amplifies rotor response.")],
            },
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={
                "answer": "## Conclusion\nCritical speed means resonance and is used for analysis.",
                "section_keys": ["conclusion"],
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1], confidence=0.9)],
        )
    )
    orchestrator = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
    )

    output = orchestrator.handle_query(
        "What is critical speed and what is it used for?",
        constraints={"scope": "in_scope"},
        task_id="t1",
    )

    quality = output.structured_result["answer_quality"]
    assert quality["schema_version"] == "phase5.answer_quality.v2"
    assert quality["citation_count"] == 1
    assert quality["subscores"]["evidence_relevance"] == 1.0
    assert quality["gate_status"] == "pass"
    assert quality["threshold"] == 0.75
    assert 0.0 <= quality["score"] <= 1.0


def test_tutor_orchestrator_attaches_answer_quality_on_insufficient_retrieval():
    # WHY: the quality score must surface on the degraded (early-return) path too --
    # a low score is the signal that the answer is unusable. _early_return previously
    # dropped answer_quality, so the operator showed no score exactly when retrieval
    # failed and the answer was worst.
    s2 = RecordingSkill(
        SkillOutput(
            status="insufficient",
            summary="S2 found no usable evidence.",
            structured_result={"retrieval_output": {"hits": []}, "retrieval_source": "file_chunks"},
            warnings=["No chunks matched the query."],
        )
    )
    orchestrator = TutorOrchestrator(retrieval_skill=s2)

    output = orchestrator.handle_query("critical speed", constraints={"scope": "in_scope"}, task_id="t1")

    assert output.status == "insufficient"
    quality = output.structured_result["answer_quality"]
    assert quality["schema_version"] == "phase5.answer_quality.v2"
    assert quality["faithfulness_status"] == "not_run"
    assert quality["gate_status"] == "blocked"
    assert "faithfulness_status=not_run" in quality["gate_reasons"]
    assert quality["citation_count"] == 0
    assert 0.0 <= quality["score"] <= 1.0
    assert output.structured_result["retrieval_source"] == "file_chunks"
    assert output.structured_result["retrieval_hits"] == 0


def test_query_coverage_counts_bilingual_term_families():
    # WHY: an English query answered from Chinese evidence must not score zero
    # coverage just because the surface tokens differ across languages. The bilingual
    # alias family ("critical speed" <-> "临界转速"/"共振") is the real coverage signal;
    # without this the quality score falsely tanks on correct cross-lingual answers.
    en_query = "What happens near critical speed in rotor vibration?"
    zh_answer = "达到固有频率时转子产生共振，也称为临界转速，此时振幅达到最大值。"
    assert _query_coverage(en_query, zh_answer) == 1.0
    assert _query_coverage(en_query, "Lubrication oil filter maintenance schedule.") < 0.5


def test_complete_sentence_ratio_ignores_evidence_tag_suffix():
    # WHY: every evidence-bound claim ends with a "(evidence: ...)" tag; a complete
    # claim sentence must not be read as a fragment because of that trailing tag.
    answer = (
        "1. 转子在临界转速产生共振，振幅达到最大值。 (evidence: doc_p1)\n"
        "2. 增大刚度会提高临界转速。 (evidence: doc_p2)"
    )
    assert _complete_sentence_ratio(answer) == 1.0


def test_complete_sentence_ratio_accepts_ocr_fullwidth_period():
    answer = "1. The measurement is feasible． (evidence: c1)"

    assert _complete_sentence_ratio(answer) == 1.0


def test_intent_completeness_rejects_keyword_repetition_without_mechanism():
    score, intent, required, covered = _intent_completeness(
        "Why do amplitude and phase change near critical speed?",
        "Critical speed amplitude phase. Critical speed amplitude phase.",
    )

    assert intent == "mechanism"
    assert score == 0.0
    assert required == ["causal_link", "excitation_natural_frequency_relation"]
    assert covered == []


def test_answer_quality_blocks_keyword_repetition_at_threshold_boundary():
    s2 = SkillOutput(
        status="ok",
        structured_result={
            "retrieval_output": {"hits": [{"chunk_id": "c1", "score": 1.0}]}
        },
    )
    answer = SkillOutput(
        status="ok",
        summary="Critical speed amplitude phase. Critical speed amplitude phase.",
        citations=[Citation(chunk_id="c1", doc_id="doc1")],
    )

    quality = _answer_quality(
        "Why do amplitude and phase change near critical speed?",
        s2_output=s2,
        answer_output=answer,
        faithfulness_status="ok",
    )

    assert quality["score"] == 0.75
    assert quality["subscores"]["completeness"] == 0.0
    assert quality["gate_status"] == "blocked"
    assert "completeness<1.0" in quality["gate_reasons"]


def test_answer_quality_blocks_complete_faithful_answer_below_threshold():
    s2 = SkillOutput(
        status="ok",
        structured_result={
            "retrieval_output": {"hits": [{"chunk_id": "different", "score": 1.0}]}
        },
    )
    answer = SkillOutput(
        status="ok",
        summary="Critical speed means resonance and is used for analysis",
        citations=[Citation(chunk_id="c1", doc_id="doc1")],
    )

    quality = _answer_quality(
        "What is critical speed and what is it used for?",
        s2_output=s2,
        answer_output=answer,
        faithfulness_status="ok",
    )

    assert quality["subscores"]["completeness"] == 1.0
    assert quality["score"] < quality["threshold"]
    assert quality["gate_status"] == "blocked"
    assert "score<0.75" in quality["gate_reasons"]


def test_intent_completeness_requires_formula_and_variable_definitions():
    score, intent, required, covered = _intent_completeness(
        "How is the influence vector calculated?",
        "Use the calibration weight and influence vector from equation 16-23.",
    )

    assert intent == "formula"
    assert score == 0.0
    assert required == ["equation", "variable_definitions"]
    assert covered == []


def test_intent_detection_prefers_primary_definition_and_workflow_forms():
    _score, definition_intent, _required, _covered = _intent_completeness(
        "What is order analysis and why is it used for variable-speed machinery?",
        "Order analysis is defined here.",
    )
    _score, workflow_intent, _required, _covered = _intent_completeness(
        "What measurement workflow should be used for vibration fault diagnosis?",
        "Collect and compare measurements.",
    )

    assert definition_intent == "definition"
    assert workflow_intent == "workflow"


def test_evidence_relevance_uses_cited_hit_rank_and_score_not_citation_confidence():
    s2 = SkillOutput(
        status="ok",
        structured_result={
            "retrieval_output": {
                "hits": [
                    {"chunk_id": "top", "score": 1.0},
                    {"chunk_id": "weak", "score": 0.1},
                ]
            }
        },
    )
    citations = [Citation(chunk_id="weak", doc_id="doc1", confidence=1.0)]

    relevance = _evidence_relevance(s2, citations)

    assert 0.0 < relevance < 0.5


def test_evidence_relevance_is_zero_without_citations():
    s2 = SkillOutput(
        status="ok",
        structured_result={
            "retrieval_output": {"hits": [{"chunk_id": "top", "score": 1.0}]}
        },
    )

    assert _evidence_relevance(s2, []) == 0.0


def test_general_intent_cannot_pass_completeness_by_answer_length():
    score, intent, required, covered = _intent_completeness(
        "Tell me about this rotating-machine observation",
        (
            "This is a long evidence-bound engineering answer with more than "
            "forty characters but no recognized request intent."
        ),
    )

    assert intent == "general"
    assert score == 0.0
    assert required == ["recognized_intent"]
    assert covered == []


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
