from vibration_agent.agent import ReviewIssue, ReviewReport, SupervisorLoop
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

    def review(self, *, query, output, loop_count, reviewer_notes):
        self.calls.append(loop_count)
        return ReviewReport(task_id="t1", issues=[ReviewIssue(description="limits still missing")])


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
    assert output.structured_result["supervisor_action"] == "opus_takeover"
    assert output.structured_result["supervisor_issues"][0]["description"] == "limits still missing"
    assert any("returning deterministic answer" in warning for warning in output.warnings)
    assert client.calls == [0, 1, 2]
