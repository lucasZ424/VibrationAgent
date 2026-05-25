from pathlib import Path

import pytest

pytest.importorskip("fitz")

from vibration_agent.config import load
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import SkillInput
from vibration_agent.skills import IngestionSkill

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
pytestmark = pytest.mark.integration


def _isolated_settings(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "configs").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "vibration_agent").mkdir(parents=True, exist_ok=True)
    return load(workspace)


def test_phase0_fixture_runs_s1_to_s2_s3_v4(tmp_path):
    pdf = FIXTURES / "raw" / "small_vibration_native.pdf"
    settings = _isolated_settings(tmp_path)

    s1_output = IngestionSkill(settings=settings).run(
        SkillInput(
            task_id="integration-s1",
            user_query="ingest fixture",
            constraints={"input_path": str(pdf), "max_pages": 1, "write_output": True},
        )
    )

    assert s1_output.status == "ok"
    assert s1_output.structured_result["chunk_count"] >= 1
    chunks_jsonl = Path(s1_output.structured_result["documents"][0]["outputs"]["chunks_jsonl"])
    assert chunks_jsonl.exists()

    answer = TutorOrchestrator().handle_query(
        "What happens near critical speed in rotor vibration?",
        context=s1_output.structured_result,
        constraints={"top_k": 2},
        task_id="integration-query",
    )

    assert answer.status == "ok"
    assert answer.structured_result["scope"] == "in_scope"
    assert [step["skill"] for step in answer.structured_result["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v4_style",
    ]
    assert answer.citations
    assert answer.citations[0].pages == [1]
    assert answer.structured_result["v4"]["language"] == "en"
    assert "## Conclusion" in answer.structured_result["answer"]
    assert "critical speed" in answer.structured_result["answer"].lower()