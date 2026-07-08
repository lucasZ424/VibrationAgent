from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from scripts.rag_qa_eval import load_questions, run_rag_qa_eval
from vibration_agent.schemas import Citation, SkillOutput

ROOT = Path(__file__).resolve().parents[2]


def _passing_output(case: Mapping[str, Any]) -> SkillOutput:
    hits = [
        {
            "chunk_id": evidence["chunk_id"],
            "doc_id": evidence["doc_id"],
            "pages": evidence["pages"],
            "score": 1.0,
        }
        for evidence in case["expected_evidence"]
    ]
    answer = "。".join(str(fact["aliases"][0]) for fact in case["key_facts"]) + "。"
    return SkillOutput(
        status="ok",
        summary=answer,
        structured_result={
            "answer": answer,
            "retrieval_source": "deterministic_fixture",
            "answer_quality": {"faithfulness_status": "ok", "subscores": {"readability": 1.0}},
            "skill_results": {
                "s2": {"retrieval_output": {"hits": hits}, "retrieval_source": "deterministic_fixture"},
                "v4": {"section_keys": case["completeness_rubric"]["required_sections"]},
            },
        },
        citations=[
            Citation(
                chunk_id=evidence["chunk_id"],
                doc_id=evidence["doc_id"],
                pages=evidence["pages"],
            )
            for evidence in case["expected_evidence"]
        ],
    )


def test_obj1_question_set_covers_every_intent_in_both_languages_with_human_labels():
    questions = load_questions()

    assert len(questions["cases"]) == 14
    assert {(case["intent"], case["language"]) for case in questions["cases"]} == {
        (intent, language)
        for intent in ("definition", "mechanism", "comparison", "diagnosis", "workflow", "standards", "formula")
        for language in ("zh", "en")
    }
    assert len({case["case_id"] for case in questions["cases"]}) == 14
    assert all(case["completeness_rubric"]["human_usable_if"] for case in questions["cases"])
    assert {case["usability_label"] for case in questions["cases"]} == {"usable", "unusable"}
    assert all(case["usability_reason"] for case in questions["cases"])


def test_obj1_scorecard_reports_required_metrics_without_live_providers():
    questions = load_questions()
    report = run_rag_qa_eval(
        questions=questions,
        query_runner=_passing_output,
        corpus_count=4436,
        git_commit="test-commit",
    )

    assert report["schema_version"] == "phase5.rag_qa.report.v3"
    assert report["live_providers_constructed"] is False
    assert report["case_count"] == 14
    assert report["scorecard"]["recall_at_5"] == 1.0
    assert report["scorecard"]["recall_at_10"] == 1.0
    assert report["scorecard"]["completeness_rate"] == 1.0
    assert report["scorecard"]["v2_faithfulness_rate"] == 1.0
    assert report["scorecard"]["sentence_completeness_rate"] == 1.0
    assert report["scorecard"]["miss_counts"] == {"pass": 14}
    assert report["scorecard"]["primary_miss_counts"] == {"pass": 14}
    assert report["scorecard"]["v2_status_counts"] == {"ok": 14}
    assert report["evaluation_contract"]["evidence_match_rule"] == (
        "exact_chunk_id OR same_doc_id_with_page_overlap"
    )
    assert report["corpus"]["embedding_dimension"] == 384
    assert report["retrieval_config"]["final_top_k"] == 10
    assert report["git_commit"] == "test-commit"
    assert report["cases"][0]["answer_quality"]["faithfulness_status"] == "ok"


def test_obj1_deterministic_fingerprint_excludes_runtime_latency():
    questions = load_questions()

    first = run_rag_qa_eval(questions=questions, query_runner=_passing_output, git_commit="same")
    second = run_rag_qa_eval(questions=questions, query_runner=_passing_output, git_commit="same")

    assert first["deterministic_fingerprint"] == second["deterministic_fingerprint"]
    assert [case["case_id"] for case in first["cases"]] == [case["case_id"] for case in second["cases"]]


def test_obj1_miss_categories_separate_retrieval_from_synthesis():
    questions = load_questions()

    def runner(case: Mapping[str, Any]) -> SkillOutput:
        if case["intent"] == "definition":
            return SkillOutput(
                status="insufficient",
                structured_result={
                    "answer": "",
                    "answer_quality": {"faithfulness_status": "insufficient", "subscores": {}},
                    "skill_results": {"s2": {"retrieval_output": {"hits": []}}, "v4": {"section_keys": []}},
                },
            )
        output = _passing_output(case)
        output.structured_result["answer"] = "A cited but incomplete answer."
        return output

    # The public fixture validator remains strict; this focused unit uses the
    # full set and changes only outputs whose classification matters.
    def full_runner(case: Mapping[str, Any]) -> SkillOutput:
        if (
            case["intent"] == "definition"
            or case["case_id"] == "p5_mechanism_zh_critical_speed"
        ):
            return runner(case)
        return _passing_output(case)

    report = run_rag_qa_eval(questions=questions, query_runner=full_runner, git_commit="test")
    by_id = {case["case_id"]: case for case in report["cases"]}

    assert by_id["p5_definition_zh_order_analysis"]["miss_category"] == "retrieval"
    assert by_id["p5_mechanism_zh_critical_speed"]["miss_category"] == "synthesis"


