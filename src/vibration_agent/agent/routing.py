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

    @classmethod
    def from_settings(cls, settings: Settings) -> "RoutingPolicy":
        routing = settings.routing
        return cls(
            gpt_owner=routing.default_owner,
            opus_difficulties=tuple(Difficulty(str(item).strip().lower()) for item in routing.opus_difficulties),
            repeated_failure_threshold=routing.repeated_failure_threshold,
            explicit_extreme_markers=tuple(str(item).strip().lower() for item in routing.explicit_extreme_markers),
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
