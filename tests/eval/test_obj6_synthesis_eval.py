import json

from scripts.obj6_synthesis_eval import HARD_CASE_IDS, evaluate_gate, main


def _report(completeness=0.708, hard=0.5):
    cases = [{"case_id": case_id, "completeness": hard} for case_id in HARD_CASE_IDS]
    cases.append({"case_id": "other", "completeness": 0.5})
    return {
        "corpus": {"actual_chunk_count": 4436},
        "scorecard": {"recall_at_10": 0.607, "completeness_rate": completeness,
                      "v2_faithfulness_rate": 1.0, "sentence_completeness_rate": 0.890,
                      "citation_alignment_rate": 1.0},
        "cases": cases,
    }


def test_obj6a_gate_requires_global_and_semantic_hard_case_gain():
    baseline = _report()
    candidate = _report(completeness=0.72, hard=0.6)

    result = evaluate_gate(candidate, baseline)

    assert result["eligible"] is True
    assert all(result["checks"].values())


def test_obj6a_gate_rejects_readability_or_faithfulness_tradeoff():
    baseline = _report()
    candidate = _report(completeness=0.72, hard=0.6)
    candidate["scorecard"]["sentence_completeness_rate"] = 0.889
    candidate["scorecard"]["v2_faithfulness_rate"] = 0.929

    result = evaluate_gate(candidate, baseline)

    assert result["eligible"] is False
    assert result["checks"]["sentence_completeness_preserved"] is False
    assert result["checks"]["v2_faithfulness_preserved"] is False


def test_obj6a_gate_uses_the_versioned_baseline_readability_floor():
    # WHY: a newly solidified corrected baseline must automatically tighten or
    # relax the candidate floor without a second magic constant in the gate.
    baseline = _report()
    baseline["scorecard"]["sentence_completeness_rate"] = 0.91
    candidate = _report(completeness=0.72, hard=0.6)
    candidate["scorecard"]["sentence_completeness_rate"] = 0.90

    result = evaluate_gate(candidate, baseline)

    assert result["eligible"] is False
    assert result["checks"]["sentence_completeness_preserved"] is False


def test_obj6a_gate_cli_writes_committed_gate_report(tmp_path):
    # WHY: Obj6A promotion depends on the checked-in gate command, not only the
    # in-process helper used by unit tests.
    baseline = _report()
    candidate = _report(completeness=0.72, hard=0.6)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    output_path = tmp_path / "gate.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    code = main(
        [
            "gate",
            "--candidate",
            str(candidate_path),
            "--baseline",
            str(baseline_path),
            "--output",
            str(output_path),
        ]
    )

    assert code == 0
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["eligible"] is True
    assert written["checks"]["sentence_completeness_preserved"] is True
