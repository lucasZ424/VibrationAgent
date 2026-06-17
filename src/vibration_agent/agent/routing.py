"""Difficulty routing for the dual-API control plane.

The router is policy-driven. Model recommendations can be recorded, but stakeholder
configuration and explicit task metadata decide whether the Opus path is allowed.
"""
from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Mapping

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from vibration_agent.config import Settings


class Difficulty(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class RouteDecision(BaseModel):
    difficulty: Difficulty
    owner: str
    use_opus_supervisor: bool = False
    reason: str = ""
    reasons: list[str] = Field(default_factory=list)
    model_recommendation: Difficulty | None = None


class AdvisoryRoutingDecision(BaseModel):
    enabled: bool = False
    selected_skills: tuple[str, ...] = ()
    reason: str = ""
    reasons: list[str] = Field(default_factory=list)
    rendering: str = "structured_handoff_only"
    v2_v4_policy: str = "do_not_render_as_final_answer"


class RoutingPolicy(BaseModel):
    """Stakeholder-owned routing policy.

    By default only `extreme` tasks may use Opus. Low, medium, and high stay on
    the GPT path unless the stakeholder explicitly changes this policy.
    """

    gpt_owner: str = "gpt"
    opus_owner: str = "opus_supervised_loop"
    opus_difficulties: tuple[Difficulty, ...] = (Difficulty.EXTREME,)
    repeated_failure_threshold: int = Field(default=2, ge=1)
    explicit_extreme_markers: tuple[str, ...] = ("extreme", "opus", "senior_supervisor")
    advisory_routing_enabled: bool = False
    advisory_intent_routing_enabled: bool = False
    advisory_allowed_skills: tuple[str, ...] = ()

    @classmethod
    def from_settings(cls, settings: Settings) -> "RoutingPolicy":
        routing = settings.routing
        return cls(
            gpt_owner=routing.default_owner,
            opus_difficulties=tuple(Difficulty(str(item).strip().lower()) for item in routing.opus_difficulties),
            repeated_failure_threshold=routing.repeated_failure_threshold,
            explicit_extreme_markers=tuple(str(item).strip().lower() for item in routing.explicit_extreme_markers),
            advisory_routing_enabled=bool(routing.advisory_routing_enabled),
            advisory_intent_routing_enabled=bool(routing.advisory_intent_routing_enabled),
            advisory_allowed_skills=tuple(_normalize_advisory_skill(item) for item in routing.advisory_allowed_skills),
        )

    def should_use_opus(self, difficulty: Difficulty) -> bool:
        return difficulty in self.opus_difficulties


@lru_cache(maxsize=1)
def _cached_default_routing_policy() -> RoutingPolicy:
    from vibration_agent.config import load

    return RoutingPolicy.from_settings(load())


def default_routing_policy() -> RoutingPolicy:
    return _cached_default_routing_policy().model_copy(deep=True)


def clear_default_routing_policy_cache() -> None:
    _cached_default_routing_policy.cache_clear()


def _coerce_difficulty(value: Any) -> Difficulty | None:
    if value in (None, ""):
        return None
    try:
        return Difficulty(str(value).strip().lower())
    except ValueError:
        return None


def _explicit_extreme(payload: Mapping[str, Any], policy: RoutingPolicy) -> bool:
    if payload.get("extreme") is True or payload.get("use_opus") is True:
        return True
    marker_values = {str(payload.get("route", "")).lower(), str(payload.get("escalation", "")).lower()}
    return any(marker in marker_values for marker in policy.explicit_extreme_markers)


_ADVISORY_SKILL_ALIASES = {
    "s6": "s6_literature_search",
    "literature": "s6_literature_search",
    "literature_search": "s6_literature_search",
    "s6_literature_search": "s6_literature_search",
    "s7": "s7_model_selection",
    "model": "s7_model_selection",
    "model_selection": "s7_model_selection",
    "s7_model_selection": "s7_model_selection",
    "s8": "s8_experiment_advice",
    "experiment": "s8_experiment_advice",
    "experiment_advice": "s8_experiment_advice",
    "measurement": "s8_experiment_advice",
    "s8_experiment_advice": "s8_experiment_advice",
}
_ADVISORY_SKILL_ORDER = (
    "s6_literature_search",
    "s7_model_selection",
    "s8_experiment_advice",
)
_S6_INTENT_TERMS = ("literature", "paper", "papers", "publication", "research", "arxiv", "semantic scholar", "文献", "论文")
_S7_INTENT_TERMS = ("model", "modeling", "model selection", "which model", "模型", "建模")
_S8_INTENT_TERMS = ("experiment", "measurement", "sensor", "test plan", "validation", "实验", "测量", "传感器", "验证")


def _normalize_advisory_skill(value: Any) -> str:
    normalized = str(value).strip().lower().replace("-", "_")
    return _ADVISORY_SKILL_ALIASES.get(normalized, normalized)


def _bool_control(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _first_control(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_skill_list(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        raw_items = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw_items = [str(item).strip() for item in value]
    else:
        raw_items = [str(value).strip()]
    selected: list[str] = []
    for item in raw_items:
        skill = _normalize_advisory_skill(item)
        if skill in _ADVISORY_SKILL_ORDER and skill not in selected:
            selected.append(skill)
    return tuple(skill for skill in _ADVISORY_SKILL_ORDER if skill in selected)


def _contains_any(query: str, terms: tuple[str, ...]) -> bool:
    normalized = query.casefold()
    return any(term.casefold() in normalized for term in terms)


def _infer_advisory_skills(query: str, user_mode: str) -> tuple[str, ...]:
    selected: list[str] = []
    if user_mode == "research" or _contains_any(query, _S6_INTENT_TERMS):
        selected.append("s6_literature_search")
    if _contains_any(query, _S7_INTENT_TERMS):
        selected.append("s7_model_selection")
    if _contains_any(query, _S8_INTENT_TERMS):
        selected.append("s8_experiment_advice")
    return tuple(skill for skill in _ADVISORY_SKILL_ORDER if skill in selected)


def route_advisory_skills(
    query: str,
    *,
    user_mode: str = "engineering",
    constraints: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    policy: RoutingPolicy | None = None,
    settings: Settings | None = None,
) -> AdvisoryRoutingDecision:
    """Return the explicit S6/S7/S8 advisory lane decision without calling skills."""
    if policy is not None:
        active_policy = policy
    elif settings is not None:
        active_policy = RoutingPolicy.from_settings(settings)
    else:
        active_policy = default_routing_policy()

    merged: dict[str, Any] = {**(context or {}), **(constraints or {})}
    gate_value = _first_control(merged, ("advisory_routing_enabled", "s6_s7_s8_routing_enabled"))
    gate_enabled = _bool_control(gate_value, default=active_policy.advisory_routing_enabled)
    if not gate_enabled:
        return AdvisoryRoutingDecision(
            enabled=False,
            reason="advisory routing disabled",
            reasons=["advisory routing disabled"],
        )

    explicit = _as_skill_list(_first_control(merged, ("advisory_skills", "routed_skills", "activate_skills")))
    allowed = explicit or active_policy.advisory_allowed_skills
    reasons = ["advisory routing gate enabled"]
    if explicit:
        selected = explicit
        reasons.append("explicit advisory skill list")
    else:
        intent_value = _first_control(merged, ("advisory_intent_routing_enabled",))
        intent_enabled = _bool_control(intent_value, default=active_policy.advisory_intent_routing_enabled)
        if not intent_enabled:
            return AdvisoryRoutingDecision(
                enabled=True,
                selected_skills=(),
                reason="advisory routing gate enabled without explicit skills",
                reasons=[*reasons, "intent routing disabled"],
            )
        selected = _infer_advisory_skills(query, user_mode)
        reasons.append("deterministic intent routing")

    if allowed:
        selected = tuple(skill for skill in selected if skill in allowed)
        if active_policy.advisory_allowed_skills and not explicit:
            reasons.append("restricted by configured advisory_allowed_skills")

    return AdvisoryRoutingDecision(
        enabled=True,
        selected_skills=selected,
        reason=reasons[-1],
        reasons=reasons,
    )


def route_task(
    *,
    constraints: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    policy: RoutingPolicy | None = None,
    settings: Settings | None = None,
    model_recommendation: Difficulty | str | None = None,
) -> RouteDecision:
    """Return the model path for a task without calling any model APIs."""
    if policy is not None:
        active_policy = policy
    elif settings is not None:
        active_policy = RoutingPolicy.from_settings(settings)
    else:
        active_policy = default_routing_policy()

    merged: dict[str, Any] = {**(context or {}), **(constraints or {})}
    recommendation = _coerce_difficulty(model_recommendation)

    reasons: list[str] = []
    difficulty = _coerce_difficulty(merged.get("difficulty")) or Difficulty.MEDIUM
    reasons.append("stakeholder difficulty" if "difficulty" in merged else "default medium")

    if _explicit_extreme(merged, active_policy):
        difficulty = Difficulty.EXTREME
        reasons.append("explicit stakeholder extreme marker")

    correction_attempts = int(merged.get("correction_attempts") or 0)
    issues_remain = bool(merged.get("issues_remain") or False)
    if issues_remain and correction_attempts >= active_policy.repeated_failure_threshold:
        difficulty = Difficulty.EXTREME
        reasons.append("repeated correction failure threshold reached")

    use_opus = active_policy.should_use_opus(difficulty)
    return RouteDecision(
        difficulty=difficulty,
        owner=active_policy.opus_owner if use_opus else active_policy.gpt_owner,
        use_opus_supervisor=use_opus,
        reason=reasons[-1] if reasons else "",
        reasons=reasons,
        model_recommendation=recommendation,
    )
