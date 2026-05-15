"""Skill interface contract."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import SkillInput, SkillOutput


class Skill(ABC):
    name: str
    version: str = "0.0.1"

    @abstractmethod
    def run(self, payload: SkillInput) -> SkillOutput: ...
