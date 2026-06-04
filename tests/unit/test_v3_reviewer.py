from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills import ReviewerSkill


def _payload(answer: str, *, sections: dict | None = None, query: str = "How does critical speed affect rotor vibration?") -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query=query,
        context={
            "upstream_result": SkillOutput(
                status="ok",
                summary="V4 ok",
                structured_result={
                    "answer": answer,
                    "sections": sections or {},
                    "section_keys": list((sections or {}).keys()),
                },
            ).model_dump(mode="python")
        },
    )


def _codes(output) -> set[str]:
    return {note["code"] for note in output.structured_result["reviewer_notes"]}


def test_v3_flags_missing_conclusion_for_extreme_answer_review():
    output = ReviewerSkill().run(
        _payload(
            "## Evidence\nCritical speed can amplify rotor vibration.\n\n## Premises\nEvidence is limited to cited chunks.",
            sections={
                "evidence": "Critical speed can amplify rotor vibration.",
                "premises": "Evidence is limited to cited chunks.",
            },
        )
    )

    assert output.status == "insufficient"
    assert "missing_conclusion" in _codes(output)


def test_v3_flags_off_topic_answer_against_original_query():
    output = ReviewerSkill().run(
        _payload(
            "## Conclusion\nDamping ratio controls decay rate.\n\n## Evidence\nDamping ratio appears in the evidence.\n\n## Premises\nOnly local evidence is used.",
            sections={
                "conclusion": "Damping ratio controls decay rate.",
                "evidence": "Damping ratio appears in the evidence.",
                "premises": "Only local evidence is used.",
            },
            query="How does critical speed affect rotor vibration?",
        )
    )

    assert output.status == "insufficient"
    assert "off_topic" in _codes(output)


def test_v3_flags_overclaiming_wording():
    output = ReviewerSkill().run(
        _payload(
            "## Conclusion\nCritical speed always eliminates rotor vibration risk.\n\n## Evidence\nCritical speed affects rotor response.\n\n## Premises\nOnly local evidence is used.",
            sections={
                "conclusion": "Critical speed always eliminates rotor vibration risk.",
                "evidence": "Critical speed affects rotor response.",
                "premises": "Only local evidence is used.",
            },
        )
    )

    assert output.status == "insufficient"
    assert "overclaiming" in _codes(output)


def test_v3_returns_ok_when_required_review_checks_pass():
    output = ReviewerSkill().run(
        _payload(
            "## Conclusion\nCritical speed can amplify rotor vibration.\n\n## Evidence\nCritical speed affects rotor response.\n\n## Premises\nOnly local evidence is used.",
            sections={
                "conclusion": "Critical speed can amplify rotor vibration.",
                "evidence": "Critical speed affects rotor response.",
                "premises": "Only local evidence is used.",
            },
        )
    )

    assert output.status == "ok"
    assert output.structured_result["reviewer_notes"] == []


def test_v3_recognizes_chinese_section_headers_for_extreme_review():
    output = ReviewerSkill().run(
        _payload(
            "## 结论\n临界转速会放大转子振动响应。\n\n## 证据\n临界转速影响转子响应。\n\n## 失效条件\n该判断只适用于已有证据覆盖的工况。",
            sections={},
            query="临界转速如何影响转子振动？",
        )
    )

    assert output.status == "ok"
    assert output.structured_result["reviewer_notes"] == []
