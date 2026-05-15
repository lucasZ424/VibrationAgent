"""V4 — Output-style shaping (URGENT).

Forces the engineering-mode answer template from section 13 of the design doc:
  conclusion → engineering meaning → premises → failure modes / caveats →
  minimal model/formula → next action → evidence labels.
"""
from __future__ import annotations

from ..schemas import SkillInput, SkillOutput
from .base import Skill


class OutputStyleSkill(Skill):
    name = "v4_style"

    def run(self, payload: SkillInput) -> SkillOutput:
        # TODO: reformat payload.structured_result into the engineering template.
        raise NotImplementedError
