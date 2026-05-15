"""S2 — Knowledge-base retrieval (URGENT).

query-normalize → BM25 + dense → rerank → source-priority fusion.
Source priority: standard > textbook > review > paper > webpage.
"""
from __future__ import annotations

from ..schemas import SkillInput, SkillOutput
from .base import Skill


class RetrievalSkill(Skill):
    name = "s2_retrieval"

    def run(self, payload: SkillInput) -> SkillOutput:
        # TODO: delegate to retrieval.hybrid.search(query, ...)
        raise NotImplementedError
