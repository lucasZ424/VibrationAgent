"""Replay-only Phase-3 golden eval runner.

The runner uses static S2/S3 fixtures and real V2/V4/V3/supervisor plumbing.
It never constructs live provider clients, so it does not require API keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.agent import ReviewReport, SupervisorLoop  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import SkillInput, SkillOutput  # noqa: E402
from vibration_agent.skills.base import Skill  # noqa: E402

DEFAULT_CASE_GLOB = "eval_*.json"
DEFAULT_FIXTURE_DIR = ROOT / "tests" / "fixtures" / "llm"


class StaticSkill(Skill):
    def __init__(self, output: SkillOutput, *, name: str) -> None:
        self.output = output
        self.name = name

    def run(self, payload: SkillInput) -> SkillOutput:
        return self.output


class ApprovingSupervisor:
    def review(self, **kwargs: Any) -> ReviewReport:
        output = kwargs.get("output")
        task_id = "eval"
        if isinstance(output, SkillOutput):
            task_id = str(output.structured_result.get("task_id") or task_id)
        return ReviewReport(task_id=task_id, approved=True)


def load_cases(fixture_dir: Path = DEFAULT_FIXTURE_DIR) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(fixture_dir.glob(DEFAULT_CASE_GLOB)):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain one JSON object.")
        data["_path"] = str(path)
        cases.append(data)
    if not cases:
        raise ValueError(f"No eval cases found in {fixture_dir} matching {DEFAULT_CASE_GLOB}.")
    return cases


def _s2_output(case: Mapping[str, Any]) -> SkillOutput:
    rows = list(case.get("retrieval_rows") or [])
    return SkillOutput(
        status="ok",
        summary=f"S2 eval fixture ok: {len(rows)} row(s).",
        structured_result={
            "retrieval_context": rows,
            "retrieval_output": {
                "hits": [
                    {
                        "chunk_id": row.get("chunk_id"),
                        "doc_id": row.get("doc_id"),
                        "score": row.get("score", 1.0),
                    }
                    for row in rows
                    if isinstance(row, Mapping)
                ]
            },
        },
    )


def _s3_output(case: Mapping[str, Any]) -> SkillOutput:
    raw = case.get("s3_output")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{case.get('case_id')} missing s3_output")
    return SkillOutput.model_validate(raw)


def _supervisor_loop(case: Mapping[str, Any]) -> SupervisorLoop:
    supervisor = case.get("supervisor")
    if isinstance(supervisor, Mapping) and supervisor.get("mode") == "approve":
        return SupervisorLoop(client=ApprovingSupervisor())
    return SupervisorLoop()


def run_case(case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "unknown")
    orchestrator = TutorOrchestrator(
        retrieval_skill=StaticSkill(_s2_output(case), name="s2_retrieval"),
        qa_summary_skill=StaticSkill(_s3_output(case), name="s3_qa_summary"),
        supervisor_loop=_supervisor_loop(case),
    )
    output = orchestrator.handle_query(
        str(case.get("query") or ""),
        constraints=dict(case.get("constraints") or {}),
        user_mode=case.get("user_mode", "engineering"),
        task_id=case_id,
    )
    return evaluate_output(case, output)


def evaluate_output(case: Mapping[str, Any], output: SkillOutput) -> dict[str, Any]:
    expect = case.get("expect")
    if not isinstance(expect, Mapping):
        raise ValueError(f"{case.get('case_id')} missing expect")
    structured = output.structured_result
    skill_results = structured.get("skill_results")
    skill_results = skill_results if isinstance(skill_results, Mapping) else {}
    v2_result = skill_results.get("v2")
    v2_result = v2_result if isinstance(v2_result, Mapping) else {}
    unsupported = v2_result.get("unsupported_claims")
    unsupported = unsupported if isinstance(unsupported, list) else []
    answer = str(structured.get("answer") or "")

    checks = {
        "status": output.status == expect.get("status"),
        "scope": structured.get("scope") == expect.get("scope", "in_scope"),
        "citation_count": len(output.citations) >= int(expect.get("min_citations", 0)),
        "required_terms": _contains_all(answer, expect.get("required_answer_terms", [])),
        "forbidden_terms": not _contains_any(answer, expect.get("forbidden_answer_terms", [])),
        "unsupported_count": len(unsupported) == int(expect.get("unsupported_count", len(unsupported))),
        "unsupported_reasons": _unsupported_reasons_contain(unsupported, expect.get("unsupported_reason_contains", [])),
        "reviewer_notes": _reviewer_notes_check(structured, expect.get("reviewer_notes_present")),
        "supervisor_status": structured.get("supervisor_status") == expect.get("supervisor_status", structured.get("supervisor_status")),
    }
    passed = all(checks.values())
    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "description": case.get("description", ""),
        "passed": passed,
        "checks": checks,
        "status": output.status,
        "scope": structured.get("scope"),
        "citation_count": len(output.citations),
        "unsupported_count": len(unsupported),
        "blocks_unsupported_numeric": _blocks_unsupported_numeric(unsupported)
        if expect.get("blocks_unsupported_numeric")
        else None,
        "expects_reviewer_notes": expect.get("reviewer_notes_present"),
        "reviewer_notes_present": bool(structured.get("reviewer_notes")),
        "supervisor_status": structured.get("supervisor_status"),
        "warnings": output.warnings,
    }


def run_eval(cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    active_cases = cases if cases is not None else load_cases()
    results = [run_case(case) for case in active_cases]
    return {
        "schema_version": "phase3.eval.v1",
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "scorecard": _scorecard(results),
        "cases": results,
    }


def _scorecard(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pass_rate": _rate(result["passed"] for result in results),
        "citation_faithfulness_pass_rate": _rate(result["checks"]["citation_count"] for result in results),
        "unsupported_numeric_block_rate": _rate(
            result["blocks_unsupported_numeric"]
            for result in results
            if result["blocks_unsupported_numeric"] is not None
        ),
        "scope_status_pass_rate": _rate(
            result["checks"]["status"] and result["checks"]["scope"] for result in results
        ),
        "reviewer_notes_presence_rate": _rate(
            result["checks"]["reviewer_notes"]
            for result in results
            if result["expects_reviewer_notes"] is not None
        ),
    }


def _rate(values: Any) -> float | None:
    items = list(values)
    if not items:
        return None
    return sum(1 for item in items if item) / len(items)


def _contains_all(text: str, terms: Any) -> bool:
    return all(str(term).casefold() in text.casefold() for term in terms or [])


def _contains_any(text: str, terms: Any) -> bool:
    return any(str(term).casefold() in text.casefold() for term in terms or [])


def _unsupported_reasons_contain(unsupported: list[Any], needles: Any) -> bool:
    haystack = json.dumps(unsupported, ensure_ascii=False).casefold()
    return all(str(needle).casefold() in haystack for needle in needles or [])


def _reviewer_notes_check(structured: Mapping[str, Any], expected: Any) -> bool:
    if expected is None:
        return True
    return bool(structured.get("reviewer_notes")) is bool(expected)


def _blocks_unsupported_numeric(unsupported: list[Any]) -> bool:
    haystack = json.dumps(unsupported, ensure_ascii=False).casefold()
    return "number/unit/symbol not found" in haystack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run replay-only Phase-3 golden eval.")
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_eval(load_cases(args.fixture_dir))
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
