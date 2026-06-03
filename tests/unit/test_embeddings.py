import pytest

from vibration_agent.config import EmbeddingSettings, Settings, load
from vibration_agent.retrieval import dense
from vibration_agent.retrieval.embeddings import clear_embedding_cache, embed_texts, text_hash
from vibration_agent.schemas import EmbeddingRecord


class FakeEmbeddingModel:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    def encode(self, texts, **kwargs):
        self.batches.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


def _embedding_settings(**overrides) -> EmbeddingSettings:
    data = {
        "enabled": True,
        "provider": "sentence_transformers",
        "model_name": "fake-model",
        "model_version": "test",
        "batch_size": 2,
        "local_files_only": False,
        "fallback_to_token_features": True,
    }
    data.update(overrides)
    return EmbeddingSettings(**data)


@pytest.fixture(autouse=True)
def _clear_embedding_cache():
    clear_embedding_cache()
    yield
    clear_embedding_cache()


def test_embedding_record_schema_carries_model_provenance():
    record = EmbeddingRecord(
        text_hash="abc",
        vector=[1.0, 2.0],
        dimension=2,
        model_name="fake-model",
        model_version="test",
        provider="sentence_transformers",
    )

    assert record.dimension == 2
    assert record.model_name == "fake-model"
    assert record.warnings == []


def test_embed_texts_batches_and_dedupes_with_fake_model():
    model = FakeEmbeddingModel()
    settings = _embedding_settings(batch_size=1)

    records = embed_texts(
        ["rotor", "rotor", "damping"],
        settings=settings,
        model_loader=lambda _: model,
    )

    assert [record.text_hash for record in records] == [text_hash("rotor"), text_hash("rotor"), text_hash("damping")]
    assert records[0].vector == records[1].vector
    assert records[0].dimension == 2
    assert records[0].model_name == "fake-model"
    assert model.batches == [["rotor"], ["damping"]]


def test_embed_texts_reuses_cached_records_across_calls():
    model = FakeEmbeddingModel()
    settings = _embedding_settings(batch_size=2)

    first = embed_texts(["rotor"], settings=settings, model_loader=lambda _: model)
    second = embed_texts(["rotor", "damping"], settings=settings, model_loader=lambda _: model)

    assert second[0].text_hash == first[0].text_hash
    assert second[0].vector == first[0].vector
    assert model.batches == [["rotor"], ["damping"]]


def test_embed_texts_falls_back_with_warning_when_model_unavailable():
    settings = _embedding_settings()

    records = embed_texts(
        ["rotor"],
        settings=settings,
        model_loader=lambda _: (_ for _ in ()).throw(RuntimeError("missing model")),
    )

    assert records[0].provider == "fallback_token_features"
    assert records[0].vector == []
    assert records[0].dimension == 0
    assert "Embedding model unavailable" in records[0].warnings[0]


def test_dense_search_uses_embedding_vectors_when_available(monkeypatch):
    chunks = [
        {"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"},
        {"chunk_id": "c2", "doc_id": "d1", "text": "bearing fault"},
    ]

    def fake_embed(texts, **kwargs):
        vectors = ([1.0, 0.0], [1.0, 0.0], [0.0, 1.0])
        return [
            EmbeddingRecord(
                text_hash=text_hash(text),
                vector=vector,
                dimension=2,
                model_name="fake-model",
                provider="sentence_transformers",
            )
            for text, vector in zip(texts, vectors, strict=True)
        ]

    monkeypatch.setattr(dense, "embed_texts", fake_embed)

    results = dense.search("rotor damping", chunks=chunks, top_k=2)

    assert results[0]["chunk"]["chunk_id"] == "c1"
    assert results[0]["lane"] == "dense_embedding"


def test_dense_search_fallback_records_warning():
    settings = load()
    settings.embeddings = _embedding_settings(enabled=False)
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    results = dense.search("rotor damping", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["chunk"]["chunk_id"] == "c1"
    assert results[0]["lane"] == "dense_local"
    assert "Embedding model is disabled" in warnings[0]


def test_dense_search_default_local_model_cold_start_is_silent():
    settings = load()
    settings.embeddings = _embedding_settings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        local_files_only=True,
    )
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    results = dense.search("rotor damping", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["chunk"]["chunk_id"] == "c1"
    assert results[0]["lane"] == "dense_local"
    assert warnings == []


def test_dense_search_missing_configured_local_path_records_warning():
    settings = load()
    settings.embeddings = _embedding_settings(
        model_name="data/tmp/missing-embedding-model",
        local_files_only=True,
    )
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    results = dense.search("rotor damping", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["lane"] == "dense_local"
    assert "Local embedding model path not found" in warnings[0]


def test_load_reads_embeddings_yaml():
    settings: Settings = load()

    assert settings.embeddings.provider == "sentence_transformers"
    assert settings.embeddings.batch_size >= 1
    assert settings.embeddings.local_files_only is True
