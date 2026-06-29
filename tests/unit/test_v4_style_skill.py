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
    assert "doc1 (第3页, 已记录): 阻尼越大，振动衰减越快。 [资产: fig1]" in answer
    assert "confidence=" not in answer
    assert "documented" not in answer


def test_v4_preserves_localized_chinese_engineering_sections():
    source = SkillOutput(
        status="ok",
        structured_result={
            "language": "zh",
            "answer": "临界转速附近转子响应会被放大。（证据：c1）",
            "engineering_meaning": "工程意义仅限于所引证据：临界转速附近转子响应会被放大。",
            "premises": "仅适用于检索到的证据块：c1。",
            "failure_modes": "请勿超出所引工况、单位或数值范围进行外推。",
            "next_action": "在应用阈值、维护措施或模型假设前，请先核对所引证据块。",
            "claims": [
                {"text": "临界转速附近转子响应会被放大。", "chunk_id": "c1", "doc_id": "doc1", "pages": [3]}
            ],
        },
        citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[3])],
    )

    output = OutputStyleSkill().run(
        SkillInput(task_id="t1", user_query="临界转速有什么影响？", context={"s3_result": source})
    )

    answer = output.structured_result["answer"]
    assert "## 工程意义" in answer
    assert "## 适用前提" in answer
    assert "Engineering implication" not in answer
    assert "Apply this only" not in answer
    assert "Do not extrapolate" not in answer
    assert "Inspect the cited chunks" not in answer


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
    assert "doc1 (p.7, documented): Critical speed amplifies rotor response." in answer
    assert output.citations[0].chunk_id == "c1"


def test_v4_evidence_prefers_filename_over_internal_slug():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "answer": "Critical speed amplifies rotor response.",
                    "claims": [
                        {
                            "text": "Critical speed amplifies rotor response.",
                            "chunk_id": "doc_slug_p0001_00001",
                            "doc_id": "doc_slug",
                            "pages": [12],
                            "source_filename": "rotor-handbook.pdf",
                        }
                    ],
                },
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    answer = output.structured_result["answer"]
    assert "rotor-handbook.pdf (p.12, documented)" in answer
    assert "doc_slug_p0001_00001" not in answer
    assert output.citations[0].source_filename == "rotor-handbook.pdf"


def test_v4_preserves_formula_render_contract_without_rendering_markup_in_answer():
    # WHY: V4 is the final answer formatter; Obj11 formula metadata is for
    # clients, not a license to inject markup into the plain-text answer.
    payload = SkillInput(
        task_id="t1",
        user_query="formula",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "minimal_model": "F = k x",
                    "claims": [{"text": "The cited formula is F = k x.", "chunk_id": "c1", "doc_id": "doc1"}],
                    "formula_renders": [
                        {
                            "formula_id": "f1",
                            "plain_text": "F = k x",
                            "latex": r"F = k x",
                            "status": "renderable",
                            "source": "asset",
                            "source_asset_id": "f1",
                        }
                    ],
                },
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [2]}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    assert output.status == "ok"
    assert output.citations[0].chunk_id == "c1"
    assert output.structured_result["formula_renders"][0]["schema_version"] == "p4.formula_render.v1"
    assert output.structured_result["formula_renders"][0]["status"] == "renderable"
    assert "## Minimal Model / Formula\nF = k x" in output.structured_result["answer"]


def test_v4_invalid_formula_markup_degrades_and_keeps_citations():
    # WHY: render metadata may be supplied by upstream skills; V4 must fail loud
    # on invalid markup while keeping the citation-bound plain-text answer.
    payload = SkillInput(
        task_id="t1",
        user_query="formula",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "minimal_model": "F = k x",
                    "claims": [{"text": "The cited formula is F = k x.", "chunk_id": "c1", "doc_id": "doc1"}],
                    "formula_renders": [
                        {
                            "formula_id": "f1",
                            "plain_text": "F = k x",
                            "latex": r"F = k {x",
                        },
                        {
                            "formula_id": "f2",
                            "plain_text": "F/k",
                            "latex": r"\frac{F}",
                        },
                        {
                            "formula_id": "f3",
                            "plain_text": "x",
                            "latex": r"\begin{matrix}x\end{array}",
                        },
                    ],
                },
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [2]}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    render = output.structured_result["formula_renders"][0]
    assert output.citations[0].chunk_id == "c1"
    assert render["status"] == "invalid_markup"
    assert render["latex"] is None
    assert render["plain_text"] == "F = k x"
    assert output.structured_result["formula_renders"][1]["status"] == "invalid_markup"
    assert output.structured_result["formula_renders"][2]["status"] == "invalid_markup"
    assert any("invalid LaTeX formula markup" in warning for warning in output.warnings)
    assert "F = k x" in output.structured_result["answer"]


def test_v4_builds_mathml_formula_render_from_formula_asset():
    # WHY: clients can render MathML from structured metadata while CLI/API
    # answer text remains a normal engineering section.
    payload = SkillInput(
        task_id="t1",
        user_query="formula",
        context={
            "s3_result": {
                "status": "ok",
                "structured_result": {
                    "language": "en",
                    "minimal_model": "x",
                    "claims": [
                        {
                            "text": "The displacement term is x.",
                            "chunk_id": "c1",
                            "doc_id": "doc1",
                            "assets": [{"asset_id": "f1", "object_type": "formula"}],
                        }
                    ],
                    "assets": [
                        {
                            "asset_id": "f1",
                            "object_type": "formula",
                            "text_preview": "x",
                            "mathml": "<math><mi>x</mi></math>",
                        }
                    ],
                },
                "citations": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [2]}],
            }
        },
    )

    output = OutputStyleSkill().run(payload)

    render = output.structured_result["formula_renders"][0]
    assert render["status"] == "renderable"
    assert render["mathml"] == "<math><mi>x</mi></math>"
    assert "## Minimal Model / Formula\nx" in output.structured_result["answer"]


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

    assert "doc1 (pp.4-17, documented)" in output.structured_result["answer"]


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
