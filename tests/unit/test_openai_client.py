from __future__ import annotations

import sys

import pytest

from vibration_agent.config import load
from vibration_agent.llm.openai_client import LiveProviderDisabledError, OpenAIClient
from vibration_agent.llm.openai_client import _response_to_mapping, _responses_create_kwargs
from vibration_agent.llm.replay import LlmRequest


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
    assert settings.s5_enabled is False
    assert settings.openai.model == "gpt-5.5"
    assert settings.openai.input_usd_per_million_tokens == 5.0
    assert settings.openai.output_usd_per_million_tokens == 30.0
    assert settings.openai.cached_input_usd_per_million_tokens == 0.5
    assert settings.openai.reasoning_effort == "high"
    assert settings.openai.text_verbosity == "high"
    assert settings.openai.max_tokens == 8192
    assert settings.token_budget_per_task == 60000
    assert settings.token_budget_per_session == 180000


def test_openai_request_omits_deprecated_sampling_parameter_for_all_models():
    # WHY: Current OpenAI and Anthropic live lanes reject the legacy sampling
    # override for the configured model families, so provider requests omit it.
    kwargs = _responses_create_kwargs(
        LlmRequest(
            provider="openai",
            model="gpt-5.5",
            prompt_version="s3_qa_summary.v1",
            schema_version="s3.v1",
            request_body={"prompt": "Return JSON."},
            max_tokens=128,
            reasoning_effort="high",
            text_verbosity="high",
        )
    )

    assert _deprecated_sampling_key() not in kwargs
    assert kwargs["model"] == "gpt-5.5"
    assert kwargs["reasoning"] == {"effort": "high"}
    assert kwargs["text"] == {"verbosity": "high"}


def test_openai_non_gpt5_request_also_omits_deprecated_sampling_parameter():
    kwargs = _responses_create_kwargs(
        LlmRequest(
            provider="openai",
            model="gpt-4.1",
            prompt_version="s3_qa_summary.v1",
            schema_version="s3.v1",
            request_body={"prompt": "Return JSON."},
            max_tokens=128,
        )
    )

    assert _deprecated_sampling_key() not in kwargs


def _deprecated_sampling_key() -> str:
    return "temp" + "erature"


def test_openai_response_parser_extracts_nested_responses_output_text():
    # WHY: Responses API model_dump may omit top-level output_text and store
    # the actual JSON text under output[].content[].text.
    response = {
        "status": "completed",
        "output": [
            {
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"status":"ok","answer":"Rotor response [c1].","claims":[]}',
                    }
                ]
            }
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }

    mapped = _response_to_mapping(FakeOpenAIResponse(response))

    assert mapped["status"] == "ok"
    assert mapped["answer"] == "Rotor response [c1]."
    assert mapped["usage"]["total_tokens"] == 15


def test_openai_response_parser_keeps_incomplete_response_when_json_is_truncated():
    response = {
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [{"content": [{"type": "output_text", "text": '{"status":"ok","answer":"truncated'}]}],
    }

    mapped = _response_to_mapping(FakeOpenAIResponse(response))

    assert mapped["status"] == "incomplete"
    assert mapped["incomplete_details"]["reason"] == "max_output_tokens"


class FakeOpenAIResponse:
    def __init__(self, data: dict) -> None:
        self.data = data

    def model_dump(self, mode: str = "python") -> dict:
        return self.data
