"""Schemas for the extreme-task supervisor loop."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


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


def next_supervisor_action(review: ReviewReport, *, loop_count: int, max_gpt_loops: int = 2) -> SupervisorAction:
    if review.approved or not review.issues:
        return SupervisorAction.FINALIZE
    if loop_count < max_gpt_loops:
        return SupervisorAction.GPT_CORRECTION
    return SupervisorAction.OPUS_TAKEOVER
