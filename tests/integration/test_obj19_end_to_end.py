import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import apps.api.main as api_main
import apps.cli.main as cli_main
from scripts.ingest_folder import main as legacy_ingest_main

pytest.importorskip("fitz")
pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PDF_FIXTURE = FIXTURES / "raw" / "small_vibration_native.pdf"
ZH_PDF_FIXTURE = FIXTURES / "raw" / "small_vibration_zh.pdf"
REAL_QUESTION = "What happens near critical speed in rotor vibration?"
GAP_QUESTION = "Pump oil API 610"
OUT_OF_SCOPE_QUESTION = "Explain stock valuation methods."
ZH_REAL_QUESTION = "阻尼比如何影响转子振动？"
ZH_GAP_QUESTION = "齿轮箱润滑油牌号要求？"
ZH_OUT_OF_SCOPE_QUESTION = "写一段市场营销文案。"


def _stdout_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def _project_workspace(path: Path) -> Path:
    (path / "configs").mkdir(parents=True, exist_ok=True)
    (path / "src" / "vibration_agent").mkdir(parents=True, exist_ok=True)
    return path


def _cli_ingest_fixture(workspace: Path, capsys, pdf: Path = PDF_FIXTURE, *, max_pages: str = "1") -> tuple[dict, Path]:
    code = cli_main.main([
        "--workspace",
        str(workspace),
        "ingest",
        str(pdf),
        "--max-pages",
        max_pages,
    ])
    payload = _stdout_json(capsys)
    assert code == 0
    assert payload["status"] == "ok"
    document = payload["documents"][0]
    chunks_jsonl = Path(document["outputs"]["chunks_jsonl"])
    assert chunks_jsonl.exists()
    assert Path(document["outputs"]["manifest_json"]).exists()
    assert Path(document["outputs"]["api_context_json"]).exists()
    return payload, chunks_jsonl


