"""S1 — Document ingestion & parsing (URGENT).

Classify source → OCR-route → extract structure → chunk → index.
Thin wrapper around `vibration_agent.ingestion.pipeline`.
"""
from __future__ import annotations

from ..schemas import SkillInput, SkillOutput
from .base import Skill


class IngestionSkill(Skill):
    name = "s1_ingestion"

    def run(self, payload: SkillInput) -> SkillOutput:
        # TODO: delegate to ingestion.pipeline
        raise NotImplementedError
