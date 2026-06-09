from __future__ import annotations

import sys

import pytest

from vibration_agent.config import load
from vibration_agent.llm.openai_client import LiveProviderDisabledError, OpenAIClient


def test_openai_module_import_does_not_import_sdk():
    sys.modules.pop("openai", None)

    import vibration_agent.llm.openai_client  # noqa: F401

    assert "openai" not in sys.modules


def test_llm_package_import_keeps_provider_modules_lazy():
    for module_name in (
        "vibration_agent.llm.openai_client",
        "vibration_agent.llm.anthropic_client",
        "vibration_agent.llm.replay",
    ):
        sys.modules.pop(module_name, None)

    import vibration_agent.llm  # noqa: F401

    assert "vibration_agent.llm.openai_client" not in sys.modules
    assert "vibration_agent.llm.anthropic_client" not in sys.modules
    assert "vibration_agent.llm.replay" not in sys.modules


def test_openai_live_client_is_forbidden_during_pytest_even_when_enabled():
    settings = load().llm.openai

    with pytest.raises(LiveProviderDisabledError, match="forbidden during pytest"):
        OpenAIClient(settings, allow_live=True)


def test_openai_live_client_requires_manual_allow_flag():
    settings = load().llm.openai

    with pytest.raises(LiveProviderDisabledError, match="allow_live=True"):
        OpenAIClient(settings)


def test_openai_settings_load_from_llm_yaml():
    settings = load().llm

    assert settings.live_enabled is False
    assert settings.capture_enabled is False
    assert settings.s4_enabled is False
    assert settings.openai.model == "gpt-5.5"
    assert settings.openai.input_usd_per_million_tokens == 5.0
    assert settings.openai.output_usd_per_million_tokens == 30.0
    assert settings.openai.cached_input_usd_per_million_tokens == 0.5
    assert settings.openai.reasoning_effort == "high"
    assert settings.openai.text_verbosity == "high"
    assert settings.token_budget_per_task == 4000
    assert settings.token_budget_per_session == 30000
