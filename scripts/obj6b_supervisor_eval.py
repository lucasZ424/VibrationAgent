"""Replay-first Obj6B supervisor correction gate."""
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

import scripts.manual_e2e as manual_e2e  # noqa: E402
from vibration_agent.agent import SupervisorLoop  # noqa: E402
from vibration_agent.config import load  # noqa: E402
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs, write_fixture  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import Citation, SkillOutput  # noqa: E402


LLM_FIXTURES = ROOT / "tests" / "fixtures" / "llm"
LIVE_PROBE_TASK_ID = "obj6b-live-correction-probe"


class ProbeSupervisorClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.review_calls: list[dict[str, Any]] = []
        self.correction_calls: list[dict[str, Any]] = []

    def review(self, **kwargs: Any) -> dict[str, Any]:
        self.review_calls.append(kwargs)
        return self.responses.pop(0)

    def correct(self, **kwargs: Any) -> dict[str, Any]:
        self.correction_calls.append(kwargs)
        return self.responses.pop(0)


class HashRecordingSupervisorClient:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.review_hashes: list[str] = []
        self.correction_hashes: list[str] = []

    def review(self, **kwargs: Any) -> dict[str, Any]:
        self.review_hashes.append(
            request_from_kwargs(task="supervisor_review", schema_version="supervisor.v1", kwargs=kwargs).request_hash
        )
        return self.client.review(**kwargs)

    def correct(self, **kwargs: Any) -> dict[str, Any]:
        self.correction_hashes.append(
            request_from_kwargs(task="supervisor_correction", schema_version="correction.v1", kwargs=kwargs).request_hash
        )
        return self.client.correct(**kwargs)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((LLM_FIXTURES / name).read_text(encoding="utf-8"))


def _run_with_supervisor(supervisor_loop: SupervisorLoop) -> Any:
    rows = manual_e2e._fixture_rows()
    settings = load(ROOT)
    return TutorOrchestrator(
        retrieval_skill=manual_e2e.StaticRetrievalSkill(rows),
        supervisor_loop=supervisor_loop,
        settings=settings,
    ).handle_query(
        manual_e2e.DEFAULT_QUERY,
        constraints={"scope": "in_scope", "difficulty": "extreme", "top_k": len(rows)},
        user_mode="definition",
        task_id="obj6b-supervisor-replay",
    )


def _bad_candidate_output() -> SkillOutput:
    rows = manual_e2e._fixture_rows()
    answer = "阻尼比对临界转速附近的振动响应没有影响，工程上只需要关注转速。"
    citations = [
        Citation(
            chunk_id=row["chunk_id"],
            doc_id=row["doc_id"],
            pages=row.get("pages"),
            source_title=row.get("title"),
            snippet=str(row.get("text") or "")[:240],
        )
        for row in rows
    ]
    return SkillOutput(
        status="ok",
        summary="Deliberately incomplete Obj6B live correction probe.",
        structured_result={
            "task_id": LIVE_PROBE_TASK_ID,
            "scope": "in_scope",
            "answer": answer,
            "v4": {"answer": answer},
            "retrieval_context": rows,
            "retrieval_output": {
                "hits": [
                    {"chunk_id": row["chunk_id"], "doc_id": row["doc_id"], "score": row.get("score", 1.0)}
                    for row in rows
                ]
            },
        },
        citations=citations,
        warnings=["Obj6B live probe intentionally starts from a bad candidate answer."],
    )


def _live_reviewer_notes() -> list[dict[str, Any]]:
    return [
        {
            "source": "obj6b_live_correction_probe",
            "note": (
                "Candidate says damping has no effect, while the supplied evidence says increasing damping "
                "lowers the resonance peak and makes resonance passage smoother."
            ),
        }
    ]


