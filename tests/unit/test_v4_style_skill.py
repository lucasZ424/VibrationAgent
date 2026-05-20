from vibration_agent.agent import AgentSkillRegistry
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import OutputStyleSkill


def test_agent_skill_registry_loads_v4_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("v4_style")
    assert "OutputStyleSkill" in skill.body
    assert skill.references
    assert skill.scripts


def test_v4_renders_s3_answer_as_conclusion_and_preserves_evidence_and_assets():
    asset = {"asset_id": "fig1", "object_type": "figure", "asset_path": "data/extracted/fig1.png"}
    s3_result = SkillOutput(
        status="ok",
        summary="S3 qa ok: 1 claim(s) from 1 chunk(s).",
        structured_result={
            "language": "zh",
            "answer": "根据已检索证据，可以确定：\n1. 阻尼越大，振动衰减越快。（证据：c1）",
            "claims": [
                {
                    "text": "阻尼越大，振动衰减越快。",
                    "chunk_id": "c1",
                    "doc_id": "doc1",
                    "pages": [3],
                    "evidence_type": "documented",
                    "asset_ids": ["fig1"],
                }
            ],
            "assets": [asset],
        },
        citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[3], confidence=0.8)],
    )
    payload = SkillInput(task_id="t1", user_query="阻尼如何影响振动？", context={"s3_result": s3_result})

    output = OutputStyleSkill().run(payload)

    assert output.status == "ok"
    assert output.citations == s3_result.citations
    assert output.structured_result["language"] == "zh"
    assert output.structured_result["section_keys"] == ["conclusion", "evidence"]
    assert output.structured_result["assets"] == [asset]
    answer = output.structured_result["answer"]
    assert "## 结论" in answer
    assert "## 证据" in answer
    assert "## 工程意义" not in answer
    assert "c1 (doc1, 第3页, 已记录): 阻尼越大，振动衰减越快。 [资产: fig1]" in answer
    assert "confidence=" not in answer
    assert "documented" not in answer


def test_v4_renders_english_sections_in_fixed_order_and_omits_empty_sections():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "answer": "Critical speed amplifies rotor response. (evidence: c1)",
                    "sections": {
                        "next_steps": "Check the speed sweep data near the suspected resonance.",
                        "premises": "Use only when the cited run-up data is representative.",
                        "engineering_meaning": "The operating band may need separation from resonance.",
                        "minimal_model": "Single-degree resonance approximation from cited text.",
                    },
                    "claims": [
                        {
                            "text": "Critical speed amplifies rotor response.",
                            "chunk_id": "c1",
                            "doc_id": "doc1",
                            "pages": [7],
                        }
                    ],
                },
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [7], "confidence": 1.0}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["language"] == "en"
    assert output.structured_result["section_keys"] == [
        "conclusion",
        "engineering_meaning",
        "premises",
        "minimal_model",
        "next_action",
        "evidence",
    ]
    answer = output.structured_result["answer"]
    assert answer.index("## Conclusion") < answer.index("## Engineering Meaning") < answer.index("## Premises")
    assert answer.index("## Premises") < answer.index("## Minimal Model / Formula") < answer.index("## Next Actions")
    assert "## Failure Conditions / Common Pitfalls" not in answer
    assert "## 结论" not in answer
    assert "c1 (doc1, p.7, documented): Critical speed amplifies rotor response." in answer
    assert output.citations[0].chunk_id == "c1"


def test_v4_compacts_page_ranges_in_evidence_lines():
    payload = SkillInput(
        task_id="t1",
        user_query="run-up",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "answer": "The speed sweep spans the resonance region.",
                    "claims": [
                        {
                            "text": "The speed sweep spans the resonance region.",
                            "chunk_id": "c1",
                            "doc_id": "doc1",
                            "pages": list(range(4, 18)),
                        }
                    ],
                },
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": list(range(4, 18))}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    assert "c1 (doc1, pp.4-17, documented)" in output.structured_result["answer"]


def test_v4_accepts_direct_context_without_s3_result_key():
    payload = SkillInput(
        task_id="t1",
        user_query="direct",
        context={
            "language": "en",
            "answer": "Direct upstream content.",
            "claims": [{"text": "Direct upstream content.", "chunk_id": "c1", "doc_id": "doc1", "pages": [1]}],
        },
    )

    output = OutputStyleSkill().run(payload)

    assert output.status == "ok"
    assert "## Conclusion" in output.structured_result["answer"]
    assert output.citations[0].chunk_id == "c1"


def test_v4_drops_malformed_citation_and_falls_back_to_claim_citation():
    payload = SkillInput(
        task_id="t1",
        user_query="bad citation",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "answer": "A cited claim exists.",
                    "claims": [{"text": "A cited claim exists.", "chunk_id": "c1", "doc_id": "doc1", "pages": [2]}],
                },
                "citations": [{"chunk_id": "broken"}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    assert output.status == "ok"
    assert output.citations[0].chunk_id == "c1"
    assert any("dropped malformed citation" in warning for warning in output.warnings)


def test_v4_summary_status_prefix_is_not_rendered_as_conclusion():
    payload = SkillInput(task_id="t1", user_query="anything", context={"summary": "S2 retrieval ok: 3 hit(s)."})

    output = OutputStyleSkill().run(payload)

    assert output.status == "insufficient"
    assert output.structured_result["section_keys"] == []


def test_v4_returns_insufficient_without_renderable_content_even_if_upstream_was_ok():
    payload = SkillInput(task_id="t1", user_query="anything", context={"s3_result": {"status": "ok"}})

    output = OutputStyleSkill().run(payload)

    assert output.status == "insufficient"
    assert output.structured_result["section_keys"] == []
    assert "No renderable upstream content" in output.warnings[-1]