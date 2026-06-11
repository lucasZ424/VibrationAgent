from __future__ import annotations

import copy

from scripts.llm_eval import load_cases, run_eval


def test_phase3_golden_eval_replay_set_passes():
    report = run_eval(load_cases())

    assert report["schema_version"] == "phase3.eval.v1"
    assert report["case_count"] == 5
    assert report["failed_count"] == 0
    assert report["scorecard"]["pass_rate"] == 1.0
    assert report["scorecard"]["citation_faithfulness_pass_rate"] == 1.0
    assert report["scorecard"]["unsupported_numeric_block_rate"] == 1.0
    assert report["scorecard"]["scope_status_pass_rate"] == 1.0
    assert report["scorecard"]["reviewer_notes_presence_rate"] == 1.0


def test_phase3_golden_eval_catches_hallucinated_visible_claim():
    cases = load_cases()
    hallucinated = copy.deepcopy(next(case for case in cases if case["case_id"] == "eval_en_visible_llm"))
    hallucinated["case_id"] = "eval_hallucinated_visible_claim"
    hallucinated["s3_output"]["structured_result"]["answer"] = "Bearing temperature proves lubrication failure [en_c1]."
    hallucinated["s3_output"]["structured_result"]["claims"][0]["text"] = "Bearing temperature proves lubrication failure."
    hallucinated["expect"]["status"] = "ok"
    hallucinated["expect"]["unsupported_count"] = 0

    report = run_eval([hallucinated])
    result = report["cases"][0]

    assert report["failed_count"] == 1
    assert result["status"] == "insufficient"
    assert result["unsupported_count"] == 1
    assert result["checks"]["status"] is False
    assert result["checks"]["unsupported_count"] is False
