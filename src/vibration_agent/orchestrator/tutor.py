"""Tutor-Orchestrator: the single user-facing entry point.

Responsibilities:
  1. classify intent (definition | summary | engineering | standard_lookup | research)
  2. route to skills (S1–S8 + V1–V4)
  3. merge skill outputs and enforce output-style (V4)
  4. attach evidence labels and confidence bounds

Phase-0 wiring only calls S2 → S3 → V4.
"""
from __future__ import annotations

from ..schemas import SkillOutput


def handle_query(query: str) -> SkillOutput:
    # TODO: intent classification
    # TODO: S2 retrieval → S3 qa/summary → V4 style
    raise NotImplementedError
