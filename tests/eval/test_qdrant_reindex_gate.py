from __future__ import annotations

from scripts.qdrant_reindex_gate import evaluate_reindex_gate
from scripts.retrieval_eval import load_targets, run_retrieval_eval
from vibration_agent.config import load


def test_obj4_qdrant_reindex_gate_records_non_replacement_for_current_baseline():
    report = run_retrieval_eval(targets=load_targets())
    settings = load()

    gate = evaluate_reindex_gate(retrieval_report=report, settings=settings)

    assert gate["schema_version"] == "phase4.obj4_qdrant_reindex_gate.v1"
    assert gate["decision"] == "non_replacement"
    assert gate["replacement"]["allowed"] is False
    assert gate["reindex"]["allowed"] is False
    assert gate["reindex"]["executed"] is False
    assert gate["runtime_settings"]["embedding_enabled"] is False
    assert gate["runtime_settings"]["qdrant_enabled"] is False
    assert gate["retrieval_scorecard"]["top_k_recall@10"] == 1.0
    assert gate["missing_evidence_cases"] == []
    assert gate["attribution_summary"]["top_hit_contribution_counts"]["hybrid"] >= 1
