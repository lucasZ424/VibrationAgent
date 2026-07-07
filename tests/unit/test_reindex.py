import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.qdrant_reindex import parse_args
from vibration_agent.config import load
from vibration_agent.schemas import EmbeddingRecord
from vibration_agent.storage import qdrant
from vibration_agent.storage.reindex import corpus_fingerprint, run_reindex


def _chunks():
    return [
        {"chunk_id": "c1", "doc_id": "d1", "text": "rotor", "source_type": "book"},
        {"chunk_id": "c2", "doc_id": "d2", "text": "转子", "source_type": "standard"},
    ]


def _indexed_chunks():
    return [
        {
            **chunk,
            "embedding_model": "test-multilingual",
            "embedding_version": "v1",
            "embedding_dimension": 2,
        }
        for chunk in _chunks()
    ]


def _settings():
    settings = load()
    settings.embeddings.enabled = True
    settings.embeddings.model_name = "test-multilingual"
    settings.embeddings.model_version = "v1"
    settings.embeddings.batch_size = 1
    settings.database.qdrant_enabled = True
    settings.database.qdrant_vector_size = 2
    settings.database.qdrant_collection = "test_chunks"
    return settings


class MissingCollectionClient:
    def collection_exists(self, _collection):
        return False


def _records(texts, **_kwargs):
    return [
        EmbeddingRecord(
            text_hash=text,
            vector=[1.0, 0.0],
            dimension=2,
            model_name="test-multilingual",
            model_version="v1",
            provider="sentence_transformers",
        )
        for text in texts
    ]


def test_reindex_cli_exposes_safe_batch_timeout_and_resume_controls():
    args = parse_args(["--batch-size", "16", "--timeout", "120", "--checkpoint", "resume.json"])

    assert args.execute is False
    assert args.batch_size == 16
    assert args.timeout == 120.0
    assert args.checkpoint.name == "resume.json"


def test_reindex_cli_help_runs_outside_pytest_import_path():
    result = subprocess.run(
        [sys.executable, "scripts/qdrant_reindex.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--recreate-collection" in result.stdout


def test_reindex_defaults_to_non_writing_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(qdrant, "upsert_chunk_points", lambda *args, **kwargs: pytest.fail("unexpected write"))

    report = run_reindex(
        _chunks(),
        client=MissingCollectionClient(),
        settings=_settings(),
        execute=False,
        checkpoint_path=tmp_path / "checkpoint.json",
    )

    assert report["status"] == "dry_run"
    assert report["embeddable_chunks"] == 2
    assert report["source_type_counts"] == {"book": 1, "standard": 1}
    assert not (tmp_path / "checkpoint.json").exists()


def test_reindex_fingerprint_includes_source_identity_payload():
    # WHY: Obj7B can mutate citation/source payloads without changing text; a
    # stale checkpoint must not hide the required Qdrant payload refresh.
    original = [{"chunk_id": "c1", "text": "rotor", "source_filename": "old.pdf"}]
    mutated = [{"chunk_id": "c1", "text": "rotor", "source_filename": "new.pdf"}]

    assert corpus_fingerprint(original) != corpus_fingerprint(mutated)


def test_reindex_rejects_empty_pre_migration_corpus(tmp_path):
    with pytest.raises(RuntimeError, match="re-ingest before reindex"):
        run_reindex(
            [],
            client=MissingCollectionClient(),
            settings=_settings(),
            execute=False,
            checkpoint_path=tmp_path / "checkpoint.json",
        )


def test_reindex_rejects_existing_vector_space_mismatch(tmp_path):
    vectors = SimpleNamespace(size=3, distance=SimpleNamespace(value="Cosine"))
    config = SimpleNamespace(params=SimpleNamespace(vectors=vectors))
    client = SimpleNamespace(get_collection=lambda _name: SimpleNamespace(config=config))

    with pytest.raises(RuntimeError, match="explicit recreate required"):
        run_reindex(
            _chunks(),
            client=client,
            settings=_settings(),
            execute=False,
            checkpoint_path=tmp_path / "checkpoint.json",
        )


def test_reindex_resumes_after_last_completed_batch(tmp_path, monkeypatch):
    checkpoint = tmp_path / "checkpoint.json"
    calls: list[list[str]] = []
    fail_second_batch = True

    def flaky_embed(texts, **kwargs):
        nonlocal fail_second_batch
        calls.append(list(texts))
        if texts == ["转子"] and fail_second_batch:
            fail_second_batch = False
            raise RuntimeError("temporary interruption")
        return _records(texts, **kwargs)

    monkeypatch.setattr(qdrant, "upsert_chunk_points", lambda *args, **kwargs: len(args[1]))
    monkeypatch.setattr(qdrant, "load_chunk_payloads", lambda *args, **kwargs: _indexed_chunks())

    with pytest.raises(RuntimeError, match="temporary interruption"):
        run_reindex(
            _chunks(),
            client=MissingCollectionClient(),
            settings=_settings(),
            execute=True,
            checkpoint_path=checkpoint,
            embedder=flaky_embed,
        )

    report = run_reindex(
        _chunks(),
        client=MissingCollectionClient(),
        settings=_settings(),
        execute=True,
        checkpoint_path=checkpoint,
        embedder=flaky_embed,
    )

    assert calls == [["rotor"], ["转子"], ["转子"]]
    assert report["status"] == "complete"
    assert report["processed_chunks"] == 2
    assert report["parity"] is True


def test_reindex_rejects_token_feature_fallback(tmp_path):
    def fallback(texts, **_kwargs):
        return [
            EmbeddingRecord(
                text_hash=text,
                vector=[],
                dimension=0,
                model_name="test-multilingual",
                provider="fallback_token_features",
            )
            for text in texts
        ]

    with pytest.raises(RuntimeError, match="cannot be written or reported as ANN"):
        run_reindex(
            _chunks(),
            client=MissingCollectionClient(),
            settings=_settings(),
            execute=True,
            checkpoint_path=tmp_path / "checkpoint.json",
            embedder=fallback,
        )


def test_reindex_parity_fails_when_payload_embedding_provenance_drifts(tmp_path, monkeypatch):
    payloads = _indexed_chunks()
    payloads[1]["embedding_model"] = "wrong-model"
    monkeypatch.setattr(qdrant, "upsert_chunk_points", lambda *args, **kwargs: len(args[1]))
    monkeypatch.setattr(qdrant, "load_chunk_payloads", lambda *args, **kwargs: payloads)

    report = run_reindex(
        _chunks(),
        client=MissingCollectionClient(),
        settings=_settings(),
        execute=True,
        checkpoint_path=tmp_path / "checkpoint.json",
        embedder=_records,
    )

    assert report["status"] == "parity_failed"
    assert report["provenance_mismatch_chunk_ids"] == ["c2"]


def test_reindex_refreshes_runtime_retrieval_state_after_complete(tmp_path, monkeypatch):
    refreshed = {"called": False}
    monkeypatch.setattr(qdrant, "upsert_chunk_points", lambda *args, **kwargs: len(args[1]))
    monkeypatch.setattr(qdrant, "load_chunk_payloads", lambda *args, **kwargs: _indexed_chunks())

    report = run_reindex(
        _chunks(),
        client=MissingCollectionClient(),
        settings=_settings(),
        execute=True,
        checkpoint_path=tmp_path / "checkpoint.json",
        embedder=_records,
        refresh_runtime_state=lambda: refreshed.update(called=True),
    )

    assert report["status"] == "complete"
    assert report["runtime_state_refreshed"] is True
    assert refreshed["called"] is True
