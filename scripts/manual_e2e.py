"""Manual Phase-3 end-to-end probe.

This script stays out of CI. By default it exercises the deterministic local
contract chain against small PDF + DOCX fixtures. When explicitly requested it
can run the Phase-3 manual live/capture lane for OpenAI S3/S4/S5 and Anthropic
supervisor calls.
"""
from __future__ import annotations

import argparse
import json
import os
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
from vibration_agent.llm.anthropic_client import AnthropicClient  # noqa: E402
from vibration_agent.llm.budget import BudgetGuard  # noqa: E402
from vibration_agent.llm.openai_client import OpenAIClient  # noqa: E402
from vibration_agent.llm.replay import RecordingClient  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import SkillInput, SkillOutput  # noqa: E402
from vibration_agent.skills import EngineeringAnalysisSkill, FormulaDerivationSkill, QASummarySkill  # noqa: E402
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
    skill_results = structured.get("skill_results") if isinstance(structured.get("skill_results"), dict) else {}
    skill_token_costs = _model_skill_token_costs(skill_results)
    skill_costs = _model_skill_costs(skill_results)
    supervisor_token_cost = structured.get("supervisor_token_cost")
    if supervisor_token_cost not in (None, ""):
        skill_token_costs["supervisor"] = int(supervisor_token_cost)
    supervisor_cost = structured.get("supervisor_cost")
    if isinstance(supervisor_cost, list):
        skill_costs["supervisor"] = supervisor_cost
    aggregate_token_cost = structured.get("token_cost")
    if aggregate_token_cost in (None, "") and skill_token_costs:
        aggregate_token_cost = sum(skill_token_costs.values())
    return {
        "status": output.status,
        "scope": structured.get("scope"),
        "chain": [step.get("skill") for step in structured.get("chain", [])],
        "citation_count": len(output.citations),
        "citations": [citation.model_dump(mode="json") for citation in output.citations],
        "reviewer_notes": structured.get("reviewer_notes", []),
        "supervisor_status": structured.get("supervisor_status"),
        "supervisor_invocations": structured.get("supervisor_invocations"),
        "token_cost": aggregate_token_cost,
        "cost": structured.get("cost") or _aggregate_cost(skill_costs),
        "skill_token_costs": skill_token_costs,
        "skill_costs": skill_costs,
        "warnings": output.warnings,
    }


def _model_skill_token_costs(skill_results: dict[str, Any]) -> dict[str, int]:
    costs: dict[str, int] = {}
    for name in ("s3", "s4", "s5"):
        result = skill_results.get(name)
        if isinstance(result, dict) and result.get("token_cost") not in (None, ""):
            costs[name] = int(result["token_cost"])
    return costs


def _model_skill_costs(skill_results: dict[str, Any]) -> dict[str, Any]:
    costs: dict[str, Any] = {}
    for name in ("s3", "s4", "s5"):
        result = skill_results.get(name)
        if (
            isinstance(result, dict)
            and result.get("token_cost") not in (None, "")
            and isinstance(result.get("cost"), dict)
        ):
            costs[name] = result["cost"]
    return costs


def _aggregate_cost(skill_costs: dict[str, Any]) -> dict[str, Any] | None:
    estimates = [
        cost.get("estimated_usd")
        for cost in skill_costs.values()
        if isinstance(cost, dict) and cost.get("estimated_usd") is not None
    ]
    if not estimates:
        return None
    return {
        "estimated_usd": sum(float(value) for value in estimates),
        "source": "local_estimate_sum",
    }


def _require_manual_live(settings: Any, *, provider_name: str) -> None:
    if not settings.llm.live_enabled:
        raise RuntimeError(
            "Set LLM_LIVE_ENABLED=true or configs/llm.yaml live_enabled: true for manual live validation."
        )
    if not settings.llm.capture_enabled:
        raise RuntimeError(
            "Set LLM_CAPTURE_ENABLED=true or configs/llm.yaml capture_enabled: true for manual live validation."
        )
    provider = settings.llm.openai if provider_name == "openai" else settings.llm.anthropic
    if not os.getenv(provider.api_key_env):
        raise RuntimeError(
            f"Set {provider.api_key_env} in the environment before running {provider_name} live validation."
        )


