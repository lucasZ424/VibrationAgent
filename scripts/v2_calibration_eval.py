"""Replay-only V2 calibration runner for Phase-4 Obj1.

The runner executes the real deterministic V2 citation checker against labeled
positive/negative cases. It does not call live providers or external services.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.schemas import SkillInput, SkillOutput  # noqa: E402
from vibration_agent.skills import CitationCheckSkill  # noqa: E402

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "eval" / "v2_calibration" / "cases.json"


def load_calibration(path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path} must contain a non-empty cases array.")
    return data


def _s2_output(case: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(case.get("retrieval_rows") or [])
    return {
        "status": "ok",
        "structured_result": {
            "retrieval_context": rows,
            "retrieval_output": {
                "hits": [
                    {
                        "chunk_id": row.get("chunk_id"),
                        "doc_id": row.get("doc_id"),
                        "score": row.get("score", 1.0),
                    }
                    for row in rows
                    if isinstance(row, Mapping)
                ]
            },
        },
    }


def _s3_output(case: Mapping[str, Any]) -> SkillOutput:
    raw = case.get("s3_output")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{case.get('case_id')} missing s3_output")
    return SkillOutput.model_validate(raw)


def run_case(case: Mapping[str, Any]) -> dict[str, Any]:
    expected_supported = bool(case.get("expected_supported"))
    expected_current_supported = bool(case.get("expected_current_supported", expected_supported))
    output = CitationCheckSkill().run(
        SkillInput(
            task_id=str(case.get("case_id") or "v2_calibration"),
            user_query=str(case.get("query") or ""),
            context={"s2_result": _s2_output(case), "s3_result": _s3_output(case).model_dump(mode="python")},
        )
    )
    unsupported = output.structured_result.get("unsupported_claims")
    unsupported = unsupported if isinstance(unsupported, list) else []
    actual_supported = output.status == "ok" and not unsupported
    expected_unsupported_count = case.get("expected_unsupported_count")
    unsupported_count_ok = (
        len(unsupported) == int(expected_unsupported_count)
        if expected_unsupported_count is not None
        else True
    )
    passed = actual_supported is expected_current_supported and unsupported_count_ok
    return {
        "case_id": str(case.get("case_id") or "unknown"),
        "label": "supported" if expected_supported else "unsupported",
        "baseline_label": "supported" if expected_current_supported else "unsupported",
        "passed": passed,
        "expected_supported": expected_supported,
        "expected_current_supported": expected_current_supported,
        "actual_supported": actual_supported,
        "status": output.status,
        "unsupported_count": len(unsupported),
        "expected_unsupported_count": expected_unsupported_count,
        "unsupported_reasons": [
            reason
            for item in unsupported
            if isinstance(item, Mapping)
            for reason in item.get("reasons", [])
        ],
    }


def run_calibration(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    active = data if data is not None else load_calibration()
    cases = active.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Calibration data must contain a non-empty cases array.")
    results = [run_case(case) for case in cases if isinstance(case, Mapping)]
    confusion = _confusion(results)
    return {
        "schema_version": "phase4.v2_calibration.report.v2",
        "fixture_schema_version": active.get("schema_version"),
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "confusion": confusion,
        "scorecard": {
            "pass_rate": _rate(result["passed"] for result in results),
            "supported_recall": _safe_div(confusion["true_supported"], confusion["expected_supported"]),
            "unsupported_block_rate": _safe_div(confusion["true_unsupported"], confusion["expected_unsupported"]),
        },
        "cases": results,
    }


def _confusion(results: list[dict[str, Any]]) -> dict[str, int]:
    true_supported = sum(
        1 for result in results if result["expected_supported"] and result["actual_supported"]
    )
    false_block = sum(
        1 for result in results if result["expected_supported"] and not result["actual_supported"]
    )
    true_unsupported = sum(
        1 for result in results if not result["expected_supported"] and not result["actual_supported"]
    )
    false_allow = sum(
        1 for result in results if not result["expected_supported"] and result["actual_supported"]
    )
    return {
        "expected_supported": true_supported + false_block,
        "expected_unsupported": true_unsupported + false_allow,
        "true_supported": true_supported,
        "false_block": false_block,
        "true_unsupported": true_unsupported,
        "false_allow": false_allow,
    }


def _rate(values: Any) -> float | None:
    items = list(values)
    if not items:
        return None
    return sum(1 for item in items if item) / len(items)


def _safe_div(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase-4 V2 calibration fixtures.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_calibration(load_calibration(args.fixture))
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if report["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