def run_eval(*, fixture_dir: Path) -> dict[str, Any]:
    settings = load(ROOT)
    probe = ProbeSupervisorClient(
        [
            _fixture("supervisor_reject_response.json"),
            _fixture("supervisor_correction_response.json"),
            _fixture("supervisor_approve_response.json"),
        ]
    )
    probe_output = _run_with_supervisor(SupervisorLoop(client=probe, settings=settings))

    review_0 = request_from_kwargs(
        task="supervisor_review",
        schema_version="supervisor.v1",
        kwargs=probe.review_calls[0],
    )
    correction_0 = request_from_kwargs(
        task="supervisor_correction",
        schema_version="correction.v1",
        kwargs=probe.correction_calls[0],
    )
    review_1 = request_from_kwargs(
        task="supervisor_review",
        schema_version="supervisor.v1",
        kwargs=probe.review_calls[1],
    )
    write_fixture(fixture_dir, review_0, _fixture("supervisor_reject_response.json"))
    write_fixture(fixture_dir, correction_0, _fixture("supervisor_correction_response.json"))
    write_fixture(fixture_dir, review_1, _fixture("supervisor_approve_response.json"))

    replay = ReplayClient(fixture_dir)
    replay_output = _run_with_supervisor(SupervisorLoop(client=replay, correction_client=replay, settings=settings))
    structured = replay_output.structured_result
    checks = {
        "answer_matches_probe": structured.get("answer") == probe_output.structured_result.get("answer"),
        "approved": structured.get("supervisor_status") == "approved",
        "one_correction": structured.get("supervisor_corrections") == 1,
        "two_invocations": structured.get("supervisor_invocations") == 2,
        "residual_risk_recorded": bool(structured.get("supervisor_residual_risk")),
        "token_cost_recorded": structured.get("supervisor_token_cost") == 60,
    }
    return {
        "schema_version": "phase5.obj6b.supervisor_replay.v1",
        "fixture_dir": str(fixture_dir),
        "request_hashes": {
            "review_reject": review_0.request_hash,
            "correction": correction_0.request_hash,
            "review_approve": review_1.request_hash,
        },
        "checks": checks,
        "passed": all(checks.values()),
        "supervisor_status": structured.get("supervisor_status"),
        "supervisor_invocations": structured.get("supervisor_invocations"),
        "supervisor_corrections": structured.get("supervisor_corrections"),
        "supervisor_residual_risk": structured.get("supervisor_residual_risk"),
        "supervisor_token_cost": structured.get("supervisor_token_cost"),
        "token_cost": structured.get("token_cost"),
    }


def run_live_eval(*, fixture_dir: Path) -> dict[str, Any]:
    settings = load(ROOT)
    recorder = manual_e2e._recorder(settings, provider_name="anthropic", fixture_dir=fixture_dir)
    tracked = HashRecordingSupervisorClient(recorder)
    result = SupervisorLoop(client=tracked, correction_client=tracked, settings=settings).run(
        query=manual_e2e.DEFAULT_QUERY,
        output=_bad_candidate_output(),
        reviewer_notes=_live_reviewer_notes(),
    )
    structured = result.output.structured_result
    checks = {
        "approved": structured.get("supervisor_status") == "approved",
        "at_least_one_correction": int(structured.get("supervisor_corrections") or 0) >= 1,
        "at_least_two_invocations": int(structured.get("supervisor_invocations") or 0) >= 2,
        "residual_risk_recorded": bool(structured.get("supervisor_residual_risk")),
        "token_cost_recorded": int(structured.get("supervisor_token_cost") or 0) > 0,
        "correction_fixture_recorded": bool(tracked.correction_hashes),
    }
    return {
        "schema_version": "phase5.obj6b.supervisor_live.v1",
        "fixture_dir": str(fixture_dir),
        "checks": checks,
        "passed": all(checks.values()),
        "status": result.output.status,
        "supervisor_status": structured.get("supervisor_status"),
        "supervisor_invocations": structured.get("supervisor_invocations"),
        "supervisor_corrections": structured.get("supervisor_corrections"),
        "supervisor_residual_risk": structured.get("supervisor_residual_risk"),
        "supervisor_token_cost": structured.get("supervisor_token_cost"),
        "supervisor_cost": structured.get("supervisor_cost"),
        "token_cost": structured.get("token_cost"),
        "review_hashes": tracked.review_hashes,
        "correction_hashes": tracked.correction_hashes,
        "warnings": result.output.warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Obj6B supervisor replay gate.")
    parser.add_argument("--fixture-dir", type=Path, default=LLM_FIXTURES / "obj6b")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true", help="Run the explicit manual live Anthropic correction gate.")
    args = parser.parse_args(argv)

    report = run_live_eval(fixture_dir=args.fixture_dir) if args.live else run_eval(fixture_dir=args.fixture_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
