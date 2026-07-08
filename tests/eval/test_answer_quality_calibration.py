from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.answer_quality_calibration import load_baseline, run_calibration
from scripts.rag_qa_eval import load_questions

ROOT = Path(__file__).resolve().parents[2]


def _questions() -> dict:
    return {
        "schema_version": "phase5.rag_qa.questions.v2",
        "cases": [
            {"case_id": "usable", "usability_label": "usable"},
            {"case_id": "bad_score", "usability_label": "unusable"},
            {"case_id": "bad_v2", "usability_label": "unusable"},
        ],
    }


def _baseline() -> dict:
    return {
        "schema_version": "phase5.rag_qa.report.v3",
        "baseline_id": "test",
        "cases": [
            {
                "case_id": "usable",
                "v2_status": "ok",
                "answer_quality": {
                    "schema_version": "phase5.answer_quality.v3",
                    "score": 0.8,
                    "subscores": {"completeness": 1.0, "language_alignment": 1.0},
                    "language_status": "aligned",
                },
            },
            {
                "case_id": "bad_score",
                "v2_status": "ok",
                "answer_quality": {
                    "schema_version": "phase5.answer_quality.v3",
                    "score": 0.4,
                    "subscores": {"completeness": 1.0, "language_alignment": 1.0},
                    "language_status": "aligned",
                },
            },
            {
                "case_id": "bad_v2",
                "v2_status": "insufficient",
                "answer_quality": {
                    "schema_version": "phase5.answer_quality.v3",
                    "score": 0.9,
                    "subscores": {"completeness": 1.0, "language_alignment": 1.0},
                    "language_status": "aligned",
                },
            },
        ],
    }


def test_obj2_calibration_reports_confusion_for_candidate_thresholds():
    report = run_calibration(questions=_questions(), baseline=_baseline(), thresholds=[0.5, 0.85])

    accepted = report["threshold_candidates"][0]
    assert report["schema_version"] == "phase5.answer_quality_calibration.report.v2"
    assert report["label_counts"] == {"unusable": 2, "usable": 1}
    assert accepted["confusion"] == {
        "true_usable": 1,
        "false_block": 0,
        "true_unusable": 2,
        "false_allow": 0,
    }
    assert report["best_observed_candidate"]["threshold"] == 0.5
    assert report["best_observed_candidate"]["decision_margin"] == 0.1


def test_obj2_calibration_hard_gate_blocks_a_high_score_without_v2_ok():
    report = run_calibration(questions=_questions(), baseline=_baseline(), thresholds=[0.5])

    assert "v2_status == ok" in report["hard_gate_rule"]
    assert report["hard_gate_rule"].endswith("language_status != mismatch")
    assert report["threshold_candidates"][0]["confusion"]["false_allow"] == 0


def test_obj2_calibration_does_not_hard_gate_mixed_acceptable_language():
    # WHY: the runtime quality gate treats prompt/answer language mismatch as a
    # hard usability failure, but Latin-heavy algorithm answers can still be
    # usable when their main prose follows the requested language.
    baseline = _baseline()
    baseline["cases"][0]["answer_quality"]["subscores"]["language_alignment"] = 0.8
    baseline["cases"][0]["answer_quality"]["language_status"] = "mixed_acceptable"

    report = run_calibration(questions=_questions(), baseline=baseline, thresholds=[0.5])
    usable_case = next(row for row in report["cases"] if row["case_id"] == "usable")

    assert usable_case["subscores"]["language_alignment"] == 0.8
    assert usable_case["language_status"] == "mixed_acceptable"
    assert report["threshold_candidates"][0]["confusion"]["false_block"] == 0


def test_obj2_calibration_hard_gate_blocks_language_status_mismatch():
    questions = _questions()
    questions["cases"][0]["usability_label"] = "unusable"
    baseline = _baseline()
    baseline["cases"][0]["answer_quality"]["language_status"] = "mismatch"

    report = run_calibration(questions=questions, baseline=baseline, thresholds=[0.5])

    assert report["threshold_candidates"][0]["confusion"]["false_allow"] == 0


def test_obj2_calibration_fails_loud_on_stale_obj1_report():
    baseline = _baseline()
    baseline["schema_version"] = "phase5.rag_qa.report.v2"

    with pytest.raises(ValueError, match="freshly generated"):
        run_calibration(questions=_questions(), baseline=baseline)


def test_obj2_calibration_accepts_obj6_combined_report_post_supervisor_v2():
    baseline = _baseline()
    baseline["schema_version"] = "phase5.obj6.combined_report.v1"
    baseline["cases"][0]["combined_chain"] = {"post_supervisor_v2_status": "insufficient"}

    report = run_calibration(questions=_questions(), baseline=baseline, thresholds=[0.5])
    usable = next(row for row in report["cases"] if row["case_id"] == "usable")

    assert usable["v2_status"] == "insufficient"
    assert report["threshold_candidates"][0]["confusion"]["false_block"] == 1


def test_obj2_calibration_fails_loud_on_stale_answer_quality_schema():
    baseline = _baseline()
    baseline["cases"][0]["answer_quality"]["schema_version"] = "phase5.answer_quality.v2"

    with pytest.raises(ValueError, match="rerun the Obj1 baseline"):
        run_calibration(questions=_questions(), baseline=baseline)


def test_obj2_calibration_accepts_unscored_blocked_early_return():
    questions = _questions()
    baseline = _baseline()
    baseline["cases"][2]["answer_quality"] = {}
    baseline["cases"][2]["v2_status"] = "unknown"

    report = run_calibration(questions=questions, baseline=baseline, thresholds=[0.5])
    case = next(row for row in report["cases"] if row["case_id"] == "bad_v2")

    assert case["score"] is None
    assert case["score_schema"] == "not_scored"
    assert report["threshold_candidates"][0]["confusion"]["false_allow"] == 0


def test_obj2_calibration_rejects_unscored_case_with_v2_ok():
    baseline = _baseline()
    baseline["cases"][0]["answer_quality"] = {}

    with pytest.raises(ValueError, match="v2_status=ok but no answer_quality"):
        run_calibration(questions=_questions(), baseline=baseline)


def test_obj2_calibration_prefers_the_zero_error_threshold_with_more_margin():
    baseline = _baseline()
    baseline["cases"][0]["answer_quality"]["score"] = 0.812
    baseline["cases"][1]["answer_quality"]["score"] = 0.706

    report = run_calibration(
        questions=_questions(),
        baseline=baseline,
        thresholds=[0.75, 0.8],
    )

    assert report["best_observed_candidate"]["threshold"] == 0.75
    assert report["best_observed_candidate"]["decision_margin"] == 0.044


def test_obj2_durable_calibration_artifact_matches_current_fixtures():
    path = ROOT / "tests" / "fixtures" / "eval" / "answer_quality" / "obj2_calibration.json"
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored == run_calibration(
        questions=load_questions(),
        baseline=load_baseline(),
    )
