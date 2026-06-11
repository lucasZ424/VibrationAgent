"""Schemas and fail-safe runtime loop for the extreme-task supervisor."""
from __future__ import annotations

import inspect
import json
from enum import StrEnum
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from vibration_agent.schemas import SkillOutput

_REVIEW_PROMPT_VERSION = "supervisor_review.v1"
_CORRECTION_PROMPT_VERSION = "supervisor_correction.v1"
_REVIEW_SCHEMA_VERSION = "supervisor.v1"
_CORRECTION_SCHEMA_VERSION = "correction.v1"


class SupervisorAction(StrEnum):
    FINALIZE = "finalize"
    GPT_CORRECTION = "gpt_correction"
    CORRECTION_LIMIT_FALLBACK = "correction_limit_fallback"


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
    status: Literal["ok", "insufficient", "refusal", "refused"] = "ok"
    task_id: str
    approved: bool = False
    issues: list[ReviewIssue] = Field(default_factory=list)
    residual_risk: str = ""
    warnings: list[str] = Field(default_factory=list)
    token_cost: int | None = Field(default=None, ge=0)
    cost: dict[str, Any] | None = None


class SupervisorCorrectionResponse(BaseModel):
    status: Literal["ok", "insufficient", "refusal", "refused"] = "ok"
    answer: str = ""
    summary: str = ""
    structured_result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    token_cost: int | None = Field(default=None, ge=0)
    cost: dict[str, Any] | None = None

    @model_validator(mode="after")
    def ok_response_must_include_candidate_update(self) -> "SupervisorCorrectionResponse":
        if self.status == "ok" and not self.answer and not self.structured_result:
            raise ValueError("ok supervisor correction must include answer or structured_result")
        return self


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


class CorrectionClient(Protocol):
    def correct(
        self,
        *,
        query: str,
        output: SkillOutput,
        review: ReviewReport,
        loop_count: int,
        reviewer_notes: list[dict[str, Any]],
    ) -> dict[str, Any] | SkillOutput: ...


def next_supervisor_action(review: ReviewReport, *, loop_count: int, max_gpt_loops: int = 2) -> SupervisorAction:
    if review.approved or not review.issues:
        return SupervisorAction.FINALIZE
    if loop_count < max_gpt_loops:
        return SupervisorAction.GPT_CORRECTION
    return SupervisorAction.CORRECTION_LIMIT_FALLBACK


def _annotate_output(
    output: SkillOutput,
    *,
    supervisor_status: str,
    supervisor_invocations: int,
    action: SupervisorAction | None = None,
    issues: list[ReviewIssue] | None = None,
    warnings: list[str] | None = None,
    supervisor_corrections: int = 0,
    supervisor_token_cost: int | None = None,
    supervisor_costs: list[dict[str, Any]] | None = None,
) -> SkillOutput:
    updated = output.model_copy(deep=True)
    structured = dict(updated.structured_result)
    structured["supervisor_status"] = supervisor_status
    structured["supervisor_invocations"] = supervisor_invocations
    structured["supervisor_corrections"] = supervisor_corrections
    if action is not None:
        structured["supervisor_action"] = action.value
    if issues is not None:
        structured["supervisor_issues"] = [issue.model_dump(mode="json") for issue in issues]
    if supervisor_token_cost is not None:
        structured["supervisor_token_cost"] = supervisor_token_cost
        existing = structured.get("token_cost")
        structured["token_cost"] = int(existing or 0) + supervisor_token_cost
    if supervisor_costs:
        structured["supervisor_cost"] = supervisor_costs
    updated.structured_result = structured
    for warning in warnings or []:
        if warning not in updated.warnings:
            updated.warnings.append(warning)
    return updated


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        dumped = value.model_dump(mode="python")
        return dumped if isinstance(dumped, Mapping) else {}
    return value if isinstance(value, Mapping) else {}


def _metadata(value: Any) -> tuple[int | None, dict[str, Any] | None]:
    data = _as_mapping(value)
    token_cost = data.get("token_cost")
    cost = data.get("cost")
    return (int(token_cost) if token_cost not in (None, "") else None), (dict(cost) if isinstance(cost, Mapping) else None)


def _accepts_llm_kwargs(method: Any) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return True
    parameters = signature.parameters.values()
    return any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters) or "prompt_version" in signature.parameters


def _task_id(output: SkillOutput, fallback: str = "supervisor") -> str:
    value = output.structured_result.get("task_id")
    return str(value or fallback)


