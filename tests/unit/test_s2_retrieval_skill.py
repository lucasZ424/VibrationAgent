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
from vibration_agent.knowledge.evidence import select_evidence_candidates
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


def test_query_normalize_expands_obj7_key_fact_alias_families():
    order = normalize("Why is equal-angle sampling used during start-up?")
    balancing = normalize("How is the influence vector calculated with a trial weight?")

    assert "angular_sampling" in order["detected_terms"]
    assert "variable_speed_operation" in order["detected_terms"]
    assert "角域采样" in order["normalized_query"]
    assert "run-up" in order["normalized_query"]
    assert "influence_vector" in balancing["detected_terms"]
    assert "trial_weight" in balancing["detected_terms"]
    assert "H=(T-O)/m" in balancing["normalized_query"]
    assert "校准配重" in balancing["normalized_query"]


def test_query_normalize_uses_curated_runtime_aliases_for_broad_obj7_terms():
    mechanism = normalize("Why do rotor vibration amplitude and phase change near critical speed?")
    gas_turbine = normalize("gas turbine torsional vibration")

    assert "complex_response_vector" not in mechanism["detected_terms"]
    assert "complex vector" not in mechanism["normalized_query"]
    assert "turbine_generator_unit" not in gas_turbine["detected_terms"]
    assert "透平发电机组" not in gas_turbine["normalized_query"]


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


def test_evidence_selector_recovers_same_doc_boundary_neighbors_without_cross_doc_leakage():
    # WHY: a retrieved boundary fragment may need its preceding definition and
    # following result, but a numerically adjacent chunk in another document is unrelated.
    seed = {**_chunk("seed", "当转子通过临界转速时", doc_id="d1"), "chunk_index": 2}
    previous = {**_chunk("previous", "临界转速对应转子共振状态", doc_id="d1"), "chunk_index": 1}
    following = {**_chunk("following", "则振幅达到最大并发生显著相位变化。", doc_id="d1"), "chunk_index": 3}
    other_doc = {**_chunk("other", "不相关标准条文。", doc_id="d2"), "chunk_index": 3}

    selected, report, warnings = select_evidence_candidates(
        [{"chunk": seed, "score": 1.0, "lanes": ["bm25", "dense"]}],
        [previous, seed, following, other_doc],
        seed_chunks=1,
        max_chunks=3,
        token_budget=100,
        adjacent_window=1,
    )

    assert [item["chunk"]["chunk_id"] for item in selected] == ["seed", "previous", "following"]
    assert selected[1]["selection_reason"] == "same_doc_adjacent_to:seed"
    assert "other" not in report["selected_chunk_ids"]
    assert warnings == []


def test_evidence_selector_deduplicates_and_enforces_hard_token_budget():
    # WHY: repeated OCR passages and oversized candidates must not silently expand S3 input.
    first = {**_chunk("first", "阻尼越大，振动衰减越快。"), "token_estimate": 20}
    duplicate = {**_chunk("duplicate", "阻尼越大，振动衰减越快。"), "token_estimate": 20}
    over_budget = {**_chunk("large", "临界转速响应。"), "token_estimate": 40}

    selected, report, warnings = select_evidence_candidates(
        [{"chunk": first}, {"chunk": duplicate}, {"chunk": over_budget}],
        [first, duplicate, over_budget],
        seed_chunks=3,
        max_chunks=3,
        token_budget=30,
        adjacent_window=0,
    )

    assert [item["chunk"]["chunk_id"] for item in selected] == ["first"]
    assert report["token_estimate"] == 20
    assert report["dropped_duplicate"] == 1
    assert report["dropped_budget"] == 1
    assert "30-token budget" in warnings[0]


def test_evidence_selector_without_verifiable_position_does_not_invent_neighbors():
    seed = _chunk("seed", "完整证据。")
    seed.pop("chunk_index")
    neighbor = {**_chunk("neighbor", "同文档但位置不可验证。"), "chunk_index": 2}

    selected, _, _ = select_evidence_candidates(
        [{"chunk": seed}], [seed, neighbor], seed_chunks=1, max_chunks=3, token_budget=100, adjacent_window=1
    )

    assert [item["chunk"]["chunk_id"] for item in selected] == ["seed"]


