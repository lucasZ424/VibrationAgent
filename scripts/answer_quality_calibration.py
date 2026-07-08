"""Offline Obj2 threshold calibration over the frozen Obj1 scorecard."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.rag_qa_eval import DEFAULT_BASELINE, DEFAULT_QUESTIONS, load_questions  # noqa: E402

DEFAULT_OUTPUT = ROOT / "run_logs" / "obj2_answer_quality_calibration.json"
DEFAULT_THRESHOLDS = tuple(round(index / 20, 2) for index in range(21))
ANSWER_QUALITY_SCHEMA = "phase5.answer_quality.v3"
REPORT_SCHEMA = "phase5.answer_quality_calibration.report.v2"
SUPPORTED_BASELINE_SCHEMAS = {
    "phase5.rag_qa.report.v3",
    "phase5.obj6.combined_report.v1",
}


def load_baseline(path: Path = DEFAULT_BASELINE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    return data


def run_calibration(
    *,
    questions: Mapping[str, Any],
    baseline: Mapping[str, Any],
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    baseline_schema = str(baseline.get("schema_version") or "")
    if baseline_schema not in SUPPORTED_BASELINE_SCHEMAS:
        supported = " or ".join(sorted(SUPPORTED_BASELINE_SCHEMAS))
        raise ValueError(f"Obj2 calibration requires a freshly generated {supported} baseline.")
    question_rows = questions.get("cases")
    baseline_rows = baseline.get("cases")
    if not isinstance(question_rows, list) or not isinstance(baseline_rows, list):
        raise ValueError("Questions and baseline must both contain cases arrays.")
    labels = {str(row["case_id"]): str(row["usability_label"]) for row in question_rows}
    results = {str(row["case_id"]): row for row in baseline_rows}
    if set(labels) != set(results):
        raise ValueError("Question labels and baseline case ids do not match.")

    rows = [_case_row(case_id, labels[case_id], results[case_id]) for case_id in labels]
    candidates = [_threshold_result(rows, float(threshold)) for threshold in thresholds]
    ranked = sorted(
        candidates,
        key=lambda item: (
            item["confusion"]["false_allow"],
            item["confusion"]["false_block"],
            -item["decision_margin"],
        ),
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "question_schema_version": questions.get("schema_version"),
        "baseline_schema_version": baseline.get("schema_version"),
        "baseline_id": baseline.get("baseline_id"),
        "case_count": len(rows),
        "label_counts": dict(sorted(Counter(row["label"] for row in rows).items())),
        "v2_status_counts": dict(sorted(Counter(row["v2_status"] for row in rows).items())),
        "hard_gate_rule": (
            "predicted_usable requires score >= threshold AND v2_status == ok "
            "AND completeness == 1.0 AND language_status != mismatch"
        ),
        "best_observed_candidate": ranked[0] if ranked else None,
        "threshold_candidates": candidates,
        "cases": rows,
    }


def _case_row(case_id: str, label: str, result: Mapping[str, Any]) -> dict[str, Any]:
    quality = result.get("answer_quality")
    quality = quality if isinstance(quality, Mapping) else {}
    v2_status = _case_v2_status(result)
    score_schema = quality.get("schema_version")
    if quality and score_schema != ANSWER_QUALITY_SCHEMA:
        raise ValueError(f"{case_id} requires {ANSWER_QUALITY_SCHEMA}; rerun the Obj1 baseline.")
    if not quality and v2_status == "ok":
        raise ValueError(f"{case_id} has v2_status=ok but no answer_quality score.")
    score = quality.get("score")
    return {
        "case_id": case_id,
        "label": label,
        "score": float(score) if isinstance(score, int | float) else None,
        "score_schema": str(score_schema or "not_scored"),
        "v2_status": v2_status,
        "subscores": dict(quality.get("subscores") or {}),
        "language_status": str(quality.get("language_status") or "unknown"),
    }


def _case_v2_status(result: Mapping[str, Any]) -> str:
    combined = result.get("combined_chain") if isinstance(result.get("combined_chain"), Mapping) else {}
    post_supervisor = combined.get("post_supervisor_v2_status")
    if isinstance(post_supervisor, str) and post_supervisor:
        return post_supervisor
    return str(result.get("v2_status") or "unknown")


def _threshold_result(rows: Sequence[Mapping[str, Any]], threshold: float) -> dict[str, Any]:
    predictions = [
        bool(
            row["score"] is not None
            and row["score"] >= threshold
            and row["v2_status"] == "ok"
            and float(row["subscores"].get("completeness") or 0.0) == 1.0
            and row.get("language_status") != "mismatch"
        )
        for row in rows
    ]
    expected = [row["label"] == "usable" for row in rows]
    true_usable = sum(want and got for want, got in zip(expected, predictions, strict=True))
    false_block = sum(want and not got for want, got in zip(expected, predictions, strict=True))
    true_unusable = sum(not want and not got for want, got in zip(expected, predictions, strict=True))
    false_allow = sum(not want and got for want, got in zip(expected, predictions, strict=True))
    usable_scores = [
        float(row["score"])
        for row in rows
        if row["label"] == "usable" and row["v2_status"] == "ok" and row["score"] is not None
    ]
    unusable_scores = [
        float(row["score"])
        for row in rows
        if row["label"] == "unusable" and row["v2_status"] == "ok" and row["score"] is not None
    ]
    lower_margin = min(usable_scores) - threshold if usable_scores else 0.0
    upper_margin = threshold - max(unusable_scores) if unusable_scores else 0.0
    return {
        "threshold": threshold,
        "decision_margin": round(min(lower_margin, upper_margin), 3),
        "confusion": {
            "true_usable": true_usable,
            "false_block": false_block,
            "true_unusable": true_unusable,
            "false_allow": false_allow,
        },
        "accuracy": round((true_usable + true_unusable) / len(rows), 3),
        "usable_recall": _safe_div(true_usable, true_usable + false_block),
        "unusable_block_rate": _safe_div(true_unusable, true_unusable + false_allow),
    }


def _safe_div(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calibrate Obj2 answer-quality thresholds offline.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = run_calibration(
        questions=load_questions(args.questions),
        baseline=load_baseline(args.baseline),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_keys = (
        "case_count",
        "label_counts",
        "v2_status_counts",
        "best_observed_candidate",
    )
    print(json.dumps({key: report[key] for key in summary_keys}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
