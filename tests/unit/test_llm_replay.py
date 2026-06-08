from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vibration_agent.llm.replay import (
    LlmRequest,
    RecordingClient,
    RecordingDisabledError,
    ReplayClient,
    ReplayMissError,
    fixture_metadata,
    stable_request_hash,
    write_fixture,
)


def _case_dir(name: str) -> Path:
    path = Path("data/exports/test_llm_replay") / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _request(**overrides) -> LlmRequest:
    data = {
        "provider": "openai",
        "model": "gpt-5.2",
        "prompt_version": "s3.v1",
        "schema_version": "s3.schema.v1",
        "request_body": {"prompt": "Use only chunk c1.", "chunk_id": "c1"},
        "temperature": 0.0,
        "max_tokens": 128,
        "reasoning_effort": "high",
        "text_verbosity": "high",
    }
    data.update(overrides)
    return LlmRequest(**data)


def test_stable_request_hash_includes_prompt_schema_model_settings_and_body():
    base = _request()

    assert stable_request_hash(base) == stable_request_hash(_request())
    assert stable_request_hash(base) != stable_request_hash(_request(prompt_version="s3.v2"))
    assert stable_request_hash(base) != stable_request_hash(_request(schema_version="s3.schema.v2"))
    assert stable_request_hash(base) != stable_request_hash(_request(model="gpt-5.2-mini"))
    assert stable_request_hash(base) != stable_request_hash(_request(max_tokens=129))
    assert stable_request_hash(base) != stable_request_hash(_request(request_body={"prompt": "Different"}))

    metadata = fixture_metadata(base)
    for key in (
        "request_hash",
        "prompt_version",
        "schema_version",
        "provider",
        "model",
        "temperature",
        "max_tokens",
        "reasoning_effort",
        "text_verbosity",
        "request_body",
    ):
        assert key in metadata


def test_replay_hit_returns_fixture_response_by_hash():
    fixture_dir = _case_dir("hit")
    request = _request()
    write_fixture(fixture_dir, request, {"answer": "Rotor response rises [c1].", "claims": []})

    response = ReplayClient(fixture_dir).complete(request)

    assert response["answer"] == "Rotor response rises [c1]."


def test_replay_miss_fails_without_live_fallback():
    fixture_dir = _case_dir("miss")

    with pytest.raises(ReplayMissError, match="No replay fixture"):
        ReplayClient(fixture_dir).complete(_request())


def test_replay_convenience_methods_have_provider_neutral_unknown_default():
    fixture_dir = _case_dir("correct_miss")

    with pytest.raises(ReplayMissError, match="No replay fixture"):
        ReplayClient(fixture_dir).correct(prompt="correct the candidate")


def test_replay_hash_mismatch_fails_loud():
    fixture_dir = _case_dir("mismatch")
    request = _request()
    path = write_fixture(fixture_dir, request, {"answer": "ok"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metadata"]["request_hash"] = "wrong"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReplayMissError, match="hash mismatch"):
        ReplayClient(fixture_dir).complete(request)


class FakeLiveClient:
    def complete(self, request: LlmRequest) -> dict:
        return {"answer": "captured", "authorization": "Bearer secret-token"}


def test_recording_client_is_manual_only():
    fixture_dir = _case_dir("manual_only")

    with pytest.raises(RecordingDisabledError):
        RecordingClient(client=FakeLiveClient(), fixture_dir=fixture_dir, capture_enabled=False, manual_lane=True)

    with pytest.raises(RecordingDisabledError):
        RecordingClient(client=FakeLiveClient(), fixture_dir=fixture_dir, capture_enabled=True, manual_lane=False)


def test_recording_client_writes_redacted_fixture():
    fixture_dir = _case_dir("redacted")
    request = _request(request_body={"prompt": "Capture this.", "api_key": "sk-secret"})
    client = RecordingClient(client=FakeLiveClient(), fixture_dir=fixture_dir, capture_enabled=True, manual_lane=True)

    response = client.complete(request)
    fixture_text = (fixture_dir / f"{request.request_hash}.json").read_text(encoding="utf-8")

    assert response["answer"] == "captured"
    assert "sk-secret" not in fixture_text
    assert "secret-token" not in fixture_text
    assert "[REDACTED]" in fixture_text
