"""Tutor-Orchestrator: the Phase-0 user-facing query entry point.

Phase-2 wiring calls S2 -> S3 -> V2 -> V4, with V3 reviewer added only for
extreme tasks. S6-S8 remain off the default path and require the Phase-4
advisory routing gate.
"""
from __future__ import annotations

import re
import time
from math import log2
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from ..agent.routing import AdvisoryRoutingDecision, Difficulty, RouteDecision, route_advisory_skills, route_task
from ..agent.supervisor import SupervisorLoop
from ..config import load
from ..retrieval.query_normalize import alias_family_coverage, is_corpus_standard_query
from ..schemas import SkillInput, SkillOutput, UserMode
from ..skills import (
    CitationCheckSkill,
    EngineeringAnalysisSkill,
    FormulaDerivationSkill,
    OutputStyleSkill,
    QASummarySkill,
    RetrievalSkill,
    ReviewerSkill,
    TermSymbolUnitNormalizerSkill,
)
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

# Normal Chinese terms for live operator input. The legacy mojibake constants
# above are kept only for backward compatibility with older fixtures.
_CJK_STRONG_TERMS = (
    *_CJK_STRONG_TERMS,
    "振动",
    "振动学",
    "转子",
    "转子动力学",
    "旋转机械",
    "轴承",
    "临界转速",
    "临界速度",
    "阻尼",
    "阻尼比",
    "模态",
    "固有频率",
    "共振",
    "频响",
    "频谱",
    "包络",
    "阶次",
    "阶比",
    "轴心轨迹",
    "动平衡",
    "不平衡",
    "不对中",
    "轴系",
    "状态监测",
    "故障诊断",
    "扭振",
)
_CJK_WEAK_TERMS = (*_CJK_WEAK_TERMS, "标准", "规范")
_CJK_WEAK_CONTEXT_TERMS = (
    *_CJK_WEAK_CONTEXT_TERMS,
    "振动",
    "转子",
    "旋转机械",
    "轴承",
    "频谱",
    "状态监测",
    "故障诊断",
    "临界转速",
    "扭振",
)
_OUT_OF_SCOPE["zh"] = "范围外：Phase-0 只处理振动、旋转机械、信号分析、状态监测和相关标准问题。"


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
    if is_corpus_standard_query(normalized):
        return True
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
        for warning in output.warnings:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _bool_value(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _first_control_value(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _chain_step(skill_name: str, output: SkillOutput) -> dict[str, str]:
    return {"skill": skill_name, "status": output.status, "summary": output.summary}


def _skill_results(**results: SkillOutput) -> dict[str, dict[str, Any]]:
    return {name: output.structured_result for name, output in results.items()}


def _token_cost(output: SkillOutput) -> int | None:
    structured = output.structured_result
    value = structured.get("token_cost")
    if value not in (None, ""):
        return int(value)

    skill_results = structured.get("skill_results")
    s3_result = skill_results.get("s3") if isinstance(skill_results, Mapping) else None
    if isinstance(s3_result, Mapping):
        value = s3_result.get("token_cost")
        if value not in (None, ""):
            return int(value)
    return None


def _bounded(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 3)


def _answer_text(output: SkillOutput) -> str:
    value = output.structured_result.get("answer")
    return value if isinstance(value, str) else output.summary


_QUERY_ASPECTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("variable_speed", ("variable-speed", "varying speed", "变速", "升降速")),
    ("amplitude", ("amplitude", "magnitude", "幅值", "振幅")),
    ("phase", ("phase", "相位")),
    ("spectrum", ("spectrum", "spectral", "频谱")),
    ("direction", ("direction", "radial", "axial", "方向", "径向", "轴向")),
    ("workflow", ("workflow", "procedure", "流程", "步骤")),
    ("scope", ("scope", "covered", "适用", "范围")),
    ("formula", ("formula", "equation", "calculate", "公式", "计算")),
)
# PROVISIONAL (2026-07-07). The Obj9 deterministic freeze baseline's calibrator
# prefers 0.85, but the label set still has one usable case and thirteen
# unusable cases, and Obj6 combined-chain calibration showed degraded
# discrimination for LLM-style answers. Keep 0.75 until a separately reviewed
# threshold migration re-labels the newly pass-like answers and recalibrates the
# default plus LLM lanes. Do NOT describe this as "calibration selects 0.75".
ANSWER_QUALITY_THRESHOLD = 0.75


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(value.casefold() in folded for value in values)


def _query_aspect_coverage(query: str, answer: str) -> tuple[float, list[str], list[str]]:
    required: list[str] = []
    covered_slots: list[str] = []
    covered, total = alias_family_coverage(query, answer)
    if total:
        required.extend(f"domain_term_{index}" for index in range(total))
        covered_slots.extend(f"domain_term_{index}" for index in range(covered))
    for name, aliases in _QUERY_ASPECTS:
        if _contains_any(query, aliases):
            required.append(name)
            if _contains_any(answer, aliases):
                covered_slots.append(name)
    if not required:
        return (1.0 if answer.strip() else 0.0), ["answer_present"], (["answer_present"] if answer.strip() else [])
    return len(covered_slots) / len(required), required, covered_slots


def _query_coverage(query: str, answer: str) -> float:
    score, _required, _covered = _query_aspect_coverage(query, answer)
    return score


def _evidence_relevance(s2_output: SkillOutput, citations: list[Any]) -> float:
    hits = s2_output.structured_result.get("retrieval_output", {}).get("hits")
    if not citations or not isinstance(hits, list) or not hits:
        return 0.0
    ranked_hits = [hit for hit in hits if isinstance(hit, Mapping) and hit.get("chunk_id")]
    max_score = max((float(hit.get("score") or 0.0) for hit in ranked_hits), default=0.0)
    if not ranked_hits or max_score <= 0:
        return 0.0
    by_chunk = {str(hit["chunk_id"]): (rank, hit) for rank, hit in enumerate(ranked_hits, start=1)}
    values: list[float] = []
    for citation in citations:
        matched = by_chunk.get(str(getattr(citation, "chunk_id", "")))
        if matched is None:
            continue
        rank, hit = matched
        rank_score = 1.0 / log2(rank + 1)
        relative_score = float(hit.get("score") or 0.0) / max_score
        values.append((rank_score + relative_score) / 2.0)
    return sum(values) / len(citations) if values else 0.0


_EVIDENCE_SUFFIX_RE = re.compile(r"\s*[（(](?:evidence|证据)\s*[:：].*?[)）]\s*$", re.IGNORECASE)
_CHUNK_REF_SUFFIX_RE = re.compile(r"(?:\s*\[[A-Za-z0-9_.:/#-]+\])+\s*$")


def _complete_sentence_ratio(answer: str) -> float:
    lines = [line.strip() for line in answer.splitlines() if line.strip() and not line.strip().startswith("## ")]
    if not lines:
        return 0.0
    # Each evidence-bound claim ends with a "(evidence: ...)" tag; strip it before
    # checking sentence-final punctuation so a complete claim is not read as a
    # fragment.
    complete = 0
    for line in lines:
        candidate = _CHUNK_REF_SUFFIX_RE.sub("", line).rstrip()
        candidate = _EVIDENCE_SUFFIX_RE.sub("", candidate).rstrip()
        if re.search(r"[。！？!?；;…\.．][\"'”’）】》]*$", candidate):
            complete += 1
    return complete / len(lines)


def _question_intent(query: str) -> str:
    if _contains_any(query, ("公式", "计算", "推导", "formula", "equation", "calculated")):
        return "formula"
    if _contains_any(query, ("gb/t", "iso ", "api ", "标准", "适用范围", "covered by", "scope")):
        return "standards"
    if _contains_any(query, ("流程", "步骤", "规划", "workflow", "procedure", "steps")):
        return "workflow"
    if _contains_any(query, ("什么是", "定义", "what is", "define", "mean")):
        return "definition"
    if _contains_any(query, ("区别", "比较", "不同", "compare", "difference", "differ", " versus ", " vs ")):
        return "comparison"
    if _contains_any(query, ("判断", "诊断", "区分", "diagnos", "distinguish", "determine")):
        return "diagnosis"
    if _contains_any(query, ("为什么", "为何", "机理", "why", "mechanism", "cause")):
        return "mechanism"
    return "general"


def _intent_completeness(query: str, answer: str) -> tuple[float, str, list[str], list[str]]:
    intent = _question_intent(query)
    checks: list[tuple[str, bool]]
    if intent == "definition":
        definition = _contains_any(
            answer,
            ("是指", "定义为", "指的是", "refers to", "is defined", "means", "角域", "angular-domain"),
        )
        purpose = _contains_any(answer, ("用于", "作用", "适用于", "used for", "allows", "enables"))
        checks = [("definition_statement", definition), ("purpose", purpose)]
    elif intent == "mechanism":
        causal = _contains_any(answer, ("因为", "由于", "导致", "接近", "because", "due to", "causes", "approaches"))
        natural = _contains_any(answer, ("固有频率", "自然频率", "natural frequency"))
        excitation = _contains_any(answer, ("激励频率", "转频", "excitation frequency", "forcing frequency"))
        checks = [("causal_link", causal), ("excitation_natural_frequency_relation", natural and excitation)]
    elif intent == "comparison":
        contrast = _contains_any(answer, ("区别", "相比", "而", "versus", "whereas", "compared", "difference"))
        entities = _contains_any(answer, ("不平衡", "unbalance")) and _contains_any(
            answer, ("不对中", "misalignment")
        )
        checks = [("contrast", contrast), ("both_entities", entities)]
    elif intent == "diagnosis":
        dimensions = sum(
            _contains_any(answer, aliases)
            for aliases in (
                ("相位", "phase"),
                ("倍频", "谐波", "harmonic"),
                ("轴向", "axial"),
                ("测量", "检查", "measure", "check"),
            )
        )
        checks = [("multiple_diagnostic_dimensions", dimensions >= 2), ("decision_action", dimensions >= 3)]
    elif intent == "workflow":
        actions = sum(
            _contains_any(answer, aliases)
            for aliases in (
                ("工况", "operating condition"),
                ("测点", "measurement point"),
                ("采集", "collect"),
                ("比较", "compare"),
                ("复核", "verify"),
            )
        )
        checks = [("ordered_measurement_actions", actions >= 3), ("verification_step", actions >= 4)]
    elif intent == "standards":
        checks = [
            ("scope", _contains_any(answer, ("适用于", "额定", "applies to", "rated", "scope"))),
            ("specified_method", _contains_any(answer, ("分析评定", "测量验证", "analysis", "measurement verification"))),
        ]
    elif intent == "formula":
        equation = re.search(r"(?:[A-Za-zΑ-Ωα-ω]\w*\s*=|=\s*[^=])", answer) is not None
        variables = _contains_any(answer, ("式中", "其中", "表示", "where", "denotes", "represents"))
        checks = [("equation", equation), ("variable_definitions", variables)]
    else:
        # Unknown intent cannot satisfy a hard completeness gate by length alone.
        checks = [("recognized_intent", False)]
    required = [name for name, _covered in checks]
    covered = [name for name, is_covered in checks if is_covered]
    return len(covered) / len(required), intent, required, covered


def _completeness(query: str, answer: str) -> float:
    score, _intent, _required, _covered = _intent_completeness(query, answer)
    return score


def _retrieval_provenance(s2_output: SkillOutput) -> tuple[str | None, int]:
    struct = s2_output.structured_result if isinstance(s2_output.structured_result, Mapping) else {}
    retrieval_output = struct.get("retrieval_output")
    hits = retrieval_output.get("hits") if isinstance(retrieval_output, Mapping) else None
    return struct.get("retrieval_source"), (len(hits) if isinstance(hits, list) else 0)


def _answer_quality(
    query: str,
    *,
    s2_output: SkillOutput,
    answer_output: SkillOutput,
    faithfulness_status: str,
) -> dict[str, Any]:
    answer = _answer_text(answer_output)
    coverage, query_aspects, covered_query_aspects = _query_aspect_coverage(query, answer)
    completeness, intent, required_slots, covered_slots = _intent_completeness(query, answer)
    subscores = {
        "question_coverage": _bounded(coverage),
        "evidence_relevance": _bounded(_evidence_relevance(s2_output, answer_output.citations)),
        "completeness": _bounded(completeness),
        "readability": _bounded(_complete_sentence_ratio(answer)),
    }
    score = _bounded(sum(subscores.values()) / len(subscores))
    gate_reasons: list[str] = []
    if faithfulness_status != "ok":
        gate_reasons.append(f"faithfulness_status={faithfulness_status}")
    if score < ANSWER_QUALITY_THRESHOLD:
        gate_reasons.append(f"score<{ANSWER_QUALITY_THRESHOLD}")
    if subscores["completeness"] < 1.0:
        gate_reasons.append("completeness<1.0")
    gate_status = "pass" if not gate_reasons else "blocked"
    return {
        "schema_version": "phase5.answer_quality.v2",
        "score": score,
        "threshold": ANSWER_QUALITY_THRESHOLD,
        "subscores": subscores,
        "faithfulness_status": faithfulness_status,
        "gate_status": gate_status,
        "gate_reasons": gate_reasons,
        "intent": intent,
        "query_aspects": query_aspects,
        "covered_query_aspects": covered_query_aspects,
        "required_slots": required_slots,
        "covered_slots": covered_slots,
        "citation_count": len(answer_output.citations),
    }


def _configured_s3_client(settings: Any | None) -> Any | None:
    if settings is None or not settings.llm.s3_enabled:
        return None
    if not settings.llm.live_enabled:
        from ..llm.replay import ReplayClient

        return ReplayClient(settings.llm.replay_dir)

    from ..llm.budget import BudgetGuard
    from ..llm.openai_client import OpenAIClient

    return OpenAIClient(
        settings.llm.openai,
        allow_live=True,
        budget_guard=BudgetGuard.from_settings(settings.llm),
    )


class TutorOrchestrator:
    """Minimal Phase-0 orchestrator for evidence-bound tutoring answers."""

    def __init__(
        self,
        *,
        retrieval_skill: Skill | None = None,
        qa_summary_skill: Skill | None = None,
        engineering_analysis_skill: Skill | None = None,
        formula_derivation_skill: Skill | None = None,
        normalizer_skill: TermSymbolUnitNormalizerSkill | None = None,
        citation_check_skill: Skill | None = None,
        style_skill: Skill | None = None,
        reviewer_skill: Skill | None = None,
        literature_search_skill: Skill | None = None,
        model_selection_skill: Skill | None = None,
        experiment_advice_skill: Skill | None = None,
        supervisor_loop: SupervisorLoop | None = None,
        settings: Any | None = None,
    ) -> None:
        self.retrieval_skill = retrieval_skill or RetrievalSkill()
        if qa_summary_skill is None:
            s3_settings = settings or load()
            self.qa_summary_skill = QASummarySkill(
                settings=s3_settings,
                llm_client=_configured_s3_client(s3_settings),
            )
        else:
            self.qa_summary_skill = qa_summary_skill
        self.engineering_analysis_skill = engineering_analysis_skill or EngineeringAnalysisSkill()
        self.formula_derivation_skill = formula_derivation_skill or FormulaDerivationSkill()
        self.normalizer_skill = normalizer_skill or TermSymbolUnitNormalizerSkill()
        self.citation_check_skill = citation_check_skill or CitationCheckSkill()
        self.style_skill = style_skill or OutputStyleSkill()
        self.reviewer_skill = reviewer_skill or ReviewerSkill()
        self.literature_search_skill = literature_search_skill
        self.model_selection_skill = model_selection_skill
        self.experiment_advice_skill = experiment_advice_skill
        self.supervisor_loop = supervisor_loop or SupervisorLoop()
        self._settings = settings

    def _normalization_enabled(
        self,
        stage: str,
        *,
        context: Mapping[str, Any],
        constraints: Mapping[str, Any],
    ) -> bool:
        settings = self._settings or load()
        normalization = settings.normalization
        enabled = _bool_value(
            _first_control_value(constraints, context, keys=("v1_enabled",)),
            default=bool(normalization.v1_enabled),
        )
        if not enabled:
            return False
        if stage == "input":
            default = bool(normalization.v1_input_enabled)
            value = _first_control_value(
                constraints,
                context,
                keys=("v1_input_enabled", "v1_normalize_input"),
            )
            return _bool_value(value, default=default)
        default = bool(normalization.v1_output_enabled)
        value = _first_control_value(
            constraints,
            context,
            keys=("v1_output_enabled", "v1_normalize_output"),
        )
        return _bool_value(value, default=default)

    def _route_decision(
        self,
        *,
        context: Mapping[str, Any],
        constraints: Mapping[str, Any],
        settings: Any | None = None,
    ) -> RouteDecision:
        settings = settings or self._settings or load()
        return route_task(constraints=constraints, context=context, settings=settings)

    def _review_enabled(self, *, route_decision: RouteDecision) -> bool:
        return route_decision.difficulty == Difficulty.EXTREME

    def _advisory_route_decision(
        self,
        query: str,
        *,
        user_mode: UserMode,
        context: Mapping[str, Any],
        constraints: Mapping[str, Any],
        settings: Any | None = None,
    ) -> AdvisoryRoutingDecision:
        settings = settings or self._settings or load()
        return route_advisory_skills(
            query,
            user_mode=user_mode,
            constraints=constraints,
            context=context,
            settings=settings,
        )

    def _advisory_skill(self, skill_name: str) -> Skill:
        if skill_name == "s6_literature_search":
            if self.literature_search_skill is None:
                from ..skills import LiteratureSearchSkill

                self.literature_search_skill = LiteratureSearchSkill()
            return self.literature_search_skill
        if skill_name == "s7_model_selection":
            if self.model_selection_skill is None:
                from ..skills import ModelSelectionSkill

                self.model_selection_skill = ModelSelectionSkill()
            return self.model_selection_skill
        if skill_name == "s8_experiment_advice":
            if self.experiment_advice_skill is None:
                from ..skills import ExperimentAdviceSkill

                self.experiment_advice_skill = ExperimentAdviceSkill()
            return self.experiment_advice_skill
        raise KeyError(f"Unknown advisory skill: {skill_name}")

    def _advisory_constraints(self, skill_name: str, constraints: Mapping[str, Any]) -> dict[str, Any]:
        next_constraints = dict(constraints)
        if skill_name == "s6_literature_search":
            next_constraints.setdefault("s6_enabled", True)
        elif skill_name == "s7_model_selection":
            next_constraints.setdefault("s7_enabled", True)
        elif skill_name == "s8_experiment_advice":
            next_constraints.setdefault("s8_enabled", True)
        return next_constraints

    def _run_advisory_lane(
        self,
        *,
        query: str,
        task_id: str,
        user_mode: UserMode,
        context: Mapping[str, Any],
        constraints: Mapping[str, Any],
        s2_result: dict[str, Any],
        route_decision: AdvisoryRoutingDecision,
    ) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]], dict[str, Any], list[str]]:
        chain: list[dict[str, str]] = []
        skill_results: dict[str, dict[str, Any]] = {}
        outputs: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for skill_name in route_decision.selected_skills:
            skill = self._advisory_skill(skill_name)
            skill_input = SkillInput(
                task_id=task_id,
                user_query=query,
                context={**context, "s2_result": s2_result},
                constraints=self._advisory_constraints(skill_name, constraints),
                user_mode=user_mode,
            )
            try:
                skill_output = skill.run(skill_input)
            except Exception as exc:  # noqa: BLE001 - advisory lane must not break final answers
                skill_output = SkillOutput(
                    status="insufficient",
                    summary=f"{skill_name} advisory route failed.",
                    structured_result={
                        "task_id": task_id,
                        "skill": skill_name,
                        "routing": {"default_chain": False, "requires_activation_gate": True},
                    },
                    warnings=[f"{skill_name} advisory route failed: {type(exc).__name__}: {exc}"],
                    handoff_recommendation="Use the default V2/V4-bound answer; rerun the advisory skill explicitly after fixing the route.",
                )
            chain.append(_chain_step(skill_name, skill_output))
            skill_key = skill_name.split("_", 1)[0]
            skill_results[skill_key] = skill_output.structured_result
            outputs[skill_key] = skill_output.model_dump(mode="python")
            warnings.extend(skill_output.warnings)
        advisory_result = {
            "enabled": route_decision.enabled,
            "selected_skills": list(route_decision.selected_skills),
            "reason": route_decision.reason,
            "reasons": route_decision.reasons,
            "rendering": route_decision.rendering,
            "v2_v4_policy": route_decision.v2_v4_policy,
            "outputs": outputs,
            "limitations": [
                "Advisory lane output is structured handoff context and is not rendered into the final answer.",
                "Final user-facing claims still require the default V2/V4-bound answer path.",
            ],
        }
        return chain, skill_results, advisory_result, warnings

    def _engineering_analysis_enabled(self, *, user_mode: UserMode, context: Mapping[str, Any], constraints: Mapping[str, Any]) -> bool:
        value = _first_control_value(constraints, context, keys=("s4_enabled", "s4_engineering_enabled"))
        if value is not None:
            return _bool_value(value, default=user_mode == "engineering")
        return user_mode == "engineering"

    def _formula_derivation_enabled(self, *, user_mode: UserMode, context: Mapping[str, Any], constraints: Mapping[str, Any]) -> bool:
        value = _first_control_value(constraints, context, keys=("s5_enabled", "s5_formula_enabled"))
        if value is not None:
            return _bool_value(value, default=user_mode == "derivation")
        return user_mode == "derivation"

    def _early_return(
        self,
        *,
        query: str,
        task_id: str,
        source: SkillOutput,
        chain: list[dict[str, str]],
        warnings: list[str],
        skill_results: dict[str, dict[str, Any]],
        s2_output: SkillOutput | None = None,
    ) -> SkillOutput:
        answer = source.structured_result.get("answer") if isinstance(source.structured_result.get("answer"), str) else source.summary
        s2_for_quality = s2_output or source
        retrieval_source, retrieval_hits = _retrieval_provenance(s2_for_quality)
        return SkillOutput(
            status=source.status,
            summary=source.summary,
            structured_result={
                "task_id": task_id,
                "scope": "in_scope",
                "answer": answer,
                "chain": chain,
                "answer_quality": _answer_quality(
                    query,
                    s2_output=s2_for_quality,
                    answer_output=source,
                    faithfulness_status="not_run",
                ),
                "retrieval_source": retrieval_source,
                "retrieval_hits": retrieval_hits,
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
        """Run the S2 -> S3 -> V2 -> V4 chain and persist one fail-safe qa_logs row.

        Persisting is an optional side effect: it never changes ``output``'s status
        and only appends a warning if a write was attempted (Postgres enabled) but
        failed. Timing covers only the answer chain, not the log write.
        """
        start = time.perf_counter()
        output = self._run_chain(
            query,
            context=context,
            constraints=constraints,
            user_mode=user_mode,
            task_id=task_id,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        self._persist_qa_log(output, query=query, latency_ms=latency_ms)
        return output

    def _persist_qa_log(self, output: SkillOutput, *, query: str, latency_ms: int) -> None:
        try:
            from ..storage.qa_logs import record_qa_log

            warning = record_qa_log(
                output,
                query=query,
                latency_ms=latency_ms,
                token_cost=_token_cost(output),
                settings=self._settings,
            )
        except Exception as exc:  # noqa: BLE001 - persistence must never break the answer
            # Fail-safe, not silent: an unexpected logging bug surfaces as a warning
            # (the primary status is still untouched).
            warning = f"qa_logs persistence skipped (unexpected failure): {type(exc).__name__}: {exc}"
        if warning and warning not in output.warnings:
            output.warnings.append(warning)

    def _run_chain(
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
        settings = self._settings or load()
        route_decision = self._route_decision(context=context_dict, constraints=constraints_dict, settings=settings)

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
                query=query,
                task_id=current_task_id,
                source=s2_output,
                chain=s2_chain,
                warnings=s2_output.warnings,
                skill_results=_skill_results(s2=s2_output),
            )

        v1_warnings: list[str] = []
        s2_for_downstream = s2_output.model_dump(mode="python")
        if self._normalization_enabled("input", context=context_dict, constraints=constraints_dict):
            try:
                s2_for_downstream, _input_replacements = self.normalizer_skill.normalize_s2_result(s2_for_downstream)
            except Exception as exc:  # noqa: BLE001 - V1 must be optional/fail-safe
                s2_for_downstream = s2_output.model_dump(mode="python")
                v1_warnings.append(
                    f"V1 input normalization skipped; passing original S2 output: {type(exc).__name__}: {exc}"
                )

        s3_context = {
            **context_dict,
            "s2_result": s2_for_downstream,
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
                query=query,
                task_id=current_task_id,
                source=s3_output,
                chain=s3_chain,
                warnings=[*v1_warnings, *_merge_warnings(s2_output, s3_output)],
                skill_results=_skill_results(s2=s2_output, s3=s3_output),
                s2_output=s2_output,
            )

        s4_warnings: list[str] = []
        s4_output: SkillOutput | None = None
        s5_warnings: list[str] = []
        s5_output: SkillOutput | None = None
        synthesis_for_quality = s3_output
        synthesis_chain = s3_chain
        s4_enabled = self._engineering_analysis_enabled(user_mode=user_mode, context=context_dict, constraints=constraints_dict)
        s5_enabled = self._formula_derivation_enabled(user_mode=user_mode, context=context_dict, constraints=constraints_dict)
        if s4_enabled and s5_enabled:
            if user_mode == "derivation":
                s4_enabled = False
                s4_warnings.append("S4 and S5 were both enabled; S5 formula derivation takes precedence in derivation mode.")
            else:
                s5_enabled = False
                s5_warnings.append("S4 and S5 were both enabled; S4 engineering analysis takes precedence outside derivation mode.")
        if s4_enabled:
            s4_input = SkillInput(
                task_id=current_task_id,
                user_query=query,
                context={
                    **context_dict,
                    "s2_result": s2_for_downstream,
                    "s3_result": s3_output.model_dump(mode="python"),
                },
                constraints=constraints_dict,
                user_mode=user_mode,
            )
            try:
                candidate_s4 = self.engineering_analysis_skill.run(s4_input)
            except Exception as exc:  # noqa: BLE001 - optional S4 must not break answering
                s4_warnings.append(
                    f"S4 engineering analysis failed; passing S3 output to V2: {type(exc).__name__}: {exc}"
                )
            else:
                if candidate_s4.status == "ok":
                    s4_output = candidate_s4
                    synthesis_for_quality = candidate_s4
                    synthesis_chain = [*s3_chain, _chain_step("s4_engineering_analysis", candidate_s4)]
                else:
                    s4_warnings.extend(candidate_s4.warnings)
        if s5_enabled:
            s5_input = SkillInput(
                task_id=current_task_id,
                user_query=query,
                context={
                    **context_dict,
                    "s2_result": s2_for_downstream,
                    "s3_result": s3_output.model_dump(mode="python"),
                },
                constraints=constraints_dict,
                user_mode=user_mode,
            )
            try:
                candidate_s5 = self.formula_derivation_skill.run(s5_input)
            except Exception as exc:  # noqa: BLE001 - optional S5 must not break answering
                s5_warnings.append(
                    f"S5 formula derivation failed; passing S3 output to V2: {type(exc).__name__}: {exc}"
                )
            else:
                if candidate_s5.status == "ok":
                    s5_output = candidate_s5
                    synthesis_for_quality = candidate_s5
                    synthesis_chain = [*s3_chain, _chain_step("s5_formula_derivation", candidate_s5)]
                else:
                    s5_warnings.extend(candidate_s5.warnings)

        v2_input = SkillInput(
            task_id=current_task_id,
            user_query=query,
            context={
                **context_dict,
                "s2_result": s2_for_downstream,
                "s3_result": synthesis_for_quality.model_dump(mode="python"),
            },
            constraints=constraints_dict,
            user_mode=user_mode,
        )
        try:
            v2_output = self.citation_check_skill.run(v2_input)
        except Exception as exc:  # noqa: BLE001 - V2 quality failure must not break answering
            v2_output = SkillOutput(
                status="ok",
                summary="V2 citation check unavailable; passing through S3 output.",
                structured_result=s3_output.structured_result,
                citations=s3_output.citations,
                warnings=[
                    *s3_output.warnings,
                    f"V2 citation check failed; passing through S3 output: {type(exc).__name__}: {exc}",
                ],
                handoff_recommendation=s3_output.handoff_recommendation,
            )
        if v2_output.status == "fail":
            v2_output = SkillOutput(
                status="ok",
                summary="V2 citation check failed; passing through S3 output.",
                structured_result=s3_output.structured_result,
                citations=s3_output.citations,
                warnings=[
                    *s3_output.warnings,
                    *v2_output.warnings,
                    "V2 citation check returned fail; passing through S3 output.",
                ],
                handoff_recommendation=s3_output.handoff_recommendation,
            )
        v2_chain = [*synthesis_chain, _chain_step("v2_citation_check", v2_output)]

        v4_context = {
            **context_dict,
            "query_language": _query_language(query),
            "s2_result": s2_for_downstream,
            "s3_result": s3_output.model_dump(mode="python"),
            "upstream_result": v2_output.model_dump(mode="python"),
        }
        v4_input = SkillInput(
            task_id=current_task_id,
            user_query=query,
            context=v4_context,
            constraints=constraints_dict,
            user_mode=user_mode,
        )
        v4_output = self.style_skill.run(v4_input)
        if self._normalization_enabled("output", context=context_dict, constraints=constraints_dict):
            try:
                v4_output, _output_replacements = self.normalizer_skill.normalize_skill_output(v4_output)
            except Exception as exc:  # noqa: BLE001 - V1 must be optional/fail-safe
                v1_warnings.append(
                    f"V1 output normalization skipped; returning original V4 output: {type(exc).__name__}: {exc}"
                )
        chain = [*v2_chain, _chain_step("v4_style", v4_output)]
        skill_results = _skill_results(s2=s2_output, s3=s3_output, v2=v2_output, v4=v4_output)
        if s4_output is not None:
            skill_results = {**skill_results, "s4": s4_output.structured_result}
        if s5_output is not None:
            skill_results = {**skill_results, "s5": s5_output.structured_result}
        advisory_warnings: list[str] = []
        advisory_result: dict[str, Any] | None = None
        advisory_route_decision = self._advisory_route_decision(
            query,
            user_mode=user_mode,
            context=context_dict,
            constraints=constraints_dict,
            settings=settings,
        )
        if advisory_route_decision.selected_skills:
            advisory_chain, advisory_skill_results, advisory_result, advisory_warnings = self._run_advisory_lane(
                query=query,
                task_id=current_task_id,
                user_mode=user_mode,
                context=context_dict,
                constraints=constraints_dict,
                s2_result=s2_for_downstream,
                route_decision=advisory_route_decision,
            )
            chain = [*chain, *advisory_chain]
            skill_results = {**skill_results, **advisory_skill_results}
        elif advisory_route_decision.enabled:
            advisory_result = {
                "enabled": True,
                "selected_skills": [],
                "reason": advisory_route_decision.reason,
                "reasons": advisory_route_decision.reasons,
                "rendering": advisory_route_decision.rendering,
                "v2_v4_policy": advisory_route_decision.v2_v4_policy,
                "outputs": {},
                "limitations": [
                    "Advisory routing gate is enabled, but no S6/S7/S8 skill was selected.",
                    "Default V2/V4-bound answer path remains authoritative.",
                ],
            }
        reviewer_notes: list[dict[str, Any]] = []
        reviewer_warnings: list[str] = []
        if self._review_enabled(route_decision=route_decision):
            v3_input = SkillInput(
                task_id=current_task_id,
                user_query=query,
                context={
                    **context_dict,
                    "s2_result": s2_for_downstream,
                    "s3_result": s3_output.model_dump(mode="python"),
                    "v2_result": v2_output.model_dump(mode="python"),
                    "upstream_result": v4_output.model_dump(mode="python"),
                },
                constraints=constraints_dict,
                user_mode=user_mode,
            )
            try:
                v3_output = self.reviewer_skill.run(v3_input)
            except Exception as exc:  # noqa: BLE001 - V3 is advisory and fail-safe
                v3_output = SkillOutput(
                    status="ok",
                    summary="V3 reviewer unavailable; returning V4 answer.",
                    structured_result={"task_id": current_task_id, "reviewer_notes": []},
                    citations=v4_output.citations,
                    warnings=[f"V3 reviewer failed; returning V4 answer: {type(exc).__name__}: {exc}"],
                    handoff_recommendation=v4_output.handoff_recommendation,
                )
            chain = [*chain, _chain_step("v3_reviewer", v3_output)]
            skill_results = {**skill_results, "v3": v3_output.structured_result}
            reviewer_warnings = v3_output.warnings
            notes = v3_output.structured_result.get("reviewer_notes")
            if isinstance(notes, list):
                reviewer_notes = [dict(note) for note in notes if isinstance(note, Mapping)]

        if "fail" in {s2_output.status, s3_output.status, v4_output.status}:
            final_status = "fail"
        elif v2_output.status == "insufficient":
            final_status = "insufficient"
        else:
            final_status = v4_output.status

        retrieval_source, retrieval_hits = _retrieval_provenance(s2_output)

        final_structured_result = {
            "task_id": current_task_id,
            "scope": "in_scope",
            "chain": chain,
            "answer": v4_output.structured_result.get("answer", ""),
            "answer_quality": _answer_quality(
                query,
                s2_output=s2_output,
                answer_output=v4_output,
                faithfulness_status=v2_output.status,
            ),
            "retrieval_source": retrieval_source,
            "retrieval_hits": retrieval_hits,
            "reviewer_notes": reviewer_notes,
            "v4": v4_output.structured_result,
            "skill_results": skill_results,
        }
        if advisory_result is not None:
            final_structured_result["advisory_routing"] = advisory_result

        final_output = SkillOutput(
            status=final_status,
            summary=v4_output.summary,
            structured_result=final_structured_result,
            citations=v4_output.citations,
            warnings=[
                *v1_warnings,
                *s4_warnings,
                *s5_warnings,
                *advisory_warnings,
                *_merge_warnings(s2_output, s3_output, v2_output, v4_output),
                *reviewer_warnings,
            ],
            handoff_recommendation=v4_output.handoff_recommendation,
        )
        supervisor_triggered = bool(route_decision.use_opus_supervisor or reviewer_notes)
        if supervisor_triggered:
            return self.supervisor_loop.run(
                query=query,
                output=final_output,
                reviewer_notes=reviewer_notes,
            ).output
        return self.supervisor_loop.annotate_not_triggered(final_output)


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
