import json
from pathlib import Path

from scripts.visual_decision_eval import evaluate_case


def test_labeled_visual_decision_cases_pass():
    # WHY: threshold changes must preserve both figure recall and decoration rejection.
    path = Path("tests/fixtures/visual_decision/cases.json")
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]

    results = [evaluate_case(case) for case in cases]
    baseline_results = [
        result["baseline_failed_as_expected"]
        for result in results
        if result.get("baseline_failed_as_expected") is not None
    ]

    assert results
    assert all(result["passed"] for result in results), results
    assert baseline_results and all(baseline_results)
