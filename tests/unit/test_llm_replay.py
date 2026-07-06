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
    request_from_kwargs,
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
        "model": "gpt-5.5",
        "prompt_version": "s3.v1",
        "schema_version": "s3.schema.v1",
        "request_body": {"prompt": "Use only chunk c1.", "chunk_id": "c1"},
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
    assert stable_request_hash(base) != stable_request_hash(_request(model="gpt-5.5-mini"))
    assert stable_request_hash(base) != stable_request_hash(_request(max_tokens=129))
    assert stable_request_hash(base) != stable_request_hash(_request(request_body={"prompt": "Different"}))

    metadata = fixture_metadata(base)
    for key in (
        "request_hash",
        "prompt_version",
        "schema_version",
        "provider",
        "model",
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


def test_replay_request_builder_supports_s4_analyze_engineering_shape():
    request = request_from_kwargs(
        task="s4_engineering_analysis",
        schema_version="s4.v1",
        kwargs={"model": "openai:gpt-5.5", "prompt": "Analyze S4.", "prompt_version": "s4_engineering_analysis.v1"},
    )

    assert request.provider == "openai"
    assert request.model == "gpt-5.5"
    assert request.prompt_version == "s4_engineering_analysis.v1"
    assert request.schema_version == "s4.v1"
    assert request.request_body["prompt"] == "Analyze S4."


def test_replay_request_builder_supports_s5_derive_formula_shape():
    request = request_from_kwargs(
        task="s5_formula_derivation",
        schema_version="s5.v1",
        kwargs={"model": "openai:gpt-5.5", "prompt": "Derive S5.", "prompt_version": "s5_formula_derivation.v1"},
    )

    assert request.provider == "openai"
    assert request.model == "gpt-5.5"
    assert request.prompt_version == "s5_formula_derivation.v1"
    assert request.schema_version == "s5.v1"
    assert request.request_body["prompt"] == "Derive S5."


def test_replay_request_builder_supports_supervisor_shapes():
    review = request_from_kwargs(
        task="supervisor_review",
        schema_version="supervisor.v1",
        kwargs={"model": "anthropic:claude-opus-4-8", "prompt": "Review.", "prompt_version": "supervisor_review.v1"},
    )
    correction = request_from_kwargs(
        task="supervisor_correction",
        schema_version="correction.v1",
        kwargs={
            "model": "anthropic:claude-opus-4-8",
            "prompt": "Correct.",
            "prompt_version": "supervisor_correction.v1",
        },
    )

    assert review.provider == "anthropic"
    assert review.model == "claude-opus-4-8"
    assert review.schema_version == "supervisor.v1"
    assert correction.provider == "anthropic"
    assert correction.model == "claude-opus-4-8"
    assert correction.schema_version == "correction.v1"


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


class FakeLiveClientWithUsage:
    def complete(self, request: LlmRequest) -> dict:
        return {
            "answer": "captured",
            "token_cost": 15,
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


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


def test_recording_client_preserves_token_count_fields():
    fixture_dir = _case_dir("token_counts")
    request = _request(request_body={"prompt": "Capture usage.", "access_token": "secret-token"})
    client = RecordingClient(
        client=FakeLiveClientWithUsage(),
        fixture_dir=fixture_dir,
        capture_enabled=True,
        manual_lane=True,
    )

    client.complete(request)
    fixture_text = (fixture_dir / f"{request.request_hash}.json").read_text(encoding="utf-8")

    assert "secret-token" not in fixture_text
    assert '"input_tokens": 10' in fixture_text
    assert '"output_tokens": 5' in fixture_text
    assert '"token_cost": 15' in fixture_text


def test_write_fixture_preserves_long_response_answer_for_replay():
    # WHY: Obj6 combined supervisor corrections can be long; truncating the
    # captured response makes replay apply a broken answer.
    fixture_dir = _case_dir("long_response")
    request = _request(request_body={"prompt": "x" * 5000})
    long_answer = "answer " * 900

    write_fixture(fixture_dir, request, {"answer": long_answer})
    payload = json.loads((fixture_dir / f"{request.request_hash}.json").read_text(encoding="utf-8"))

    assert payload["metadata"]["request_body"]["prompt"].endswith("...[TRUNCATED]")
    assert payload["response"]["answer"] == long_answer
    assert "...[TRUNCATED]" not in payload["response"]["answer"]


def test_recording_client_redacts_local_absolute_paths():
    fixture_dir = _case_dir("path_redaction")
    request = _request(
        request_body={
            "prompt": "Capture paths.",
            "source_path": r"C:\Users\zhoul\secret corpus\document.pdf",
            "trace": r"loaded C:\Challenge\Viberation\Agent\data\raw\doc.pdf",
        }
    )

    class PathLeakingClient:
        def complete(self, request: LlmRequest) -> dict:
            return {
                "answer": "captured",
                "debug_path": "/home/zhoul/secret/document.pdf",
                "unc_path": r"\\server\share\secret\document.pdf",
            }

    client = RecordingClient(client=PathLeakingClient(), fixture_dir=fixture_dir, capture_enabled=True, manual_lane=True)

    client.complete(request)
    fixture_text = (fixture_dir / f"{request.request_hash}.json").read_text(encoding="utf-8")

    assert "secret corpus" not in fixture_text
    assert "Viberation" not in fixture_text
    assert "/home/zhoul" not in fixture_text
    assert "server" not in fixture_text
    assert "[REDACTED_PATH]" in fixture_text


def test_recording_client_convenience_methods_write_task_fixtures():
    # WHY: Obj9 manual capture injects RecordingClient directly into S3/S4/S5
    # and supervisor seams. Each seam must record the same request shape that
    # replay later consumes in CI.
    fixture_dir = _case_dir("convenience")
    client = RecordingClient(
        client=FakeLiveClientWithUsage(),
        fixture_dir=fixture_dir,
        capture_enabled=True,
        manual_lane=True,
    )

    calls = [
        (
            client.synthesize,
            "s3_qa_summary",
            "s3.v1",
            {"model": "openai:gpt-5.5", "prompt": "S3", "prompt_version": "s3_qa_summary.v1"},
        ),
        (
            client.analyze_engineering,
            "s4_engineering_analysis",
            "s4.v1",
            {"model": "openai:gpt-5.5", "prompt": "S4", "prompt_version": "s4_engineering_analysis.v1"},
        ),
        (
            client.derive_formula,
            "s5_formula_derivation",
            "s5.v1",
            {"model": "openai:gpt-5.5", "prompt": "S5", "prompt_version": "s5_formula_derivation.v1"},
        ),
        (
            client.review,
            "supervisor_review",
            "supervisor.v1",
            {"model": "anthropic:claude-opus-4-8", "prompt": "review", "prompt_version": "supervisor_review.v1"},
        ),
        (
            client.correct,
            "supervisor_correction",
            "correction.v1",
            {
                "model": "anthropic:claude-opus-4-8",
                "prompt": "correct",
                "prompt_version": "supervisor_correction.v1",
            },
        ),
    ]

    for method, task, schema_version, kwargs in calls:
        response = method(**kwargs)
        request = request_from_kwargs(task=task, schema_version=schema_version, kwargs=kwargs)
        path = fixture_dir / f"{request.request_hash}.json"

        assert response["token_cost"] == 15
        assert path.exists()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["metadata"]["request_hash"] == request.request_hash
        assert payload["metadata"]["schema_version"] == schema_version
