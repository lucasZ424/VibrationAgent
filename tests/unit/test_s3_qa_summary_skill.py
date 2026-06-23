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


def test_s3_domain_focus_does_not_fill_order_analysis_answer_with_torsion_standard_text():
    # WHY: broad shared vibration terms must not displace the query's more specific domain phrase.
    payload = SkillInput(
        task_id="domain-focus",
        user_query="阶比分析在旋转机械扭振测量中的作用是什么？",
        context={
            "retrieval_context": [
                _evidence("paper", "阶比分析用于旋转机械升降速过程的非平稳信号分析。", language="zh"),
                _evidence("standard", "本部分规定了旋转机械扭振标准的适用要求。", language="zh"),
            ]
        },
        constraints={"max_claims": 4},
    )

    output = QASummarySkill().run(payload)

    assert [claim["chunk_id"] for claim in output.structured_result["claims"]] == ["paper"]


def test_s3_standard_scope_query_prefers_scope_claims_over_shared_domain_terms():
    # WHY: a standard scope question must not be answered by higher-overlap mechanism text.
    payload = SkillInput(
        task_id="scope",
        user_query="GB/T 33199.1-2016 对汽轮发电机组轴系扭振的适用范围是什么？",
        context={
            "retrieval_context": [
                _evidence("mechanism", "透平发电机组轴系扭振由发电机气隙扭矩变化激起。"),
                _evidence(
                    "scope",
                    "本部分适用于陆地安装、额定功率大于50MW的电站透平发电机组。"
                    "凡是注日期的引用文件，仅注日期的版本适用于本文件。"
                    "ISO 2041 界定的术语和定义适用于本文件。",
                ),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert [claim["chunk_id"] for claim in output.structured_result["claims"]] == ["scope"]
    assert len(output.structured_result["claims"]) == 1


def test_s3_english_standard_scope_query_recognizes_specification_clause():
    # WHY: English standards usually state scope with "This document specifies", not "applies to".
    payload = SkillInput(
        task_id="scope-en",
        user_query="What is the scope of ISO 22266-1?",
        context={
            "retrieval_context": [
                _evidence("mechanism", "Torsional vibration is excited by air-gap torque.", language="en"),
                _evidence(
                    "scope",
                    "This document specifies requirements for land-based turbine generator sets.",
                    language="en",
                ),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert [claim["chunk_id"] for claim in output.structured_result["claims"]] == ["scope"]


def test_s3_does_not_treat_gb_standard_prose_as_an_uppercase_structural_label():
    # WHY: a GB/T-prefixed scope sentence is evidence, not a document-code heading.
    payload = SkillInput(
        task_id="scope-prose",
        user_query="GB/T 33199.1-2016 的适用范围是什么？",
        context={
            "retrieval_context": [
                _evidence(
                    "scope",
                    "GB/T33199的本部分规定了透平发电机组耦合轴系的扭振准\n则，尤其适用于并网运行机组。",
                )
            ]
        },
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"].startswith("GB/T33199的本部分规定")


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


def test_s3_critical_speed_outcome_question_rejects_definition_only_evidence():
    # WHY: a user asking what happens at/after critical speed needs mechanism or
    # response evidence; returning a definition note is worse than insufficient.
    payload = SkillInput(
        task_id="critical-outcome",
        user_query="旋转机械到达临界转速后会发生什么？",
        context={
            "retrieval_context": [
                _evidence("def", "注：ISO2041中给出了相同的共振转速/临界转速定义。", language="zh")
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "insufficient"
    assert "outcome" in output.warnings[-1]


def test_s3_critical_speed_outcome_question_prefers_response_evidence():
    # WHY: when both definition and response evidence are retrieved, answer with
    # the engineering effect that the user asked about.
    payload = SkillInput(
        task_id="critical-outcome",
        user_query="旋转机械到达临界转速后会发生什么？",
        context={
            "retrieval_context": [
                _evidence("def", "注：ISO2041中给出了相同的共振转速/临界转速定义。", language="zh"),
                _evidence("effect", "临界转速附近转子振动响应会被放大，振幅明显增大。", language="zh"),
            ]
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert [claim["chunk_id"] for claim in output.structured_result["claims"]] == ["effect"]


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


def test_s3_does_not_warn_about_bare_hits_when_s2_provides_retrieval_context():
    payload = SkillInput(
        task_id="t1",
        user_query="critical speed",
        context={
            "s2_result": {
                "structured_result": {
                    "retrieval_context": [
                        _evidence("c1", "Critical speed amplifies rotor response.", pages=[4])
                    ],
                    "retrieval_output": {
                        "hits": [{"chunk_id": "c1", "doc_id": "doc1", "pages": [4], "score": 0.02}]
                    },
                }
            }
        },
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert not any("without usable chunk text" in warning for warning in output.warnings)


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


def test_s3_reflows_wrapped_cjk_prose_before_selecting_claims():
    # WHY: PDF/OCR visual line wrapping must not surface incomplete clauses as claims.
    text = (
        "把Orbit 60状态监测模块（CMM）作为系统的只读访问接入点，为用户提供了一种通过\n"
        "办公网络或其他外部系统即可获取机器状态数据的网络安全措施；"
    )
    payload = SkillInput(
        task_id="t1",
        user_query="Orbit 60如何获取机器状态数据？",
        context={"retrieval_context": [_evidence("c1", text, language="zh")]},
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["claims"][0]["text"] == (
        "把Orbit 60状态监测模块（CMM）作为系统的只读访问接入点，为用户提供了一种通过"
        "办公网络或其他外部系统即可获取机器状态数据的网络安全措施；"
    )


def test_s3_uses_typed_segments_to_skip_title_blocks():
    # WHY: a title containing every query term must not outrank the body evidence.
    row = _evidence(
        "c1",
        "Orbit 60 System Overview\n\nOrbit 60 continuously monitors machinery.",
        language="en",
    )
    title = "Orbit 60 System Overview"
    label = "Selection Guide"
    body = "Orbit 60 continuously monitors machinery."
    row["text"] = f"{title}\n\n{label}\n\n{body}"
    row["metadata"]["text_segments"] = [
        {"page_no": 1, "start": 0, "end": len(title), "block_type": "title"},
        {
            "page_no": 1,
            "start": len(title) + 2,
            "end": len(title) + 2 + len(label),
            "block_type": "body",
            "layout_role": "label",
        },
        {
            "page_no": 1,
            "start": len(title) + 2 + len(label) + 2,
            "end": len(title) + 2 + len(label) + 2 + len(body),
            "block_type": "body",
        },
    ]
    payload = SkillInput(
        task_id="layout",
        user_query="What does the Orbit 60 system monitor?",
        context={"retrieval_context": [row]},
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"] == "Orbit 60 continuously monitors machinery."


def test_s3_skips_typed_and_legacy_bibliography_blocks():
    # WHY: cited-paper titles inside bibliography entries are not answer evidence claims.
    body = "阶比分析用于旋转机械非平稳信号分析。"
    reference = "[7] 张某等. 旋转机械阶比分析技术中采样方式的研究."
    row = _evidence("typed", f"{reference}\n\n{body}", language="zh")
    row["metadata"]["text_segments"] = [
        {
            "page_no": 7,
            "start": 0,
            "end": len(reference),
            "block_type": "body",
            "layout_role": "bibliography",
        },
        {
            "page_no": 7,
            "start": len(reference) + 2,
            "end": len(reference) + 2 + len(body),
            "block_type": "body",
        },
    ]
    payload = SkillInput(
        task_id="bibliography",
        user_query="阶比分析有什么作用？",
        context={
            "retrieval_context": [
                row,
                _evidence("legacy", f"{reference}\n\n{body}", language="zh"),
            ]
        },
        constraints={"max_claims": 4},
    )

    output = QASummarySkill().run(payload)

    assert all("采样方式的研究" not in claim["text"] for claim in output.structured_result["claims"])
    assert {claim["text"] for claim in output.structured_result["claims"]} == {body}


def test_s3_excludes_reference_sections_and_cross_chunk_company_suffix_orphans():
    # WHY: reference-section titles and a leading 公司 suffix are not standalone claims.
    reference_row = _evidence(
        "references",
        "Order Analysis Technique of Rotating Machinery.",
        language="en",
    )
    reference_row["metadata"]["section_title"] = "参考文献"
    payload = SkillInput(
        task_id="reference-section",
        user_query="阶比分析有什么作用？",
        context={
            "retrieval_context": [
                reference_row,
                _evidence(
                    "body",
                    "司LabVIEW 的Order Analysis Toolset[28]。\n\n阶比分析用于提取旋转机械阶比分量。",
                    language="zh",
                ),
            ]
        },
        constraints={"max_claims": 4},
    )

    output = QASummarySkill().run(payload)

    assert [claim["text"] for claim in output.structured_result["claims"]] == ["阶比分析用于提取旋转机械阶比分量。"]


def test_s3_legacy_layout_blocks_do_not_overjoin_labels_with_body():
    # WHY: old chunks lack typed segments but retain blank-line block boundaries.
    text = (
        "ORBIT 60系列系统概述\n\n选型样本\n\n本特利内华达机械状态监测\n"
        "137M5182 修订版K\n\n涵盖全厂• 一体化系统\n\n"
        "Orbit 60系列保护与状态监测系统为全厂关键设备提供连续在线监测和保护。"
    )
    payload = SkillInput(
        task_id="legacy-layout",
        user_query="Orbit 60提供什么监测功能？",
        context={"retrieval_context": [_evidence("c1", text, language="zh")]},
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"] == (
        "Orbit 60系列保护与状态监测系统为全厂关键设备提供连续在线监测和保护。"
    )


def test_s3_legacy_short_cjk_label_is_skipped_but_short_assertion_is_kept():
    # WHY: compact brochure labels are not claims, while short engineering assertions remain evidence.
    payload = SkillInput(
        task_id="short-label",
        user_query="状态监测有什么作用？",
        context={
            "retrieval_context": [
                _evidence("c1", "本特利内华达机械状态监测\n\n状态监测用于识别设备风险。", language="zh")
            ]
        },
        constraints={"max_claims": 2},
    )

    output = QASummarySkill().run(payload)

    assert [claim["text"] for claim in output.structured_result["claims"]] == ["状态监测用于识别设备风险。"]


def test_s3_legacy_cjk_tight_split_repairs_only_punctuated_continuation():
    # WHY: preserving layout boundaries must not reintroduce the observed 准/则，orphan.
    text = "本部分规定了透平发电机组耦合轴系的扭振准\n\n则，尤其适用于并网运行机组。"
    payload = SkillInput(
        task_id="tight-cjk",
        user_query="GB/T 33199 的适用范围是什么？",
        context={"retrieval_context": [_evidence("c1", text, language="zh")]},
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"].startswith("本部分规定了")
    assert "扭振准则，" in output.structured_result["claims"][0]["text"]


def test_s3_legacy_long_body_blocks_rejoin_without_absorbing_short_labels():
    # WHY: PyMuPDF may split one sentence into adjacent body blocks stored with blank lines.
    text = (
        "网络安全• 数据隔离\n\n"
        "把Orbit 60状态监测模块作为只读访问接入点，为用户提供了一种通过\n\n"
        "办公网络或其他外部系统即可获取机器状态数据的网络安全措施；"
    )
    payload = SkillInput(
        task_id="body-blocks",
        user_query="Orbit 60如何获取机器状态数据？",
        context={"retrieval_context": [_evidence("c1", text, language="zh")]},
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"] == (
        "把Orbit 60状态监测模块作为只读访问接入点，为用户提供了一种通过"
        "办公网络或其他外部系统即可获取机器状态数据的网络安全措施；"
    )


def test_s3_preserves_structural_boundaries_and_does_not_rank_heading_as_claim():
    # WHY: reflow may join visual lines, but section markers/headings are not answer claims.
    payload = SkillInput(
        task_id="t1",
        user_query="禁止频率范围是什么？",
        context={
            "retrieval_context": [
                _evidence(
                    "c1",
                    "3.15\n禁止频率范围\n轴系固有频率应避开线路频率和二倍线路频率。",
                    language="zh",
                )
            ]
        },
        constraints={"max_claims": 2},
    )

    output = QASummarySkill().run(payload)

    assert output.status == "ok"
    claim_texts = [claim["text"] for claim in output.structured_result["claims"]]
    assert "3.15" not in claim_texts
    assert "禁止频率范围" not in claim_texts
    assert "轴系固有频率应避开线路频率和二倍线路频率。" in claim_texts


def test_s3_reflows_hyphenated_english_line_wrap():
    payload = SkillInput(
        task_id="t1",
        user_query="What does vibration monitoring measure?",
        context={
            "retrieval_context": [
                _evidence("c1", "The system supports vibra-\ntion monitoring.", language="en")
            ]
        },
        constraints={"max_claims": 1},
    )

    output = QASummarySkill().run(payload)

    assert output.structured_result["claims"][0]["text"] == "The system supports vibration monitoring."


def test_s3_reflow_never_joins_across_chunk_rows():
    payload = SkillInput(
        task_id="t1",
        user_query="Orbit network access",
        context={
            "retrieval_context": [
                _evidence("c1", "Orbit provides network", language="en"),
                _evidence("c2", "access for monitoring.", language="en"),
            ]
        },
        constraints={"max_claims": 2},
    )

    output = QASummarySkill().run(payload)

    claim_texts = [claim["text"] for claim in output.structured_result["claims"]]
    assert "Orbit provides network access for monitoring." not in claim_texts
    assert {claim["chunk_id"] for claim in output.structured_result["claims"]} == {"c1"}


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

