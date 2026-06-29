from uuid import UUID

from vibration_agent.config import load
from vibration_agent.retrieval import dense
from vibration_agent.retrieval.embeddings import text_hash
from vibration_agent.schemas import EmbeddingRecord
from vibration_agent.storage import qdrant
from vibration_agent.storage.qdrant_client import QdrantSearchHit


def test_qdrant_payload_keeps_retrieval_context_text():
    chunk = {
        "chunk_id": "c1",
        "doc_id": "d1",
        "source_type": "manual",
        "text": "rotor damping evidence",
        "api_context": "short context",
        "assets": [{"asset_id": "a1"}],
    }

    payload = qdrant.chunk_payload(chunk, embedding_model="fake-model", embedding_version="v1")

    assert payload["chunk_id"] == "c1"
    assert payload["text"] == "rotor damping evidence"
    assert payload["api_context"] == "short context"
    assert payload["embedding_model"] == "fake-model"


def test_qdrant_stable_point_id_is_uuid_for_runtime_api_compatibility():
    # WHY: Qdrant's HTTP API rejects arbitrary SHA1 hex strings as point ids; a
    # stable UUID keeps reindex idempotent while satisfying the runtime contract.
    point_id = qdrant.stable_point_id("doc1_p0001_00001")

    assert str(UUID(point_id)) == point_id
    assert qdrant.stable_point_id("doc1_p0001_00001") == point_id


