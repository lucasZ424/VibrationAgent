"""Placeholder launcher for S1 ingestion skill packages.

The stable runtime entry remains `vibration_agent.skills.s1_ingestion.IngestionSkill`.
This file exists so agent skill packages can advertise a scripts/ surface without
owning business logic.
"""
from __future__ import annotations

from vibration_agent.skills.s1_ingestion import IngestionSkill

__all__ = ["IngestionSkill"]
