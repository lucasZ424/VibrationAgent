"""Manual Phase-2 end-to-end probe.

This script stays out of CI. It exercises the local Phase-2 contract chain
against the small PDF + DOCX fixtures and can optionally feed a manually
captured S3 LLM JSON response through the same V2/V4/V3 gates. The optional LLM
mode is captured-response replay, not a live provider call.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.agent import SupervisorLoop  # noqa: E402
from vibration_agent.config import load  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import SkillInput, SkillOutput  # noqa: E402
from vibration_agent.skills import QASummarySkill  # noqa: E402
from vibration_agent.skills.base import Skill  # noqa: E402


PDF_CHUNKS = ROOT / "tests" / "fixtures" / "chunks" / "sample_zh_chunks.jsonl"
DOCX_CHUNKS = ROOT / "tests" / "fixtures" / "chunks" / "sample_zh_docx_chunks.jsonl"


class StaticRetrievalSkill(Skill):
    name = "s2_retrieval"

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def run(self, payload: SkillInput) -> SkillOutput:
        return SkillOutput(
            status="ok",
            summary=f"S2 fixture ok: {len(self._rows)} row(s).",
            structured_result={
                "retrieval_context": self._rows,
                "retrieval_output": {
                    "hits": [
                        {"chunk_id": row["chunk_id"], "doc_id": row["doc_id"], "score": row.get("score", 1.0)}
                        for row in self._rows
                    ]
                },
            },
        )


class RecordedS3Client:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def synthesize(self, **kwargs: Any) -> dict[str, Any]:
        return self.response


def _load_first_jsonl(path: Path) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            return json.loads(line)
    raise ValueError(f"No JSONL rows found in {path}")


def _fixture_rows() -> list[dict[str, Any]]:
    rows = [_load_first_jsonl(PDF_CHUNKS), _load_first_jsonl(DOCX_CHUNKS)]
    for row in rows:
        row.setdefault("score", 1.0)
        row.setdefault("confidence", 1.0)
        row.setdefault("language", "zh")
    return rows


def _summary(output: SkillOutput) -> dict[str, Any]:
    structured = output.structured_result
    return {
        "status": output.status,
        "scope": structured.get("scope"),
        "chain": [step.get("skill") for step in structured.get("chain", [])],
        "citation_count": len(output.citations),
        "citations": [citation.model_dump(mode="json") for citation in output.citations],
        "reviewer_notes": structured.get("reviewer_notes", []),
        "supervisor_status": structured.get("supervisor_status"),
        "supervisor_invocations": structured.get("supervisor_invocations"),
        "warnings": output.warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the manual Phase-2 E2E probe.")
    parser.add_argument(
        "--query",
        default="阻尼比如何影响转子临界转速附近的振动响应？",
        help="Question to ask against the PDF + DOCX fixtures.",
    )
    parser.add_argument("--difficulty", default="extreme", choices=["low", "medium", "high", "extreme"])
    parser.add_argument("--user-mode", default="definition", choices=["engineering", "definition", "derivation", "research"])
    parser.add_argument(
        "--s3-llm-response-json",
        type=Path,
        default=None,
        help="Optional captured S3 JSON response replay. This is not a live LLM call.",
    )
    args = parser.parse_args(argv)

    rows = _fixture_rows()
    settings = load(ROOT)
    constraints: dict[str, Any] = {
        "scope": "in_scope",
        "difficulty": args.difficulty,
        "s4_enabled": False,
        "top_k": len(rows),
    }
    qa_summary_skill = None
    if args.s3_llm_response_json is not None:
        response = json.loads(args.s3_llm_response_json.read_text(encoding="utf-8-sig"))
        if not isinstance(response, dict):
            raise ValueError("--s3-llm-response-json must contain one JSON object.")
        qa_summary_skill = QASummarySkill(settings=settings, llm_client=RecordedS3Client(response))
        constraints["s3_llm_enabled"] = True

    output = TutorOrchestrator(
        retrieval_skill=StaticRetrievalSkill(rows),
        qa_summary_skill=qa_summary_skill,
        supervisor_loop=SupervisorLoop(),
        settings=settings,
    ).handle_query(
        args.query,
        constraints=constraints,
        user_mode=args.user_mode,
        task_id="manual-phase2-e2e",
    )
    print(json.dumps(_summary(output), ensure_ascii=False, indent=2))
    return 0 if output.status in {"ok", "insufficient"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
