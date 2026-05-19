"""Model role registry for GPT-first / Opus-on-extreme orchestration."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from vibration_agent.config import Settings

logger = logging.getLogger(__name__)


class ModelSpec(BaseModel):
    provider: str
    model: str
    role: str
    purpose: str = ""

    @property
    def ref(self) -> str:
        return f"{self.provider}:{self.model}"


class ModelRegistry(BaseModel):
    roles: dict[str, ModelSpec]

    @classmethod
    def from_settings(cls, settings: Settings) -> "ModelRegistry":
        roles: dict[str, ModelSpec] = {}
        for role, reference in settings.llm.providers.items():
            provider, model = _parse_model_ref(role, reference)
            purpose = _ROLE_PURPOSES.get(role, "")
            if not purpose:
                logger.warning("Unknown model role configured: %s", role)
            roles[role] = ModelSpec(
                provider=provider,
                model=model,
                role=role,
                purpose=purpose,
            )
        return cls(roles=roles)

    def get(self, role: str) -> ModelSpec:
        try:
            return self.roles[role]
        except KeyError as exc:
            raise KeyError(f"Unknown model role: {role}") from exc

    def provider_for(self, role: str) -> str:
        return self.get(role).provider


def _parse_model_ref(role: str, reference: str) -> tuple[str, str]:
    if ":" not in reference:
        raise ValueError(f"Model role {role!r} must use 'provider:model' format")
    provider, model = reference.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError(f"Model role {role!r} must include both provider and model")
    return provider, model


_ROLE_PURPOSES = {
    "interaction_main": "low/medium/high user interaction",
    "task_router": "policy-aware routing recommendation",
    "executor": "implementation, tests, candidate answer",
    "senior_planner": "extreme-task framework design",
    "senior_reviewer": "extreme-task review",
    "emergency_owner": "take ownership after repeated failed correction loops",
    "main_answer": "legacy phase-0 user-facing synthesis role",
    "coder": "legacy phase-0 implementation role",
    "reviewer": "legacy high-risk reviewer role",
    "citation_checker": "legacy citation verification role",
}


@lru_cache(maxsize=1)
def _cached_default_model_registry() -> ModelRegistry:
    from vibration_agent.config import load

    return ModelRegistry.from_settings(load())


def default_model_registry() -> ModelRegistry:
    return _cached_default_model_registry().model_copy(deep=True)


def clear_default_model_registry_cache() -> None:
    _cached_default_model_registry.cache_clear()
