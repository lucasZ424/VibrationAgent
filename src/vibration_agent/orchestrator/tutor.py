"""Tutor-Orchestrator: the Phase-0 user-facing query entry point.

Phase-0 wiring calls only S2 -> S3 -> V4. Deferred skills stay registered but
are not invoked by this orchestrator.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from ..schemas import SkillInput, SkillOutput, UserMode
from ..skills import OutputStyleSkill, QASummarySkill, RetrievalSkill
from ..skills.base import Skill

_ASCII_STRONG_TERMS = (
    "vibration",
    "vibrations",
    "vibro",
    "rotor",
    "rotordynamics",
    "rotor dynamics",
    "rotating machinery",
    "critical speed",
    "damping",
    "damping ratio",
    "zeta",
    "resonance",
    "frequency response",
    "fft",
    "order tracking",
    "balancing",
    "unbalance",
    "misalignment",
    "condition monitoring",
    "iso 10816",
    "iso 20816",
    "api 684",
)
_ASCII_WEAK_TERMS = ("bearing", "modal", "orbit", "shaft", "spectrum", "spectral")
_ASCII_WEAK_CONTEXT_TERMS = (
    "analysis",
    "diagnosis",
    "diagnostic",
    "dynamics",
    "fault",
    "frequency",
    "machine",
    "machinery",
    "response",
    "signal",
    "turbine",
    "vibration",
)
_CJK_STRONG_TERMS = (
    "振动",
    "振动学",
    "转子",
    "转子动力学",
    "旋转机械",
    "轴承",
    "临界转速",
    "阻尼",
    "阻尼比",
    "模态",
    "固有频率",
    "共振",
    "频响",
    "频谱",
    "包络",
    "阶次",
    "轴心轨迹",
    "动平衡",
    "不平衡",
    "不对中",
    "轴系",
    "状态监测",
    "故障诊断",
)
_CJK_WEAK_TERMS = ("标准",)
_CJK_WEAK_CONTEXT_TERMS = ("振动", "转子", "旋转机械", "轴承", "频谱", "状态监测", "故障诊断", "临界转速")
_NEGATIVE_SCOPE_PATTERNS = (
    "autism spectrum",
    "balance sheet",
    "elevator shaft",
    "english modal",
    "modal verb",
    "modal verbs",
    "shaft of an elevator",
    "standard operating procedure",
)
_OUT_OF_SCOPE = {
    "zh": "范围外：Phase-0 只处理振动、旋转机械、信号分析、状态监测和相关标准问题。",
    "en": "Out of scope: Phase-0 only handles vibration, rotating machinery, signal analysis, condition monitoring, and related standards.",
}


def _task_id(value: str | None = None) -> str:
    return value or f"task-{uuid4().hex}"


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _query_language(query: str) -> str:
    return "zh" if _has_cjk(query) else "en"


def _word_match(query: str, term: str) -> bool:
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![A-Za-z0-9])"
    return re.search(pattern, query, flags=re.IGNORECASE) is not None


def _any_word_match(query: str, terms: tuple[str, ...]) -> bool:
    return any(_word_match(query, term) for term in terms)


def _is_explicitly_in_scope(context: Mapping[str, Any], constraints: Mapping[str, Any]) -> bool | None:
    for mapping in (constraints, context):
        value = mapping.get("scope") or mapping.get("domain_scope")
        if value in {"in_scope", "vibration", "rotating_machinery", "signal_analysis", "standards_interpretation"}:
            return True
        if value in {"out_of_scope", "out-of-scope"}:
            return False
    return None


def is_in_scope(query: str, *, context: Mapping[str, Any] | None = None, constraints: Mapping[str, Any] | None = None) -> bool:
    """Return whether a query belongs to the Phase-0 domain boundary."""

    context = context or {}
    constraints = constraints or {}
    explicit = _is_explicitly_in_scope(context, constraints)
    if explicit is not None:
        return explicit

    normalized = query.casefold()
    if any(pattern in normalized for pattern in _NEGATIVE_SCOPE_PATTERNS):
        return False
    if _any_word_match(query, _ASCII_STRONG_TERMS):
        return True
    if any(term in query for term in _CJK_STRONG_TERMS):
        return True
    if _any_word_match(query, _ASCII_WEAK_TERMS) and _any_word_match(query, _ASCII_WEAK_CONTEXT_TERMS):
        return True
    if any(term in query for term in _CJK_WEAK_TERMS) and any(term in query for term in _CJK_WEAK_CONTEXT_TERMS):
        return True
    return False


def _copy_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(context or {})


def _copy_constraints(constraints: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(constraints or {})


def _merge_warnings(*outputs: SkillOutput) -> list[str]:
    warnings: list[str] = []
    for output in outputs:
        warnings.extend(output.warnings)
    return warnings


def _chain_step(skill_name: str, output: SkillOutput) -> dict[str, str]:
    return {"skill": skill_name, "status": output.status, "summary": output.summary}


def _skill_results(**results: SkillOutput) -> dict[str, dict[str, Any]]:
    return {name: output.structured_result for name, output in results.items()}


class TutorOrchestrator:
    """Minimal Phase-0 orchestrator for evidence-bound tutoring answers."""

    def __init__(
        self,
        *,
        retrieval_skill: Skill | None = None,
        qa_summary_skill: Skill | None = None,
        style_skill: Skill | None = None,
    ) -> None:
        self.retrieval_skill = retrieval_skill or RetrievalSkill()
        self.qa_summary_skill = qa_summary_skill or QASummarySkill()
        self.style_skill = style_skill or OutputStyleSkill()

    def _early_return(
        self,
        *,
        task_id: str,
        source: SkillOutput,
        chain: list[dict[str, str]],
        warnings: list[str],
        skill_results: dict[str, dict[str, Any]],
    ) -> SkillOutput:
        answer = source.structured_result.get("answer") if isinstance(source.structured_result.get("answer"), str) else source.summary
        return SkillOutput(
            status=source.status,
            summary=source.summary,
            structured_result={
                "task_id": task_id,
                "scope": "in_scope",
                "answer": answer,
                "chain": chain,
                "skill_results": skill_results,
            },
            citations=source.citations,
            warnings=warnings,
            handoff_recommendation=source.handoff_recommendation,
        )

    def handle_query(
        self,
        query: str,
        *,
        context: Mapping[str, Any] | None = None,
        constraints: Mapping[str, Any] | None = None,
        user_mode: UserMode = "engineering",
        task_id: str | None = None,
    ) -> SkillOutput:
        context_dict = _copy_context(context)
        constraints_dict = _copy_constraints(constraints)
        current_task_id = _task_id(task_id or str(context_dict.get("task_id") or constraints_dict.get("task_id") or ""))

        if not is_in_scope(query, context=context_dict, constraints=constraints_dict):
            language = _query_language(query)
            summary = _OUT_OF_SCOPE[language]
            return SkillOutput(
                status="insufficient",
                summary=summary,
                structured_result={
                    "task_id": current_task_id,
                    "scope": "out_of_scope",
                    "language": language,
                    "chain": [],
                    "skill_results": {},
                    "answer": summary,
                },
                warnings=["Query is outside the Phase-0 vibration-agent scope."],
                handoff_recommendation="Ask a question about vibration, rotating machinery, signal analysis, condition monitoring, or related standards.",
            )

        s2_input = SkillInput(
            task_id=current_task_id,
            user_query=query,
            context=context_dict,
            constraints=constraints_dict,
            user_mode=user_mode,
        )
        s2_output = self.retrieval_skill.run(s2_input)
        s2_chain = [_chain_step("s2_retrieval", s2_output)]
        if s2_output.status != "ok":
            return self._early_return(
                task_id=current_task_id,
                source=s2_output,
                chain=s2_chain,
                warnings=s2_output.warnings,
                skill_results=_skill_results(s2=s2_output),
            )

        s3_context = {
            **context_dict,
            "s2_result": s2_output.model_dump(mode="python"),
        }
        s3_input = SkillInput(
            task_id=current_task_id,
            user_query=query,
            context=s3_context,
            constraints=constraints_dict,
            user_mode=user_mode,
        )
        s3_output = self.qa_summary_skill.run(s3_input)
        s3_chain = [*s2_chain, _chain_step("s3_qa_summary", s3_output)]
        if s3_output.status != "ok":
            return self._early_return(
                task_id=current_task_id,
                source=s3_output,
                chain=s3_chain,
                warnings=_merge_warnings(s2_output, s3_output),
                skill_results=_skill_results(s2=s2_output, s3=s3_output),
            )

        v4_context = {
            **context_dict,
            "s2_result": s2_output.model_dump(mode="python"),
            "s3_result": s3_output.model_dump(mode="python"),
        }
        v4_input = SkillInput(
            task_id=current_task_id,
            user_query=query,
            context=v4_context,
            constraints=constraints_dict,
            user_mode=user_mode,
        )
        v4_output = self.style_skill.run(v4_input)
        chain = [*s3_chain, _chain_step("v4_style", v4_output)]
        final_status = "fail" if "fail" in {s2_output.status, s3_output.status, v4_output.status} else v4_output.status

        return SkillOutput(
            status=final_status,
            summary=v4_output.summary,
            structured_result={
                "task_id": current_task_id,
                "scope": "in_scope",
                "chain": chain,
                "answer": v4_output.structured_result.get("answer", ""),
                "v4": v4_output.structured_result,
                "skill_results": _skill_results(s2=s2_output, s3=s3_output, v4=v4_output),
            },
            citations=v4_output.citations,
            warnings=_merge_warnings(s2_output, s3_output, v4_output),
            handoff_recommendation=v4_output.handoff_recommendation,
        )


def handle_query(
    query: str,
    *,
    context: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
    user_mode: UserMode = "engineering",
    task_id: str | None = None,
) -> SkillOutput:
    """Handle a user query through the default Phase-0 Tutor-Orchestrator."""

    return TutorOrchestrator().handle_query(
        query,
        context=context,
        constraints=constraints,
        user_mode=user_mode,
        task_id=task_id,
    )