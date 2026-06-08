from __future__ import annotations

import sys

import pytest

from vibration_agent.config import load
from vibration_agent.llm.anthropic_client import AnthropicClient
from vibration_agent.llm.openai_client import LiveProviderDisabledError


def test_anthropic_module_import_does_not_import_sdk():
    sys.modules.pop("anthropic", None)

    import vibration_agent.llm.anthropic_client  # noqa: F401

    assert "anthropic" not in sys.modules


def test_anthropic_live_client_is_forbidden_during_pytest_even_when_enabled():
    settings = load().llm.anthropic

    with pytest.raises(LiveProviderDisabledError, match="forbidden during pytest"):
        AnthropicClient(settings, allow_live=True)


def test_anthropic_live_client_requires_manual_allow_flag():
    settings = load().llm.anthropic

    with pytest.raises(LiveProviderDisabledError, match="allow_live=True"):
        AnthropicClient(settings)


def test_anthropic_settings_load_from_llm_yaml():
    settings = load().llm.anthropic

    assert settings.model == "claude-opus-4-8"
    assert settings.api_key_env == "ANTHROPIC_API_KEY"
    assert settings.max_tokens == 1024
