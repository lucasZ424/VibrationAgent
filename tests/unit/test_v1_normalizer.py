from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import TermSymbolUnitNormalizerSkill
from vibration_agent.skills.base import Skill


class RecordingSkill(Skill):
    name = "recording"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


def _s2_output() -> SkillOutput:
    return SkillOutput(
        status="ok",
        summary="S2 ok",
        structured_result={
            "retrieval_context": [
                {
                    "chunk_id": "c1",
                    "doc_id": "doc1",
                    "pages": [1],
                    "text": "The damping factor is reported at 12 Hertz [c1].",
                    "api_context": "[chunk_id=c1]\nThe damping factor is reported at 12 Hertz [c1].",
                }
            ],
            "retrieval_output": {"hits": [{"chunk_id": "c1", "doc_id": "doc1"}]},
        },
        citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
    )


def _s3_output() -> SkillOutput:
    return SkillOutput(
        status="ok",
        summary="S3 ok",
        structured_result={
            "language": "en",
            "answer": "The damping factor is reported at 12 Hertz [c1].",
            "claims": [{"text": "The damping factor is reported at 12 Hertz.", "chunk_id": "c1", "doc_id": "doc1"}],
            "synthesis_mode": "llm",
        },
        citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
    )


def test_v1_maps_terms_and_preserves_citation_anchors():
    output = TermSymbolUnitNormalizerSkill().run(
        SkillInput(
            task_id="t1",
            user_query="normalize",
            context={"text": "damping factor and zeta are aliases [c1]."},
        )
    )

    assert output.status == "ok"
    assert output.structured_result["normalized_text"] == "damping ratio and damping ratio are aliases [c1]."
    assert "[c1]" in output.structured_result["normalized_text"]


def test_v1_keeps_chinese_terms_in_chinese_text():
    output = TermSymbolUnitNormalizerSkill().run(
        SkillInput(
            task_id="t1",
            user_query="normalize",
            context={"text": "zeta 是 阻尼比 的常用符号 [c1]。"},
        )
    )

    text = output.structured_result["normalized_text"]
    assert "阻尼比 是 阻尼比" in text
    assert "damping ratio" not in text
    assert "[c1]" in text


def test_v1_passes_missing_terms_through():
    output = TermSymbolUnitNormalizerSkill().run(
        SkillInput(task_id="t1", user_query="normalize", context={"text": "unknown local phrase [c1]"})
    )

    assert output.structured_result["normalized_text"] == "unknown local phrase [c1]"
    assert output.structured_result["replacements"] == []


def test_v1_normalizes_si_spelling_without_engineering_unit_conversion():
    output = TermSymbolUnitNormalizerSkill().run(
        SkillInput(task_id="t1", user_query="normalize", context={"text": "12 Hertz, 7 rad/sec, and 3 mm/s [c1]"})
    )

    text = output.structured_result["normalized_text"]
    assert "12 Hz" in text
    assert "7 rad/s" in text
    assert "3 mm/s" in text
    assert "[c1]" in text


def test_v1_normalizes_s3_input_copy_and_v4_output_without_chain_entry():
    s2 = RecordingSkill(_s2_output())
    s3 = RecordingSkill(_s3_output())
    v2 = RecordingSkill(_s3_output())
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "Final damping factor answer at 12 Hertz [c1]."},
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )

    output = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
    ).handle_query("critical speed", constraints={"scope": "in_scope", "v1_input_enabled": True})

    s3_text = s3.calls[0].context["s2_result"]["structured_result"]["retrieval_context"][0]["text"]
    assert "damping ratio" in s3_text
    assert "12 Hz" in s3_text
    assert "damping factor" not in output.structured_result["answer"]
    assert "12 Hz [c1]" in output.structured_result["answer"]
    assert [step["skill"] for step in output.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
    ]


def test_v1_input_and_output_call_points_can_be_disabled_independently():
    s2 = RecordingSkill(_s2_output())
    s3 = RecordingSkill(_s3_output())
    v2 = RecordingSkill(_s3_output())
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={"answer": "Final damping factor answer at 12 Hertz [c1]."},
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )

    output = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
    ).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "v1_input_enabled": False, "v1_output_enabled": False},
    )

    s3_text = s3.calls[0].context["s2_result"]["structured_result"]["retrieval_context"][0]["text"]
    assert "damping factor" in s3_text
    assert "12 Hertz" in s3_text
    assert "Final damping factor answer at 12 Hertz [c1]." == output.structured_result["answer"]


def test_v1_output_does_not_flip_chinese_query_headers_to_english():
    s2 = RecordingSkill(_s2_output())
    s3 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S3 ok",
            structured_result={
                "language": "en",
                "answer": "The damping factor is reported at 12 Hertz [c1].",
                "claims": [{"text": "The damping factor is reported at 12 Hertz.", "chunk_id": "c1", "doc_id": "doc1"}],
                "synthesis_mode": "llm",
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )
    v2 = RecordingSkill(s3.output)

    output = TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
    ).handle_query("阻尼比如何影响振动？", constraints={"scope": "in_scope"})

    assert "## 结论" in output.structured_result["answer"]
    assert "## 证据" in output.structured_result["answer"]
    assert "## Conclusion" not in output.structured_result["answer"]
    assert "阻尼比" in output.structured_result["answer"]
    assert "damping ratio" not in output.structured_result["answer"]
    assert output.structured_result["chain"][-1]["skill"] == "v4_style"
