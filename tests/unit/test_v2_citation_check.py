from __future__ import annotations

from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills import CitationCheckSkill
from vibration_agent.skills.base import Skill


def _row(chunk_id: str = "c1", text: str = "Critical speed amplifies rotor response.") -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": "doc1",
        "pages": [1],
        "text": text,
        "score": 1.0,
    }


def _s2(rows: list[dict] | None = None) -> dict:
    rows = rows or [_row()]
    return {
        "status": "ok",
        "structured_result": {
            "retrieval_context": rows,
            "retrieval_output": {"hits": [{"chunk_id": row["chunk_id"], "doc_id": row["doc_id"]} for row in rows]},
        },
    }


def _s3(*, answer: str, claims: list[dict], citations: list[dict] | None = None, mode: str = "llm") -> dict:
    return {
        "status": "ok",
        "structured_result": {
            "language": "en",
            "answer": answer,
            "claims": claims,
            "synthesis_mode": mode,
            "unsupported_claims": [],
        },
        "citations": citations or [{"chunk_id": "c1", "doc_id": "doc1", "pages": [1], "confidence": 1.0}],
    }


def _payload(s3: dict, *, s2: dict | None = None) -> SkillInput:
    return SkillInput(
        task_id="t1",
        user_query="critical speed",
        context={"s2_result": s2 or _s2(), "s3_result": s3},
    )


def test_v2_accepts_claims_citing_visible_retrieved_chunks():
    s3 = _s3(
        answer="Critical speed amplifies rotor response [c1].",
        claims=[{"text": "Critical speed amplifies rotor response.", "chunk_id": "c1", "doc_id": "doc1", "pages": [1]}],
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "ok"
    assert output.structured_result["unsupported_claims"] == []
    assert output.citations[0].chunk_id == "c1"


def test_v2_blocks_references_to_chunks_not_visible_to_s2():
    s3 = _s3(
        answer="Critical speed amplifies rotor response [missing].",
        claims=[{"text": "Critical speed amplifies rotor response.", "chunk_id": "missing", "doc_id": "doc1"}],
        citations=[{"chunk_id": "missing", "doc_id": "doc1"}],
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "insufficient"
    assert output.structured_result["claims"] == []
    assert output.structured_result["answer"] == ""
    assert output.structured_result["unsupported_claims"][0]["chunk_id"] == "missing"


def test_v2_blocks_llm_claim_without_visible_chunk_reference():
    s3 = _s3(
        answer="Critical speed amplifies rotor response.",
        claims=[{"text": "Critical speed amplifies rotor response.", "chunk_id": "c1", "doc_id": "doc1"}],
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "insufficient"
    assert "claim missing visible [chunk_id] reference" in output.structured_result["unsupported_claims"][0]["reasons"]


def test_v2_allows_deterministic_structured_claim_without_bracket_reference():
    s3 = _s3(
        answer="Critical speed amplifies rotor response. (evidence: c1)",
        claims=[{"text": "Critical speed amplifies rotor response.", "chunk_id": "c1", "doc_id": "doc1"}],
        mode="deterministic",
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "ok"


def test_v2_blocks_answer_prose_without_structured_claims_or_refs():
    s3 = _s3(answer="Critical speed amplifies rotor response.", claims=[], citations=[])

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "insufficient"
    assert "answer contains unstructured claim" in output.structured_result["unsupported_claims"][0]["reasons"]


def test_v2_blocks_answer_prose_with_refs_but_without_structured_claims():
    s3 = _s3(answer="Critical speed amplifies rotor response [c1].", claims=[], citations=[])

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "insufficient"
    assert "answer contains unstructured claim" in output.structured_result["unsupported_claims"][0]["reasons"]


def test_v2_blocks_obvious_lexical_mismatch_against_cited_evidence():
    s3 = _s3(
        answer="Bearing temperature proves lubrication failure [c1].",
        claims=[{"text": "Bearing temperature proves lubrication failure.", "chunk_id": "c1", "doc_id": "doc1"}],
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "insufficient"
    assert "claim text does not lexically match cited evidence" in output.structured_result["unsupported_claims"][0]["reasons"]


def test_v2_allows_vocab_overlapping_false_claim_as_known_obj10_limit():
    s3 = _s3(
        answer="Critical speed eliminates rotor damping risk [c1].",
        claims=[{"text": "Critical speed eliminates rotor damping risk.", "chunk_id": "c1", "doc_id": "doc1"}],
    )

    output = CitationCheckSkill().run(_payload(s3))

    assert output.status == "ok"
    assert output.structured_result["citation_check"]["unsupported_count"] == 0


def test_v2_blocks_at_least_90_percent_of_constructed_fake_references():
    blocked = 0
    for index in range(10):
        s3 = _s3(
            answer=f"Unsupported claim [{index}_fake].",
            claims=[{"text": "Unsupported claim.", "chunk_id": f"{index}_fake", "doc_id": "doc1"}],
            citations=[{"chunk_id": f"{index}_fake", "doc_id": "doc1"}],
        )
        output = CitationCheckSkill().run(_payload(s3))
        blocked += int(output.status == "insufficient")

    assert blocked >= 9


class StaticSkill(Skill):
    name = "static"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output

    def run(self, payload: SkillInput) -> SkillOutput:
        return self.output


def test_tutor_orchestrator_v2_removes_unsupported_claim_before_v4():
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
            structured_result={
                "language": "en",
                "answer": "Bearing temperature proves lubrication failure [c1].",
                "claims": [{"text": "Bearing temperature proves lubrication failure.", "chunk_id": "c1", "doc_id": "doc1"}],
                "synthesis_mode": "llm",
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )

    output = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False},
    )

    assert "Bearing temperature proves lubrication failure" not in output.structured_result["answer"]
    assert output.structured_result["chain"][2]["skill"] == "v2_citation_check"
    assert output.structured_result["skill_results"]["v2"]["unsupported_claims"]


def test_tutor_orchestrator_v2_block_forces_final_insufficient_even_if_v4_returns_ok():
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
            structured_result={
                "language": "en",
                "answer": "Bearing temperature proves lubrication failure [c1].",
                "claims": [{"text": "Bearing temperature proves lubrication failure.", "chunk_id": "c1", "doc_id": "doc1"}],
                "synthesis_mode": "llm",
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )
    v4 = StaticSkill(SkillOutput(status="ok", summary="V4 ok", structured_result={"answer": "Rendered anyway."}))

    output = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, style_skill=v4).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False},
    )

    assert output.status == "insufficient"
    assert output.structured_result["chain"][2]["status"] == "insufficient"
    assert output.structured_result["chain"][3]["status"] == "ok"


