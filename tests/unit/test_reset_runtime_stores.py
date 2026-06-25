from scripts import reset_runtime_stores


def test_postgres_reset_sql_targets_only_ingestion_tables():
    # WHY: the reset command is destructive and must not wipe taxonomy/config
    # tables that are not part of regenerated ingestion state.
    sql = reset_runtime_stores.postgres_reset_sql()

    assert "documents" in sql
    assert "chunks" in sql
    assert "document_sections" in sql
    assert "figures_tables" in sql
    assert "citations" in sql
    assert "qa_logs" not in sql
    assert "terms" not in sql
    assert "RESTART IDENTITY CASCADE" in sql


def test_reset_qdrant_deletes_only_configured_collection(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.deleted = []

        def collection_exists(self, collection):
            return collection == "chunks"

        def delete_collection(self, collection):
            self.deleted.append(collection)

    class Database:
        qdrant_enabled = True
        qdrant_collection = "chunks"

    class Settings:
        database = Database()

    fake = FakeClient()
    monkeypatch.setattr(reset_runtime_stores.qdrant, "runtime_client", lambda settings: fake)

    result = reset_runtime_stores._reset_qdrant(Settings(), execute=True)

    assert result == {"status": "reset", "collection": "chunks", "existed": True}
    assert fake.deleted == ["chunks"]
