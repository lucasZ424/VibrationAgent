import json
from pathlib import Path

from vibration_agent.retrieval.bm25 import search as bm25_search
from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.retrieval.hybrid import load_chunks, search
from vibration_agent.retrieval.query_normalize import (
    focus_aliases,
    is_corpus_standard_query,
    normalize,
    standard_identifiers_from_sources,
)
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
    source_filename: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "title": "Rotor Dynamics",
        "source_filename": source_filename,
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


def test_query_normalize_bridges_real_corpus_turbine_and_order_analysis_terms():
    turbine = normalize("汽轮发电机组轴系扭振的适用范围")
    order = normalize("旋转机械阶比分析有什么作用")

    assert "透平" in turbine["normalized_query"]
    assert "轴系" in turbine["normalized_query"]
    assert "torsional vibration" in turbine["normalized_query"]
    assert "order analysis" in order["normalized_query"]


def test_query_normalize_does_not_expand_gas_turbine_to_steam_turbine():
    # WHY: the generic English word "turbine" must not turn a gas-turbine query into 汽轮机 evidence.
    result = normalize("gas turbine torsional vibration")

    assert "汽轮机" not in result["normalized_query"]


def test_corpus_standard_catalog_uses_document_identity_not_body_references():
    # WHY: a standard merely cited in a document is not itself retrievable as an
    # in-corpus standard and must not widen the pre-retrieval scope boundary.
    rows = [
        {
            "source_title": "GB∕T 33199.1-2016 机械振动（ISO 10816）",
            "text": "Normative reference: GB/T 19001 quality management.",
        }
    ]

    assert standard_identifiers_from_sources(rows) == ("GB/T 33199", "ISO 10816")
    assert is_corpus_standard_query("GB/T 11348.4 的适用范围是什么？") is True
    assert is_corpus_standard_query("GB/T 19001 quality management requirements") is False


def test_query_focus_aliases_choose_the_longest_detected_domain_phrase():
    aliases = focus_aliases("阶比分析在旋转机械扭振测量中的作用是什么？")

    assert "阶比分析" in aliases
    assert "扭振" not in aliases


def test_query_normalize_prioritizes_standard_scope_over_generic_definition():
    result = normalize("GB/T 33199.1-2016 的适用范围是什么？")

    assert result["intent_hint"] == "standard_lookup"


def test_tokenize_indexes_hyphenated_compounds_as_whole_and_parts():
    tokens = tokenize("rotor-bearing-system")

    assert "rotor-bearing-system" in tokens
    assert "rotor" in tokens
    assert "bearing" in tokens
    assert "system" in tokens


def test_tokenize_cjk_avoids_single_character_noise_for_engineering_queries():
    # WHY: broad single-character matches such as 旋/转/机/械 can outrank the
    # actual engineering phrase and make real-corpus answers cite irrelevant chunks.
    tokens = tokenize("旋转机械临界转速")

    assert "旋" not in tokens
    assert "转" not in tokens
    assert "旋转" in tokens
    assert "临界转速" in tokens


def test_query_normalize_expands_critical_speed_outcome_questions():
    # WHY: "what happens after reaching critical speed" needs response/outcome
    # evidence, not only definition chunks containing the phrase.
    result = normalize("旋转机械到达临界转速后会发生什么？")

    assert "critical speed" in result["normalized_query"]
    assert "共振" in result["normalized_query"]
    assert "响应放大" in result["normalized_query"]


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
    assert result["retrieval_context"][0]["retrieval_contribution"] == "hybrid"
    assert set(result["retrieval_context"][0]["retrieval_lanes"]) == {"bm25", "dense"}
    assert set(result["retrieval_context"][0]["lane_scores"]) == {"bm25", "dense"}
    assert set(result["retrieval_context"][0]["lane_contributions"]) == {"bm25", "dense"}
    assert result["lanes"]["lexical"]["hits"][0]["rank"] == 1
    assert result["lanes"]["lexical"]["hits"][0]["normalized_score"] == 1.0


def test_hybrid_search_propagates_source_filename_to_context():
    chunks = [_chunk("c1", "Critical speed amplifies rotor response.", source_filename="rotor-handbook.pdf")]

    result = search("critical speed", chunks=chunks, top_k=1)

    assert result["retrieval_context"][0]["source_filename"] == "rotor-handbook.pdf"
    assert result["retrieval_context"][0]["source_title"] == "Rotor Dynamics"