def _recorder(settings: Any, *, provider_name: str, fixture_dir: Path) -> RecordingClient:
    _require_manual_live(settings, provider_name=provider_name)
    budget = BudgetGuard.from_settings(settings.llm)
    if provider_name == "openai":
        live = OpenAIClient(settings.llm.openai, allow_live=True, budget_guard=budget)
    else:
        live = AnthropicClient(settings.llm.anthropic, allow_live=True, budget_guard=budget)
    return RecordingClient(
        client=live,
        fixture_dir=fixture_dir,
        capture_enabled=settings.llm.capture_enabled,
        manual_lane=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the manual Phase-3 E2E probe.")
    parser.add_argument(
        "--query",
        default="阻尼比如何影响转子临界转速附近的振动响应？",
        help="Question to ask against the PDF + DOCX fixtures.",
    )
    parser.add_argument("--difficulty", default="extreme", choices=["low", "medium", "high", "extreme"])
    parser.add_argument(
        "--user-mode",
        default="definition",
        choices=["engineering", "definition", "derivation", "research"],
    )
    parser.add_argument(
        "--s3-llm-response-json",
        type=Path,
        default=None,
        help="Optional captured S3 JSON response replay. This is not a live LLM call.",
    )
    parser.add_argument(
        "--live-openai",
        action="store_true",
        help="Use the explicit manual live/capture lane for OpenAI-backed S3/S4/S5.",
    )
    parser.add_argument(
        "--live-supervisor",
        action="store_true",
        help="Use the explicit manual live/capture lane for Anthropic supervisor review/correction.",
    )
    parser.add_argument("--fixture-dir", type=Path, default=ROOT / "tests" / "fixtures" / "llm")
    args = parser.parse_args(argv)
    if args.live_openai and args.s3_llm_response_json is not None:
        raise ValueError("--live-openai and --s3-llm-response-json are mutually exclusive.")

    rows = _fixture_rows()
    settings = load(ROOT)
    constraints: dict[str, Any] = {
        "scope": "in_scope",
        "difficulty": args.difficulty,
        "top_k": len(rows),
    }
    qa_summary_skill = None
    engineering_analysis_skill = None
    formula_derivation_skill = None
    if args.s3_llm_response_json is not None:
        response = json.loads(args.s3_llm_response_json.read_text(encoding="utf-8-sig"))
        if not isinstance(response, dict):
            raise ValueError("--s3-llm-response-json must contain one JSON object.")
        qa_summary_skill = QASummarySkill(settings=settings, llm_client=RecordedS3Client(response))
        constraints["s3_llm_enabled"] = True
    if args.live_openai:
        openai_recorder = _recorder(settings, provider_name="openai", fixture_dir=args.fixture_dir)
        qa_summary_skill = QASummarySkill(settings=settings, llm_client=openai_recorder)
        engineering_analysis_skill = EngineeringAnalysisSkill(settings=settings, llm_client=openai_recorder)
        formula_derivation_skill = FormulaDerivationSkill(settings=settings, llm_client=openai_recorder)
        constraints["s3_llm_enabled"] = True
        constraints["s4_llm_enabled"] = True
        constraints["s5_llm_enabled"] = True

    supervisor_loop = SupervisorLoop(settings=settings)
    if args.live_supervisor:
        anthropic_recorder = _recorder(settings, provider_name="anthropic", fixture_dir=args.fixture_dir)
        supervisor_loop = SupervisorLoop(
            client=anthropic_recorder,
            correction_client=anthropic_recorder,
            settings=settings,
        )

    output = TutorOrchestrator(
        retrieval_skill=StaticRetrievalSkill(rows),
        qa_summary_skill=qa_summary_skill,
        engineering_analysis_skill=engineering_analysis_skill,
        formula_derivation_skill=formula_derivation_skill,
        supervisor_loop=supervisor_loop,
        settings=settings,
    ).handle_query(
        args.query,
        constraints=constraints,
        user_mode=args.user_mode,
        task_id="manual-phase3-e2e",
    )
    print(json.dumps(_summary(output), ensure_ascii=False, indent=2))
    return 0 if output.status in {"ok", "insufficient"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