def _review_report_from_response(response: ReviewReport | Mapping[str, Any], *, task_id: str) -> ReviewReport:
    if isinstance(response, ReviewReport):
        return response
    data = dict(response)
    data.setdefault("task_id", task_id)
    if isinstance(data.get("issues"), list):
        data["issues"] = [_review_issue_payload(issue) for issue in data["issues"]]
    return ReviewReport.model_validate(data)


def _review_issue_payload(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    issue = dict(value)
    if not issue.get("description"):
        issue["description"] = str(
            issue.get("message")
            or issue.get("recommendation")
            or issue.get("code")
            or "Supervisor returned an issue without a description."
        )
    return issue


def _prompt(*, query: str, output: SkillOutput, reviewer_notes: list[dict[str, Any]], loop_count: int, purpose: str) -> str:
    payload = {
        "purpose": purpose,
        "query": query,
        "loop_count": loop_count,
        "candidate": output.model_dump(mode="json"),
        "reviewer_notes": reviewer_notes,
    }
    return (
        "You are the senior supervisor for a vibration-engineering answer. "
        "Use only the supplied candidate, citations, reviewer notes, and issues. "
        "Return only valid JSON matching the requested schema.\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def _provider_kwargs(settings: Any) -> dict[str, Any]:
    provider = settings.llm.anthropic
    return {
        "model": f"{provider.provider}:{provider.model}",
        "max_tokens": provider.max_tokens,
        "timeout": provider.timeout,
    }


def _review_kwargs(
    *,
    settings: Any,
    query: str,
    output: SkillOutput,
    loop_count: int,
    reviewer_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_provider_kwargs(settings),
        "prompt_version": _REVIEW_PROMPT_VERSION,
        "schema_version": _REVIEW_SCHEMA_VERSION,
        "prompt": _prompt(
            query=query,
            output=output,
            reviewer_notes=reviewer_notes,
            loop_count=loop_count,
            purpose="review",
        ),
        "task_id": _task_id(output),
        "query": query,
        "candidate": output.model_dump(mode="json"),
        "loop_count": loop_count,
        "reviewer_notes": reviewer_notes,
    }


def _correction_kwargs(
    *,
    settings: Any,
    query: str,
    output: SkillOutput,
    review: ReviewReport,
    loop_count: int,
    reviewer_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_provider_kwargs(settings),
        "prompt_version": _CORRECTION_PROMPT_VERSION,
        "schema_version": _CORRECTION_SCHEMA_VERSION,
        "prompt": _prompt(
            query=query,
            output=output,
            reviewer_notes=reviewer_notes,
            loop_count=loop_count,
            purpose="correct",
        ),
        "task_id": _task_id(output),
        "query": query,
        "candidate": output.model_dump(mode="json"),
        "review": review.model_dump(mode="json"),
        "loop_count": loop_count,
        "reviewer_notes": reviewer_notes,
    }


def _apply_correction(current: SkillOutput, response: dict[str, Any] | SkillOutput) -> SkillOutput:
    if isinstance(response, SkillOutput):
        return response

    correction = SupervisorCorrectionResponse.model_validate(response)
    if correction.status != "ok":
        raise ValueError(f"Synthetic correction returned {correction.status}")

    updated = current.model_copy(deep=True)
    structured = dict(updated.structured_result)
    if correction.structured_result:
        structured.update(correction.structured_result)

    answer = correction.answer or str(structured.get("answer") or "")
    if not answer:
        raise ValueError("Supervisor correction did not provide an answer")
    structured["answer"] = answer
    v4 = structured.get("v4")
    if isinstance(v4, Mapping):
        nested_v4 = dict(v4)
        nested_v4["answer"] = answer
        structured["v4"] = nested_v4

    updated.structured_result = structured
    if correction.summary:
        updated.summary = correction.summary
    for warning in correction.warnings:
        if warning not in updated.warnings:
            updated.warnings.append(warning)
    return updated


class SupervisorLoop:
    """Run the advisory Opus-supervisor loop without owning a network client."""

    def __init__(
        self,
        *,
        client: SupervisorClient | None = None,
        correction_client: CorrectionClient | None = None,
        max_gpt_loops: int = 2,
        settings: Any | None = None,
    ) -> None:
        self.client = client
        self.correction_client = correction_client if correction_client is not None else client
        self.max_gpt_loops = max_gpt_loops
        self.settings = settings

    def _settings(self) -> Any:
        if self.settings is None:
            from vibration_agent.config import load

            self.settings = load()
        return self.settings

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
        corrections = 0
        supervisor_token_cost = 0
        supervisor_costs: list[dict[str, Any]] = []
        try:
            for loop_count in range(self.max_gpt_loops + 1):
                review_response = self._call_review_client(
                    query=query,
                    output=current,
                    loop_count=loop_count,
                    reviewer_notes=notes,
                )
                token_cost, cost = _metadata(review_response)
                if token_cost is not None:
                    supervisor_token_cost += token_cost
                if cost is not None:
                    supervisor_costs.append(cost)
                review = _review_report_from_response(review_response, task_id=_task_id(current))
                if review.status != "ok":
                    raise ValueError(f"Opus supervisor returned {review.status}")
                invocations += 1
                action = next_supervisor_action(review, loop_count=loop_count, max_gpt_loops=self.max_gpt_loops)
                if action == SupervisorAction.FINALIZE:
                    annotated = _annotate_output(
                        current,
                        supervisor_status="approved",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=[],
                        warnings=review.warnings,
                        supervisor_corrections=corrections,
                        supervisor_token_cost=supervisor_token_cost or None,
                        supervisor_costs=supervisor_costs,
                    )
                    return SupervisorLoopResult(
                        output=annotated,
                        supervisor_status="approved",
                        supervisor_invocations=invocations,
                        action=action,
                    )
                if action == SupervisorAction.CORRECTION_LIMIT_FALLBACK:
                    warning = (
                        "Opus supervisor did not approve within the GPT correction loop limit; "
                        "returning deterministic answer."
                    )
                    annotated = _annotate_output(
                        output,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                        supervisor_corrections=corrections,
                        supervisor_token_cost=supervisor_token_cost or None,
                        supervisor_costs=supervisor_costs,
                    )
                    return SupervisorLoopResult(
                        output=annotated,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                    )
                if self.correction_client is None or not hasattr(self.correction_client, "correct"):
                    warning = "Supervisor correction client unavailable; returning deterministic answer."
                    annotated = _annotate_output(
                        output,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                        supervisor_corrections=corrections,
                        supervisor_token_cost=supervisor_token_cost or None,
                        supervisor_costs=supervisor_costs,
                    )
                    return SupervisorLoopResult(
                        output=annotated,
                        supervisor_status="fallback",
                        supervisor_invocations=invocations,
                        action=action,
                        issues=review.issues,
                        warnings=[warning],
                    )
                correction_response = self._call_correction_client(
                    query=query,
                    output=current,
                    review=review,
                    loop_count=loop_count,
                    reviewer_notes=notes,
                )
                token_cost, cost = _metadata(correction_response)
                if token_cost is not None:
                    supervisor_token_cost += token_cost
                if cost is not None:
                    supervisor_costs.append(cost)
                current = _apply_correction(current, correction_response)
                corrections += 1
        except Exception as exc:  # noqa: BLE001 - supervisor must never break answering
            warning = f"Opus supervisor failed; returning deterministic answer: {type(exc).__name__}: {exc}"
            annotated = _annotate_output(
                output,
                supervisor_status="fallback",
                supervisor_invocations=max(invocations, 1),
                warnings=[warning],
                supervisor_corrections=corrections,
                supervisor_token_cost=supervisor_token_cost or None,
                supervisor_costs=supervisor_costs,
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
            supervisor_corrections=corrections,
            supervisor_token_cost=supervisor_token_cost or None,
            supervisor_costs=supervisor_costs,
        )
        return SupervisorLoopResult(
            output=annotated,
            supervisor_status="fallback",
            supervisor_invocations=max(invocations, 1),
            warnings=[warning],
        )

    def _call_review_client(
        self,
        *,
        query: str,
        output: SkillOutput,
        loop_count: int,
        reviewer_notes: list[dict[str, Any]],
    ) -> ReviewReport | dict[str, Any]:
        assert self.client is not None
        method = self.client.review
        if _accepts_llm_kwargs(method):
            return method(
                **_review_kwargs(
                    settings=self._settings(),
                    query=query,
                    output=output,
                    loop_count=loop_count,
                    reviewer_notes=reviewer_notes,
                )
            )
        return method(query=query, output=output, loop_count=loop_count, reviewer_notes=reviewer_notes)

    def _call_correction_client(
        self,
        *,
        query: str,
        output: SkillOutput,
        review: ReviewReport,
        loop_count: int,
        reviewer_notes: list[dict[str, Any]],
    ) -> dict[str, Any] | SkillOutput:
        assert self.correction_client is not None
        method = self.correction_client.correct
        if _accepts_llm_kwargs(method):
            return method(
                **_correction_kwargs(
                    settings=self._settings(),
                    query=query,
                    output=output,
                    review=review,
                    loop_count=loop_count,
                    reviewer_notes=reviewer_notes,
                )
            )
        return method(query=query, output=output, review=review, loop_count=loop_count, reviewer_notes=reviewer_notes)
