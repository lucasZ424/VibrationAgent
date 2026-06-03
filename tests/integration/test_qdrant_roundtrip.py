import uuid

import pytest

from vibration_agent.config import load
from vibration_agent.storage import qdrant
from vibration_agent.storage.qdrant_client import create_client


pytestmark = pytest.mark.integration


def test_qdrant_roundtrip_with_live_instance():
    pytest.importorskip("qdrant_client")
    settings = load()
    client = create_client(
        url=settings.database.qdrant_url,
        api_key=settings.database.qdrant_api_key,
        timeout=settings.database.qdrant_timeout,
    )
    try:
        client.get_collections()
    except Exception as exc:
        pytest.skip(f"Qdrant instance is not available: {exc}")

    collection = f"test_chunks_{uuid.uuid4().hex}"
    try:
        chunks = [
            {"chunk_id": "c1", "doc_id": "d1", "text": "rotor damping evidence"},
            {"chunk_id": "c2", "doc_id": "d1", "text": "bearing fault evidence"},
        ]
        qdrant.upsert_chunk_points(
            client,
            chunks,
            embeddings={"c1": [1.0, 0.0], "c2": [0.0, 1.0]},
            collection=collection,
            embedding_model="fake-model",
        )

        results = qdrant.search_chunks(client, [1.0, 0.0], top_k=1, collection=collection)

        assert results[0]["chunk"]["chunk_id"] == "c1"
        assert results[0]["lane"] == "dense_qdrant"
    finally:
        try:
            client.delete_collection(collection)
        except Exception:
            pass
