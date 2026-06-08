from .client import chat

_EXPORTS = {
    "AnthropicClient": ("anthropic_client", "AnthropicClient"),
    "BudgetDecision": ("budget", "BudgetDecision"),
    "BudgetDeniedError": ("budget", "BudgetDeniedError"),
    "BudgetGuard": ("budget", "BudgetGuard"),
    "LiveProviderDisabledError": ("_guards", "LiveProviderDisabledError"),
    "LlmFixture": ("replay", "LlmFixture"),
    "LlmRequest": ("replay", "LlmRequest"),
    "OpenAIClient": ("openai_client", "OpenAIClient"),
    "RecordingClient": ("replay", "RecordingClient"),
    "RecordingDisabledError": ("replay", "RecordingDisabledError"),
    "ReplayClient": ("replay", "ReplayClient"),
    "ReplayMissError": ("replay", "ReplayMissError"),
    "attach_cost_metadata": ("budget", "attach_cost_metadata"),
    "estimate_cost": ("budget", "estimate_cost"),
    "stable_request_hash": ("replay", "stable_request_hash"),
    "usage_from_response": ("budget", "usage_from_response"),
    "write_fixture": ("replay", "write_fixture"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _EXPORTS[name]
    module = __import__(f"{__name__}.{module_name}", fromlist=[attr_name])
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

__all__ = [
    "AnthropicClient",
    "BudgetDecision",
    "BudgetDeniedError",
    "BudgetGuard",
    "LiveProviderDisabledError",
    "LlmFixture",
    "LlmRequest",
    "OpenAIClient",
    "RecordingClient",
    "RecordingDisabledError",
    "ReplayClient",
    "ReplayMissError",
    "attach_cost_metadata",
    "chat",
    "estimate_cost",
    "stable_request_hash",
    "usage_from_response",
    "write_fixture",
]