def test_obj1_ranking_signal_is_reported_when_evidence_moves_from_top_5_to_top_10():
    questions = load_questions()

    def runner(case: Mapping[str, Any]) -> SkillOutput:
        output = _passing_output(case)
        if case["case_id"] == "p5_diagnosis_zh_fault_discrimination":
            expected_hits = output.structured_result["skill_results"]["s2"][
                "retrieval_output"
            ]["hits"]
            output.structured_result["skill_results"]["s2"]["retrieval_output"]["hits"] = [
                {"chunk_id": f"decoy_{index}", "doc_id": "decoy", "pages": [index], "score": 1.0}
                for index in range(5)
            ] + expected_hits
            output.structured_result["answer"] = "Incomplete."
        return output

    report = run_rag_qa_eval(questions=questions, query_runner=runner, git_commit="test")
    case = next(row for row in report["cases"] if row["case_id"] == "p5_diagnosis_zh_fault_discrimination")

    assert case["recall_at_5"] == 0.0
    assert case["recall_at_10"] == 1.0
    assert case["miss_category"] == "ranking"
    assert case["miss_categories"] == ["ranking", "synthesis"]
    assert report["scorecard"]["miss_counts"]["ranking"] == 1


def test_obj1_terminology_requires_asymmetric_recall_for_a_bilingual_evidence_pair():
    questions = load_questions()
    missing_ids = {
        "p5_definition_en_order_analysis",
        "p5_workflow_zh_measurement_diagnosis",
        "p5_workflow_en_measurement_diagnosis",
    }

    def runner(case: Mapping[str, Any]) -> SkillOutput:
        if case["case_id"] not in missing_ids:
            return _passing_output(case)
        return SkillOutput(
            status="insufficient",
            structured_result={
                "answer": "",
                "answer_quality": {"faithfulness_status": "insufficient", "subscores": {}},
                "skill_results": {"s2": {"retrieval_output": {"hits": []}}, "v4": {"section_keys": []}},
            },
        )

    report = run_rag_qa_eval(questions=questions, query_runner=runner, git_commit="test")
    by_id = {case["case_id"]: case for case in report["cases"]}

    assert by_id["p5_definition_en_order_analysis"]["miss_category"] == "terminology"
    assert by_id["p5_workflow_zh_measurement_diagnosis"]["miss_category"] == "retrieval"
    assert by_id["p5_workflow_en_measurement_diagnosis"]["miss_category"] == "retrieval"


def test_obj1_evidence_matching_accepts_a_neighbor_chunk_on_the_labeled_doc_page():
    questions = load_questions()

    def runner(case: Mapping[str, Any]) -> SkillOutput:
        output = _passing_output(case)
        if case["case_id"] == "p5_definition_zh_order_analysis":
            hit = output.structured_result["skill_results"]["s2"]["retrieval_output"]["hits"][0]
            hit["chunk_id"] = "neighbor_chunk_on_same_page"
        return output

    report = run_rag_qa_eval(questions=questions, query_runner=runner, git_commit="test")
    case = next(row for row in report["cases"] if row["case_id"] == "p5_definition_zh_order_analysis")

    assert case["recall_at_5"] == 1.0
    assert case["matched_evidence_at_5"] == ["order_definition"]


def test_obj1_loader_rejects_a_rubric_without_human_usable_criteria():
    questions = copy.deepcopy(load_questions())
    questions["cases"][0]["completeness_rubric"].pop("human_usable_if")

    with pytest.raises(ValueError, match="human completeness rubric"):
        run_rag_qa_eval(questions=questions, query_runner=_passing_output, git_commit="test")


def test_obj9_committed_baseline_is_phase5_backend_freeze_regression_net():
    baseline = json.loads(
        (ROOT / "tests" / "fixtures" / "rag_qa" / "post_r3_baseline.json").read_text(
            encoding="utf-8"
        )
    )

    assert baseline["schema_version"] == "phase5.rag_qa.report.v3"
    assert baseline["live_providers_constructed"] is False
    assert baseline["corpus"]["actual_chunk_count"] == 4436
    assert baseline["corpus"]["embedding_model"] == (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    assert baseline["corpus"]["embedding_dimension"] == 384
    assert baseline["retrieval_config"] == {
        "bm25_top_k": 50,
        "dense_top_k": 50,
        "final_top_k": 10,
        "fusion": "rrf",
        "mode": "hybrid",
        "rerank_enabled": False,
    }
    assert baseline["evaluation_contract"]["evidence_match_rule"] == (
        "exact_chunk_id OR same_doc_id_with_page_overlap"
    )
    assert baseline["scorecard"]["recall_at_5"] == 0.643
    assert baseline["scorecard"]["recall_at_10"] == 0.821
    assert baseline["scorecard"]["completeness_rate"] == 0.72
    assert baseline["scorecard"]["v2_faithfulness_rate"] == 1.0
    assert baseline["scorecard"]["citation_alignment_rate"] == 1.0
    assert all(
        case["answer_quality"]["schema_version"] == "phase5.answer_quality.v3"
        for case in baseline["cases"]
    )
    assert all(
        "language_alignment" in case["answer_quality"]["subscores"]
        for case in baseline["cases"]
    )
    assert all("language_status" in case["answer_quality"] for case in baseline["cases"])