def test_cli_end_to_end_real_gap_and_out_of_scope(tmp_path, capsys):
    workspace = _project_workspace(tmp_path / "workspace")
    ingest_payload, chunks_jsonl = _cli_ingest_fixture(workspace, capsys)

    ok_code = cli_main.main([
        "--workspace",
        str(tmp_path),
        "ask",
        REAL_QUESTION,
        "--chunks-jsonl",
        str(chunks_jsonl),
        "--top-k",
        "2",
    ])
    ok_payload = _stdout_json(capsys)
    assert ok_code == 0
    assert ok_payload["status"] == "ok"
    assert ok_payload["structured_result"]["scope"] == "in_scope"
    assert [step["skill"] for step in ok_payload["structured_result"]["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "s4_engineering_analysis",
        "v2_citation_check",
        "v4_style",
    ]
    assert ok_payload["citations"]
    assert ok_payload["citations"][0]["pages"] == [1]
    assert "## Conclusion" in ok_payload["structured_result"]["answer"]
    assert "critical speed" in ok_payload["structured_result"]["answer"].lower()

    gap_code = cli_main.main([
        "--workspace",
        str(tmp_path),
        "ask",
        GAP_QUESTION,
        "--chunks-jsonl",
        str(chunks_jsonl),
        "--top-k",
        "2",
        "--scope",
        "in_scope",
    ])
    gap_payload = _stdout_json(capsys)
    assert gap_code == 2
    assert gap_payload["status"] == "insufficient"
    assert gap_payload["structured_result"]["scope"] == "in_scope"
    assert gap_payload["structured_result"]["chain"][0]["skill"] == "s2_retrieval"

    out_code = cli_main.main(["--workspace", str(workspace), "ask", OUT_OF_SCOPE_QUESTION])
    out_payload = _stdout_json(capsys)
    assert out_code == 2
    assert out_payload["status"] == "insufficient"
    assert out_payload["structured_result"]["scope"] == "out_of_scope"

    manifest = json.loads(Path(ingest_payload["documents"][0]["outputs"]["manifest_json"]).read_text(encoding="utf-8"))
    assert manifest["outputs"]["chunks_jsonl"] == str(chunks_jsonl)
    assert manifest["counts"]["chunk_count"] >= 1


def test_cli_zh_end_to_end_real_gap_and_out_of_scope(tmp_path, capsys):
    workspace = _project_workspace(tmp_path / "workspace")
    _ingest_payload, chunks_jsonl = _cli_ingest_fixture(workspace, capsys, ZH_PDF_FIXTURE, max_pages="2")

    ok_code = cli_main.main([
        "--workspace",
        str(tmp_path),
        "ask",
        ZH_REAL_QUESTION,
        "--chunks-jsonl",
        str(chunks_jsonl),
        "--top-k",
        "2",
    ])
    ok_payload = _stdout_json(capsys)
    assert ok_code == 0
    assert ok_payload["status"] == "ok"
    assert ok_payload["structured_result"]["scope"] == "in_scope"
    assert ok_payload["structured_result"]["v4"]["language"] == "zh"
    assert ok_payload["citations"][0]["pages"] == [1, 2]
    assert "## 结论" in ok_payload["structured_result"]["answer"]
    assert "## 证据" in ok_payload["structured_result"]["answer"]

    gap_code = cli_main.main([
        "--workspace",
        str(tmp_path),
        "ask",
        ZH_GAP_QUESTION,
        "--chunks-jsonl",
        str(chunks_jsonl),
        "--top-k",
        "2",
        "--scope",
        "in_scope",
    ])
    gap_payload = _stdout_json(capsys)
    assert gap_code == 2
    assert gap_payload["status"] == "insufficient"
    assert gap_payload["structured_result"]["scope"] == "in_scope"

    out_code = cli_main.main(["--workspace", str(workspace), "ask", ZH_OUT_OF_SCOPE_QUESTION])
    out_payload = _stdout_json(capsys)
    assert out_code == 2
    assert out_payload["status"] == "insufficient"
    assert out_payload["structured_result"]["scope"] == "out_of_scope"


def test_api_end_to_end_ingest_and_query(tmp_path):
    workspace = _project_workspace(tmp_path / "workspace")
    workspace_fixture = workspace / PDF_FIXTURE.name
    shutil.copy2(PDF_FIXTURE, workspace_fixture)
    api_main.get_settings.cache_clear()
    api_main.get_orchestrator.cache_clear()
    client = TestClient(api_main.app)

    ingest_response = client.post(
        "/ingest",
        json={"workspace": str(workspace), "path": str(workspace_fixture), "max_pages": 1},
    )
    ingest_payload = ingest_response.json()
    assert ingest_response.status_code == 200
    assert ingest_payload["status"] == "ok"
    chunks_jsonl = Path(ingest_payload["result"]["documents"][0]["outputs"]["chunks_jsonl"])
    assert chunks_jsonl.exists()

    ok_response = client.post(
        "/query",
        json={
            "workspace": str(workspace),
            "query": REAL_QUESTION,
            "chunks_jsonl": [str(chunks_jsonl)],
            "top_k": 2,
        },
    )
    ok_payload = ok_response.json()
    assert ok_response.status_code == 200
    assert ok_payload["status"] == "ok"
    assert ok_payload["output"]["citations"][0]["pages"] == [1]
    assert "## Conclusion" in ok_payload["output"]["structured_result"]["answer"]

    gap_response = client.post(
        "/query",
        json={
            "workspace": str(workspace),
            "query": GAP_QUESTION,
            "chunks_jsonl": [str(chunks_jsonl)],
            "top_k": 2,
            "scope": "in_scope",
        },
    )
    gap_payload = gap_response.json()
    assert gap_response.status_code == 200
    assert gap_payload["status"] == "insufficient"
    assert gap_payload["output"]["structured_result"]["scope"] == "in_scope"

    out_response = client.post(
        "/query",
        json={"workspace": str(workspace), "query": OUT_OF_SCOPE_QUESTION},
    )
    out_payload = out_response.json()
    assert out_response.status_code == 200
    assert out_payload["status"] == "insufficient"
    assert out_payload["output"]["structured_result"]["scope"] == "out_of_scope"


def test_legacy_ingest_folder_end_to_end_exports_chunks(tmp_path, capsys):
    code = legacy_ingest_main([
        "--workspace",
        str(_project_workspace(tmp_path / "workspace")),
        "--src",
        str(PDF_FIXTURE),
        "--chunk-documents",
        "--max-pages",
        "1",
    ])
    payload = _stdout_json(capsys)

    assert code == 0
    assert payload["workspace"].endswith("workspace")
    assert payload["status"] == "ok"
    assert payload["stage"] == "document_structured_export_batch"
    chunks_jsonl = Path(payload["documents"][0]["outputs"]["chunks_jsonl"])
    manifest_json = Path(payload["documents"][0]["outputs"]["manifest_json"])
    assert chunks_jsonl.exists()
    assert manifest_json.exists()
