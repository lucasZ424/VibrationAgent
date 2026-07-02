import subprocess
import sys

from scripts.obj5_evidence_gate import evaluate


def _baseline():
    return {
        "corpus": {"chunk_count": 4436},
        "full_chain": {
            "recall_at_10": 0.607,
            "completeness_rate": 0.339,
            "v2_faithfulness_rate": 0.5,
            "sentence_completeness_rate": 0.902,
            "citation_alignment_rate": 1.0,
        },
    }


def _candidate():
    return {
        "corpus": {"actual_chunk_count": 4436},
        "evidence_selection_config": {"enabled": True, "rerank_enabled": False},
        "scorecard": {
            "recall_at_10": 0.607,
            "completeness_rate": 0.4,
            "v2_faithfulness_rate": 0.5,
            "sentence_completeness_rate": 0.902,
            "citation_alignment_rate": 1.0,
        },
    }


def test_obj5_gate_requires_completeness_gain_without_retrieval_or_v2_regression():
    report = evaluate(_candidate(), _baseline())

    assert report["eligible"] is True
    assert all(report["checks"].values())


def test_obj5_gate_rejects_equal_completeness_and_model_reranker():
    candidate = _candidate()
    candidate["scorecard"]["completeness_rate"] = 0.339
    candidate["evidence_selection_config"]["rerank_enabled"] = True

    report = evaluate(candidate, _baseline())

    assert report["eligible"] is False
    assert report["checks"]["completeness_improved"] is False
    assert report["checks"]["model_reranker_disabled"] is False


def test_obj5_gate_rejects_sentence_completeness_regression():
    candidate = _candidate()
    candidate["scorecard"]["sentence_completeness_rate"] = 0.888

    report = evaluate(candidate, _baseline())

    assert report["eligible"] is False
    assert report["checks"]["sentence_completeness_preserved"] is False


def test_obj5_gate_rejects_incomplete_inline_citation_alignment():
    candidate = _candidate()
    candidate["scorecard"]["citation_alignment_rate"] = 0.875

    report = evaluate(candidate, _baseline())

    assert report["eligible"] is False
    assert report["checks"]["citation_alignment_complete"] is False


def test_obj5_gate_accepts_corrected_selector_off_report_as_baseline():
    baseline = {
        "corpus": {"actual_chunk_count": 4436},
        "evidence_selection_config": {"enabled": False, "rerank_enabled": False},
        "scorecard": _baseline()["full_chain"],
    }

    report = evaluate(_candidate(), baseline)

    assert report["eligible"] is True
    assert report["checks"]["baseline_selector_disabled"] is True
    assert report["checks"]["baseline_citation_alignment_complete"] is True


def test_obj5_gate_cli_help_runs_without_project_pythonpath():
    result = subprocess.run(
        [sys.executable, "scripts/obj5_evidence_gate.py", "--help"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert "--candidate" in result.stdout
