from __future__ import annotations

import copy

from scripts.retrieval_eval import load_targets, run_retrieval_eval


def test_phase4_retrieval_eval_reports_top_k_recall_and_expected_misses():
    report = run_retrieval_eval(targets=load_targets())

    assert report["schema_version"] == "phase4.retrieval_eval.report.v1"
    assert report["target_schema_version"] == "phase4.retrieval_targets.v1"
    assert report["case_count"] == 4
    assert report["evidence_case_count"] == 3
    assert report["expected_miss_case_count"] == 1
    assert report["required_top_k"] == [5, 10]
    assert report["scorecard"]["top_k_recall@5"] == 1.0
    assert report["scorecard"]["top_k_recall@10"] == 1.0
    assert report["replacement_gate"]["decision_top_k"] == 10
    assert report["replacement_gate"]["minimum_recall_at_decision_top_k"] == 0.8
    assert report["replacement_gate"]["missing_evidence_case_threshold"] == 1
    assert report["replacement_gate"]["replacement_justified_by_baseline"] is False
    assert report["missing_evidence_cases"] == []
    assert report["expected_miss_cases"] == ["rt_bearing_fault_out_of_fixture_scope"]
    assert report["unexpected_expected_miss_hits"] == ["rt_bearing_fault_out_of_fixture_scope"]


def test_phase4_retrieval_eval_diagnostics_explain_each_case():
    report = run_retrieval_eval(targets=load_targets())

    for case in report["cases"]:
        assert case["case_id"]
        assert case["query"]
        assert case["diagnostics"]["normalized_query"] is not None
        assert case["diagnostics"]["synthesis_evaluated"] is False
        assert case["diagnostics"]["top_hit_contributions"]
        assert isinstance(case["hit_chunk_ids"], list)
        if case["expected_evidence_count"]:
            assert case["failure_type"] == "retrieval_hit"
            assert case["recall_at_k"]["5"] is True
        else:
            assert case["failure_type"] in {"expected_miss", "unexpected_hit_for_expected_miss"}


def test_phase4_retrieval_eval_detects_missing_evidence_case():
    targets = {
        "schema_version": "phase4.retrieval_targets.v1",
        "default_required_top_k": [5, 10],
        "targets": [
            {
                "case_id": "rt_synthetic_missing_existing_chunk",
                "query": "thermal treatment hardness metallurgy unrelated query",
                "intent": "engineering",
                "required_top_k": [5, 10],
                "expected_evidence": [
                    {
                        "chunk_id": "expected_chunk",
                        "doc_id": "synthetic_doc",
                        "pages": [1],
                        "rationale": "Synthetic negative: expected chunk exists but decoy chunks should outrank it.",
                    }
                ],
            }
        ],
    }
    chunks = [
        {
            "chunk_id": "expected_chunk",
            "doc_id": "synthetic_doc",
            "source_type": "book",
            "pages": [1],
            "text": "Rotor critical speed and damping are discussed here.",
        },
        *[
            {
                "chunk_id": f"decoy_{index}",
                "doc_id": "synthetic_doc",
                "source_type": "book",
                "pages": [index + 2],
                "text": "thermal treatment hardness metallurgy unrelated query",
            }
            for index in range(10)
        ],
    ]

    report = run_retrieval_eval(targets=targets, chunks=chunks, chunks_dir=None)
    case = next(item for item in report["cases"] if item["case_id"] == "rt_synthetic_missing_existing_chunk")

    assert case["failure_type"] == "retrieval_miss"
    assert case["recall_at_k"]["10"] is False
    assert "rt_synthetic_missing_existing_chunk" in report["missing_evidence_cases"]
    assert report["replacement_gate"]["replacement_justified_by_baseline"] is True
