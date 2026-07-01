import json
import subprocess
import sys
from pathlib import Path

from scripts.obj4_retrieval_eval import run_obj4_eval


def _questions():
    return {
        "cases": [
            {
                "case_id": "existing_pass",
                "language": "zh",
                "query": "known",
                "expected_evidence": [{"evidence_id": "e1", "chunk_id": "c1", "doc_id": "d1", "pages": [1]}],
            },
            {
                "case_id": "baseline_miss",
                "language": "en",
                "query": "cross language",
                "expected_evidence": [{"evidence_id": "e2", "chunk_id": "c2", "doc_id": "d2", "pages": [2]}],
            },
        ]
    }


def _baseline():
    return {
        "scorecard": {"recall_at_10": 0.5},
        "cases": [
            {"case_id": "existing_pass", "recall_at_10": 1.0},
            {"case_id": "baseline_miss", "recall_at_10": 0.0},
        ],
    }


def test_obj4_eval_requires_hybrid_to_match_best_lane_and_fix_real_miss():
    def runner(mode, case):
        hit = {"chunk_id": "c1", "doc_id": "d1", "pages": [1]}
        if case["case_id"] == "baseline_miss" and mode in {"bm25", "hybrid"}:
            hit = {"chunk_id": "c2", "doc_id": "d2", "pages": [2]}
        elif case["case_id"] == "baseline_miss":
            return {"hits": [], "lanes": {}, "warnings": []}
        return {"hits": [hit], "lanes": {}, "warnings": []}

    report = run_obj4_eval(questions=_questions(), baseline=_baseline(), query_runner=runner)

    assert report["scorecards"]["bm25"]["recall_at_10"] == 1.0
    assert report["scorecards"]["dense"]["recall_at_10"] == 0.5
    assert report["scorecards"]["hybrid"]["recall_at_10"] == 1.0
    assert report["replacement_gate"]["candidate_eligible"] is True
    assert report["replacement_gate"]["fixed_baseline_miss_case_ids"] == ["baseline_miss"]
    assert report["replacement_gate"]["regressed_baseline_pass_case_ids"] == []
    assert report["replacement_gate"]["v2_full_chain_validation_required"] is True


def test_obj4_eval_blocks_candidate_that_regresses_existing_pass():
    def runner(mode, case):
        if mode == "hybrid" and case["case_id"] == "existing_pass":
            return {"hits": [], "warnings": []}
        target = case["expected_evidence"][0]
        return {"hits": [target], "warnings": []}

    report = run_obj4_eval(questions=_questions(), baseline=_baseline(), query_runner=runner)

    assert report["replacement_gate"]["candidate_eligible"] is False
    assert report["replacement_gate"]["regressed_baseline_pass_case_ids"] == ["existing_pass"]


def test_obj4_eval_cli_help_runs_without_project_pythonpath():
    result = subprocess.run(
        [sys.executable, "scripts/obj4_retrieval_eval.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--questions" in result.stdout


def test_obj4_committed_replacement_baseline_records_both_gates():
    path = Path("tests/fixtures/eval/retrieval/obj4_replacement_baseline.json")
    baseline = json.loads(path.read_text(encoding="utf-8"))

    assert baseline["schema_version"] == "phase5.obj4_replacement_baseline.v1"
    assert baseline["lane_scorecards"]["hybrid"]["recall_at_10"] == 0.607
    assert baseline["replacement_gate"]["candidate_eligible"] is True
    assert baseline["replacement_gate"]["fixed_baseline_miss_case_ids"] == [
        "p5_standards_zh_gbt33199_scope"
    ]
    assert baseline["replacement_gate"]["regressed_baseline_pass_case_ids"] == []
    assert baseline["full_chain"]["v2_faithfulness_rate"] == 0.5
    assert baseline["promotion"]["independent_lanes_default"] is True
    assert baseline["promotion"]["canonical_nonlarge"] == {
        "passed": 591,
        "deselected": 1,
        "failed": 0,
    }
