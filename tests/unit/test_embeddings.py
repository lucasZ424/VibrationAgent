import sys

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


class FakeOpenAIEmbeddingClient:
    def __init__(self) -> None:
        self.embeddings = self
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "data": [
                {"embedding": [float(index), float(len(text))]}
                for index, text in enumerate(kwargs["input"], start=1)
            ]
        }


class FakeOpenAIObjectResponseClient:
    def __init__(self) -> None:
        self.embeddings = self

    def create(self, **kwargs):
        return type(
            "EmbeddingResponse",
            (),
            {
                "data": [
                    type("EmbeddingItem", (), {"embedding": [float(len(text)), 2.0]})()
                    for text in kwargs["input"]
                ]
            },
        )()


class FakeOpenAIModelDumpResponseClient:
    def __init__(self) -> None:
        self.embeddings = self

    def create(self, **kwargs):
        data = [{"embedding": [3.0, float(len(text))]} for text in kwargs["input"]]

        class EmbeddingResponse:
            def model_dump(self, **_kwargs):
                return {"data": data}

        return EmbeddingResponse()


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


def test_openai_embedding_provider_uses_injected_client_without_live_sdk():
    sys.modules.pop("openai", None)
    client = FakeOpenAIEmbeddingClient()
    settings = _embedding_settings(
        provider="openai",
        model_name="text-embedding-3-small",
        model_version="2026-06",
        batch_size=2,
        local_files_only=False,
    )

    records = embed_texts(["rotor", "damping"], settings=settings, model_loader=lambda _: client)

    assert [record.provider for record in records] == ["openai", "openai"]
    assert [record.model_name for record in records] == ["text-embedding-3-small", "text-embedding-3-small"]
    assert [record.model_version for record in records] == ["2026-06", "2026-06"]
    assert [record.dimension for record in records] == [2, 2]
    assert records[0].vector == [1.0, 5.0]
    assert client.calls == [{"model": "text-embedding-3-small", "input": ["rotor", "damping"]}]
    assert "openai" not in sys.modules


@pytest.mark.parametrize(
    ("client", "expected_vector"),
    [
        (FakeOpenAIObjectResponseClient(), [5.0, 2.0]),
        (FakeOpenAIModelDumpResponseClient(), [3.0, 5.0]),
    ],
)
def test_openai_embedding_provider_parses_object_response_shapes(client, expected_vector):
    # WHY: Provider SDK response shapes have changed before; replay tests must
    # cover the supported non-dict shapes without making a live call.
    settings = _embedding_settings(
        provider="openai",
        model_name="text-embedding-3-small",
        local_files_only=False,
    )

    records = embed_texts(["rotor"], settings=settings, model_loader=lambda _: client)

    assert records[0].provider == "openai"
    assert records[0].vector == expected_vector


def test_openai_embedding_provider_falls_back_under_pytest_without_injected_client():
    settings = _embedding_settings(
        provider="openai",
        model_name="text-embedding-3-small",
        local_files_only=False,
    )

    records = embed_texts(["rotor"], settings=settings)

    assert records[0].provider == "fallback_token_features"
    assert records[0].dimension == 0
    assert "forbidden during pytest" in records[0].warnings[0]


def test_sentence_transformer_provider_falls_back_under_pytest_before_real_load():
    settings = _embedding_settings(
        provider="sentence_transformers",
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        local_files_only=False,
    )

    records = embed_texts(["rotor"], settings=settings)

    assert records[0].provider == "fallback_token_features"
    assert "forbidden during pytest" in records[0].warnings[0]


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


def test_dense_search_fallback_is_silent_when_embeddings_disabled():
    settings = load()
    settings.embeddings = _embedding_settings(enabled=False)
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    results = dense.search("rotor damping", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["chunk"]["chunk_id"] == "c1"
    assert results[0]["lane"] == "dense_local"
    assert warnings == []


def test_default_embedding_settings_are_disabled_and_silent():
    settings = load()

    records = embed_texts(["rotor"], settings=settings)

    assert settings.embeddings.enabled is False
    assert records[0].provider == "fallback_token_features"
    assert records[0].warnings == []


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
    assert settings.embeddings.enabled is False
    assert settings.embeddings.batch_size >= 1
    assert settings.embeddings.local_files_only is True
    assert settings.embeddings.api_key_env == "OPENAI_API_KEY"
    assert settings.embeddings.timeout == 30.0


def test_load_reads_embedding_environment_overrides(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBEDDING_MODEL_VERSION", "test-version")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "7")
    monkeypatch.setenv("EMBEDDING_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_LOCAL_FILES_ONLY", "false")
    monkeypatch.setenv("EMBEDDING_FALLBACK_TO_TOKEN_FEATURES", "false")
    monkeypatch.setenv("EMBEDDING_API_KEY_ENV", "CUSTOM_OPENAI_KEY")
    monkeypatch.setenv("EMBEDDING_TIMEOUT", "12.5")

    settings = load()

    assert settings.embeddings.provider == "openai"
    assert settings.embeddings.model_name == "text-embedding-3-small"
    assert settings.embeddings.model_version == "test-version"
    assert settings.embeddings.batch_size == 7
    assert settings.embeddings.enabled is True
    assert settings.embeddings.local_files_only is False
    assert settings.embeddings.fallback_to_token_features is False
    assert settings.embeddings.api_key_env == "CUSTOM_OPENAI_KEY"
    assert settings.embeddings.timeout == 12.5
