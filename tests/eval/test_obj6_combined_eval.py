from scripts.obj6_combined_eval import evaluate_combined_gate
from scripts.obj6_synthesis_eval import HARD_CASE_IDS


def _report(*, supervisor_status="approved", post_v2_status="ok", hard_completeness=0.6):
    cases = []
    for case_id in HARD_CASE_IDS:
        cases.append(
            {
                "case_id": case_id,
                "completeness": hard_completeness,
                "combined_chain": {
                    "supervisor_status": supervisor_status,
                    "post_supervisor_v2_status": post_v2_status,
                },
            }
        )
    cases.append({"case_id": "other", "completeness": 0.5})
    return {
        "corpus": {"actual_chunk_count": 4436},
        "scorecard": {
            "recall_at_10": 0.607,
            "completeness_rate": 0.72,
            "v2_faithfulness_rate": 1.0,
            "sentence_completeness_rate": 0.890,
            "citation_alignment_rate": 1.0,
        },
        "cases": cases,
    }


def test_combined_gate_requires_supervisor_and_post_supervisor_v2():
    # WHY: Obj6 closure must prove Opus-supervised answers remain V2-faithful,
    # rather than relying on the pre-supervisor S3 V2 result.
    baseline = _report()
    baseline["scorecard"]["completeness_rate"] = 0.708
    for row in baseline["cases"]:
        if row["case_id"] in HARD_CASE_IDS:
            row["completeness"] = 0.5
    candidate = _report()

    result = evaluate_combined_gate(candidate, baseline)

    assert result["eligible"] is True
    assert result["checks"]["supervisor_approved_on_hard_cases"] is True
    assert result["checks"]["post_supervisor_v2_ok_on_hard_cases"] is True


def test_combined_gate_rejects_fallback_or_post_supervisor_v2_failure():
    baseline = _report()
    baseline["scorecard"]["completeness_rate"] = 0.708
    for row in baseline["cases"]:
        if row["case_id"] in HARD_CASE_IDS:
            row["completeness"] = 0.5
    candidate = _report(supervisor_status="fallback", post_v2_status="insufficient")

    result = evaluate_combined_gate(candidate, baseline)

    assert result["eligible"] is False
    assert result["checks"]["supervisor_approved_on_hard_cases"] is False
    assert result["checks"]["post_supervisor_v2_ok_on_hard_cases"] is False
