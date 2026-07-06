import json

from vibration_agent.config import PathSettings, Settings

from scripts import persist_ingestion_exports


def test_load_export_documents_pairs_manifest_with_chunks(tmp_path):
    # WHY: long OCR books may be processed through the resumable file workflow,
    # then persisted later without re-running OCR. The handoff depends on this
    # manifest/chunks pairing staying stable.
    settings = Settings(
        paths=PathSettings(
            workspace=tmp_path,
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            ocr_dir=tmp_path / "data" / "ocr",
            extracted_dir=tmp_path / "data" / "extracted",
            chunks_dir=tmp_path / "data" / "chunks",
            embeddings_dir=tmp_path / "data" / "embeddings",
            exports_dir=tmp_path / "data" / "exports",
        )
    )

    manifest_dir = settings.paths.exports_dir / "book" / "doc1"
    chunks_dir = settings.paths.chunks_dir / "book" / "doc1"
    manifest_dir.mkdir(parents=True)
    chunks_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(
        json.dumps({"doc_id": "doc1", "outputs": {"chunks_jsonl": str(chunks_dir / "chunks.jsonl")}}),
        encoding="utf-8",
    )
    (chunks_dir / "chunks.jsonl").write_text(
        json.dumps({"chunk_id": "doc1_p0001_00001", "text": "rotor text"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    documents = persist_ingestion_exports.load_export_documents(settings, source_type="book")

    assert len(documents) == 1
    assert documents[0]["manifest"]["doc_id"] == "doc1"
    assert documents[0]["chunks"][0]["chunk_id"] == "doc1_p0001_00001"


def test_apply_storage_overrides_can_skip_qdrant_without_disabling_postgres(tmp_path):
    # WHY: Obj7B runtime rebuild persists file exports into Postgres first, then
    # performs one controlled Qdrant reindex with a fresh checkpoint.
    settings = Settings(
        paths=PathSettings(
            workspace=tmp_path,
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            ocr_dir=tmp_path / "data" / "ocr",
            extracted_dir=tmp_path / "data" / "extracted",
            chunks_dir=tmp_path / "data" / "chunks",
            embeddings_dir=tmp_path / "data" / "embeddings",
            exports_dir=tmp_path / "data" / "exports",
        )
    )
    settings.database.postgres_enabled = True
    settings.database.qdrant_enabled = True

    updated = persist_ingestion_exports.apply_storage_overrides(settings, skip_qdrant=True)

    assert updated.database.postgres_enabled is True
    assert updated.database.qdrant_enabled is False
