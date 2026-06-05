"""Schemas and fail-safe runtime loop for the extreme-task supervisor."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from vibration_agent.schemas import SkillOutput


class SupervisorAction(StrEnum):
    FINALIZE = "finalize"
    GPT_CORRECTION = "gpt_correction"
    OPUS_TAKEOVER = "opus_takeover"


class SupervisorPlan(BaseModel):
    task_id: str
    objective: str
    decomposition: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    acceptance_checks: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    task_id: str
    summary: str
    changed_files: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    severity: str = "medium"
    description: str
    file: str | None = None
    line: int | None = None
    recommendation: str = ""


class ReviewReport(BaseModel):
    task_id: str
    approved: bool = False
    issues: list[ReviewIssue] = Field(default_factory=list)
    residual_risk: str = ""


class RevisionRequest(BaseModel):
    task_id: str
    loop_count: int
    issues: list[ReviewIssue]
    action: SupervisorAction


class SupervisorLoopResult(BaseModel):
    output: SkillOutput
    supervisor_status: str
    supervisor_invocations: int = 0
    action: SupervisorAction | None = None
    issues: list[ReviewIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SupervisorClient(Protocol):
    def review(
        self,
        *,
        query: str,
        output: SkillOutput,
        loop_count: int,
        reviewer_notes: list[dict[str, Any]],
    ) -> ReviewReport: ...


def next_supervisor_action(review: ReviewReport, *, loop_count: int, max_gpt_loops: int = 2) -> SupervisorAction:
    if review.approved or not review.issues:
        return SupervisorAction.FINALIZE
    if loop_count < max_gpt_loops:
        return SupervisorAction.GPT_CORRECTION
    return SupervisorAction.OPUS_TAKEOVER


def _annotate_output(
    output: SkillOutput,
    *,
    supervisor_status: str,
    supervisor_invocations: int,
    action: SupervisorAction | None = None,
    issues: list[ReviewIssue] | None = None,
    warnings: list[str] | None = None,
) -> SkillOutput:
    updated = output.model_copy(deep=True)
    structured = dict(updated.structured_result)
    structured["supervisor_status"] = supervisor_status
    structured["supervisor_invocations"] = supervisor_invocations
    if action is not None:
        structured["supervisor_action"] = action.value
    if issues is not None:
        structured["supervisor_issues"] = [issue.model_dump(mode="json") for issue in issues]
    updated.structured_result = structured
    for warning in warnings or []:
        if warning not in updated.warnings:
            updated.warnings.append(warning)
    return updated


class SupervisorLoop:
    """Run the advisory Opus-supervisor loop without owning a network client."""

    def __init__(self, *, client: SupervisorClient | None = None, max_gpt_loops: int = 2) -> None:
        self.client = client
        self.max_gpt_loops = max_gpt_loops

    def annotate_not_triggered(self, output: SkillOutput) -> SkillOutput:
        return _annotate_output(
            output,
            supervisor_status="not_triggered",
            supervisor_invocations=0,
        )

    def run(
        self,
        *,
        query: str,
        output: SkillOutput,
        reviewer_notes: list[dict[str, Any]] | None = None,
    ) -> SupervisorLoopResult:
        notes = reviewer_notes or []
        if self.client is None:
            warning = "Opus supervisor unavailable; returning deterministic answer."
            annotated = _annotate_output(
                output,
                supervisor_status="fallback",
                supervisor_invocations=1,
                warnings=[warning],
            )
            return SupervisorLoopResult(
                output=annotated,
                supervisor_status="fallback",
                supervisor_invocations=1,
                warnings=[warning],
            )

        current = output
        invocations = 0
        try:
            for loop_count in range(self.max_gpt_loops + 1):
                review = self.client.review(
                    query=query,
                    output=current,
                    loop_count=loop_count,
                    reviewer_notes=notes,
                )
                invocations += 1
                action = next_supervisor_action(review, loop_count=loop_count, max_gpt_loops=self.max_gpt_loops)
                if action == SupervisorAction.FINALIZE:
                    annotated = _annotate_output(
                        current,
                        supervisor_status="approved",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=[],
                    )
                    return SupervisorLoopResult(
                        output=annotated,
                        supervisor_status="approved",
                        supervisor_invocations=invocations,
                        action=action,
                    )
                if action == SupervisorAction.OPUS_TAKEOVER:
                    warning = (
                        "Opus supervisor did not approve within the GPT correction loop limit; "
                        "returning deterministic answer."
                    )
                    annotated = _annotate_output(
                        current,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                    )
                    return SupervisorLoopResult(
                        output=annotated,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                    )
                # Obj13 establishes supervisor control flow and observability.
                # Real GPT correction is a future injected capability, so the
                # same deterministic candidate is re-reviewed until the limit.
        except Exception as exc:  # noqa: BLE001 - supervisor must never break answering
            warning = f"Opus supervisor failed; returning deterministic answer: {type(exc).__name__}: {exc}"
            annotated = _annotate_output(
                output,
                supervisor_status="fallback",
                supervisor_invocations=max(invocations, 1),
                warnings=[warning],
            )
            return SupervisorLoopResult(
                output=annotated,
                supervisor_status="fallback",
                supervisor_invocations=max(invocations, 1),
                warnings=[warning],
            )

        warning = "Opus supervisor loop exhausted unexpectedly; returning deterministic answer."
        annotated = _annotate_output(
            output,
            supervisor_status="fallback",
            supervisor_invocations=max(invocations, 1),
            warnings=[warning],
        )
        return SupervisorLoopResult(
            output=annotated,
            supervisor_status="fallback",
            supervisor_invocations=max(invocations, 1),
            warnings=[warning],
        )
