"""Phase-2 chain-contract E2E tests.

These tests intentionally inject S2/S3 fixture outputs so the assertions target
the frozen Phase-2 handoff contract through real V2/V4/V3/supervisor logic.
Real S1/S2/S3 fixture-chain coverage remains in test_phase0_fixture_chain.py and
test_obj19_end_to_end.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vibration_agent.agent import ReviewReport, SupervisorLoop
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillInput, SkillOutput
from vibration_agent.skills.base import Skill

ROOT = Path(__file__).resolve().parents[2]
PDF_CHUNKS = ROOT / "tests" / "fixtures" / "chunks" / "sample_zh_chunks.jsonl"
DOCX_CHUNKS = ROOT / "tests" / "fixtures" / "chunks" / "sample_zh_docx_chunks.jsonl"

pytestmark = pytest.mark.integration


class StaticSkill(Skill):
    name = "static"

    def __init__(self, output: SkillOutput, *, name: str) -> None:
        self.output = output
        self.name = name
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


class ApprovingSupervisor:
    def __init__(self) -> None:
        self.calls = 0

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.calls += 1
        return ReviewReport(task_id="phase2-e2e", approved=True)


def _load_first_jsonl(path: Path) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            return json.loads(line)
    raise AssertionError(f"No JSONL row found in {path}")


def _fixture_rows() -> list[dict[str, Any]]:
    rows = [_load_first_jsonl(PDF_CHUNKS), _load_first_jsonl(DOCX_CHUNKS)]
    for row in rows:
        row.setdefault("score", 1.0)
        row.setdefault("confidence", 1.0)
        row.setdefault("language", "zh")
    return rows


def _s2_output(rows: list[dict[str, Any]]) -> SkillOutput:
    return SkillOutput(
        status="ok",
        summary=f"S2 fixture ok: {len(rows)} row(s).",
        structured_result={
            "retrieval_context": rows,
            "retrieval_output": {
                "hits": [
                    {"chunk_id": row["chunk_id"], "doc_id": row["doc_id"], "score": row.get("score", 1.0)}
                    for row in rows
                ]
            },
        },
    )


def _claim(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": str(row["text"]),
        "chunk_id": row["chunk_id"],
        "doc_id": row["doc_id"],
        "pages": row.get("pages"),
        "evidence_type": "documented",
        "asset_ids": [asset["asset_id"] for asset in row.get("assets", []) if isinstance(asset, dict) and asset.get("asset_id")],
    }


def _s3_output(rows: list[dict[str, Any]]) -> SkillOutput:
    claims = [_claim(row) for row in rows]
    answer = "\n".join(claim["text"] for claim in claims)
    return SkillOutput(
        status="ok",
        summary=f"S3 fixture ok: {len(claims)} claim(s).",
        structured_result={
            "language": "zh",
            "answer": answer,
            "claims": claims,
            "assets": [asset for row in rows for asset in row.get("assets", [])],
            "synthesis_mode": "deterministic",
            "unsupported_claims": [],
        },
        citations=[
            Citation(
                chunk_id=str(row["chunk_id"]),
                doc_id=str(row["doc_id"]),
                pages=row.get("pages") if isinstance(row.get("pages"), list) else None,
            )
            for row in rows
        ],
    )


def _orchestrator(
    *,
    s2: SkillOutput,
    s3: SkillOutput,
    supervisor_loop: SupervisorLoop | None = None,
) -> TutorOrchestrator:
    return TutorOrchestrator(
        retrieval_skill=StaticSkill(s2, name="s2_retrieval"),
        qa_summary_skill=StaticSkill(s3, name="s3_qa_summary"),
        supervisor_loop=supervisor_loop or SupervisorLoop(),
    )


def _chain(output: SkillOutput) -> list[str]:
    return [step["skill"] for step in output.structured_result["chain"]]


def test_phase2_zh_pdf_docx_chain_reaches_v3_with_citations_and_scope():
    rows = _fixture_rows()
    supervisor = ApprovingSupervisor()

    output = _orchestrator(
        s2=_s2_output(rows),
        s3=_s3_output(rows),
        supervisor_loop=SupervisorLoop(client=supervisor),
    ).handle_query(
        "阻尼比如何影响转子临界转速附近的振动响应？",
        constraints={"scope": "in_scope", "difficulty": "extreme", "s4_enabled": False},
        user_mode="definition",
        task_id="phase2-e2e-zh",
    )

    assert output.status == "ok"
    assert output.structured_result["scope"] == "in_scope"
    assert _chain(output) == ["s2_retrieval", "s3_qa_summary", "v2_citation_check", "v4_style", "v3_reviewer"]
    assert {citation.doc_id for citation in output.citations} == {"fixture_rotor_zh_doc", "fixture_rotor_zh_docx"}
    assert isinstance(output.structured_result["reviewer_notes"], list)
    assert output.structured_result["supervisor_status"] == "approved"
    assert supervisor.calls == 1


def test_phase2_extreme_query_uses_supervisor_fallback_without_client():
    rows = _fixture_rows()

    output = _orchestrator(s2=_s2_output(rows), s3=_s3_output(rows)).handle_query(
        "阻尼不足时，极端工况下转子通过共振区有什么风险？",
        constraints={"scope": "in_scope", "difficulty": "extreme", "s4_enabled": False},
        user_mode="definition",
        task_id="phase2-e2e-supervisor",
    )

    assert output.status == "ok"
    assert output.structured_result["scope"] == "in_scope"
    assert output.structured_result["supervisor_status"] == "fallback"
    assert output.structured_result["supervisor_invocations"] == 1
    assert _chain(output)[-1] == "v3_reviewer"
    assert output.citations
    assert isinstance(output.structured_result["reviewer_notes"], list)
    assert any("Opus supervisor unavailable" in warning for warning in output.warnings)


def test_phase2_v2_fake_citation_strips_conclusion_and_keeps_reviewer_notes_key():
    visible = {
        "chunk_id": "c1",
        "doc_id": "doc1",
        "pages": [1],
        "text": "Critical speed amplifies rotor response.",
        "score": 1.0,
    }
    s3 = SkillOutput(
        status="ok",
        summary="S3 fake citation",
        structured_result={
            "language": "en",
            "answer": "Bearing temperature proves lubrication failure [c1].",
            "claims": [
                {
                    "text": "Bearing temperature proves lubrication failure.",
                    "chunk_id": "c1",
                    "doc_id": "doc1",
                    "pages": [1],
                }
            ],
            "synthesis_mode": "llm",
            "unsupported_claims": [],
        },
        citations=[Citation(chunk_id="c1", doc_id="doc1", pages=[1])],
    )

    output = _orchestrator(s2=_s2_output([visible]), s3=s3).handle_query(
        "What happens near critical speed in rotor vibration?",
        constraints={"scope": "in_scope", "difficulty": "extreme", "s4_enabled": False},
        user_mode="definition",
        task_id="phase2-e2e-v2-block",
    )

    assert output.status == "insufficient"
    assert output.structured_result["scope"] == "in_scope"
    assert _chain(output) == ["s2_retrieval", "s3_qa_summary", "v2_citation_check", "v4_style", "v3_reviewer"]
    assert output.structured_result["chain"][2]["status"] == "insufficient"
    assert "Bearing temperature proves lubrication failure" not in output.structured_result["answer"]
    assert output.citations == []
    assert isinstance(output.structured_result["reviewer_notes"], list)
    assert output.structured_result["skill_results"]["v2"]["unsupported_claims"]
