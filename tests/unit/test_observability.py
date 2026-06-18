import json
import logging

from vibration_agent.observability import (
    LOCAL_PATH_REDACTED,
    LONG_TEXT_REDACTED,
    REDACTED,
    log_event,
    redact_text,
    redact_value,
)


def test_redaction_removes_secrets_bearer_tokens_paths_and_long_text():
    text = (
        "OPENAI_API_KEY=sk-test Bearer abc.def "
        "C:\\Users\\local\\secret\\file.txt /home/local/secret/file.txt"
    )

    redacted = redact_text(text)

    assert "sk-test" not in redacted
    assert "abc.def" not in redacted
    assert "C:\\Users" not in redacted
    assert "/home/local" not in redacted
    assert REDACTED in redacted
    assert LOCAL_PATH_REDACTED in redacted
    assert redact_text("x" * 300) == LONG_TEXT_REDACTED


def test_redact_value_uses_sensitive_keys_recursively():
    payload = {
        "api_key": "sk-test",
        "nested": {"authorization": "Bearer abc"},
        "safe": "rotor vibration",
    }

    redacted = redact_value(payload)

    assert redacted["api_key"] == REDACTED
    assert redacted["nested"]["authorization"] == REDACTED
    assert redacted["safe"] == "rotor vibration"


def test_redaction_uses_explicit_local_path_prefix_for_custom_posix_roots():
    text = "failed at /opt/custom-agent/workspace/data/private/chunks.jsonl"

    redacted = redact_text(text, path_prefixes=["/opt/custom-agent/workspace"])

    assert "/opt/custom-agent" not in redacted
    assert "private/chunks.jsonl" not in redacted
    assert LOCAL_PATH_REDACTED in redacted


def test_redact_value_propagates_explicit_path_prefixes():
    payload = {"detail": "failed at /srv/vibration-agent/data/private.txt"}

    redacted = redact_value(payload, path_prefixes=["/srv/vibration-agent"])

    assert "/srv/vibration-agent" not in redacted["detail"]
    assert "private.txt" not in redacted["detail"]
    assert LOCAL_PATH_REDACTED in redacted["detail"]


def test_log_event_emits_json_without_raw_secret(caplog):
    logger = logging.getLogger("tests.observability")
    caplog.set_level(logging.INFO, logger=logger.name)

    log_event(logger, logging.INFO, "manual_check", api_token="secret", path="C:\\Challenge\\private.txt")

    record = next(item for item in caplog.records if item.name == logger.name)
    payload = json.loads(record.message)
    assert payload["schema_version"] == "p4.local_observability.v1"
    assert payload["event"] == "manual_check"
    assert payload["api_token"] == REDACTED
    assert payload["path"] == LOCAL_PATH_REDACTED
    assert "secret" not in record.message
