"""S3 — Concept explanation / summary / QA (URGENT).

Three modes:
  - whole_doc_summary(doc_id)
  - section_summary(doc_id, section_id)
  - qa(query, retrieved_chunks)  ← default entry for user questions

All answers must emit citations referencing chunk ids returned by S2.
"""
from __future__ import annotations

from ..schemas import SkillInput, SkillOutput
from .base import Skill


class QASummarySkill(Skill):
    name = "s3_qa_summary"

    def run(self, payload: SkillInput) -> SkillOutput:
        # TODO: build prompt from payload.retrieval_results + taxonomy,
        #       call llm.client, parse JSON answer + citations.
        raise NotImplementedError