def test_hybrid_search_returns_insufficient_when_recall_is_weak():
    result = search("完全无关的热处理材料问题", chunks=[_chunk("c1", "转子不平衡同步响应。")])

    assert result["status"] == "insufficient"
    assert result["hits"] == []
    assert "Weak recall" in result["warnings"][0]


def test_hybrid_search_returns_insufficient_for_empty_query():
    result = search("", chunks=[_chunk("c1", "转子不平衡同步响应。")])

    assert result["status"] == "insufficient"
    assert result["warnings"] == ["Empty query."]


def test_hybrid_search_uses_runtime_qdrant_corpus_when_no_file_chunks(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid

    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = "test_chunks"
    settings.embeddings.enabled = False
    monkeypatch.setattr(hybrid.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        hybrid.qdrant,
        "load_chunk_payloads",
        lambda client, *, collection: [_chunk("c1", "critical speed amplifies rotor vibration response")],
    )

    result = search("critical speed", top_k=1, settings=settings)

    assert result["status"] == "ok"
    assert result["retrieval_source"] == "runtime_qdrant_payloads"
    assert result["hits"][0]["chunk_id"] == "c1"


def test_runtime_lexical_lane_is_not_limited_to_ann_candidates(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid
    from vibration_agent.schemas import EmbeddingRecord

    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = "test_chunks"
    settings.embeddings.enabled = True
    settings.retrieval.independent_lanes_enabled = True
    client = object()
    hybrid.clear_runtime_lexical_cache()
    monkeypatch.setattr(hybrid.qdrant, "runtime_client", lambda _: client)
    monkeypatch.setattr(
        hybrid,
        "embed_texts",
        lambda texts, *, settings: [
            EmbeddingRecord(
                text_hash="query",
                vector=[1.0, 0.0],
                dimension=2,
                model_name="same-as-index",
                provider="sentence_transformers",
            )
        ],
    )
    monkeypatch.setattr(
        hybrid.qdrant,
        "search_chunks",
        lambda client, vector, *, top_k, collection: [
            {"chunk": _chunk("c1", "semantic-only candidate"), "score": 0.8, "lane": "dense_qdrant"}
        ],
    )
    monkeypatch.setattr(
        hybrid.qdrant,
        "load_chunk_payloads",
        lambda client, *, collection: [
            _chunk("c1", "semantic-only candidate"),
            _chunk("c2", "critical speed definition and operating limit"),
        ],
    )

    result = search("critical speed", top_k=2, settings=settings)

    assert result["status"] == "ok"
    assert result["retrieval_source"] == "runtime_qdrant_independent_lanes"
    by_id = {item["chunk_id"]: item for item in result["retrieval_context"]}
    assert by_id["c1"]["retrieval_lanes"] == ["dense"]
    assert by_id["c2"]["retrieval_lanes"] == ["bm25"]
    assert result["lanes"]["lexical"]["hits"][0]["chunk_id"] == "c2"
    assert result["lanes"]["ann"]["hits"][0]["chunk_id"] == "c1"


def test_independent_runtime_candidate_can_be_explicitly_disabled(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid
    from vibration_agent.schemas import EmbeddingRecord

    settings = load()
    settings.database.qdrant_enabled = True
    settings.embeddings.enabled = True
    settings.retrieval.independent_lanes_enabled = False
    assert settings.retrieval.independent_lanes_enabled is False
    monkeypatch.setattr(hybrid.qdrant, "runtime_client", lambda _: object())
    monkeypatch.setattr(
        hybrid,
        "embed_texts",
        lambda texts, *, settings: [
            EmbeddingRecord(text_hash="q", vector=[1.0, 0.0], dimension=2, provider="sentence_transformers")
        ],
    )
    monkeypatch.setattr(
        hybrid.qdrant,
        "search_chunks",
        lambda *args, **kwargs: [{"chunk": _chunk("ann", "critical speed"), "score": 0.8}],
    )
    monkeypatch.setattr(
        hybrid.qdrant,
        "load_chunk_payloads",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("default path must not scroll payloads")),
    )

    result = search("critical speed", settings=settings)

    assert result["retrieval_source"] == "runtime_qdrant_ann"
    assert [hit["chunk_id"] for hit in result["hits"]] == ["ann"]


def test_independent_runtime_lanes_are_promoted_with_env_rollback(monkeypatch):
    from vibration_agent.config import load

    assert load().retrieval.independent_lanes_enabled is True
    monkeypatch.setenv("RETRIEVAL_INDEPENDENT_LANES_ENABLED", "false")
    assert load().retrieval.independent_lanes_enabled is False


def test_bm25_indexes_qdrant_source_title_for_standard_lookup():
    chunks = [
        {
            **_chunk("standard", "scope and methods"),
            "source_title": "GB/T 33199.1 rotating machinery torsional vibration",
        },
        _chunk("other", "scope and methods"),
    ]

    results = bm25_search("GB/T 33199.1", chunks=chunks, top_k=2)

    assert results[0]["chunk"]["chunk_id"] == "standard"


def test_standard_lookup_candidate_uses_lexical_weight_without_changing_other_intents(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid

    target = _chunk("target", "scope and specified method")
    distractors = [_chunk(f"dense-{index}", f"semantic result {index}") for index in range(10)]
    settings = load()
    settings.retrieval.mode = "hybrid"
    monkeypatch.setattr(hybrid.bm25, "search", lambda *args, **kwargs: [{"chunk": target, "score": 1.0}])
    monkeypatch.setattr(
        hybrid.dense,
        "search",
        lambda *args, **kwargs: [
            {"chunk": chunk, "score": 1.0 - index * 0.01}
            for index, chunk in enumerate(distractors)
        ],
    )

    result = search("What is covered by GB/T 33199.1?", chunks=[target, *distractors], settings=settings)

    assert result["fusion_method"] == "standard_lookup_weighted"
    assert result["hits"][0]["chunk_id"] == "target"
    assert result["retrieval_context"][0]["lane_contributions"]["bm25"] == 0.9


def test_retrieval_modes_report_only_enabled_lanes(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid

    chunks = [_chunk("c1", "critical speed resonance")]
    settings = load()
    settings.retrieval.mode = "bm25"

    lexical = search("critical speed", chunks=chunks, settings=settings)

    assert lexical["lanes"]["lexical"]["enabled"] is True
    assert lexical["lanes"]["ann"]["enabled"] is False
    assert lexical["retrieval_context"][0]["retrieval_lanes"] == ["bm25"]

    settings.retrieval.mode = "dense"
    monkeypatch.setattr(
        hybrid.dense,
        "search",
        lambda *args, **kwargs: [{"chunk": chunks[0], "score": 0.9, "lane": "dense_embedding"}],
    )
    ann = search("critical speed", chunks=chunks, settings=settings)

    assert ann["lanes"]["lexical"]["enabled"] is False
    assert ann["lanes"]["ann"]["enabled"] is True
    assert ann["retrieval_context"][0]["retrieval_lanes"] == ["dense"]


def test_query_normalize_reports_versioned_alias_taxonomy():
    result = normalize("order analysis for variable speed")

    assert result["alias_schema_version"] == "phase5.retrieval_aliases.v1"
    assert "阶比分析" in result["normalized_query"]


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


def test_retrieval_skill_citations_use_readable_source_metadata(tmp_path):
    chunks_path = _write_jsonl(
        tmp_path / "chunks.jsonl",
        [_chunk("c1", "Critical speed amplifies rotor response.", source_filename="rotor-handbook.pdf")],
    )
    payload = SkillInput(task_id="t1", user_query="critical speed", constraints={"chunks_jsonl": str(chunks_path)})

    output = RetrievalSkill().run(payload)

    assert output.citations[0].source_filename == "rotor-handbook.pdf"
    assert output.citations[0].source_title == "Rotor Dynamics"



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
    from vibration_agent.config import load

    settings = load()
    settings.database.qdrant_enabled = False
    output = RetrievalSkill(settings=settings).run(SkillInput(task_id="t1", user_query="临界转速"))

    assert output.status == "insufficient"
    assert output.structured_result["task_id"] == "t1"
    assert "No chunk corpus" in output.warnings[0]
