import json
import sys
from pathlib import Path

from vibration_agent.orchestrator import TutorOrchestrator, handle_query, is_in_scope
from vibration_agent.orchestrator.tutor import _token_cost
from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills import (
    CitationCheckSkill,
    OutputStyleSkill,
    QASummarySkill,
    RetrievalSkill,
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
        orchestrator.normalizer_skill,
        orchestrator.citation_check_skill,
        orchestrator.style_skill,
    ]
    active_names = {skill.name for skill in active_skills}
    deferred_prefixes = ("s4_", "s5_", "s6_", "s7_", "s8_", "v3_")

    assert type(orchestrator.retrieval_skill) is RetrievalSkill
    assert type(orchestrator.qa_summary_skill) is QASummarySkill
    assert type(orchestrator.normalizer_skill) is TermSymbolUnitNormalizerSkill
    assert type(orchestrator.citation_check_skill) is CitationCheckSkill
    assert type(orchestrator.style_skill) is OutputStyleSkill
    assert active_names == {
        "s2_retrieval",
        "s3_qa_summary",
        "v1_term_symbol_unit_normalizer",
        "v2_citation_check",
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
        "v2_citation_check",
        "v4_style",
    ]
    assert output.structured_result["chain"][0]["status"] == "ok"
    assert output.structured_result["chain"][1]["status"] == "ok"
    assert "## 结论" in output.structured_result["answer"]
    assert "## 证据" in output.structured_result["answer"]
    assert output.structured_result["v4"]["answer"] == output.structured_result["answer"]
    assert set(output.structured_result["skill_results"]) == {"s2", "s3", "v2", "v4"}
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


def test_tutor_token_cost_reads_s3_skill_result_for_qa_logs():
    output = SkillOutput(
        status="ok",
        structured_result={"skill_results": {"s3": {"token_cost": 17}}},
    )

    assert _token_cost(output) == 17
