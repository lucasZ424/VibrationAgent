"""Evaluate the replay-first Obj6A + Obj6B combined chain."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import scripts.manual_e2e as manual_e2e  # noqa: E402
from scripts.obj6_synthesis_eval import HARD_CASE_IDS, evaluate_gate  # noqa: E402
from scripts.rag_qa_eval import _offline_settings, load_questions, run_rag_qa_eval  # noqa: E402
from vibration_agent.agent import SupervisorLoop  # noqa: E402
from vibration_agent.config import load  # noqa: E402
from vibration_agent.llm.replay import ReplayClient  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.retrieval.hybrid import load_runtime_chunks  # noqa: E402
from vibration_agent.schemas import SkillInput, SkillOutput  # noqa: E402
from vibration_agent.skills.s2_retrieval import RetrievalSkill  # noqa: E402
from vibration_agent.skills.s3_qa_summary import QASummarySkill  # noqa: E402
from vibration_agent.skills.v2_citation_check import CitationCheckSkill  # noqa: E402


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _supervisor_loop(*, settings: Any, replay_dir: Path | None, live: bool, fixture_dir: Path) -> SupervisorLoop:
    if live:
        recorder = manual_e2e._recorder(settings, provider_name="anthropic", fixture_dir=fixture_dir)
        return SupervisorLoop(client=recorder, correction_client=recorder, settings=settings)
    if replay_dir is None:
        return SupervisorLoop(settings=settings)
    replay = ReplayClient(replay_dir)
    return SupervisorLoop(client=replay, correction_client=replay, settings=settings)


def _post_supervisor_v2(output: SkillOutput, *, query: str, task_id: str, user_mode: str) -> SkillOutput:
    structured = output.structured_result if isinstance(output.structured_result, Mapping) else {}
    skills = structured.get("skill_results") if isinstance(structured.get("skill_results"), Mapping) else {}
    s2_result = skills.get("s2") if isinstance(skills.get("s2"), Mapping) else {}
    v2_result = dict(skills.get("v2") or {}) if isinstance(skills.get("v2"), Mapping) else {}
    final_structured = dict(v2_result)
    final_structured["answer"] = str(structured.get("answer") or "")
    if isinstance(structured.get("claims"), list):
        final_structured["claims"] = list(structured["claims"])
    if structured.get("synthesis_mode"):
        final_structured["synthesis_mode"] = structured["synthesis_mode"]

    source = SkillOutput(
        status="ok",
        summary="Combined-chain post-supervisor V2 source.",
        structured_result=final_structured,
        citations=output.citations,
        warnings=output.warnings,
    )
    checked = CitationCheckSkill().run(
        SkillInput(
            task_id=task_id,
            user_query=query,
            user_mode=user_mode,
            context={"s2_result": s2_result, "skill_output": source.model_dump(mode="python")},
        )
    )
    updated = output.model_copy(deep=True)
    updated_structured = dict(structured)
    quality = dict(updated_structured.get("answer_quality") or {})
    quality["faithfulness_status"] = checked.status
    updated_structured["answer_quality"] = quality
    updated_structured["combined_post_supervisor_v2"] = {
        "status": checked.status,
        "summary": checked.summary,
        "unsupported_claims": checked.structured_result.get("unsupported_claims", []),
        "citation_check": checked.structured_result.get("citation_check", {}),
    }
    updated.structured_result = updated_structured
    updated.citations = checked.citations if checked.status == "ok" else []
    if checked.status == "insufficient":
        updated.status = "insufficient"
    for warning in checked.warnings:
        if warning not in updated.warnings:
            updated.warnings.append(warning)
    return updated


def run_combined(
    *,
    s3_replay_dir: Path,
    supervisor_replay_dir: Path | None = None,
    live_supervisor: bool = False,
    capture_dir: Path | None = None,
) -> dict[str, Any]:
    settings = _offline_settings(load(ROOT))
    chunks = load_runtime_chunks(settings)
    if not chunks:
        raise RuntimeError("Local Qdrant corpus is unavailable or empty.")
    supervisor_loop = _supervisor_loop(
        settings=settings,
        replay_dir=supervisor_replay_dir,
        live=live_supervisor,
        fixture_dir=capture_dir or ROOT / "tests" / "fixtures" / "llm" / "obj6_combined",
    )
    orchestrator = TutorOrchestrator(
        settings=settings,
        retrieval_skill=RetrievalSkill(settings=settings),
        qa_summary_skill=QASummarySkill(settings=settings, llm_client=ReplayClient(s3_replay_dir)),
        supervisor_loop=supervisor_loop,
    )
    case_meta: dict[str, dict[str, Any]] = {}

    def runner(case: Mapping[str, Any]) -> SkillOutput:
        case_id = str(case["case_id"])
        hard_case = str(case["case_id"]) in HARD_CASE_IDS
        constraints: dict[str, Any] = {
            "top_k": 10,
            "difficulty": "low",
            "s3_llm_enabled": hard_case,
            "llm_enabled": False,
            "advisory_routing_enabled": False,
        }
        if hard_case:
            constraints["use_opus"] = True
        output = orchestrator.handle_query(
            str(case["query"]),
            task_id=case_id,
            user_mode="engineering",
            context={"chunks": list(chunks)},
            constraints=constraints,
        )
        checked = _post_supervisor_v2(
            output,
            query=str(case["query"]),
            task_id=case_id,
            user_mode="engineering",
        )
        structured = checked.structured_result if isinstance(checked.structured_result, Mapping) else {}
        post_v2 = structured.get("combined_post_supervisor_v2")
        case_meta[case_id] = {
            "supervisor_status": structured.get("supervisor_status"),
            "supervisor_invocations": structured.get("supervisor_invocations"),
            "supervisor_corrections": structured.get("supervisor_corrections"),
            "post_supervisor_v2_status": post_v2.get("status") if isinstance(post_v2, Mapping) else None,
        }
        return checked

    report = run_rag_qa_eval(
        questions=load_questions(),
        query_runner=runner,
        corpus_count=len(chunks),
        evidence_selection_config={"enabled": False, "rerank_enabled": False},
    )
    report["schema_version"] = "phase5.obj6.combined_report.v1"
    report["combined_chain"] = {
        "s3_replay_dir": str(s3_replay_dir),
        "supervisor_replay_dir": str(supervisor_replay_dir) if supervisor_replay_dir else None,
        "live_supervisor": live_supervisor,
        "supervisor_hard_case_ids": sorted(HARD_CASE_IDS),
    }
    for row in report["cases"]:
        meta = case_meta.get(str(row["case_id"]))
        if meta:
            row["combined_chain"] = meta
    return report


def capture_case(
    *,
    case_id: str,
    s3_replay_dir: Path,
    supervisor_replay_dir: Path | None = None,
    live_supervisor: bool = False,
    capture_dir: Path | None = None,
) -> dict[str, Any]:
    settings = _offline_settings(load(ROOT))
    chunks = load_runtime_chunks(settings)
    case = next((row for row in load_questions()["cases"] if str(row["case_id"]) == case_id), None)
    if case is None:
        raise ValueError(f"Unknown case_id: {case_id}")
    supervisor_loop = _supervisor_loop(
        settings=settings,
        replay_dir=supervisor_replay_dir,
        live=live_supervisor,
        fixture_dir=capture_dir or ROOT / "tests" / "fixtures" / "llm" / "obj6_combined",
    )
    orchestrator = TutorOrchestrator(
        settings=settings,
        retrieval_skill=RetrievalSkill(settings=settings),
        qa_summary_skill=QASummarySkill(settings=settings, llm_client=ReplayClient(s3_replay_dir)),
        supervisor_loop=supervisor_loop,
    )
    output = orchestrator.handle_query(
        str(case["query"]),
        task_id=case_id,
        user_mode="engineering",
        context={"chunks": list(chunks)},
        constraints={
            "top_k": 10,
            "difficulty": "low",
            "s3_llm_enabled": case_id in HARD_CASE_IDS,
            "llm_enabled": False,
            "advisory_routing_enabled": False,
            "use_opus": case_id in HARD_CASE_IDS,
        },
    )
    checked = _post_supervisor_v2(
        output,
        query=str(case["query"]),
        task_id=case_id,
        user_mode="engineering",
    )
    structured = checked.structured_result if isinstance(checked.structured_result, Mapping) else {}
    post_v2 = structured.get("combined_post_supervisor_v2")
    return {
        "schema_version": "phase5.obj6.combined_case_capture.v1",
        "case_id": case_id,
        "status": checked.status,
        "supervisor_status": structured.get("supervisor_status"),
        "supervisor_invocations": structured.get("supervisor_invocations"),
        "supervisor_corrections": structured.get("supervisor_corrections"),
        "post_supervisor_v2_status": post_v2.get("status") if isinstance(post_v2, Mapping) else None,
        "token_cost": structured.get("token_cost"),
        "supervisor_token_cost": structured.get("supervisor_token_cost"),
        "warnings": checked.warnings,
    }


def evaluate_combined_gate(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    base_gate = evaluate_gate(candidate, baseline)
    cases = {str(row["case_id"]): row for row in candidate["cases"]}
    hard_cases = [cases[case_id] for case_id in sorted(HARD_CASE_IDS)]
    supervisor_approved = all(_case_supervisor_status(row) == "approved" for row in hard_cases)
    post_v2_ok = all(_case_post_v2_status(row) == "ok" for row in hard_cases)
    checks = {
        **base_gate["checks"],
        "supervisor_approved_on_hard_cases": supervisor_approved,
        "post_supervisor_v2_ok_on_hard_cases": post_v2_ok,
    }
    return {
        "schema_version": "phase5.obj6.combined_gate.v1",
        "eligible": all(checks.values()),
        "checks": checks,
        "baseline_scorecard": base_gate["baseline_scorecard"],
        "candidate_scorecard": base_gate["candidate_scorecard"],
        "hard_case_supervisor_status": {row["case_id"]: _case_supervisor_status(row) for row in hard_cases},
        "hard_case_post_v2_status": {row["case_id"]: _case_post_v2_status(row) for row in hard_cases},
    }


def _case_supervisor_status(row: Mapping[str, Any]) -> str:
    combined = row.get("combined_chain") if isinstance(row.get("combined_chain"), Mapping) else {}
    return str(combined.get("supervisor_status") or "unknown")


def _case_post_v2_status(row: Mapping[str, Any]) -> str:
    combined = row.get("combined_chain") if isinstance(row.get("combined_chain"), Mapping) else {}
    return str(combined.get("post_supervisor_v2_status") or row.get("v2_status") or "unknown")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--s3-replay-dir", type=Path, required=True)
    evaluate.add_argument("--supervisor-replay-dir", type=Path)
    evaluate.add_argument("--live-supervisor", action="store_true")
    evaluate.add_argument("--capture-dir", type=Path, default=ROOT / "tests" / "fixtures" / "llm" / "obj6_combined")
    evaluate.add_argument("--output", type=Path, required=True)
    capture = sub.add_parser("capture-case")
    capture.add_argument("--case-id", required=True)
    capture.add_argument("--s3-replay-dir", type=Path, required=True)
    capture.add_argument("--supervisor-replay-dir", type=Path)
    capture.add_argument("--live-supervisor", action="store_true")
    capture.add_argument("--capture-dir", type=Path, default=ROOT / "tests" / "fixtures" / "llm" / "obj6_combined")
    capture.add_argument("--output", type=Path, required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--candidate", type=Path, required=True)
    gate.add_argument("--baseline", type=Path, required=True)
    gate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        report = run_combined(
            s3_replay_dir=args.s3_replay_dir,
            supervisor_replay_dir=args.supervisor_replay_dir,
            live_supervisor=bool(args.live_supervisor),
            capture_dir=args.capture_dir,
        )
    elif args.command == "capture-case":
        report = capture_case(
            case_id=args.case_id,
            s3_replay_dir=args.s3_replay_dir,
            supervisor_replay_dir=args.supervisor_replay_dir,
            live_supervisor=bool(args.live_supervisor),
            capture_dir=args.capture_dir,
        )
    else:
        report = evaluate_combined_gate(_read(args.candidate), _read(args.baseline))
    _write(args.output, report)
    print(json.dumps({key: report[key] for key in report if key in {"schema_version", "eligible", "checks"}}, indent=2))
    return 1 if report.get("eligible") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
