import json

from scripts import data_cleanup


def test_data_cleanup_dry_run_keeps_raw_and_chunks_by_default(tmp_path, capsys):
    # WHY: cleanup must save space without deleting source corpus or the current
    # file-backed retrieval corpus unless explicitly requested.
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "source.pdf").write_text("raw", encoding="utf-8")
    (tmp_path / "data" / "chunks" / "doc").mkdir(parents=True)
    (tmp_path / "data" / "chunks" / "doc" / "chunks.jsonl").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "run_logs").mkdir(parents=True)
    (tmp_path / "data" / "run_logs" / "run.log").write_text("log", encoding="utf-8")

    code = data_cleanup.main(["--workspace", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "dry_run"
    paths = "\n".join(item["path"] for item in payload["candidates"])
    assert "run_logs" in paths
    assert "raw" not in paths
    assert "chunks" not in paths
    assert (tmp_path / "data" / "run_logs" / "run.log").exists()


def test_data_cleanup_execute_deletes_regenerable_outputs_but_not_raw_or_chunks(tmp_path):
    # WHY: regenerable cleanup should remove OCR/export artifacts while leaving
    # provenance and current file-backed retrieval usable.
    for dirname in ("raw", "chunks", "ocr", "extracted", "exports"):
        path = tmp_path / "data" / dirname
        path.mkdir(parents=True)
        (path / "item.txt").write_text(dirname, encoding="utf-8")

    code = data_cleanup.main(["--workspace", str(tmp_path), "--profile", "regenerable", "--execute"])

    assert code == 0
    assert (tmp_path / "data" / "raw" / "item.txt").exists()
    assert (tmp_path / "data" / "chunks" / "item.txt").exists()
    assert not (tmp_path / "data" / "ocr").exists()
    assert not (tmp_path / "data" / "extracted").exists()
    assert not (tmp_path / "data" / "exports").exists()
