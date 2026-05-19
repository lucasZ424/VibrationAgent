from pathlib import Path

from vibration_agent.schemas import SkillInput
from vibration_agent.skills import IngestionSkill


def _payload(**overrides):
    data = {
        "task_id": "task-1",
        "user_query": "ingest this document",
        "context": {},
        "constraints": {},
    }
    data.update(overrides)
    return SkillInput(**data)


def test_s1_ingestion_returns_structured_success(tmp_path):
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF fixture")
    calls = []

    def runner(path, **kwargs):
        calls.append((Path(path), kwargs))
        return {
            "status": "ok",
            "stage": "document_structured_export_batch",
            "input_path": str(source),
            "documents": [
                {
                    "status": "ok",
                    "doc_id": "doc1",
                    "source_path": str(source),
                    "processed_pages": 2,
                    "chunk_count": 3,
                    "outputs": {
                        "pages_jsonl": "data/ocr/book/doc1/pages.jsonl",
                        "chunks_jsonl": "data/chunks/book/doc1/chunks.jsonl",
                        "api_context_json": "data/exports/book/doc1/api_context.json",
                        "manifest_json": "data/exports/book/doc1/manifest.json",
                    },
                    "manifest": {
                        "doc_id": "doc1",
                        "counts": {"processed_pages": 2, "chunk_count": 3},
                        "quality": {"page_ocr_confidence_avg": 0.91},
                        "needs_review_pages": [2],
                        "warnings": ["Page 2 needs review"],
                    },
                }
            ],
            "warnings": [],
        }

    skill = IngestionSkill(runner=runner)
    output = skill.run(
        _payload(
            constraints={
                "input_path": str(source),
                "recursive": False,
                "max_pages": 5,
                "write_output": True,
                "keep_images": True,
                "source_type": "book",
            }
        )
    )

    assert output.status == "ok"
    assert output.structured_result["document_count"] == 1
    assert output.structured_result["chunk_count"] == 3
    assert output.structured_result["documents"][0]["doc_id"] == "doc1"
    assert output.structured_result["documents"][0]["outputs"]["chunks_jsonl"].endswith("chunks.jsonl")
    assert output.warnings == ["Page 2 needs review"]
    assert calls[0][0] == source
    assert calls[0][1]["recursive"] is False
    assert calls[0][1]["max_pages"] == 5
    assert calls[0][1]["keep_images"] is True


def test_s1_ingestion_missing_input_path_is_insufficient():
    output = IngestionSkill(runner=lambda *args, **kwargs: {}).run(_payload())

    assert output.status == "insufficient"
    assert "input_path" in output.summary


def test_s1_ingestion_missing_filesystem_path_is_insufficient(tmp_path):
    missing = tmp_path / "missing.pdf"
    output = IngestionSkill(runner=lambda *args, **kwargs: {}).run(_payload(constraints={"input_path": str(missing)}))

    assert output.status == "insufficient"
    assert output.structured_result["input_path"] == str(missing)
    assert "does not exist" in output.warnings[0]




def test_s1_ingestion_ok_batch_with_no_chunks_is_insufficient(tmp_path):
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF fixture")

    def runner(*args, **kwargs):
        return {
            "status": "ok",
            "stage": "document_structured_export_batch",
            "input_path": str(source),
            "documents": [{"status": "insufficient", "doc_id": "doc1", "source_path": str(source), "processed_pages": 1, "chunk_count": 0}],
            "warnings": [],
        }

    output = IngestionSkill(runner=runner).run(_payload(constraints={"input_path": str(source)}))

    assert output.status == "insufficient"
    assert output.structured_result["chunk_count"] == 0
    assert "produced no chunks" in output.warnings[0]

def test_s1_ingestion_runner_failure_returns_fail(tmp_path):
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF fixture")

    def runner(*args, **kwargs):
        raise RuntimeError("ocr unavailable")

    output = IngestionSkill(runner=runner).run(_payload(context={"input_path": str(source)}))

    assert output.status == "fail"
    assert "RuntimeError" in output.summary
    assert "ocr unavailable" in output.warnings[0]


def test_s1_ingestion_runner_insufficient_passes_through(tmp_path):
    source_dir = tmp_path / "empty"
    source_dir.mkdir()

    def runner(*args, **kwargs):
        return {"status": "insufficient", "stage": "document_structured_export_batch", "input_path": str(source_dir), "documents": [], "warnings": ["No supported input files found."]}

    output = IngestionSkill(runner=runner).run(_payload(constraints={"input_path": str(source_dir)}))

    assert output.status == "insufficient"
    assert output.structured_result["document_count"] == 0
    assert output.warnings == ["No supported input files found."]
