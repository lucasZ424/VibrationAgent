from vibration_agent.agent import AgentSkillRegistry
from vibration_agent.schemas import SkillInput
from vibration_agent.skills import QASummarySkill


def _evidence(
    chunk_id: str,
    text: str,
    *,
    doc_id: str = "doc1",
    pages: list[int] | None = None,
    topic: str | None = None,
    section_key: str | None = None,
    confidence: float = 0.9,
    language: str | None = None,
    assets: list[dict] | None = None,
) -> dict:
    metadata = {"section_key": section_key} if section_key else {}
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "pages": pages or [1],
        "source_type": "book",
        "topic": topic,
        "score": 1.0,
        "confidence": confidence,
        "language": language,
        "text": text,
        "assets": assets or [],
        "metadata": metadata,
    }


def test_agent_skill_registry_loads_s3_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("s3_qa_summary")
    assert "QASummarySkill" in skill.body
    assert skill.references
    assert skill.scripts


def test_s3_without_evidence_returns_insufficient():
    output = QASummarySkill().run(SkillInput(task_id="t1", user_query="阻尼比是什么？"))

    assert output.status == "insufficient"
    assert output.structured_result["mode"] == "qa"
    assert "No usable retrieval evidence" in output.warnings[-1]


def test_s3_qa_empty_query_uses_retrieved_evidence_by_confidence():
    payload = SkillInput(
        task_id="t1",
        user_query="",
        context={
            "retrieval_context": [
                _evidence("c1", "低置信度证据。", confidence=0.1),
                _evidence("c2", "高置信度证据。", confidence=0.9),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["mode"] == "qa"
    assert output.structured_result["claims"][0]["chunk_id"] == "c2"
    assert [claim["chunk_id"] for claim in output.structured_result["claims"]] == ["c2", "c1"]
    assert [citation.chunk_id for citation in output.citations] == ["c2", "c1"]

def test_s3_qa_uses_only_retrieved_evidence_and_cites_claims():
    payload = SkillInput(
        task_id="t1",
        user_query="阻尼比如何影响自由振动？",
        context={
            "retrieval_context": [
                _evidence("c1", "阻尼比 zeta 控制自由振动的衰减速度。阻尼越大，振动衰减越快。", pages=[3]),
                _evidence("c2", "临界转速附近转子响应会被放大。", pages=[8]),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.summary.startswith("S3 qa ok: ")
    assert output.structured_result["task_id"] == "t1"
    assert output.structured_result["mode"] == "qa"
    assert output.structured_result["language"] == "zh"
    assert "证据：c1" in output.structured_result["answer"]
    assert "documented" not in output.structured_result["answer"]
    assert output.citations[0].chunk_id == "c1"
    assert output.citations[0].pages == [3]
    assert output.structured_result["unsupported_claims"] == []


def test_s3_accepts_s2_result_handoff_shape_and_relative_confidence():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed summary",
        context={
            "s2_result": {
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [4], "confidence": 1.0}],
                "structured_result": {
                    "retrieval_context": [
                        _evidence("c1", "Critical speed is where rotor response is amplified.", pages=[4], confidence=0.02)
                    ]
                },
            }
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["language"] == "en"
    assert "evidence: c1" in output.structured_result["answer"]
    assert output.citations[0].confidence == 1.0


def test_s3_uses_retrieval_results_field_path():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed",
        retrieval_results=[_evidence("c1", "Critical speed amplifies rotor response.", pages=[7])],
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.citations[0].chunk_id == "c1"


def test_s3_warns_when_only_bare_hits_are_supplied():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed",
        context={
            "s2_result": {
                "structured_result": {
                    "retrieval_output": {
                        "hits": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [1], "score": 0.02}]
                    }
                }
            }
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "insufficient"
    assert any("retrieval hits without text" in warning for warning in output.warnings)


def test_s3_whole_doc_summary_filters_doc_id_and_sorts_by_score():
    payload = SkillInput(
        task_id="t1",
        user_query="整本文档总结",
        constraints={"mode": "whole_doc_summary", "doc_id": "doc1"},
        context={
            "retrieval_context": [
                _evidence("c1", "弱相关内容。", doc_id="doc1", pages=[1], confidence=0.1),
                _evidence("c2", "转子不平衡会产生一倍频同步响应。", doc_id="doc1", pages=[2], confidence=0.9),
                _evidence("c3", "其他文档内容。", doc_id="doc2", pages=[9], confidence=1.0),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["mode"] == "whole_doc_summary"
    assert {citation.doc_id for citation in output.citations} == {"doc1"}
    assert output.structured_result["claims"][0]["chunk_id"] == "c2"
    assert "c3" not in output.structured_result["answer"]


def test_s3_section_summary_filters_section_key():
    payload = SkillInput(
        task_id="t1",
        user_query="总结本节",
        constraints={"mode": "section_summary", "section_key": "s2"},
        context={
            "retrieval_context": [
                _evidence("c1", "第一节讨论不平衡。", section_key="s1"),
                _evidence("c2", "第二节讨论临界转速。", section_key="s2"),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["mode"] == "section_summary"
    assert [citation.chunk_id for citation in output.citations] == ["c2"]
    assert "c1" not in output.structured_result["answer"]


def test_s3_section_summary_topic_filter_accepts_canonical_underscore():
    payload = SkillInput(
        task_id="t1",
        user_query="总结本节",
        constraints={"mode": "section_summary", "topic": "rotor_unbalance"},
        context={
            "retrieval_context": [
                _evidence("c1", "不平衡会产生一倍频响应。", topic="Rotor Unbalance"),
                _evidence("c2", "轴承故障需要包络分析。", topic="bearing_fault"),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert [citation.chunk_id for citation in output.citations] == ["c1"]


def test_s3_section_filter_with_no_matching_evidence_is_insufficient():
    payload = SkillInput(
        task_id="t1",
        user_query="总结本节",
        constraints={"mode": "section_summary", "section_key": "missing"},
        context={"retrieval_context": [_evidence("c1", "第一节讨论不平衡。", section_key="s1")]},
    )

    output = QASummarySkill().run(payload)

    assert output.status == "insufficient"
    assert output.structured_result["evidence_count"] == 0


def test_s3_deduplicates_citations_for_multiple_claims_from_same_chunk():
    payload = SkillInput(
        task_id="t1",
        user_query="阻尼 振动",
        context={"retrieval_context": [_evidence("c1", "阻尼影响振动。阻尼越大衰减越快。", pages=[5])]},
        constraints={"max_claims": 2},
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert len(output.structured_result["claims"]) == 2
    assert [citation.chunk_id for citation in output.citations] == ["c1"]


def test_s3_propagates_assets_to_claims_and_top_level_assets():
    asset = {"asset_id": "fig1", "object_type": "figure", "page_no": 3, "asset_path": "data/extracted/fig1.png"}
    payload = SkillInput(
        task_id="t1",
        user_query="orbit figure",
        context={"retrieval_context": [_evidence("c1", "The orbit plot shows forward precession.", assets=[asset])]},
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["claims"][0]["asset_ids"] == ["fig1"]
    assert output.structured_result["assets"] == [asset]


def test_s3_language_hint_overrides_ascii_header_bias():
    payload = SkillInput(
        task_id="t1",
        user_query="summary",
        context={
            "retrieval_context": [
                _evidence("c1", "[chunk_id=c1; doc_id=doc1; pages=1-1]\n阻尼影响振动。", language="zh")
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["language"] == "zh"


def test_s3_runner_injection_controls_answer_generation():
    def runner(rows, payload, mode, language):
        assert mode == "qa"
        assert language in {"zh", "en"}
        return "custom answer", [{"text": "custom", "evidence": rows[0], "assets": [], "score": 1.0, "order": (0, 0)}], []

    payload = SkillInput(
        task_id="t1",
        user_query="anything",
        context={"retrieval_context": [_evidence("c1", "Evidence text.")]},
    )

    output = QASummarySkill(runner=runner).run(payload)

    assert output.status == "ok"
    assert output.structured_result["answer"] == "custom answer"
    assert output.summary == "S3 qa ok: 1 claim(s) from 1 chunk(s)."

