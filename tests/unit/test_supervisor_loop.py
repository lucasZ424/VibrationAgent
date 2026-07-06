import json
from pathlib import Path

from vibration_agent.agent import ReviewIssue, ReviewReport, SupervisorLoop
from vibration_agent.config import load
from vibration_agent.llm.budget import BudgetDeniedError
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs, write_fixture
from vibration_agent.orchestrator import TutorOrchestrator
from vibration_agent.schemas import SkillInput, SkillOutput
from vibration_agent.skills.base import Skill


class RecordingSkill(Skill):
    name = "recording"

    def __init__(self, output: SkillOutput) -> None:
        self.output = output
        self.calls: list[SkillInput] = []

    def run(self, payload: SkillInput) -> SkillOutput:
        self.calls.append(payload)
        return self.output


class ApprovingSupervisor:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.calls.append(loop_count)
        return ReviewReport(task_id="t1", approved=True)


class RejectingSupervisor:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.corrections: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.calls.append(loop_count)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="limits still missing")])

    def correct(self, *, query, output, review, loop_count, reviewer_notes):
        self.corrections.append(loop_count)
        return {"status": "ok", "answer": output.structured_result["answer"], "summary": output.summary}


class RejectThenApproveSupervisor:
    def __init__(self) -> None:
        self.review_calls: list[int] = []
        self.correction_calls: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.review_calls.append(loop_count)
        if "boundary condition" in output.structured_result["answer"].casefold():
            return ReviewReport(task_id="t1", approved=True)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="missing boundary condition")])

    def correct(self, *, query, output, review, loop_count, reviewer_notes):
        self.correction_calls.append(loop_count)
        return {
            "status": "ok",
            "answer": output.structured_result["answer"] + "\nBoundary condition: use the cited operating region.",
            "summary": "Corrected candidate.",
        }


class ProbeSupervisorClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.review_calls: list[dict] = []
        self.correction_calls: list[dict] = []

    def review(self, **kwargs):
        self.review_calls.append(kwargs)
        return self.responses.pop(0)

    def correct(self, **kwargs):
        self.correction_calls.append(kwargs)
        return self.responses.pop(0)


class BudgetDeniedSupervisor:
    def review(self, *, query, output, loop_count, reviewer_notes):
        raise BudgetDeniedError("per-task token budget exceeded")


class MalformedCorrectionSupervisor:
    def __init__(self) -> None:
        self.review_calls: list[int] = []
        self.correction_calls: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.review_calls.append(loop_count)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="missing boundary condition")])

    def correct(self, *, query, output, review, loop_count, reviewer_notes):
        self.correction_calls.append(loop_count)
        return {"status": "ok", "summary": "Claimed correction without candidate content."}


class StructuredResultCorrectionSupervisor:
    def __init__(self) -> None:
        self.review_calls: list[int] = []
        self.correction_calls: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.review_calls.append(loop_count)
        if "boundary condition" in output.structured_result["answer"].casefold():
            return ReviewReport(task_id="t1", approved=True)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="missing boundary condition")])

    def correct(self, *, query, output, review, loop_count, reviewer_notes):
        self.correction_calls.append(loop_count)
        return {
            "status": "ok",
            "summary": "Corrected via structured_result.",
            "structured_result": {
                "answer": output.structured_result["answer"]
                + "\nBoundary condition: use the cited operating region."
            },
        }


class NestedJsonAnswerCorrectionSupervisor:
    def __init__(self) -> None:
        self.review_calls: list[int] = []
        self.correction_calls: list[int] = []

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.review_calls.append(loop_count)
        if "clean corrected answer" in output.structured_result["answer"].casefold():
            return ReviewReport(task_id="t1", approved=True)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="answer needs cleanup")])

    def correct(self, *, query, output, review, loop_count, reviewer_notes):
        self.correction_calls.append(loop_count)
        nested = {
            "status": "ok",
            "answer": "Clean corrected answer.",
            "summary": "Corrected nested payload.",
            "structured_result": {"answer": "Clean corrected answer."},
        }
        return {"answer": json.dumps(nested), "token_cost": 7}


