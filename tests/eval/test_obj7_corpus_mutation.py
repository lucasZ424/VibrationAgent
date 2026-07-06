import json

from scripts.obj7_corpus_mutation import run_obj7_corpus_mutation


def _write_doc(root, *, source_type="book", doc_id="doc1"):
    chunks_dir = root / "chunks" / source_type / doc_id
    exports_dir = root / "exports" / source_type / doc_id
    chunks_dir.mkdir(parents=True)
    exports_dir.mkdir(parents=True)
    chunks_path = chunks_dir / "chunks.jsonl"
    chunks_path.write_text(
        json.dumps(
            {
                "chunk_id": f"{doc_id}_p0001_00001",
                "doc_id": doc_id,
                "title": "Old Title",
                "source_type": source_type,
                "source_path": "old/path.pdf",
                "text": "rotor text",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (exports_dir / "manifest.json").write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "title": "Rotor Handbook",
                "input": {
                    "filename": "rotor-handbook.pdf",
                    "source_path": "data/raw/book/rotor-handbook.pdf",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return chunks_path


def test_obj7_corpus_mutation_dry_run_reports_without_writing(tmp_path):
    # WHY: Obj7B needs an auditable plan before mutating the ignored corpus
    # snapshot or runtime stores.
    chunks_path = _write_doc(tmp_path)

    report = run_obj7_corpus_mutation(
        chunks_dir=tmp_path / "chunks",
        exports_dir=tmp_path / "exports",
        execute=False,
    )
    row = json.loads(chunks_path.read_text(encoding="utf-8"))

    assert report["mode"] == "dry_run"
    assert report["changed_chunk_count"] == 1
    assert report["field_update_counts"] == {
        "source_filename": 1,
        "source_path": 1,
        "source_title": 1,
    }
    assert row.get("source_filename") is None


def test_obj7_corpus_mutation_execute_backfills_direct_source_identity(tmp_path):
    chunks_path = _write_doc(tmp_path)

    report = run_obj7_corpus_mutation(
        chunks_dir=tmp_path / "chunks",
        exports_dir=tmp_path / "exports",
        execute=True,
    )
    row = json.loads(chunks_path.read_text(encoding="utf-8"))

    assert report["mode"] == "execute"
    assert report["content_fingerprint_before"] == report["content_fingerprint_after"]
    assert report["identity_fingerprint_before"] != report["identity_fingerprint_after"]
    assert row["source_filename"] == "rotor-handbook.pdf"
    assert row["source_title"] == "Rotor Handbook"
    assert row["source_path"] == "data/raw/book/rotor-handbook.pdf"


def test_obj7_corpus_mutation_idempotent_plan_does_not_request_rebuild(tmp_path):
    # WHY: after the Obj7B file snapshot is already mutated, the dry-run report
    # must not imply another runtime rebuild is still required.
    _write_doc(tmp_path)
    run_obj7_corpus_mutation(
        chunks_dir=tmp_path / "chunks",
        exports_dir=tmp_path / "exports",
        execute=True,
    )

    report = run_obj7_corpus_mutation(
        chunks_dir=tmp_path / "chunks",
        exports_dir=tmp_path / "exports",
        execute=False,
    )

    assert report["changed_chunk_count"] == 0
    assert report["runtime_rebuild_requirement"]["postgres_refresh_required"] is False
    assert "not required" in report["runtime_rebuild_requirement"]["reason"]
