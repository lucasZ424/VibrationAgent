import json
from pathlib import Path

import apps.cli.main as cli_main


def main(argv):
    return cli_main.main(argv)


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


def _stdout_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_cli_scope_returns_phase0_registry_and_workspace(capsys):
    code = main(["scope"])
    payload = _stdout_json(capsys)

    assert code == 0
    assert payload["workspace"]
    assert "s2_retrieval" in payload["phase0_pipeline"]
    assert "v4_style" in payload["active_skills"]


def test_cli_config_honors_compact_json_and_workspace(capsys):
    code = main(["--compact-json", "config"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert code == 0
    assert "\n" not in output.strip()
    assert payload["workspace"]
    assert "paths" in payload


def test_cli_ask_runs_tutor_chain_with_chunks_jsonl(tmp_path, capsys):
    chunks_path = _write_jsonl(
        tmp_path / "chunks.jsonl",
        [_chunk("c1", "阻尼比 zeta 控制自由振动衰减速度。阻尼越大，振动衰减越快。", pages=[3])],
    )

    code = main(["ask", "阻尼比如何影响转子振动？", "--chunks-jsonl", str(chunks_path), "--top-k", "1"])
    payload = _stdout_json(capsys)

    assert code == 0
    assert payload["workspace"]
    assert payload["status"] == "ok"
    assert payload["structured_result"]["scope"] == "in_scope"
    assert [step["skill"] for step in payload["structured_result"]["chain"]] == [
        "s2_retrieval",
        "s3_qa_summary",
        "v4_style",
    ]
    assert "## 结论" in payload["structured_result"]["answer"]
    assert payload["citations"][0]["chunk_id"] == "c1"


def test_cli_ask_accepts_multiple_chunks_jsonl_paths(tmp_path, capsys):
    first = _write_jsonl(tmp_path / "a" / "chunks.jsonl", [_chunk("c1", "轴承故障与包络谱有关。", pages=[1])])
    second = _write_jsonl(tmp_path / "b" / "chunks.jsonl", [_chunk("c2", "阻尼比 zeta 控制自由振动衰减速度。", pages=[2])])

    code = main([
        "ask",
        "阻尼比如何影响转子振动？",
        "--chunks-jsonl",
        str(first),
        "--chunks-jsonl",
        str(second),
        "--top-k",
        "1",
    ])
    payload = _stdout_json(capsys)

    assert code == 0
    assert payload["citations"][0]["chunk_id"] == "c2"
    assert len(payload["structured_result"]["skill_results"]["s2"]["chunk_paths"]) == 2


def test_cli_ask_accepts_chunks_dir(tmp_path, capsys):
    _write_jsonl(
        tmp_path / "book" / "doc1" / "chunks.jsonl",
        [_chunk("c1", "临界转速附近转子振动响应会被放大。", pages=[4])],
    )

    code = main(["ask", "临界转速下转子振动如何变化？", "--chunks-dir", str(tmp_path), "--top-k", "1"])
    payload = _stdout_json(capsys)

    assert code == 0
    assert payload["citations"][0]["chunk_id"] == "c1"
    assert payload["structured_result"]["skill_results"]["s2"]["chunks_dir"] == str(tmp_path)


def test_cli_ask_returns_insufficient_exit_code_for_out_of_scope(capsys):
    code = main(["ask", "请解释股票估值"])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["workspace"]
    assert payload["status"] == "insufficient"
    assert payload["structured_result"]["scope"] == "out_of_scope"


def test_cli_ask_returns_insufficient_exit_code_without_chunk_corpus(capsys):
    code = main(["ask", "临界转速下转子振动如何变化？"])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["status"] == "insufficient"
    assert payload["structured_result"]["chain"][0]["skill"] == "s2_retrieval"


def test_cli_returns_fail_json_on_handler_exception(tmp_path, capsys, monkeypatch):
    def boom(*args, **kwargs):
        raise PermissionError("blocked")

    monkeypatch.setattr(cli_main, "chunk_documents", boom)

    code = main(["ingest", str(tmp_path)])
    payload = _stdout_json(capsys)

    assert code == 1
    assert payload["status"] == "fail"
    assert payload["command"] == "ingest"
    assert payload["workspace"]
    assert payload["error_type"] == "PermissionError"
    assert payload["error"] == "blocked"


def test_cli_parse_pages_returns_workspace_for_empty_dir(tmp_path, capsys):
    code = main(["parse-pages", str(tmp_path)])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["workspace"]
    assert payload["status"] == "insufficient"
    assert payload["stage"] == "page_parse_batch"


def test_cli_ingest_plan_only_returns_insufficient_for_empty_dir(tmp_path, capsys):
    code = main(["ingest", str(tmp_path), "--plan-only"])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["workspace"]
    assert payload["status"] == "insufficient"
    assert payload["stage"] == "input_classification"