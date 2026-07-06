import json

from scripts.obj7_text_repair import run_text_repairs


def _write_chunk(root):
    chunks_dir = root / "chunks" / "book" / "doc1"
    chunks_dir.mkdir(parents=True)
    path = chunks_dir / "chunks.jsonl"
    row = {
        "chunk_id": "c1",
        "doc_id": "doc1",
        "source_type": "book",
        "text": "alpha start. bad�formula�block end marker beta",
        "api_context": "ctx alpha start. bad�formula�block end marker beta",
        "char_count": 43,
        "token_estimate": 12,
        "metadata": {},
    }
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _repair():
    return {
        "id": "repair1",
        "chunk_id": "c1",
        "fields": ["text", "api_context"],
        "start_marker": "start.",
        "end_marker": "end marker",
        "replacement": " [artifact removed] ",
    }


def test_obj7_text_repair_dry_run_does_not_write(tmp_path):
    path = _write_chunk(tmp_path)

    report = run_text_repairs(
        repairs=[_repair()],
        chunks_dir=tmp_path / "chunks",
        execute=False,
    )
    row = json.loads(path.read_text(encoding="utf-8"))

    assert report["changed_chunk_count"] == 1
    assert "bad�formula" in row["text"]


def test_obj7_text_repair_execute_updates_text_and_is_idempotent(tmp_path):
    path = _write_chunk(tmp_path)

    report = run_text_repairs(
        repairs=[_repair()],
        chunks_dir=tmp_path / "chunks",
        execute=True,
    )
    row = json.loads(path.read_text(encoding="utf-8"))
    rerun = run_text_repairs(
        repairs=[_repair()],
        chunks_dir=tmp_path / "chunks",
        execute=False,
    )

    assert report["changed_chunk_count"] == 1
    assert "�" not in row["text"]
    assert "�" not in row["api_context"]
    assert row["metadata"]["corpus_text_repairs"] == ["repair1"]
    assert rerun["changed_chunk_count"] == 0
    assert rerun["repairs"][0]["field_status"] == {
        "api_context": "already_applied",
        "text": "already_applied",
    }
