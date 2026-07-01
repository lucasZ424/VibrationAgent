import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ann_retrieval_eval import run_ann_eval
from vibration_agent.config import load
from vibration_agent.schemas import EmbeddingRecord


def _settings():
    settings = load()
    settings.embeddings.enabled = True
    settings.embeddings.model_name = "test-multilingual"
    settings.embeddings.model_version = "v1"
    settings.database.qdrant_enabled = True
    settings.database.qdrant_vector_size = 2
    settings.database.qdrant_collection = "test_chunks"
    return settings


def _questions():
    cases = []
    for index, (intent, language) in enumerate(
        (("definition", "zh"), ("definition", "en"), ("workflow", "zh"), ("workflow", "en"))
    ):
        cases.append(
            {
                "case_id": f"case_{index}",
                "intent": intent,
                "language": language,
                "query": f"query {index}",
                "expected_evidence": [
                    {"evidence_id": f"e{index}", "chunk_id": f"c{index}", "doc_id": f"d{index}", "pages": [1]}
                ],
            }
        )
    return {
        "baseline_id": "test-baseline",
        "corpus": {"embedding_model": "test-multilingual", "embedding_dimension": 2},
        "cases": cases,
    }


def _embedder(texts, **_kwargs):
    index = int(texts[0].rsplit(" ", 1)[-1])
    return [
        EmbeddingRecord(
            text_hash=str(index),
            vector=[float(index), 1.0],
            dimension=2,
            model_name="test-multilingual",
            model_version="v1",
            provider="sentence_transformers",
        )
    ]


def test_ann_eval_isolated_lane_reports_language_pair_recall_and_latency():
    ticks = iter(value / 1000 for value in (0, 30, 30, 40, 40, 50, 50, 60))

    def searcher(vector, top_k):
        index = int(vector[0])
        return [{"chunk": {"chunk_id": f"c{index}", "doc_id": f"d{index}", "pages": [1]}, "score": 0.9}]

    report = run_ann_eval(
        questions=_questions(),
        post_r3_hybrid_recall_at_10=0.571,
        settings=_settings(),
        searcher=searcher,
        embedder=_embedder,
        clock=lambda: next(ticks),
    )

    assert report["lane"] == "ann_qdrant_only"
    assert report["fallback_allowed"] is False
    assert report["scorecard"]["recall_at_10"] == 1.0
    assert report["scorecard"]["recall_at_10_by_language"] == {"en": 1.0, "zh": 1.0}
    assert report["scorecard"]["cross_lingual_pair_recall_at_10"] == 1.0
    assert report["latency_ms"] == {"cold_start": 30.0, "steady_p50": 10.0, "steady_p95": 10.0}
    assert report["schema_version"] == "phase5.obj3_ann_eval.report.v2"
    assert report["reference"]["direct_comparison_valid"] is False
    assert report["acceptance"] == {
        "ann_baseline_recorded": True,
        "integrity_checks_passed": True,
    }


def test_ann_eval_accepts_same_document_page_overlap():
    questions = _questions()
    case = questions["cases"][0]
    case["expected_evidence"][0]["chunk_id"] = "neighbor"

    report = run_ann_eval(
        questions={**questions, "cases": [case]},
        post_r3_hybrid_recall_at_10=1.0,
        settings=_settings(),
        searcher=lambda _vector, _top_k: [
            {"chunk": {"chunk_id": "c0", "doc_id": "d0", "pages": [1]}, "score": 0.8}
        ],
        embedder=_embedder,
        clock=iter((0.0, 0.01)).__next__,
    )

    assert report["cases"][0]["matched_evidence_at_10"] == ["e0"]


def test_ann_eval_fails_loud_on_embedding_fallback():
    def fallback(texts, **_kwargs):
        return [EmbeddingRecord(text_hash=texts[0], provider="fallback_token_features")]

    with pytest.raises(RuntimeError, match="forbids token-feature"):
        run_ann_eval(
            questions={**_questions(), "cases": [_questions()["cases"][0]]},
            post_r3_hybrid_recall_at_10=0.571,
            settings=_settings(),
            searcher=lambda _vector, _top_k: [],
            embedder=fallback,
        )


def test_ann_eval_fails_loud_on_query_model_drift():
    def wrong_model(texts, **_kwargs):
        record = _embedder(texts)[0]
        return [record.model_copy(update={"model_name": "wrong-model"})]

    with pytest.raises(RuntimeError, match="provenance"):
        run_ann_eval(
            questions={**_questions(), "cases": [_questions()["cases"][0]]},
            post_r3_hybrid_recall_at_10=0.571,
            settings=_settings(),
            searcher=lambda _vector, _top_k: [],
            embedder=wrong_model,
        )


def test_ann_eval_cli_help_runs_without_project_pythonpath():
    result = subprocess.run(
        [sys.executable, "scripts/ann_retrieval_eval.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--baseline" in result.stdout


def test_obj3_committed_ann_baseline_records_operator_provenance():
    path = Path("tests/fixtures/eval/retrieval/obj3_ann_baseline.json")
    baseline = json.loads(path.read_text(encoding="utf-8"))

    assert baseline["schema_version"] == "phase5.obj3_ann_baseline.v1"
    assert baseline["corpus"]["parity"] is True
    assert baseline["corpus"]["embeddable_chunks"] == baseline["corpus"]["qdrant_points"] == 4436
    assert baseline["corpus"]["provenance_mismatch_count"] == 0
    assert baseline["ann_scorecard"]["recall_at_10"] == 0.5
    assert baseline["interpretation"]["direct_comparison_valid"] is False
    assert baseline["interpretation"]["obj4_ann_recall_floor"] == 0.5
    assert baseline["interpretation"]["post_reindex_hybrid_recall_at_10"] == 0.571
    assert baseline["interpretation"]["hybrid_no_regression"] is True