def _fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "llm" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _orchestrator(*, supervisor_loop: SupervisorLoop) -> TutorOrchestrator:
    s2 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="S2 ok",
            structured_result={"retrieval_context": [{"chunk_id": "c1", "doc_id": "d1", "text": "Critical speed affects response."}]},
        )
    )
    s3 = RecordingSkill(SkillOutput(status="ok", summary="S3 ok", structured_result={"answer": "S3 answer"}))
    v2 = RecordingSkill(SkillOutput(status="ok", summary="V2 ok", structured_result={"answer": "V2 answer"}))
    v4 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V4 ok",
            structured_result={
                "answer": "## Conclusion\nCritical speed affects rotor response.\n\n## Evidence\nCritical speed affects response.",
                "sections": {
                    "conclusion": "Critical speed affects rotor response.",
                    "evidence": "Critical speed affects response.",
                },
            },
        )
    )
    v3 = RecordingSkill(
        SkillOutput(
            status="ok",
            summary="V3 ok",
            structured_result={"reviewer_notes": []},
        )
    )
    return TutorOrchestrator(
        retrieval_skill=s2,
        qa_summary_skill=s3,
        citation_check_skill=v2,
        style_skill=v4,
        reviewer_skill=v3,
        supervisor_loop=supervisor_loop,
    )


def test_supervisor_loop_not_triggered_for_normal_query():
    client = ApprovingSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "not_triggered"
    assert output.structured_result["supervisor_invocations"] == 0
    assert client.calls == []


def test_supervisor_loop_runs_for_extreme_query_and_can_approve():
    client = ApprovingSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "approved"
    assert output.structured_result["supervisor_invocations"] == 1
    assert output.structured_result["supervisor_action"] == "finalize"
    assert client.calls == [0]


def test_supervisor_loop_falls_back_after_review_loop_limit():
    client = RejectingSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client, max_gpt_loops=2)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["answer"].startswith("## Conclusion")
    assert output.structured_result["supervisor_status"] == "fallback"
    assert output.structured_result["supervisor_invocations"] == 3
    assert output.structured_result["supervisor_action"] == "correction_limit_fallback"
    assert output.structured_result["supervisor_issues"][0]["description"] == "limits still missing"
    assert any("returning deterministic answer" in warning for warning in output.warnings)
    assert client.calls == [0, 1, 2]
    assert client.corrections == [0, 1]


def test_supervisor_loop_reject_correct_approve_returns_improved_candidate():
    client = RejectThenApproveSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "approved"
    assert output.structured_result["supervisor_invocations"] == 2
    assert output.structured_result["supervisor_corrections"] == 1
    assert "boundary condition" in output.structured_result["answer"].casefold()
    assert output.structured_result["v4"]["answer"] == output.structured_result["answer"]
    assert client.review_calls == [0, 1]
    assert client.correction_calls == [0]


def test_supervisor_loop_rejects_malformed_ok_correction_without_approving():
    # WHY: Obj6B's supervisor correction gate must not treat a schema-shaped
    # empty "ok" as an improved answer. The only safe result is visible fallback.
    client = MalformedCorrectionSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "fallback"
    assert output.structured_result["supervisor_corrections"] == 0
    assert output.structured_result["answer"].startswith("## Conclusion")
    assert client.review_calls == [0]
    assert client.correction_calls == [0]
    assert any("answer or structured_result" in warning for warning in output.warnings)


def test_supervisor_loop_accepts_structured_result_only_correction():
    # WHY: The Obj6B correction contract permits either a top-level answer or a
    # structured_result carrying the candidate answer; both paths must remain valid.
    client = StructuredResultCorrectionSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "approved"
    assert output.structured_result["supervisor_corrections"] == 1
    assert "boundary condition" in output.structured_result["answer"].casefold()
    assert output.structured_result["v4"]["answer"] == output.structured_result["answer"]
    assert client.review_calls == [0, 1]
    assert client.correction_calls == [0]


def test_supervisor_loop_unwraps_nested_json_correction_answer():
    # WHY: Live Opus may put the whole correction JSON inside answer; applying
    # that string directly corrupts the final V4 payload.
    client = NestedJsonAnswerCorrectionSupervisor()
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.structured_result["supervisor_status"] == "approved"
    assert output.structured_result["answer"] == "Clean corrected answer."
    assert not output.structured_result["answer"].startswith("{")
    assert output.summary == "Corrected nested payload."


