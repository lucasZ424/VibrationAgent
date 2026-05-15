"""Multi-model client (see §12 of the design doc).

Roles:
  main_answer      — user-facing synthesis (default: Anthropic Claude)
  coder            — code generation for ingestion/retrieval
  reviewer         — reads without writing; fires only on high-risk answers
  citation_checker — verifies claims against retrieved chunks
"""
from __future__ import annotations

from typing import Literal

Role = Literal["main_answer", "coder", "reviewer", "citation_checker"]


def chat(role: Role, messages: list[dict], **kwargs) -> str:
    # TODO: route to the configured provider/model per role
    raise NotImplementedError