def test_qdrant_upsert_initializes_collection_with_vector_dimension(monkeypatch):
    calls: list[tuple[str, object]] = []

    def fake_ensure(client, *, collection, vector_size, distance):
        calls.append(("ensure", (client, collection, vector_size, distance)))

    def fake_upsert(client, *, collection, points):
        calls.append(("upsert", (client, collection, len(points))))
        return sum(1 for point in points if point.vector)

    monkeypatch.setattr(qdrant, "ensure_collection", fake_ensure)
    monkeypatch.setattr(qdrant, "upsert_points", fake_upsert)

    count = qdrant.upsert_chunk_points(
        object(),
        [{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        embeddings={"c1": [0.1, 0.2, 0.3]},
        collection="test_chunks",
    )

    assert count == 1
    assert calls[0][0] == "ensure"
    assert calls[0][1][2] == 3
    assert calls[1][0] == "upsert"


def test_qdrant_document_refresh_deletes_stale_points_before_reinsert(monkeypatch):
    # WHY: changed chunk boundaries must not leave orphan vectors after repeat ingestion.
    calls = {}
    monkeypatch.setattr(
        qdrant,
        "delete_points_by_doc_ids",
        lambda client, *, collection, doc_ids: calls.update({"collection": collection, "doc_ids": doc_ids}) or len(doc_ids),
    )

    count = qdrant.delete_chunk_points_for_documents(object(), ["doc1"], collection="test_chunks")

    assert count == 1
    assert calls == {"collection": "test_chunks", "doc_ids": ["doc1"]}


def test_qdrant_dry_run_reports_actual_vector_dimension():
    plan = qdrant.prepare_chunk_points(
        [{"chunk_id": "c1"}],
        embeddings={"c1": [0.1, 0.2, 0.3]},
    )

    assert plan.dry_run()["vector_size"] == 3


def test_qdrant_search_maps_hits_to_dense_lane(monkeypatch):
    monkeypatch.setattr(
        qdrant,
        "search_points",
        lambda client, *, collection, query_vector, top_k: [
            QdrantSearchHit(id="p1", score=0.9, payload={"chunk_id": "c1", "text": "rotor"})
        ],
    )

    results = qdrant.search_chunks(object(), [1.0, 0.0], top_k=1, collection="test_chunks")

    assert results == [{"chunk": {"chunk_id": "c1", "text": "rotor"}, "score": 0.9, "lane": "dense_qdrant"}]


def test_qdrant_load_chunk_payloads_scrolls_runtime_collection(monkeypatch):
    class Point:
        def __init__(self, payload):
            self.payload = payload

    class Client:
        def __init__(self):
            self.calls = 0

        def collection_exists(self, collection):
            return collection == "test_chunks"

        def scroll(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return [Point({"chunk_id": "c1", "text": "rotor damping"}), Point({"text": "no id"})], "next"
            return [Point({"chunk_id": "c2", "text": ""})], None

    payloads = qdrant.load_chunk_payloads(Client(), collection="test_chunks")

    assert payloads == [{"chunk_id": "c1", "text": "rotor damping"}]


def test_dense_search_uses_qdrant_when_enabled(monkeypatch):
    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = "test_chunks"
    chunks = [
        {"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"},
        {"chunk_id": "c2", "doc_id": "d1", "text": "bearing fault"},
    ]

    monkeypatch.setattr(
        dense,
        "embed_texts",
        lambda texts, **kwargs: [
            EmbeddingRecord(
                text_hash=text_hash(texts[0]),
                vector=[1.0, 0.0],
                dimension=2,
                model_name="fake-model",
                provider="sentence_transformers",
            )
        ],
    )
    monkeypatch.setattr(dense.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        dense.qdrant,
        "search_chunks",
        lambda client, vector, *, top_k, collection: [{"chunk": chunks[1], "score": 0.8, "lane": "dense_qdrant"}],
    )

    results = dense.search("bearing", chunks=chunks, top_k=1, settings=settings, warnings=[])

    assert results[0]["chunk"]["chunk_id"] == "c2"
    assert results[0]["lane"] == "dense_qdrant"


def test_dense_search_filters_qdrant_hits_to_supplied_corpus(monkeypatch):
    settings = load()
    settings.database.qdrant_enabled = True
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    monkeypatch.setattr(
        dense,
        "embed_texts",
        lambda texts, **kwargs: [
            EmbeddingRecord(
                text_hash=text_hash(texts[0]),
                vector=[1.0, 0.0],
                dimension=2,
                model_name="fake-model",
                provider="sentence_transformers",
            )
        ],
    )
    monkeypatch.setattr(dense.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        dense.qdrant,
        "search_chunks",
        lambda client, vector, *, top_k, collection: [
            {"chunk": {"chunk_id": "outside", "text": "outside corpus"}, "score": 0.99, "lane": "dense_qdrant"}
        ],
    )

    results = dense.search("rotor", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["chunk"]["chunk_id"] == "c1"
    assert results[0]["lane"] == "dense_local"
    assert warnings == []


def test_dense_search_empty_qdrant_result_skips_local_embedding_corpus_pass(monkeypatch):
    settings = load()
    settings.database.qdrant_enabled = True
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]
    calls: list[list[str]] = []

    def fake_embed(texts, **kwargs):
        calls.append(list(texts))
        return [
            EmbeddingRecord(
                text_hash=text_hash(texts[0]),
                vector=[1.0, 0.0],
                dimension=2,
                model_name="fake-model",
                provider="sentence_transformers",
            )
        ]

    monkeypatch.setattr(dense, "embed_texts", fake_embed)
    monkeypatch.setattr(dense.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(dense.qdrant, "search_chunks", lambda client, vector, *, top_k, collection: [])

    results = dense.search("rotor", chunks=chunks, top_k=1, settings=settings, warnings=[])

    assert results[0]["lane"] == "dense_local"
    assert calls == [["rotor"]]


def test_dense_search_qdrant_failure_falls_back_with_warning(monkeypatch):
    settings = load()
    settings.database.qdrant_enabled = True
    warnings: list[str] = []
    chunks = [{"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping"}]

    monkeypatch.setattr(
        dense,
        "embed_texts",
        lambda texts, **kwargs: [
            EmbeddingRecord(
                text_hash=text_hash(texts[0]),
                vector=[1.0, 0.0],
                dimension=2,
                model_name="fake-model",
                provider="sentence_transformers",
            )
        ],
    )
    monkeypatch.setattr(dense.qdrant, "runtime_client", lambda _: object())

    def fail_search(client, vector, *, top_k, collection):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(dense.qdrant, "search_chunks", fail_search)

    results = dense.search("rotor", chunks=chunks, top_k=1, settings=settings, warnings=warnings)

    assert results[0]["lane"] == "dense_local"
    assert "Qdrant dense retrieval unavailable" in warnings[0]


def test_load_uses_default_qdrant_dimension_matching_default_model():
    settings = load()

    assert settings.database.qdrant_vector_size == 384