def test_tutor_orchestrator_v2_failure_warns_and_passes_s3_through():
    class BrokenV2(Skill):
        name = "v2_citation_check"

        def run(self, payload: SkillInput) -> SkillOutput:
            raise RuntimeError("v2 boom")

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
            structured_result={
                "language": "en",
                "answer": "Critical speed amplifies rotor response.",
                "claims": [{"text": "Critical speed amplifies rotor response.", "chunk_id": "c1", "doc_id": "doc1"}],
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )

    output = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, citation_check_skill=BrokenV2()).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False},
    )

    assert output.status == "ok"
    assert "Critical speed amplifies rotor response" in output.structured_result["answer"]
    assert any("V2 citation check failed" in warning for warning in output.warnings)


def test_tutor_orchestrator_v2_fail_status_warns_and_passes_s3_through():
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
            structured_result={
                "language": "en",
                "answer": "Critical speed amplifies rotor response.",
                "claims": [{"text": "Critical speed amplifies rotor response.", "chunk_id": "c1", "doc_id": "doc1"}],
            },
            citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
        )
    )
    v2 = StaticSkill(SkillOutput(status="fail", summary="V2 failed", warnings=["quality backend down"]))

    output = TutorOrchestrator(retrieval_skill=s2, qa_summary_skill=s3, citation_check_skill=v2).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "s4_enabled": False},
    )

    assert output.status == "ok"
    assert "Critical speed amplifies rotor response" in output.structured_result["answer"]
    assert "quality backend down" in output.warnings
    assert any("V2 citation check returned fail" in warning for warning in output.warnings)
