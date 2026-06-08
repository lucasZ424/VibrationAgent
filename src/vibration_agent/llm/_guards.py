"""Shared guards for live LLM provider clients."""
from __future__ import annotations

import os


class LiveProviderDisabledError(RuntimeError):
    """Raised when code tries to construct a live provider client outside manual mode."""


def pytest_guard_active() -> bool:
    if os.getenv("VIBRATION_AGENT_ALLOW_LIVE_LLM_IN_TESTS"):
        return False
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("VIBRATION_AGENT_PYTEST"))


__all__ = ["LiveProviderDisabledError", "pytest_guard_active"]