def test_supervisor_loop_replay_reject_correct_approve_records_token_cost(tmp_path):
    settings = load()
    responses = [
        _fixture("supervisor_reject_response.json"),
        _fixture("supervisor_correction_response.json"),
        _fixture("supervisor_approve_response.json"),
    ]
    probe = ProbeSupervisorClient(responses)

    probe_output = _orchestrator(supervisor_loop=SupervisorLoop(client=probe, settings=settings)).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )
    write_fixture(
        tmp_path,
        request_from_kwargs(task="supervisor_review", schema_version="supervisor.v1", kwargs=probe.review_calls[0]),
        _fixture("supervisor_reject_response.json"),
    )
    write_fixture(
        tmp_path,
        request_from_kwargs(task="supervisor_correction", schema_version="correction.v1", kwargs=probe.correction_calls[0]),
        _fixture("supervisor_correction_response.json"),
    )
    write_fixture(
        tmp_path,
        request_from_kwargs(task="supervisor_review", schema_version="supervisor.v1", kwargs=probe.review_calls[1]),
        _fixture("supervisor_approve_response.json"),
    )

    replay_output = _orchestrator(
        supervisor_loop=SupervisorLoop(client=ReplayClient(tmp_path), settings=settings)
    ).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert probe_output.structured_result["answer"] == replay_output.structured_result["answer"]
    assert replay_output.structured_result["supervisor_status"] == "approved"
    assert replay_output.structured_result["supervisor_invocations"] == 2
    assert replay_output.structured_result["supervisor_corrections"] == 1
    assert replay_output.structured_result["supervisor_residual_risk"] == "Low residual risk after correction."
    assert replay_output.structured_result["supervisor_token_cost"] == 60
    assert replay_output.structured_result["token_cost"] == 60


def test_supervisor_loop_fills_missing_review_task_id_from_candidate():
    client = ProbeSupervisorClient([{"status": "ok", "approved": True}])

    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client, settings=load())).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.structured_result["supervisor_status"] == "approved"
    assert output.structured_result["supervisor_invocations"] == 1
    assert client.review_calls[0]["task_id"] == "t1"


def test_supervisor_loop_fills_issue_description_from_message():
    client = ProbeSupervisorClient(
        [
            {
                "status": "ok",
                "approved": False,
                "issues": [{"code": "missing_limits", "message": "Limits section is missing."}],
            },
            {"status": "ok", "answer": "Corrected answer.", "summary": "Corrected."},
            {"status": "ok", "approved": True},
        ]
    )

    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client, settings=load())).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.structured_result["supervisor_status"] == "approved"
    assert client.correction_calls[0]["review"]["issues"][0]["description"] == "Limits section is missing."


def test_supervisor_loop_prompts_pin_live_schema_status_values():
    # WHY: Live Opus may otherwise return a correction-shaped payload during
    # review, such as status="revised", which must be rejected before replay.
    client = ProbeSupervisorClient(
        [
            {"status": "ok", "approved": False, "issues": [{"description": "missing boundary condition"}]},
            {"status": "ok", "answer": "Corrected answer.", "summary": "Corrected."},
            {"status": "ok", "approved": True},
        ]
    )

    _orchestrator(supervisor_loop=SupervisorLoop(client=client, settings=load())).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert "Do not return a revised answer in the review response." in client.review_calls[0]["prompt"]
    assert 'Do not use "revised".' in client.correction_calls[0]["prompt"]


def test_supervisor_loop_normalizes_text_location_in_review_issue_line():
    # WHY: Live Opus can put a paragraph/chunk location string into issues[].line;
    # the review should stay usable instead of falling back on a type mismatch.
    client = ProbeSupervisorClient(
        [
            {
                "status": "ok",
                "approved": False,
                "issues": [
                    {
                        "description": "Clarify the diagnostic discriminator.",
                        "line": "evidence bullet (chunk_1)",
                    }
                ],
            },
            {"status": "ok", "answer": "Corrected answer.", "summary": "Corrected."},
            {"status": "ok", "approved": True},
        ]
    )

    output = _orchestrator(supervisor_loop=SupervisorLoop(client=client, settings=load())).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.structured_result["supervisor_status"] == "approved"
    assert client.correction_calls[0]["review"]["issues"][0]["line"] is None
    assert "Location: evidence bullet (chunk_1)" in client.correction_calls[0]["review"]["issues"][0]["recommendation"]


def test_supervisor_loop_replay_miss_falls_back_to_deterministic_answer(tmp_path):
    output = _orchestrator(
        supervisor_loop=SupervisorLoop(client=ReplayClient(tmp_path), settings=load())
    ).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "fallback"
    assert output.structured_result["supervisor_invocations"] == 1
    assert output.structured_result["answer"].startswith("## Conclusion")
    assert any("ReplayMissError" in warning for warning in output.warnings)


def test_supervisor_loop_budget_deny_falls_back_to_deterministic_answer():
    output = _orchestrator(supervisor_loop=SupervisorLoop(client=BudgetDeniedSupervisor())).handle_query(
        "critical speed",
        constraints={"scope": "in_scope", "difficulty": "extreme"},
        task_id="t1",
    )

    assert output.status == "ok"
    assert output.structured_result["supervisor_status"] == "fallback"
    assert output.structured_result["supervisor_invocations"] == 1
    assert output.structured_result["answer"].startswith("## Conclusion")
    assert any("BudgetDeniedError" in warning for warning in output.warnings)