def test_evidence_selector_does_not_expand_a_complete_seed():
    # WHY: unconditional adjacency injects unrelated OCR passages and can game
    # keyword completeness while reducing answer usability.
    seed = {**_chunk("seed", "该段已经给出完整的测量结论。"), "chunk_index": 2}
    neighbors = [
        {**_chunk("previous", "上一页摘要。"), "chunk_index": 1},
        {**_chunk("following", "下一节无关内容。"), "chunk_index": 3},
    ]

    selected, _, _ = select_evidence_candidates(
        [{"chunk": seed}], [*neighbors, seed], seed_chunks=1, max_chunks=3, token_budget=100, adjacent_window=1
    )

    assert [item["chunk"]["chunk_id"] for item in selected] == ["seed"]


def test_obj5_selection_expands_s3_evidence_without_redefining_obj4_hits():
    # WHY: Obj5 quality gains must remain attributable to evidence hand-off, not
    # silently alter the frozen Obj4 retrieval scorecard.
    from vibration_agent.config import load

    settings = load()
    settings.retrieval.final_top_k = 1
    settings.retrieval.evidence_selection_enabled = True
    settings.retrieval.evidence_seed_chunks = 1
    settings.retrieval.evidence_max_chunks = 3
    settings.retrieval.evidence_token_budget = 100
    chunks = [
        {**_chunk("previous", "前置定义"), "chunk_index": 1},
        {**_chunk("seed", "当 boundaryterm 当前片段"), "chunk_index": 2},
        {**_chunk("following", "则后续工程结果。"), "chunk_index": 3},
    ]

    result = search("boundaryterm", chunks=chunks, settings=settings)

    assert [hit["chunk_id"] for hit in result["hits"]] == ["seed"]
    assert [row["chunk_id"] for row in result["retrieval_context"]] == ["seed"]
    assert [row["chunk_id"] for row in result["evidence_context"]] == ["seed", "previous", "following"]
    assert result["evidence_selection"]["selected_count"] == 3
    assert "intent:engineering" in result["evidence_context"][0]["selection_reason"]


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


def test_runtime_lexical_cache_reports_and_clears_payload_state(monkeypatch):
    from vibration_agent.config import load
    from vibration_agent.retrieval import hybrid

    settings = load()
    settings.database.qdrant_enabled = True
    settings.database.qdrant_collection = "test_chunks"
    client = object()
    hybrid.clear_runtime_retrieval_state()
    monkeypatch.setattr(hybrid.qdrant, "runtime_client", lambda _: client)
    monkeypatch.setattr(
        hybrid.qdrant,
        "load_chunk_payloads",
        lambda client, *, collection: [_chunk("c1", "critical speed")],
    )

    assert hybrid.load_runtime_chunks(settings)[0]["chunk_id"] == "c1"
    stats = hybrid.runtime_lexical_cache_stats()

    assert stats["entry_count"] == 1
    assert stats["chunk_count"] == 1
    assert stats["collections"] == ["test_chunks"]

    hybrid.clear_runtime_retrieval_state()

    assert hybrid.runtime_lexical_cache_stats()["entry_count"] == 0


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


def test_obj5_evidence_selector_is_default_off_with_explicit_env_candidate(monkeypatch):
    from vibration_agent.config import load

    assert load().retrieval.evidence_selection_enabled is False
    monkeypatch.setenv("EVIDENCE_SELECTION_ENABLED", "true")
    assert load().retrieval.evidence_selection_enabled is True


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


def test_retrieval_skill_citations_follow_selected_evidence_not_raw_hits():
    # WHY: adjacent evidence can support S3 claims even though it must not be
    # counted as a newly retrieved Obj4 hit.
    seed = _chunk("seed", "边界片段", pages=[2])
    neighbor = _chunk("neighbor", "完整结果。", pages=[3])

    def runner(*args, **kwargs):
        del args, kwargs
        return {
            "status": "ok",
            "hits": [{"chunk_id": "seed", "doc_id": "doc1", "pages": [2], "score": 1.0}],
            "retrieval_context": [{**seed, "score": 1.0}],
            "evidence_context": [{**seed, "score": 1.0}, {**neighbor, "score": 0.8}],
            "evidence_selection": {"selected_count": 2},
            "warnings": [],
        }

    output = RetrievalSkill(runner=runner).run(
        SkillInput(task_id="obj5", user_query="边界问题", context={"chunks": [seed, neighbor]})
    )

    assert output.structured_result["retrieval_output"]["hits"][0]["chunk_id"] == "seed"
    assert [citation.chunk_id for citation in output.citations] == ["seed", "neighbor"]
    assert output.structured_result["evidence_selection"] == {"selected_count": 2}
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
