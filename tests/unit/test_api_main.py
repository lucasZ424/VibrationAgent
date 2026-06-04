import json
from pathlib import Path

from fastapi.testclient import TestClient

import apps.api.main as api_main


client = TestClient(api_main.app)


def _chunk(chunk_id: str, text: str, *, pages: list[int] | None = None, doc_id: str = "doc1") -> dict:
    pages = pages or [1]
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "title": "Rotor Dynamics",
        "source_type": "book",
        "chunk_index": 1,
        "page_start": pages[0],
        "page_end": pages[-1],
        "pages": pages,
        "chunk_type": "body",
        "topic": "rotor_dynamics",
        "token_estimate": 20,
        "char_count": len(text),
        "text": text,
        "api_context": f"[chunk_id={chunk_id}; doc_id={doc_id}; pages={pages[0]}-{pages[-1]}]\n{text}",
        "assets": [],
        "metadata": {},
    }


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_api_health_returns_runtime_status():
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["app"]
    assert payload["workspace"]
    assert "s2_retrieval" in payload["phase0_pipeline"]
    assert "v2_citation_check" in payload["phase0_pipeline"]


def test_api_scope_returns_phase0_registry():
    response = client.get("/scope")
    payload = response.json()

    assert response.status_code == 200
    assert "s2_retrieval" in payload["active_skills"]
    assert "v2_citation_check" in payload["active_skills"]
    assert "s4_engineering_analysis" in payload["deferred_skills"]
    assert "v2_citation_check" not in payload["deferred_skills"]


def test_api_ingest_plan_only_empty_dir_returns_insufficient(tmp_path):
    response = client.post("/ingest", json={"path": str(tmp_path), "plan_only": True})
    payload = response.json()

    assert response.status_code == 200
    assert payload["workspace"]
    assert payload["status"] == "insufficient"
    assert payload["result"]["stage"] == "input_classification"


def test_api_ingest_chunk_documents_empty_dir_returns_insufficient(tmp_path):
    response = client.post("/ingest", json={"path": str(tmp_path)})
    payload = response.json()

    assert response.status_code == 200
    assert payload["workspace"]
    assert payload["status"] == "insufficient"
    assert payload["result"]["stage"] == "document_structured_export_batch"


def test_api_query_runs_tutor_chain_with_chunks_jsonl(tmp_path):
    chunks_path = _write_jsonl(
        tmp_path / "chunks.jsonl",
        [_chunk("c1", "阻尼比 zeta 控制自由振动衰减速度。阻尼越大，振动衰减越快。", pages=[3])],
    )

    response = client.post(
        "/query",
        json={
            "query": "阻尼比如何影响转子振动？",
            "chunks_jsonl": [str(chunks_path)],
            "top_k": 1,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["output"]["structured_result"]["scope"] == "in_scope"
    assert [step["skill"] for step in payload["output"]["structured_result"]["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v2_citation_check",
        "v4_style",
    ]
    assert payload["output"]["citations"][0]["chunk_id"] == "c1"


def test_api_query_accepts_chunks_dir_scope_context_and_task_id(tmp_path):
    _write_jsonl(
        tmp_path / "book" / "doc1" / "chunks.jsonl",
        [_chunk("c1", "临界转速附近转子振动响应会被放大。", pages=[4])],
    )

    response = client.post(
        "/query",
        json={
            "query": "临界转速下转子振动如何变化？",
            "context": {"note": "api-test"},
            "task_id": "task-api-1",
            "scope": "in_scope",
            "chunks_dir": str(tmp_path),
            "top_k": 1,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["task_id"] == "task-api-1"
    assert payload["output"]["structured_result"]["skill_results"]["s2"]["chunks_dir"] == str(tmp_path)




def test_api_query_accepts_domain_scope_as_scope_alias(tmp_path):
    _write_jsonl(
        tmp_path / "book" / "doc1" / "chunks.jsonl",
        [_chunk("c1", "临界转速附近转子振动响应会被放大。", pages=[4])],
    )

    response = client.post(
        "/query",
        json={
            "query": "临界转速下转子振动如何变化？",
            "domain_scope": "in_scope",
            "chunks_dir": str(tmp_path),
            "top_k": 1,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["output"]["structured_result"]["scope"] == "in_scope"

def test_api_query_returns_insufficient_without_corpus():
    response = client.post("/query", json={"query": "临界转速下转子振动如何变化？"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "insufficient"
    assert payload["output"]["structured_result"]["chain"][0]["skill"] == "s2_retrieval"


def test_api_runtime_error_response_has_locatable_reason(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise PermissionError("blocked")

    monkeypatch.setattr(api_main, "chunk_documents", boom)

    response = client.post("/ingest", json={"path": str(tmp_path)})
    payload = response.json()

    assert response.status_code == 403
    assert payload["status"] == "fail"
    assert payload["detail"][0]["loc"] == ["body", "path"]
    assert payload["detail"][0]["error_type"] == "PermissionError"
    assert payload["detail"][0]["reason"] == "blocked"


def test_api_validation_error_uses_api_error_envelope():
    response = client.post("/query", json={"query": ""})
    payload = response.json()

    assert response.status_code == 422
    assert payload["status"] == "fail"
    assert payload["detail"][0]["loc"][:2] == ["body", "query"]
    assert payload["detail"][0]["reason"]


def test_api_ingest_rejects_unknown_source_type(tmp_path):
    response = client.post("/ingest", json={"path": str(tmp_path), "source_type": "unknown-source"})
    payload = response.json()

    assert response.status_code == 422
    assert payload["status"] == "fail"
    assert payload["detail"][0]["loc"][:2] == ["body", "source_type"]
