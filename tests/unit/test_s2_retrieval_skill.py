import json
from pathlib import Path

from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.retrieval.hybrid import load_chunks, search
from vibration_agent.retrieval.query_normalize import normalize
from vibration_agent.retrieval.rerank import run as rerank_run
from vibration_agent.schemas import SkillInput
from vibration_agent.skills import RetrievalSkill
from vibration_agent.agent import AgentSkillRegistry


def _chunk(
    chunk_id: str,
    text: str,
    *,
    doc_id: str = "doc1",
    source_type: str = "book",
    pages: list[int] | None = None,
    topic: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "title": "Rotor Dynamics",
        "source_type": source_type,
        "chunk_index": 1,
        "page_start": (pages or [1])[0],
        "page_end": (pages or [1])[-1],
        "pages": pages or [1],
        "chunk_type": "body",
        "topic": topic,
        "token_estimate": 20,
        "char_count": len(text),
        "text": text,
        "api_context": f"[chunk_id={chunk_id}; doc_id={doc_id}; pages={(pages or [1])[0]}-{(pages or [1])[-1]}]\n{text}",
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


def test_agent_skill_registry_loads_s2_skill_package():
    registry = AgentSkillRegistry.load("agent_skills")

    skill = registry.get("s2_retrieval")
    assert skill.path.name == "SKILL.md"
    assert "RetrievalSkill" in skill.body
    assert skill.references
    assert skill.scripts


def test_query_normalize_detects_vibration_intent_terms_and_symbols():
    result = normalize("阻尼比是什么？zeta 如何用于转子响应？")

    assert result["intent_hint"] == "definition"
    assert "damping_ratio" in result["detected_terms"]
    assert "zeta" in result["detected_symbols"]
    assert "阻尼比" in result["normalized_query"]
    assert "damping ratio" in result["normalized_query"]


def test_tokenize_indexes_hyphenated_compounds_as_whole_and_parts():
    tokens = tokenize("rotor-bearing-system")

    assert "rotor-bearing-system" in tokens
    assert "rotor" in tokens
    assert "bearing" in tokens
    assert "system" in tokens


def test_hybrid_search_returns_retrieval_output_with_reasons():
    chunks = [
        _chunk("c1", "转子不平衡会产生明显的一倍频同步响应，幅值和相位随转速变化。", pages=[10], topic="rotor_unbalance"),
        _chunk("c2", "轴承故障通常需要包络谱和故障特征频率匹配。", pages=[20], topic="bearing_fault"),
    ]

    result = search("转子不平衡的一倍频响应", chunks=chunks, top_k=1)

    assert result["status"] == "ok"
    assert result["intent"] == "engineering"
    assert result["hits"][0]["chunk_id"] == "c1"
    assert result["hits"][0]["doc_id"] == "doc1"
    assert result["hits"][0]["source_type"] == "book"
    assert result["hits"][0]["pages"] == [10]
    assert result["hits"][0]["reason"]
    assert result["retrieval_context"][0]["text"].startswith("[chunk_id=c1")


def test_hybrid_search_returns_insufficient_when_recall_is_weak():
    result = search("完全无关的热处理材料问题", chunks=[_chunk("c1", "转子不平衡同步响应。")])

    assert result["status"] == "insufficient"
    assert result["hits"] == []
    assert "Weak recall" in result["warnings"][0]


def test_hybrid_search_returns_insufficient_for_empty_query():
    result = search("", chunks=[_chunk("c1", "转子不平衡同步响应。")])

    assert result["status"] == "insufficient"
    assert result["warnings"] == ["Empty query."]


def test_hybrid_search_uses_source_priority_as_tie_boost():
    chunks = [
        _chunk("web", "critical speed critical speed", source_type="webpage", pages=[1]),
        _chunk("std", "critical speed critical speed", source_type="standard", pages=[2]),
    ]

    result = search("critical speed", chunks=chunks, top_k=2)

    assert [hit["chunk_id"] for hit in result["hits"]] == ["std", "web"]


def test_load_chunks_dir_uses_only_chunk_jsonl_and_drops_rows_without_chunk_id(tmp_path):
    _write_jsonl(tmp_path / "pages.jsonl", [{"doc_id": "doc1", "page_no": 1, "normalized_text": "page text"}])
    _write_jsonl(tmp_path / "chunksomething.jsonl", [_chunk("wrong", "should not load")])
    _write_jsonl(tmp_path / "chunks.jsonl", [_chunk("c1", "critical speed"), {"doc_id": "doc1", "text": "no id"}])

    chunks = load_chunks(chunks_dir=tmp_path)

    assert [chunk["chunk_id"] for chunk in chunks] == ["c1"]


def test_load_chunks_dedupes_same_chunk_id_across_paths(tmp_path):
    first = _write_jsonl(tmp_path / "a" / "chunks.jsonl", [_chunk("same", "old text")])
    second = _write_jsonl(tmp_path / "b" / "chunks.jsonl", [_chunk("same", "new text")])

    chunks = load_chunks(chunk_paths=[first, second])

    assert len(chunks) == 1
    assert chunks[0]["text"] == "new text"


def test_rerank_pass_through_sorts_by_score():
    ranked = rerank_run("critical speed", [{"score": 0.1}, {"score": 0.3}], top_k=1)

    assert ranked == [{"score": 0.3}]


def test_retrieval_skill_reads_chunks_jsonl_and_returns_relative_citations(tmp_path):
    chunks_path = _write_jsonl(
        tmp_path / "chunks.jsonl",
        [
            _chunk("c1", "阻尼比 zeta 控制自由振动衰减速度。", pages=[3]),
            _chunk("c2", "轴承故障与包络分析有关。", pages=[4]),
        ],
    )
    payload = SkillInput(
        task_id="t1",
        user_query="阻尼比 zeta",
        constraints={"chunks_jsonl": str(chunks_path), "top_k": 1},
    )

    output = RetrievalSkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["task_id"] == "t1"
    assert output.structured_result["retrieval_output"]["hits"][0]["chunk_id"] == "c1"
    assert output.structured_result["retrieval_context"][0]["chunk_id"] == "c1"
    assert output.citations[0].chunk_id == "c1"
    assert output.citations[0].pages == [3]
    assert output.citations[0].confidence == 1.0


def test_retrieval_skill_accepts_s1_document_context(tmp_path):
    chunks_path = _write_jsonl(tmp_path / "chunks.jsonl", [_chunk("c1", "临界转速附近振幅会显著增大。")])
    payload = SkillInput(
        task_id="t1",
        user_query="临界转速",
        context={"documents": [{"outputs": {"chunks_jsonl": str(chunks_path)}}]},
    )

    output = RetrievalSkill().run(payload)

    assert output.status == "ok"
    assert output.structured_result["chunk_paths"] == [str(chunks_path)]


def test_retrieval_skill_supports_runner_injection(tmp_path):
    chunks_path = _write_jsonl(tmp_path / "chunks.jsonl", [_chunk("c1", "临界转速")])
    calls = []

    def runner(query, **kwargs):
        calls.append((query, kwargs))
        return {
            "normalized_query": query,
            "intent": "engineering",
            "hits": [],
            "status": "insufficient",
            "warnings": ["mock weak recall"],
            "retrieval_context": [],
        }

    payload = SkillInput(task_id="t1", user_query="临界转速", constraints={"chunks_jsonl": str(chunks_path)})
    output = RetrievalSkill(runner=runner).run(payload)

    assert output.status == "insufficient"
    assert calls[0][0] == "临界转速"
    assert calls[0][1]["chunk_paths"] == [chunks_path]


def test_retrieval_skill_top_k_zero_is_not_replaced_by_default(tmp_path):
    chunks_path = _write_jsonl(tmp_path / "chunks.jsonl", [_chunk("c1", "临界转速")])
    payload = SkillInput(task_id="t1", user_query="临界转速", constraints={"chunks_jsonl": str(chunks_path), "top_k": 0})

    output = RetrievalSkill().run(payload)

    assert output.status == "insufficient"
    assert output.structured_result["retrieval_output"]["warnings"] == ["top_k must be greater than 0 for retrieval hits."]


def test_retrieval_skill_missing_chunk_path_is_insufficient(tmp_path):
    missing = tmp_path / "missing.jsonl"
    payload = SkillInput(task_id="t1", user_query="临界转速", constraints={"chunks_jsonl": str(missing)})

    output = RetrievalSkill().run(payload)

    assert output.status == "insufficient"
    assert output.structured_result["task_id"] == "t1"
    assert str(missing) in output.structured_result["missing_paths"]
    assert "Missing chunks_jsonl" in output.warnings[0]


def test_retrieval_skill_requires_corpus():
    output = RetrievalSkill().run(SkillInput(task_id="t1", user_query="临界转速"))

    assert output.status == "insufficient"
    assert output.structured_result["task_id"] == "t1"
    assert "No chunk corpus" in output.warnings[0]
